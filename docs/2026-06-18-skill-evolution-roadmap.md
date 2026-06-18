# Skill 自进化路线图 — 从被动存储到主动学习

> 基于 2026-06-18 差距分析（04-gap-analysis.md），结合已有实现
> 目标：补齐 P0 差距，让技能系统从"只读库"变成"学习循环"

## 进度

| Phase | 目标 | 状态 | 完成日期 |
|-------|------|------|---------|
| **0** | 反馈循环 | ✅ 完成 | 2026-06-18 |
| **1** | 失败学习 | ✅ 完成 | 2026-06-18 |
| **2** | 自动技能发现 | ✅ 完成 | 2026-06-18 |
| **3** | 技能组合升级 | ✅ 完成 | 2026-06-18 |
| **4** | RL 优化 | ✅ 完成 | 2026-06-18 |

---

## 现状盘点

| 组件 | 文件 | 行数 | 状态 |
|------|------|------|------|
| 语义搜索 | `tools/skill_index.py` | 741+ | ✅ 生产可用 |
| 质量评分 | `tools/skill_index.py` | 同上 | ✅ **6 维度**（含 success_rate） |
| 技能链发现 | `tools/skill_index.py` | 同上 | ✅ BFS |
| 质量淘汰 | cron job | — | ✅ 质量感知阈值 |
| 独立工具 | `tools/skill_evolution.py` | 468 | ✅ **7 个工具**已注册 |
| 使用统计 | `tools/skill_usage.py` | +92 | ✅ **record_outcome()** 已添加 |
| 反馈循环 | skill_feedback 工具 | — | ✅ **Phase 0 完成** |
| 失败学习 | `tools/failure_learning.py` | 350 | ✅ **Phase 1 完成** |
| 自动发现 | — | — | ❌ Phase 2 待做 |

**关键发现**：Hermes 已有 `skill_usage.py`，追踪 `use`/`view`/`patch` 次数和 `active`/`stale`/`archived` 状态。我们可以在这个基础上扩展，而不是从零开始。

---

## Phase 0: 反馈循环（Week 1）

**目标**：任务结果回流到质量评分，让评分从"静态启发式"变成"动态实证"

### 0.1 扩展 skill_usage.py — 添加结果追踪

在 `tools/skill_usage.py` 中添加：

```python
# 新增字段（每个 skill 的 usage record 中）
{
  "use_count": 12,
  "view_count": 45,
  "last_used_at": "2026-06-18T10:00:00Z",
  "state": "active",
  # ---- NEW ----
  "outcome_log": [                     # 最近 50 次结果
    {
      "ts": "2026-06-18T10:00:00Z",
      "success": true,
      "task": "deploy nginx server",
      "latency_ms": 1200,
      "error_type": null
    },
    ...
  ],
  "success_rate": 0.85,               # 滚动成功率
  "total_outcomes": 20,
  "total_successes": 17
}
```

新增函数：
```python
def record_outcome(skill_name: str, success: bool, task: str = "",
                   latency_ms: int = 0, error_type: str = None) -> None:
    """记录一次 skill 使用结果。"""
    # 追加到 outcome_log（保留最近 50 条）
    # 重算 success_rate
```

**验收标准**：
- [ ] `record_outcome()` 写入 JSON
- [ ] `success_rate` 正确计算
- [ ] outcome_log 不超过 50 条（FIFO 淘汰）
- [ ] 不影响现有 bump_use/bump_view 逻辑

### 0.2 更新质量评分 — 添加 success_rate 维度

修改 `tools/skill_index.py` 的 `calculate_scores()`：

```python
# 新增第 6 维度
weights = {
    "usage": 0.20,           # 使用频率（已有）
    "completeness": 0.20,    # 文档完整性（已有）
    "trust": 0.15,           # 信任度（已有）
    "freshness": 0.15,       # 新鲜度（已有）
    "activity": 0.10,        # 活跃度（已有）
    "success_rate": 0.20,    # 成功率（NEW）
}
```

从 `skill_usage.py` 的 `outcome_log` 读取成功率，作为第 6 个评分维度。

**验收标准**：
- [ ] 质量评分包含 success_rate 维度
- [ ] 无 outcome_log 的 skill 使用默认值 0.5（中性）
- [ ] 评分 JSON 格式向后兼容（旧评分文件能被新代码读取）

