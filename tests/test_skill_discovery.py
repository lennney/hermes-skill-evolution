"""Tests for skill_discovery module — trajectory analysis, pattern detection, skill generation."""
import json
import tempfile
from pathlib import Path

import sys
HERMES_SRC = Path.home() / ".hermes" / "hermes-agent"
if str(HERMES_SRC) not in sys.path:
    sys.path.insert(0, str(HERMES_SRC))


# ── TrajectoryAnalyzer Tests ──

def test_record_tool_call_creates_file():
    """record_tool_call creates the JSONL file."""
    from tools.skill_discovery import TrajectoryAnalyzer
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = Path(f.name)
    try:
        analyzer = TrajectoryAnalyzer(trajectory_file=path)
        analyzer.record_tool_call("t1", "terminal", True, "test task")
        assert path.exists()
        lines = path.read_text().strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["task_id"] == "t1"
        assert entry["tool"] == "terminal"
        assert entry["success"] is True
        assert entry["task"] == "test task"
    finally:
        path.unlink(missing_ok=True)


def test_record_tool_call_appends():
    """Multiple record_tool_call calls append to file."""
    from tools.skill_discovery import TrajectoryAnalyzer
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = Path(f.name)
    try:
        analyzer = TrajectoryAnalyzer(trajectory_file=path)
        analyzer.record_tool_call("t1", "terminal", True)
        analyzer.record_tool_call("t1", "write_file", True)
        analyzer.record_tool_call("t1", "patch", True)
        lines = path.read_text().strip().split("\n")
        assert len(lines) == 3
        tools = [json.loads(l)["tool"] for l in lines]
        assert tools == ["terminal", "write_file", "patch"]
    finally:
        path.unlink(missing_ok=True)


def test_extract_empty_file():
    """Empty trajectory file returns empty list."""
    from tools.skill_discovery import TrajectoryAnalyzer
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = Path(f.name)
    try:
        analyzer = TrajectoryAnalyzer(trajectory_file=path)
        result = analyzer.extract_tool_sequences()
        assert result == []
    finally:
        path.unlink(missing_ok=True)


def test_extract_missing_file():
    """Missing trajectory file returns empty list."""
    from tools.skill_discovery import TrajectoryAnalyzer
    analyzer = TrajectoryAnalyzer(trajectory_file=Path("/tmp/nonexistent_test_file.jsonl"))
    result = analyzer.extract_tool_sequences()
    assert result == []


def test_extract_groups_by_task_id():
    """Extract groups tool calls by task_id."""
    from tools.skill_discovery import TrajectoryAnalyzer
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = Path(f.name)
    try:
        analyzer = TrajectoryAnalyzer(trajectory_file=path)
        # Task 1: 5 calls
        for tool in ["terminal", "write_file", "terminal", "patch", "terminal"]:
            analyzer.record_tool_call("t1", tool, True, "deploy")
        # Task 2: 3 calls (below default min_calls=5)
        for tool in ["read_file", "search_files", "read_file"]:
            analyzer.record_tool_call("t2", tool, True, "search")

        seqs = analyzer.extract_tool_sequences(min_calls=3)
        assert len(seqs) == 1  # Only task 1 qualifies
        assert seqs[0]["task_id"] == "t1"
        # Unique tools in order
        assert "terminal" in seqs[0]["sequence"]
        assert "write_file" in seqs[0]["sequence"]
        assert "patch" in seqs[0]["sequence"]
    finally:
        path.unlink(missing_ok=True)


def test_extract_filters_failed_tasks():
    """Failed tasks are filtered out."""
    from tools.skill_discovery import TrajectoryAnalyzer
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = Path(f.name)
    try:
        analyzer = TrajectoryAnalyzer(trajectory_file=path)
        # Successful task
        for tool in ["terminal", "write_file", "terminal", "patch", "terminal"]:
            analyzer.record_tool_call("t1", tool, True)
        # Failed task
        for tool in ["terminal", "write_file", "terminal", "patch", "terminal"]:
            analyzer.record_tool_call("t2", tool, False)

        seqs = analyzer.extract_tool_sequences(min_calls=3)
        assert len(seqs) == 1
        assert seqs[0]["task_id"] == "t1"
    finally:
        path.unlink(missing_ok=True)


