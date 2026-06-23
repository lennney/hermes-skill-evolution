# Hermes Skill Evolution

> 从被动存储到主动学习 — Hermes Agent 技能自进化系统

[![Tests](https://img.shields.io/badge/tests-80%20passed-brightgreen)](#测试)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Hermes](https://img.shields.io/badge/Hermes-Agent-compatible-brightgreen)](https://github.com/NousResearch/hermes-agent)

## 这是什么

Hermes Agent 的技能自进化系统。让技能库从"只读库"变成"学习循环"：

| Phase | 功能 | 说明 |
|-------|------|------|
| **0** 反馈循环 | `skill_feedback` | 任务结果回流到质量评分 |
| **1** 失败学习 | `skill_failure_report` | 分类失败 + 自动修补建议 |
| **2** 自动发现 | `skill_discover` | 从轨迹中自动提取新 skill |
| **3** 技能组合 | `skill_graph` | DAG 加权路径 + 合并 |
| **4** RL优化 | `skill_rank` | Thompson Sampling 排名 |
| **整合** | `reflection_record` | 统一反思（compound + skill） |

## 17 个工具

### 核心搜索与评分
| 工具 | 功能 |
|------|------|
| `skill_search` | 语义搜索 skills |
| `skill_scores` | 6 维度质量评分 |
| `skill_chain` | BFS 技能链发现 |
| `skill_suggest` | 下游推荐 |

### 反馈与失败学习
| 工具 | 功能 |
|------|------|
| `skill_feedback` | 记录任务结果 |
| `skill_failure_report` | 报告失败 + 分类 |
| `skill_failure_analysis` | 分析失败模式 |

### 自动发现
| 工具 | 功能 |
|------|------|
| `skill_discover` | 轨迹模式发现 |
| `skill_generate` | 生成 SKILL.md |
| `skill_approve` | 审批保存 |

### 组合与优化
| 工具 | 功能 |
|------|------|
| `skill_graph` | DAG 加权最短路径 |
| `skill_compose` | improve / merge |
| `skill_rank` | Thompson Sampling 排名 |
| `skill_thompson_stats` | RL 统计 |

### 统一反思（新增）
| 工具 | 功能 |
|------|------|
| `reflection_record` | 记录事件（来自 compound 或 skill） |
| `reflection_suggestions` | 检索类似事件的建议 |
| `reflection_patterns` | 提取重复模式 |

## 安装

### 方式 1：手动复制（推荐）

```bash
# 只复制你需要的工具，不需要全部复制
# 例如只需要反馈循环 + 失败学习：
cp tools/skill_index.py ~/.hermes/hermes-agent/tools/
cp tools/skill_evolution.py ~/.hermes/hermes-agent/tools/
cp tools/failure_learning.py ~/.hermes/hermes-agent/tools/

# 重启 Hermes
hermes gateway restart
```

### 方式 2：全部安装

```bash
cp tools/*.py ~/.hermes/hermes-agent/tools/
cp tests/*.py ~/.hermes/hermes-agent/tests/tools/
hermes gateway restart
```

### 按需选择

| 你需要 | 复制这些文件 |
|--------|-------------|
| 只要语义搜索 + 评分 | `skill_index.py`, `skill_evolution.py` |
| 要失败学习 | + `failure_learning.py` |
| 要自动发现 | + `skill_discovery.py` |
| 要 DAG 组合 | + `skill_graph.py` |
| 要 RL 排名 | + `skill_ranking.py` |
| 要统一反思 | + `unified_reflection.py` |
| **全部** | `tools/*.py` |

> **注意**：`skill_evolution.py` 是工具注册入口，必须复制。其他文件按需选择。

## 与 Compound System 整合

本系统与 Hermes 的 Compound System（任务后反思系统）整合：

```
┌──────────────┐  ┌──────────────┐
│ compound.sh  │  │ skill tools  │
│ task_end     │  │ skill_used   │
└──────┬───────┘  └──────┬───────┘
       │                  │
       ▼                  ▼
┌──────────────────────────────────┐
│     unified_reflection.py        │
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
```

- **compound.sh** 任务结束时自动调用 `reflection_record`
- **skill tools** 失败时调用 `reflection_record`
- **统一检索** `reflection_suggestions` 同时查两个存储

## 设计原则

- **零核心改动**：不修改 `skills_tool.py`、`curator.py` 等核心文件
- **解耦模式**：通过 `tools/registry` 自动发现注册
- **向后兼容**：所有新功能通过 optional 参数扩展
- **安全优先**：生成的 skill 标记 `auto_generated: true`，默认不启用

## 架构

```
tools/skill_index.py        ← 核心：语义搜索 + 6 维评分 + BFS chaining
tools/skill_evolution.py    ← 工具注册层（17 个工具）
tools/skill_usage.py        ← 使用统计（需 Hermes 原有）
tools/failure_learning.py   ← 失败分类 + 日志 + 修补建议
tools/skill_discovery.py    ← 轨迹分析 + 模式发现 + 模板生成
tools/skill_graph.py        ← DAG + Dijkstra + SkillComposer
tools/skill_ranking.py      ← Thompson Sampling RL 排名
tools/unified_reflection.py ← 统一反思模块（compound + skill 整合）
```

## 测试

```bash
cd ~/.hermes/hermes-agent
python -m pytest tests/tools/test_skill_index.py tests/tools/test_skill_discovery.py tests/tools/test_skill_graph.py tests/tools/test_skill_ranking.py tests/test_unified_reflection.py -v
```

## 路线图

| Phase | 目标 | 状态 |
|-------|------|------|
| 0 | 反馈循环 | ✅ |
| 1 | 失败学习 | ✅ |
| 2 | 自动技能发现 | ✅ |
| 3 | 技能组合升级 | ✅ |
| 4 | RL 优化 | ✅ |
| 5 | 统一反思整合 | ✅ |

## 多平台计划

- [ ] 飞书/Lark 集成
- [ ] Discord bot 增强
- [ ] Web Dashboard
- [ ] API Server 端点

## License

MIT

## 致谢

基于 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 的插件系统构建。
