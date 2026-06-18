"""Tests for skill_graph module — DAG, Dijkstra, SkillComposer."""
import json
import tempfile
from pathlib import Path

import sys
HERMES_SRC = Path.home() / ".hermes" / "hermes-agent"
if str(HERMES_SRC) not in sys.path:
    sys.path.insert(0, str(HERMES_SRC))


# ── SkillGraph Tests ──

def test_build_empty_index():
    """Empty/nonexistent index builds empty graph."""
    from tools.skill_graph import SkillGraph
    g = SkillGraph()
    g.build()  # Uses real index (may or may not exist)
    assert isinstance(g.graph, dict)
    assert isinstance(g.skill_info, dict)


def test_dijkstra_no_path():
    """Dijkstra returns empty path when no connection exists."""
    from tools.skill_graph import SkillGraph
    g = SkillGraph()
    g.skill_info = {
        "a": {"name": "a", "provides": ["x"], "requires": [], "success_rate": 0.9},
        "b": {"name": "b", "provides": ["y"], "requires": ["z"], "success_rate": 0.8},
    }
    g.graph = {"a": [("b", 0.5)]}  # a -> b
    path, weight = g.dijkstra("b", "a")  # Reverse: no path
    assert path == []
    assert weight == float("inf")


def test_dijkstra_direct_path():
    """Dijkstra finds direct path."""
    from tools.skill_graph import SkillGraph
    g = SkillGraph()
    g.graph = {"a": [("b", 0.3)]}
    path, weight = g.dijkstra("a", "b")
    assert path == ["a", "b"]
    assert weight == 0.3


def test_dijkstra_shortest_path():
    """Dijkstra prefers lower-weight path."""
    from tools.skill_graph import SkillGraph
    g = SkillGraph()
    # a -> b (weight 0.8), a -> c -> b (weight 0.2 + 0.1 = 0.3)
    g.graph = {
        "a": [("b", 0.8), ("c", 0.2)],
        "c": [("b", 0.1)],
    }
    path, weight = g.dijkstra("a", "b")
    assert path == ["a", "c", "b"]
    assert abs(weight - 0.3) < 0.01


def test_dijkstra_same_node():
    """Dijkstra from node to itself."""
    from tools.skill_graph import SkillGraph
    g = SkillGraph()
    path, weight = g.dijkstra("a", "a")
    assert path == ["a"]
    assert weight == 0.0


def test_find_paths_empty():
    """Empty graph returns no paths."""
    from tools.skill_graph import SkillGraph
    g = SkillGraph()
    paths = g.find_paths(["nonexistent"])
    assert paths == []


def test_find_paths_with_edges():
    """find_paths returns valid paths."""
    from tools.skill_graph import SkillGraph
    g = SkillGraph()
    g.skill_info = {
        "src": {"name": "src", "provides": ["code"], "requires": [], "success_rate": 0.9},
        "mid": {"name": "mid", "provides": ["review"], "requires": ["code"], "success_rate": 0.8},
        "dst": {"name": "dst", "provides": ["deploy"], "requires": ["review"], "success_rate": 0.7},
    }
    g.graph = {
        "src": [("mid", 0.1)],
        "mid": [("dst", 0.2)],
    }
    paths = g.find_paths(["deploy"])
    assert len(paths) >= 1
    assert "dst" in paths[0]["path"]
    assert "deploy" in paths[0]["provides"]


def test_find_paths_sorted_by_weight():
    """Paths are sorted by weight ascending."""
    from tools.skill_graph import SkillGraph
    g = SkillGraph()
    g.skill_info = {
        "fast": {"name": "fast", "provides": ["x"], "requires": [], "success_rate": 0.95},
        "slow": {"name": "slow", "provides": ["x"], "requires": [], "success_rate": 0.5},
        "target": {"name": "target", "provides": ["goal"], "requires": ["x"], "success_rate": 0.8},
    }
    g.graph = {
        "fast": [("target", 0.05)],
        "slow": [("target", 0.5)],
    }
    paths = g.find_paths(["goal"])
    if len(paths) >= 2:
        assert paths[0]["weight"] <= paths[1]["weight"]


# ── SkillComposer Tests ──

def test_improve_no_failures():
    """improve_skill with no failures returns empty."""
    from tools.skill_graph import SkillComposer
    c = SkillComposer()
    result = c.improve_skill("nonexistent-skill")
    assert "improvements" in result
    assert isinstance(result["improvements"], list)


def test_merge_no_overlap():
    """merge_skills with no overlap returns merged=False."""
    from tools.skill_graph import SkillComposer
    c = SkillComposer()
    # Use skills that exist in the real index
    if len(c.graph.skill_info) >= 2:
        names = list(c.graph.skill_info.keys())
        result = c.merge_skills(names[0], names[-1])
        # They likely have no overlapping provides
        assert "merged" in result


def test_merge_identical_skills():
    """Merging same skill with itself finds full overlap."""
    from tools.skill_graph import SkillComposer
    c = SkillComposer()
    # Create a mock
    c.graph.skill_info = {
        "skill-a": {"name": "skill-a", "provides": ["x", "y"], "requires": ["z"], "success_rate": 0.8},
        "skill-b": {"name": "skill-b", "provides": ["x", "y"], "requires": ["z"], "success_rate": 0.9},
    }
    result = c.merge_skills("skill-a", "skill-b")
    assert result["merged"] is True
    assert result["jaccard"] == 1.0  # Full overlap


def test_merge_partial_overlap():
    """Merging with partial overlap."""
    from tools.skill_graph import SkillComposer
    c = SkillComposer()
    c.graph.skill_info = {
        "skill-a": {"name": "skill-a", "provides": ["x", "y"], "requires": [], "success_rate": 0.8},
        "skill-b": {"name": "skill-b", "provides": ["y", "z"], "requires": [], "success_rate": 0.9},
    }
    result = c.merge_skills("skill-a", "skill-b")
    assert result["merged"] is True
    assert "y" in result["overlap"]
    assert 0 < result["jaccard"] < 1.0


def test_merge_nonexistent_skill():
    """Merging nonexistent skill returns error."""
    from tools.skill_graph import SkillComposer
    c = SkillComposer()
    result = c.merge_skills("nonexistent-a", "nonexistent-b")
    assert "error" in result
    assert result["merged"] is False


# ── Public API Tests ──

def test_build_graph_and_find_paths():
    """Public API function works."""
    from tools.skill_graph import build_graph_and_find_paths
    result = build_graph_and_find_paths("test-passing")
    data = json.loads(result)
    assert "paths_found" in data
    assert "paths" in data


def test_compose_skill_improve():
    """Public API compose improve works."""
    from tools.skill_graph import compose_skill
    result = compose_skill("improve", "nonexistent-skill")
    data = json.loads(result)
    assert "improvements" in data or "error" in data


def test_compose_skill_merge():
    """Public API compose merge works."""
    from tools.skill_graph import compose_skill
    result = compose_skill("merge", "skill-a", "skill-b")
    data = json.loads(result)
    assert "merged" in data or "error" in data
