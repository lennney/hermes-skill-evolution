# Skill Evolution System — Changelog

All notable changes to the Skill Evolution system will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Changed
- hermes-agent: modified 5 file(s) — scripts/release.py, tests/tools/test_skill_index.py, tools/failure_learning.py (+2 more)

### Added
- Phase 4: skill_ranking.py — Thompson Sampling RL optimization (15 tests)
- Phase 3: skill_graph.py — DAG weighted pathfinding + SkillComposer (16 tests)
- Phase 2: skill_discovery.py — auto skill discovery from trajectories (22 tests)
- doc-sync.py: automatic documentation sync script (Phase 1 — Failure Learning)
- `tools/failure_learning.py`: FailureClassifier + FailureLogger + FailureAnalyzer + SkillPatcher
- `skill_failure_report` tool: report failures, auto-classify, suggest SKILL.md patches
- `skill_failure_analysis` tool: analyze failure patterns per-skill or globally
- Failure categories: missing_skill, wrong_skill, execution_error, timeout, insufficient, hallucination
- Failure log storage: `.skill-index/failures.jsonl`

### Added (Phase 0 — Feedback Loop)
- `record_outcome()` in `tools/skill_usage.py`: record task success/failure per skill
- `get_success_rate()` / `get_outcome_stats()` helpers
- 6th quality dimension: `success_rate` (weight 0.20) in `tools/skill_index.py`
- `skill_feedback` tool: report task outcomes → feeds into quality scoring
- Updated `skill_scores` tool: now shows success_rate and total_outcomes

### Added (Earlier)
- `tools/skill_index.py`: semantic search (sentence-transformers), quality scoring (5→6 dimensions), skill chaining (BFS)
- `tools/skill_evolution.py`: 7 independent tools registered via Hermes auto-discovery
- Chaining metadata: provides/requires/chain_with in 10+ SKILL.md files
- Daily cron: index rebuild at 02:00, quality scores at 02:05

## [0.1.0] — 2026-06-18

### Initial
- Semantic search with paraphrase-multilingual-MiniLM-L12-v2 (384-dim)
- Hash-based fallback (zero dependencies)
- 56 skills indexed
- 14 tests passing