def test_get_stats():
    """get_stats returns correct counts."""
    from tools.skill_discovery import TrajectoryAnalyzer
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = Path(f.name)
    try:
        analyzer = TrajectoryAnalyzer(trajectory_file=path)
        analyzer.record_tool_call("t1", "terminal", True)
        analyzer.record_tool_call("t1", "write_file", True)
        analyzer.record_tool_call("t2", "terminal", True)

        stats = analyzer.get_stats()
        assert stats["total_calls"] == 3
        assert stats["unique_tasks"] == 2
        assert stats["file_exists"] is True
    finally:
        path.unlink(missing_ok=True)


# ── PatternDetector Tests ──

def test_find_patterns_empty():
    """Empty sequences returns empty patterns."""
    from tools.skill_discovery import PatternDetector
    detector = PatternDetector()
    result = detector.find_repeated_patterns([])
    assert result == []


def test_find_patterns_min_occurrences():
    """Patterns below min_occurrences are filtered."""
    from tools.skill_discovery import PatternDetector
    detector = PatternDetector()
    sequences = [
        {"task_id": "t1", "sequence": ["terminal", "write_file", "patch"], "task": "a", "success": True},
        {"task_id": "t2", "sequence": ["terminal", "write_file", "patch"], "task": "b", "success": True},
    ]
    # min_occurrences=3, but only 2 occurrences
    result = detector.find_repeated_patterns(sequences, min_occurrences=3)
    assert len(result) == 0

    # min_occurrences=2, should find it
    result = detector.find_repeated_patterns(sequences, min_occurrences=2)
    assert len(result) >= 1


def test_find_patterns_sorted_by_count():
    """Patterns are sorted by count descending."""
    from tools.skill_discovery import PatternDetector
    detector = PatternDetector()
    sequences = [
        {"task_id": "t1", "sequence": ["a", "b", "c", "d", "e"], "task": "", "success": True},
        {"task_id": "t2", "sequence": ["a", "b", "c", "d", "e"], "task": "", "success": True},
        {"task_id": "t3", "sequence": ["a", "b", "c", "d", "e"], "task": "", "success": True},
        {"task_id": "t4", "sequence": ["x", "y", "z", "w", "v"], "task": "", "success": True},
    ]
    result = detector.find_repeated_patterns(sequences, min_occurrences=2, min_length=3)
    if len(result) >= 2:
        assert result[0]["count"] >= result[1]["count"]


def test_merge_overlapping():
    """Overlapping patterns are merged."""
    from tools.skill_discovery import PatternDetector
    detector = PatternDetector()
    # Two patterns that share 2/3 elements (Jaccard = 2/4 = 0.5 < 0.7)
    # Need higher overlap to trigger merge
    patterns = [
        {"pattern": ["a", "b", "c", "d"], "count": 5, "task_summaries": ["t1"]},
        {"pattern": ["a", "b", "c", "e"], "count": 4, "task_summaries": ["t2"]},
    ]
    merged = detector._merge_overlapping(patterns, threshold=0.7)
    # Jaccard([a,b,c,d], [a,b,c,e]) = 3/5 = 0.6 < 0.7, should NOT merge
    assert len(merged) == 2

    # Patterns with higher overlap
    patterns2 = [
        {"pattern": ["a", "b", "c"], "count": 5, "task_summaries": ["t1"]},
        {"pattern": ["a", "b", "c"], "count": 4, "task_summaries": ["t2"]},
    ]
    merged2 = detector._merge_overlapping(patterns2, threshold=0.7)
    assert len(merged2) == 1


# ── SkillGenerator Tests ──

def test_generate_valid_yaml():
    """Generated skill has valid YAML frontmatter."""
    from tools.skill_discovery import SkillGenerator
    gen = SkillGenerator()
    pattern = {
        "pattern": ["terminal", "write_file", "patch"],
        "count": 5,
        "task_summaries": ["deploy nginx server"],
        "confidence": 0.8,
    }
    skill_md = gen.generate(pattern)
    assert skill_md.startswith("---")
    assert "name:" in skill_md
    assert "description:" in skill_md
    assert "auto_generated: true" in skill_md


def test_generate_includes_steps():
    """Generated skill includes step-by-step instructions."""
    from tools.skill_discovery import SkillGenerator
    gen = SkillGenerator()
    pattern = {
        "pattern": ["terminal", "write_file", "patch"],
        "count": 3,
        "task_summaries": ["setup project"],
    }
    skill_md = gen.generate(pattern)
    assert "## Steps" in skill_md
    assert "terminal" in skill_md
    assert "write_file" in skill_md


def test_generate_min_length():
    """Generated skill meets minimum length requirement."""
    from tools.skill_discovery import SkillGenerator
    gen = SkillGenerator()
    pattern = {
        "pattern": ["terminal", "write_file", "patch", "read_file", "search_files"],
        "count": 5,
        "task_summaries": ["complex deployment workflow"],
    }
    skill_md = gen.generate(pattern)
    assert len(skill_md) >= 200


