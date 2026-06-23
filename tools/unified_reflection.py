#!/usr/bin/env python3
"""
unified_reflection.py — 统一反思模块

将 compound-system（任务后反思）和 skill-evolution（技能自进化）整合到一个模块。

职责：
1. 记录失败/成功事件（来自 compound 或 skill）
2. 提取模式（错误模式、使用模式）
3. 检索类似事件的建议
4. 同时写入 .skill-index/ 和 .compound/

数据流：
┌──────────────┐  ┌──────────────┐
│ compound.sh  │  │ skill tools  │
│ task_end     │  │ skill_used   │
└──────┬───────┘  └──────┬───────┘
       │                  │
       ▼                  ▼
┌──────────────────────────────────┐
│     UnifiedReflection            │
│  - record_event()                │
│  - extract_patterns()            │
│  - get_suggestions()             │
└──────────────────────────────────┘
       │                  │
       ▼                  ▼
┌──────────────┐  ┌──────────────┐
│ .skill-index │  │ .compound/   │
│ failure_log  │  │ reflections/ │
└──────────────┘  └──────────────┘
"""

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ============================================================
# 配置
# ============================================================

HOME = Path.home()
SKILL_INDEX_DIR = HOME / ".skill-index"
COMPOUND_DIR = HOME / ".compound"
FAILURE_LOG = SKILL_INDEX_DIR / "failure_log.jsonl"
PATTERNS_FILE = SKILL_INDEX_DIR / "patterns.json"
COMPOUND_REFLECTIONS = COMPOUND_DIR / "reflections"

# 确保目录存在
SKILL_INDEX_DIR.mkdir(exist_ok=True)
COMPOUND_DIR.mkdir(exist_ok=True)
COMPOUND_REFLECTIONS.mkdir(parents=True, exist_ok=True)

# ============================================================
# 事件类型
# ============================================================

class EventType:
    TASK_END = "task_end"           # 任务完成（来自 compound）
    SKILL_USED = "skill_used"       # 技能被使用
    SKILL_FAILED = "skill_failed"   # 技能使用失败
    ERROR_RECOVERED = "error_recovered"  # 错误已解决
    ERROR_UNRESOLVED = "error_unresolved"  # 错误未解决

class Severity:
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    BLOCKING = 4

# ============================================================
# 核心函数
# ============================================================

def record_event(
    event_type: str,
    description: str,
    outcome: str = "success",
    severity: int = Severity.NONE,
    skill_name: Optional[str] = None,
    error_message: Optional[str] = None,
    tool_calls: Optional[list] = None,
    files_modified: Optional[list] = None,
    tags: Optional[list] = None,
    source: str = "unknown",  # "compound" or "skill_evolution"
) -> dict:
    """
    记录事件（来自 compound 或 skill evolution）。
    
    返回记录的事件 dict。
    """
    now = datetime.now(timezone.utc).isoformat()
    
    event = {
        "timestamp": now,
        "event_type": event_type,
        "description": description[:200],
        "outcome": outcome,
        "severity": severity,
        "skill_name": skill_name,
        "error_message": (error_message or "")[:500],
        "tool_calls": (tool_calls or [])[:20],
        "files_modified": (files_modified or [])[:10],
        "tags": tags or [],
        "source": source,
    }
    
    # 写入 skill-index failure_log.jsonl
    _append_jsonl(FAILURE_LOG, event)
    
    # 同时写入 .compound/reflections/（如果来自 compound）
    if source == "compound":
        _write_compound_reflection(event)
    
    return event


def extract_patterns(events: Optional[list] = None) -> list:
    """
    从事件列表中提取重复模式。
    
    如果不传 events，自动读取 failure_log.jsonl。
    """
    if events is None:
        events = _read_jsonl(FAILURE_LOG)
    
    if not events:
        return []
    
    # 按错误类型分组
    error_groups = {}
    for event in events:
        if event.get("outcome") in ("failure", "error_unresolved", "error_recovered"):
            # 从 error_message 提取错误类型
            error_type = _classify_error(event.get("error_message", ""))
            if error_type not in error_groups:
                error_groups[error_type] = []
            error_groups[error_type].append(event)
    
    patterns = []
    for error_type, group_events in error_groups.items():
        if len(group_events) >= 2:  # 至少出现 2 次才算模式
            # 提取共同标签
            all_tags = []
            for e in group_events:
                all_tags.extend(e.get("tags", []))
            tag_counts = {}
            for tag in all_tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
            common_tags = sorted(tag_counts.keys(), key=lambda t: tag_counts[t], reverse=True)[:5]
            
            # 提取共同解决方案
            solutions = []
            for e in group_events:
                sol = e.get("solution", "")
                if sol and sol not in solutions:
                    solutions.append(sol)
            
            patterns.append({
                "pattern_type": "error",
                "error_type": error_type,
                "occurrence_count": len(group_events),
                "common_tags": common_tags,
                "sample_errors": [e.get("error_message", "")[:100] for e in group_events[:3]],
                "solutions": solutions[:3],
                "first_seen": group_events[0].get("timestamp"),
                "last_seen": group_events[-1].get("timestamp"),
            })
    
    # 保存 patterns
    _save_json(PATTERNS_FILE, patterns)
    
    return patterns


