# Changelog

## [0.3.0] - 2026-06-18

### Added
- `unified_reflection.py`: 整合 compound-system 和 skill-evolution 的统一反思模块
- `reflection_record`: 记录事件（来自 compound 或 skill evolution）
- `reflection_suggestions`: 检索类似事件的建议
- `reflection_patterns`: 提取重复模式
- 13 个新测试，总计 80 个测试全绿

### Changed
- `compound.sh`: 任务结束时自动调用 `reflection_record` 记录事件
- `skill_evolution.py`: 注册 3 个新工具（reflection_record/suggestions/patterns）

### Integration
- Compound System（任务后反思）和 Skill Evolution（技能自进化）现在共享统一存储
- 数据流：compound.sh / skill tools → unified_reflection.py → .skill-index/ + .compound/

## [0.2.0] - 2026-06-18

### Added
- Phase 2: 自动技能发现 (`skill_discovery.py`)
- Phase 3: 技能组合 (`skill_graph.py`)
- Phase 4: RL 优化 (`skill_ranking.py`)
- 54 个新测试

## [0.1.0] - 2026-06-18

### Added
- Phase 0: 反馈循环 (`skill_feedback`)
- Phase 1: 失败学习 (`failure_learning.py`)
- 语义搜索 + 6 维评分 (`skill_index.py`)
- 13 个核心工具
