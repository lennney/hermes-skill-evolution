"""Tests for skill_ranking module — Thompson Sampling ranking."""
import json
import tempfile
from pathlib import Path

import sys
HERMES_SRC = Path.home() / ".hermes" / "hermes-agent"
if str(HERMES_SRC) not in sys.path:
    sys.path.insert(0, str(HERMES_SRC))


# ── ThompsonSampler Tests ──

def test_sampler_expected_value():
    """Expected value matches alpha/(alpha+beta)."""
    from tools.skill_ranking import ThompsonSampler
    s = ThompsonSampler("test", alpha=10, beta=5)
    assert abs(s.expected_value() - 10 / 15) < 0.001


def test_sampler_confidence():
    """Confidence = 1/(alpha+beta)."""
    from tools.skill_ranking import ThompsonSampler
    s = ThompsonSampler("test", alpha=10, beta=5)
    assert abs(s.confidence() - 1 / 15) < 0.001


def test_sampler_sample_range():
    """Sample is in [0, 1]."""
    from tools.skill_ranking import ThompsonSampler
    s = ThompsonSampler("test", alpha=3, beta=7)
    for _ in range(50):
        sample = s.sample()
        assert 0.0 <= sample <= 1.0


def test_sampler_high_success():
    """High alpha/beta ratio → high expected value."""
    from tools.skill_ranking import ThompsonSampler
    s = ThompsonSampler("test", alpha=90, beta=10)
    assert s.expected_value() > 0.8


def test_sampler_low_success():
    """Low alpha/beta ratio → low expected value."""
    from tools.skill_ranking import ThompsonSampler
    s = ThompsonSampler("test", alpha=10, beta=90)
    assert s.expected_value() < 0.2


def test_sampler_uniform_prior():
    """Alpha=1, beta=1 → expected value = 0.5."""
    from tools.skill_ranking import ThompsonSampler
    s = ThompsonSampler("test", alpha=1, beta=1)
    assert s.expected_value() == 0.5


# ── SkillRanker Tests ──

def test_ranker_empty_candidates():
    """Empty candidates returns empty results."""
    from tools.skill_ranking import SkillRanker
    ranker = SkillRanker()
    results = ranker.rank_skills([])
    assert results == []


def test_ranker_no_usage_data():
    """Ranking works with no usage data (uniform prior)."""
    from tools.skill_ranking import SkillRanker
    ranker = SkillRanker()
    candidates = [
        {"name": "skill-a", "score": 0.8},
        {"name": "skill-b", "score": 0.6},
    ]
    results = ranker.rank_skills(candidates, top_k=5)
    assert len(results) == 2
    # With uniform prior, ranking is by similarity
    assert results[0]["name"] == "skill-a"
    assert results[0]["rank_score"] > results[1]["rank_score"]


def test_ranker_top_k():
    """top_k limits results."""
    from tools.skill_ranking import SkillRanker
    ranker = SkillRanker()
    candidates = [{"name": f"skill-{i}", "score": 0.5} for i in range(20)]
    results = ranker.rank_skills(candidates, top_k=3)
    assert len(results) == 3


def test_ranker_includes_fields():
    """Results include all expected fields."""
    from tools.skill_ranking import SkillRanker
    ranker = SkillRanker()
    candidates = [{"name": "test-skill", "score": 0.7}]
    results = ranker.rank_skills(candidates)
    assert len(results) == 1
    r = results[0]
    assert "name" in r
    assert "rank_score" in r
    assert "thompson" in r
    assert "similarity" in r
    assert "confidence" in r
    assert "expected_value" in r


def test_get_skill_stats_no_data():
    """Stats for nonexistent skill returns defaults."""
    from tools.skill_ranking import SkillRanker
    ranker = SkillRanker()
    stats = ranker.get_skill_stats("nonexistent-skill")
    assert stats["has_data"] is False
    assert stats["expected_value"] == 0.5
    assert stats["confidence"] == 1.0


# ── Public API Tests ──

def test_thompson_rank_valid_json():
    """thompson_rank with valid JSON."""
    from tools.skill_ranking import thompson_rank
    candidates = json.dumps([{"name": "a", "score": 0.8}])
    result = thompson_rank(candidates)
    data = json.loads(result)
    assert "ranked" in data
    assert "results" in data


def test_thompson_rank_invalid_json():
    """thompson_rank with invalid JSON."""
    from tools.skill_ranking import thompson_rank
    result = thompson_rank("not-json")
    data = json.loads(result)
    assert "error" in data


def test_thompson_stats_valid():
    """thompson_stats with valid name."""
    from tools.skill_ranking import thompson_stats
    result = thompson_stats("test-skill")
    data = json.loads(result)
    assert "skill" in data
    assert "expected_value" in data


def test_thompson_ranking_stability():
    """Multiple calls produce similar rankings (low variance)."""
    from tools.skill_ranking import SkillRanker
    ranker = SkillRanker()
    candidates = [
        {"name": "high-quality", "score": 0.9},
        {"name": "low-quality", "score": 0.3},
    ]
    # Run multiple times, high-quality should usually rank higher
    wins = 0
    for _ in range(20):
        results = ranker.rank_skills(candidates, top_k=2, n_samples=10)
        if results[0]["name"] == "high-quality":
            wins += 1
    assert wins >= 15  # Should win most of the time
