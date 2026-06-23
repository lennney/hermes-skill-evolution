#!/usr/bin/env python3
"""
Tests for unified_reflection.py — 统一反思模块
"""
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def temp_dirs():
    """Create temp directories for testing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_index = Path(tmpdir) / ".skill-index"
        compound = Path(tmpdir) / ".compound"
        reflections = compound / "reflections"
        skill_index.mkdir()
        compound.mkdir()
        reflections.mkdir()
        
        with patch("tools.unified_reflection.SKILL_INDEX_DIR", skill_index), \
             patch("tools.unified_reflection.COMPOUND_DIR", compound), \
             patch("tools.unified_reflection.FAILURE_LOG", skill_index / "failure_log.jsonl"), \
             patch("tools.unified_reflection.PATTERNS_FILE", skill_index / "patterns.json"), \
             patch("tools.unified_reflection.COMPOUND_REFLECTIONS", reflections):
            yield {
                "skill_index": skill_index,
                "compound": compound,
                 "reflections": reflections,
                "failure_log": skill_index / "failure_log.jsonl",
                "patterns": skill_index / "patterns.json",
            }


# ============================================================
# Tests: record_event
# ============================================================

class TestRecordEvent:
    def test_record_basic_event(self, temp_dirs):
        from tools.unified_reflection import record_event
        
        event = record_event(
            event_type="task_end",
            description="Test task",
            outcome="success",
            severity=0,
            source="compound",
        )
        
        assert event["event_type"] == "task_end"
        assert event["description"] == "Test task"
        assert event["outcome"] == "success"
        assert event["source"] == "compound"
        
        # Check file was written
        assert temp_dirs["failure_log"].exists()
        with open(temp_dirs["failure_log"]) as f:
            lines = f.readlines()
        assert len(lines) == 1
        recorded = json.loads(lines[0])
        assert recorded["event_type"] == "task_end"
    
    def test_record_error_event(self, temp_dirs):
        from tools.unified_reflection import record_event
        
        event = record_event(
            event_type="skill_failed",
            description="Skill execution failed",
            outcome="failure",
            severity=2,
            skill_name="test-skill",
            error_message="Connection timeout",
            tags=["network", "timeout"],
            source="skill_evolution",
        )
        
        assert event["skill_name"] == "test-skill"
        assert event["error_message"] == "Connection timeout"
        assert event["tags"] == ["network", "timeout"]
    
    def test_record_writes_to_compound(self, temp_dirs):
        from tools.unified_reflection import record_event
        
        record_event(
            event_type="task_end",
            description="Compound task",
            source="compound",
        )
        
        # Check .compound/reflections/ was written
        reflections_dir = temp_dirs["compound"] / "reflections"
        assert reflections_dir.exists()
        files = list(reflections_dir.glob("*.json"))
        assert len(files) == 1


# ============================================================
# Tests: get_suggestions
# ============================================================

class TestGetSuggestions:
    def _seed_events(self, temp_dirs):
        """Seed failure_log.jsonl with test events"""
        events = [
            {
                "event_type": "skill_failed",
                "description": "API rate limit",
                "outcome": "failure",
                "error_message": "Rate limit exceeded for API calls",
                "tags": ["api", "rate-limit"],
                "skill_name": "web-search",
                "solution": "Wait and retry",
            },
            {
                "event_type": "skill_failed",
                "description": "API auth error",
                "outcome": "failure",
                "error_message": "401 Unauthorized - invalid API key",
                "tags": ["api", "auth"],
                "skill_name": "web-search",
                "solution": "Check API key",
            },
            {
                "event_type": "task_end",
                "description": "Success",
                "outcome": "success",
                "tags": [],
            },
        ]
        
        with open(temp_dirs["failure_log"], "w") as f:
            for event in events:
                f.write(json.dumps(event) + "\n")
    
    def test_suggestions_by_error_message(self, temp_dirs):
        from tools.unified_reflection import get_suggestions
        
        self._seed_events(temp_dirs)
        
        suggestions = get_suggestions(error_message="API key invalid")
        
        assert len(suggestions) > 0
        # Should find the auth error
        found_auth = any("auth" in s.get("error_message", "").lower() or
                        "401" in s.get("error_message", "") or
                        "api" in str(s.get("tags", []))
                        for s in suggestions)
        assert found_auth
    
    def test_suggestions_by_skill_name(self, temp_dirs):
        from tools.unified_reflection import get_suggestions
        
        self._seed_events(temp_dirs)
        
        suggestions = get_suggestions(skill_name="web-search")
        
        assert len(suggestions) > 0
        # Should find events for web-search skill
        found_skill = any(s.get("skill_name") == "web-search" for s in suggestions)
        assert found_skill
    
    def test_suggestions_by_tags(self, temp_dirs):
        from tools.unified_reflection import get_suggestions
        
        self._seed_events(temp_dirs)
        
        suggestions = get_suggestions(tags=["rate-limit"])
        
        assert len(suggestions) > 0
    
    def test_suggestions_limit(self, temp_dirs):
        from tools.unified_reflection import get_suggestions
        
        self._seed_events(temp_dirs)
        
        suggestions = get_suggestions(limit=2)
        assert len(suggestions) <= 2


# ============================================================
# Tests: extract_patterns
# ============================================================

class TestExtractPatterns:
    def test_extract_patterns_from_repeated_errors(self, temp_dirs):
        from tools.unified_reflection import extract_patterns
        
        # Seed with repeated API errors
        events = [
            {
                "event_type": "skill_failed",
                "description": f"API error {i}",
                "outcome": "failure",
                "error_message": "Rate limit exceeded",
                "tags": ["api", "rate-limit"],
            }
            for i in range(3)
        ]
        
        with open(temp_dirs["failure_log"], "w") as f:
            for event in events:
                f.write(json.dumps(event) + "\n")
        
        patterns = extract_patterns()
        
        assert len(patterns) > 0
        # Should find API error pattern
        api_pattern = next((p for p in patterns if "api" in p.get("error_type", "")), None)
        assert api_pattern is not None
        assert api_pattern["occurrence_count"] == 3
    
    def test_extract_patterns_empty_log(self, temp_dirs):
        from tools.unified_reflection import extract_patterns
        
        patterns = extract_patterns()
        assert patterns == []
    
    def test_extract_patterns_saves_to_file(self, temp_dirs):
        from tools.unified_reflection import extract_patterns
        
        events = [
            {
                "event_type": "skill_failed",
                "description": "Error 1",
                "outcome": "failure",
                "error_message": "Network timeout",
                "tags": ["network"],
            },
            {
                "event_type": "skill_failed",
                "description": "Error 2",
                "outcome": "failure",
                "error_message": "Connection timeout",
                "tags": ["network"],
            },
        ]
        
        with open(temp_dirs["failure_log"], "w") as f:
            for event in events:
                f.write(json.dumps(event) + "\n")
        
        extract_patterns()
        
        assert temp_dirs["patterns"].exists()
        with open(temp_dirs["patterns"]) as f:
            saved = json.load(f)
        assert len(saved) > 0


# ============================================================
# Tests: CLI
# ============================================================

class TestCLI:
    def test_cli_record(self, temp_dirs):
        from tools.unified_reflection import cli_record
        
        cli_record(["task_end", "Test task", "success", "0", ""])
        
        assert temp_dirs["failure_log"].exists()
    
    def test_cli_suggestions(self, temp_dirs):
        from tools.unified_reflection import cli_suggestions
        
        # Seed data
        with open(temp_dirs["failure_log"], "w") as f:
            f.write(json.dumps({
                "event_type": "skill_failed",
                "description": "API error",
                "outcome": "failure",
                "error_message": "Rate limit exceeded",
                "tags": ["api"],
            }) + "\n")
        
        # Should not raise
        cli_suggestions(["Rate limit"])
    
    def test_cli_patterns(self, temp_dirs):
        from tools.unified_reflection import cli_patterns
        
        # Should not raise
        cli_patterns([])