### 0.3 添加 skill_feedback 工具

在 `tools/skill_evolution.py` 中注册新工具：

```python
registry.register(
    name="skill_feedback",
    toolset="skills",
    schema=SKILL_FEEDBACK_SCHEMA,
    handler=lambda args, **kw: _handle_skill_feedback(args),
    emoji="📝",
)
```

工具功能：Agent 完成任务后调用，报告哪些 skill 有用/没用。

```json
// 输入
{"skill": "server-operations", "success": true, "task": "deploy nginx"}

// 输出
{"ok": true, "new_success_rate": 0.87, "total_outcomes": 21}
```

**验收标准**：
- [ ] `skill_feedback` 工具可被 Agent 调用
- [ ] 成功率实时更新
- [ ] 调用后 `skill_scores` 结果变化

---

## Phase 1: 失败学习（Week 2-3）

**目标**：失败不留痕迹 → 失败成为学习信号

### 1.1 失败分类器

创建 `tools/failure_learning.py`：

```python
class FailureClassifier:
    """将任务失败分类为可操作的类型。"""
    
    CATEGORIES = {
        "missing_skill":    "需要的 skill 不存在",
        "wrong_skill":      "选了错误的 skill",
        "execution_error":  "skill 内容正确但执行出错",
        "insufficient":     "skill 内容不够完整",
        "timeout":          "超时",
        "hallucination":    "Agent 幻觉",
    }
    
    def classify(self, error_info: dict) -> str:
        """根据错误信息分类。"""
        # 基于关键词 + 错误模式的规则分类
```

### 1.2 失败日志

```python
class FailureLogger:
    """记录失败的完整上下文。"""
    
    def log(self, skill_name: str, error_type: str, 
            context: str, task: str) -> str:
        """写入 failures.jsonl，返回 failure_id。"""
    
    def analyze_patterns(self, skill_name: str = None) -> list:
        """分析失败模式 — 哪个 skill 最容易失败？什么类型的错误？"""
```

数据存储：`~/.hermes/hermes-agent/.skill-index/failures.jsonl`

```jsonl
{"id": "f001", "ts": "...", "skill": "server-operations", "category": "execution_error", "context": "sudo permission denied", "task": "deploy nginx", "resolution": null}
```

### 1.3 Skill 自动修补建议

```python
class SkillPatcher:
    """基于失败模式生成 skill 修补建议。"""
    
    def suggest_patch(self, failure_id: str) -> dict:
        """分析失败，生成 SKILL.md 修补建议。"""
        # 读取失败上下文
        # 读取对应 skill 的 SKILL.md
        # 用 LLM 生成修补建议（添加错误处理/边界情况）
        # 返回：{section, old_text, new_text, reason}
```

**验收标准**：
- [ ] 失败可被记录到 failures.jsonl
- [ ] 分类器能识别 6 种错误类型
- [ ] 失败模式分析能输出统计
- [ ] 修补建议能输出具体的 SKILL.md 修改

---

## Phase 2: 自动技能发现（Week 3-4）

**目标**：从成功的任务轨迹中自动提取新 skill

### 2.1 轨迹捕获

```python
class TrajectoryCapture:
    """捕获 Agent 的工具调用序列。"""
    
    def capture(self, task: str, tool_calls: list, 
                outcome: bool) -> dict:
        """保存一次完整的任务轨迹。"""
        # tool_calls: [{"tool": "terminal", "args": {...}, "result": "..."}, ...]
        # 返回 trajectory_id
    
    def find_repeated_patterns(self, min_occurrences: int = 3) -> list:
        """发现重复出现的工具调用模式。"""
```

数据存储：`~/.hermes/hermes-agent/.skill-index/trajectories.jsonl`

### 2.2 Skill 模板生成

```python
class SkillGenerator:
    """从成功轨迹生成 SKILL.md。"""
    
    def generate(self, pattern: dict) -> str:
        """生成 SKILL.md 内容。"""
        # 1. 提取通用步骤（去掉具体参数）
        # 2. 生成 name/description/triggers
        # 3. 生成 step-by-step 指令
        # 4. 添加警告和边界情况
```