# ── SkillValidator Tests ──

def test_validate_valid_skill():
    """Valid skill passes validation."""
    from tools.skill_discovery import SkillValidator
    validator = SkillValidator()
    skill_md = """---
name: test-skill
description: A test skill for validation
auto_generated: true
---

# Test Skill

This is a test skill with enough content.

## When to Use

- When testing

## Steps

1. **Run command** (`terminal`)
2. **Create file** (`write_file`)
"""
    result = validator.validate(skill_md)
    assert result["valid"] is True
    assert result["score"] == 1.0
    assert len(result["issues"]) == 0


def test_validate_missing_frontmatter():
    """Missing YAML frontmatter is caught."""
    from tools.skill_discovery import SkillValidator
    validator = SkillValidator()
    result = validator.validate("# No frontmatter\n\n## Steps\n\n1. Run")
    assert result["valid"] is False
    assert any("frontmatter" in i.lower() for i in result["issues"])


def test_validate_missing_steps():
    """Missing steps section is caught."""
    from tools.skill_discovery import SkillValidator
    validator = SkillValidator()
    skill_md = """---
name: test
description: test
---

# Test

No steps here.
"""
    result = validator.validate(skill_md)
    assert result["valid"] is False
    assert any("steps" in i.lower() for i in result["issues"])


def test_validate_too_short():
    """Too-short skill is caught."""
    from tools.skill_discovery import SkillValidator
    validator = SkillValidator()
    skill_md = """---
name: test
description: test
---

## Steps

1. Run
"""
    result = validator.validate(skill_md)
    assert result["valid"] is False
    assert any("short" in i.lower() for i in result["issues"])


def test_validate_has_secrets():
    """Sensitive patterns are detected."""
    from tools.skill_discovery import SkillValidator
    validator = SkillValidator()
    skill_md = """---
name: test
description: test
---

## Steps

1. Run with API_KEY=sk-abc123def456

## Notes

This is a long enough skill to pass the length check. Adding more content here to ensure we meet the minimum 200 character threshold for validation. This is just filler text to make the skill longer.
"""
    result = validator.validate(skill_md)
    assert result["checks"]["no_secrets"] is False


# ── SkillDiscovery Integration Tests ──

def test_discover_analyze_empty():
    """analyze returns empty results with no data."""
    from tools.skill_discovery import SkillDiscovery
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = Path(f.name)
    try:
        sd = SkillDiscovery()
        sd.analyzer.trajectory_file = path
        result = sd.analyze()
        assert result["patterns_found"] == 0
        assert result["total_trajectories"] == 0
    finally:
        path.unlink(missing_ok=True)


def test_generate_and_validate():
    """generate_skill produces valid output."""
    from tools.skill_discovery import SkillDiscovery
    sd = SkillDiscovery()
    pattern = {
        "pattern": ["terminal", "write_file", "terminal", "patch", "terminal"],
        "count": 5,
        "task_summaries": ["deploy web app", "setup server"],
        "confidence": 0.8,
    }
    result = sd.generate_skill(pattern)
    assert "skill_md" in result
    assert "validation" in result
    assert result["validation"]["valid"] is True
    assert result["suggested_name"].startswith("learned-")


def test_approve_and_save():
    """approve_and_save writes files correctly."""
    from tools.skill_discovery import SkillDiscovery
    import shutil
    with tempfile.TemporaryDirectory() as tmpdir:
        sd = SkillDiscovery()
        # Override the learned skills dir
        from tools import skill_discovery
        original_dir = skill_discovery.LEARNED_SKILLS_DIR
        skill_discovery.LEARNED_SKILLS_DIR = Path(tmpdir) / "skills"

        skill_md = """---
name: test-approved
description: An approved test skill
auto_generated: true
---

# Test Approved

This is an approved skill for testing purposes.

## When to Use

- When testing approval

## Steps

1. **Run command** (`terminal`)
2. **Create file** (`write_file`)
"""
        result = sd.approve_and_save("test-approved", skill_md)
        assert result["saved"] is True
        assert Path(result["path"]).exists()
        assert (Path(result["path"]) / "SKILL.md").exists()
        assert (Path(result["path"]) / "meta.yaml").exists()

        # Verify content
        saved_skill = (Path(result["path"]) / "SKILL.md").read_text()
        assert "test-approved" in saved_skill

        # Restore
        skill_discovery.LEARNED_SKILLS_DIR = original_dir