def get_suggestions(
    error_message: str = "",
    skill_name: Optional[str] = None,
    tags: Optional[list] = None,
    limit: int = 5,
) -> list:
    """
    检索类似事件的建议。
    
    优先级：
    1. 精确匹配 skill_name + error_message
    2. 标签匹配
    3. 模糊匹配 error_message
    """
    events = _read_jsonl(FAILURE_LOG)
    patterns = _load_json(PATTERNS_FILE) or []
    
    suggestions = []
    
    # 1. 从 patterns 中找匹配
    for pattern in patterns:
        score = 0
        if pattern.get("error_type") and error_message:
            # 错误类型匹配
            if pattern["error_type"].lower() in error_message.lower():
                score += 5
        if tags and pattern.get("common_tags"):
            # 标签匹配
            common = set(tags) & set(pattern["common_tags"])
            score += len(common) * 2
        
        if score > 0:
            suggestions.append({
                "type": "pattern",
                "score": score,
                "error_type": pattern.get("error_type"),
                "occurrence_count": pattern.get("occurrence_count", 0),
                "solutions": pattern.get("solutions", []),
                "common_tags": pattern.get("common_tags", []),
            })
    
    # 2. 从 events 中找直接匹配
    for event in reversed(events):  # 最新的优先
        score = 0
        if skill_name and event.get("skill_name") == skill_name:
            score += 3
        if error_message and event.get("error_message"):
            # 简单模糊匹配
            error_words = set(error_message.lower().split())
            event_words = set(event.get("error_message", "").lower().split())
            overlap = error_words & event_words
            if len(overlap) >= 2:
                score += len(overlap)
        # 标签匹配
        if tags and event.get("tags"):
            common = set(tags) & set(event.get("tags", []))
            score += len(common) * 2
        
        if score > 0:
            suggestions.append({
                "type": "event",
                "score": score,
                "description": event.get("description", ""),
                "error_message": event.get("error_message", "")[:200],
                "solution": event.get("solution", ""),
                "timestamp": event.get("timestamp"),
                "skill_name": event.get("skill_name"),
                "tags": event.get("tags", []),
            })
    
    # 按 score 排序
    suggestions.sort(key=lambda s: s.get("score", 0), reverse=True)
    
    return suggestions[:limit]


# ============================================================
# 内部辅助函数
# ============================================================

def _append_jsonl(path: Path, data: dict):
    """追加一行 JSON 到 JSONL 文件"""
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path) -> list:
    """读取 JSONL 文件"""
    if not path.exists():
        return []
    
    events = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return events


def _save_json(path: Path, data):
    """保存 JSON 文件"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_json(path: Path):
    """加载 JSON 文件"""
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_compound_reflection(event: dict):
    """写入 .compound/reflections/ 目录"""
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H%M%S")
    
    filename = f"{date_str}_{time_str}.json"
    filepath = COMPOUND_REFLECTIONS / filename
    
    _save_json(filepath, event)


def _classify_error(error_message: str) -> str:
    """从错误信息分类错误类型"""
    if not error_message:
        return "unknown"
    
    error_lower = error_message.lower()
    
    patterns = {
        "api_error": ["api", "401", "403", "404", "500", "502", "503", "timeout", "rate limit"],
        "config_error": ["config", "yaml", "json", "toml", "env", "variable"],
        "network_error": ["network", "connection", "dns", "socket", "ssh", "tunnel"],
        "tool_error": ["tool", "command", "not found", "permission denied"],
        "code_error": ["syntax", "import", "module", "type", "attribute", "name"],
        "environment_error": ["disk", "memory", "space", "oom", "killed"],
    }
    
    for error_type, keywords in patterns.items():
        for keyword in keywords:
            if keyword in error_lower:
                return error_type
    
    return "other"


# ============================================================
# CLI 接口（供 compound.sh 调用）
# ============================================================

def cli_record(args: list):
    """CLI: record <type> <description> [outcome] [severity] [error_msg]"""
    if len(args) < 2:
        print("Usage: unified_reflection.py record <type> <description> [outcome] [severity] [error_msg]")
        return
    
    event_type = args[0]
    description = args[1]
    outcome = args[2] if len(args) > 2 else "success"
    severity = int(args[3]) if len(args) > 3 else 0
    error_msg = args[4] if len(args) > 4 else None
    
    event = record_event(
        event_type=event_type,
        description=description,
        outcome=outcome,
        severity=severity,
        error_message=error_msg,
        source="compound",
    )
    
    print(json.dumps(event, ensure_ascii=False, indent=2))


def cli_suggestions(args: list):
    """CLI: suggestions <error_message> [skill_name] [limit]"""
    if len(args) < 1:
        print("Usage: unified_reflection.py suggestions <error_message> [skill_name] [limit]")
        return
    
    error_msg = args[0]
    skill_name = args[1] if len(args) > 1 else None
    limit = int(args[2]) if len(args) > 2 else 5
    
    suggestions = get_suggestions(
        error_message=error_msg,
        skill_name=skill_name,
        limit=limit,
    )
    
    print(json.dumps(suggestions, ensure_ascii=False, indent=2))


def cli_patterns(args: list):
    """CLI: patterns — 提取并显示模式"""
    patterns = extract_patterns()
    print(json.dumps(patterns, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: unified_reflection.py <command> [args...]")
        print("Commands:")
        print("  record <type> <description> [outcome] [severity] [error_msg]")
        print("  suggestions <error_message> [skill_name] [limit]")
        print("  patterns")
        sys.exit(1)
    
    command = sys.argv[1]
    args = sys.argv[2:]
    
    if command == "record":
        cli_record(args)
    elif command == "suggestions":
        cli_suggestions(args)
    elif command == "patterns":
        cli_patterns(args)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