### 2.3 验证门

```python
class SkillValidator:
    """验证生成的 skill 是否可用。"""
    
    def validate(self, skill_md: str, test_task: str = None) -> dict:
        """验证 skill。"""
        # 1. 格式检查（YAML frontmatter 合法？）
        # 2. 内容检查（有步骤？有命令？）
        # 3. 可选：dry-run（用 LLM 模拟执行）
        # 返回：{valid: bool, issues: list, score: float}
```

### 2.4 集成到 learning_loop.py

```python
# 主循环
def learning_loop():
    """每次 Agent 完成任务后调用。"""
    # 1. 检查最近的成功轨迹
    # 2. 发现重复模式
    # 3. 生成 skill 模板
    # 4. 验证
    # 5. 通过 → 写入 skills/learned/
    # 6. 失败 → 记录但不创建
```

**验收标准**：
- [ ] 成功轨迹可被捕获
- [ ] 重复模式可被发现（≥3 次相似轨迹）
- [ ] 生成的 SKILL.md 格式合法
- [ ] 验证门能拦截不合格的 skill
- [ ] 新 skill 写入 `skills/learned/` 目录

---

## Phase 3: 技能组合升级（Week 5-6）

**目标**：BFS → DAG 加权路径 + SkillComposer 操作

### 3.1 Skill DAG

```python
class SkillGraph:
    """技能有向无环图。"""
    
    def build(self) -> None:
        """从 provides/requires 元数据构建 DAG。"""
    
    def find_path(self, goal: list[str], method: str = "dijkstra") -> list:
        """加权最短路径（权重 = success_rate × relevance）。"""
    
    def suggest_composition(self, task: str) -> list:
        """根据任务推荐组合方案。"""
```

### 3.2 SkillComposer 操作

```python
def create_skill(trajectory: dict) -> str:
    """从轨迹创建新 skill（已在 Phase 2 实现）。"""

def improve_skill(skill_name: str, failure_patterns: list) -> str:
    """基于失败模式改进现有 skill。"""

def merge_skills(skill_a: str, skill_b: str) -> str:
    """合并两个功能重叠的 skill。"""
```

---

## Phase 4: RL 优化（Week 7-8，可选）

**目标**：Thompson Sampling 替代静态排名

```python
class ThompsonSampler:
    """基于 Beta 分布的技能选择。"""
    
    def __init__(self):
        self.alpha = successes + 1  # 成功次数
        self.beta = failures + 1    # 失败次数
    
    def sample_score(self) -> float:
        """从 Beta(α, β) 采样 → 排序。"""
        return np.random.beta(self.alpha, self.beta)
```

替换 `semantic_search()` 中的排序逻辑：
- 当前：cosine similarity 排序
- 升级：cosine similarity × Thompson sample

---

## 执行原则

1. **向后兼容**：所有新功能通过 optional 参数和 JSON 扩展，不破坏现有数据
2. **渐进式**：每个 Phase 独立可用，不需要全部完成才能部署
3. **可观测性优先**：先记录一切，再优化
4. **LLM-in-the-loop**：分析/蒸馏用 LLM，选择/排序用轻量算法
5. **遵循 SPARK 模式**：执行→判断→反思→重试→蒸馏

---

## 文件清单

| Phase | 新增文件 | 修改文件 |
|-------|---------|---------|
| 0 | — | `tools/skill_usage.py`, `tools/skill_index.py`, `tools/skill_evolution.py` |
| 1 | `tools/failure_learning.py` | `tools/skill_evolution.py`（新工具） |
| 2 | `tools/skill_discovery.py`, `tools/learning_loop.py` | — |
| 3 | `tools/skill_graph.py` | `tools/skill_index.py`（BFS→DAG） |
| 4 | `tools/thompson_sampler.py` | `tools/skill_index.py`（排序逻辑） |

---

## 风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| outcome_log 膨胀 | 磁盘 | FIFO 50 条 + 定期清理 |
| 自动发现产生低质量 skill | 噪声 | 验证门 + 人工审批 |
| Thompson Sampling 探索期 | 不稳定 | 先在只读模式观察 |
| 失败分类器不准 | 错误学习 | 规则优先，LLM 辅助 |
