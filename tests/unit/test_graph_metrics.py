"""
tests/unit/test_graph_metrics.py
=================================

WP-3.8 / R-13 — response-contract tests for
``Layer0_AdaptiveTelemetryController.get_advanced_graph_metrics``
and the module-level ``get_advanced_graph_metrics`` convenience shim.

Permanent set candidate.  Covers: R-13, WP-3.8.

Design notes
------------
* Never instantiate ``Layer0_AdaptiveTelemetryController`` directly — its
  ``__init__`` starts a background ``RuntimeControlLoop`` and imports several
  heavy ML subsystems.  Instead we call the *unbound* method with a minimal
  ``MagicMock`` that exposes ``self.graph_builder.graph``.
* All assertions target the public API shape, not implementation details, so
  they remain valid if the internals are refactored.
"""
from __future__ import annotations

import unittest
from typing import Any, Dict
from unittest import mock

import networkx as nx

from layer0.app_main import Layer0_AdaptiveTelemetryController


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ctrl(g: nx.DiGraph) -> Any:
    """Return a minimal mock controller wired with *g* as the graph store."""
    ctrl = mock.MagicMock()
    ctrl.graph_builder.graph = g
    return ctrl


def _call(g: nx.DiGraph) -> Dict[str, Any]:
    """Invoke the unbound method with a mock controller backed by *g*."""
    return Layer0_AdaptiveTelemetryController.get_advanced_graph_metrics(_ctrl(g))


# ---------------------------------------------------------------------------
# Contract tests: dict must be non-empty and contain the four required keys
# ---------------------------------------------------------------------------

REQUIRED_KEYS = {"node_count", "edge_count", "top_nodes", "communities"}


class TestResponseContract(unittest.TestCase):
    """Core R-13 fix: get_advanced_graph_metrics must never return {}."""

    def _assert_contract(self, result: Dict[str, Any]) -> None:
        self.assertIsInstance(result, dict, "result must be a dict")
        self.assertNotEqual(result, {}, "result must not be the empty dict")
        for key in REQUIRED_KEYS:
            self.assertIn(key, result, f"required key '{key}' missing from result")

    def test_empty_graph_satisfies_contract(self):
        """An empty graph must still return the four required keys (never {})."""
        self._assert_contract(_call(nx.DiGraph()))

    def test_populated_graph_satisfies_contract(self):
        g = nx.DiGraph()
        g.add_edges_from([("a", "b"), ("b", "c"), ("c", "d"), ("a", "d")])
        self._assert_contract(_call(g))

    def test_result_is_not_empty_dict_for_any_graph(self):
        """Regression guard for R-13: both empty and non-empty graphs return non-{}."""
        for g in (nx.DiGraph(), _three_node_chain()):
            result = _call(g)
            self.assertNotEqual(result, {})


# ---------------------------------------------------------------------------
# node_count / edge_count accuracy
# ---------------------------------------------------------------------------

class TestNodeAndEdgeCounts(unittest.TestCase):

    def test_empty_graph_counts_are_zero(self):
        result = _call(nx.DiGraph())
        self.assertEqual(result["node_count"], 0)
        self.assertEqual(result["edge_count"], 0)

    def test_single_edge_counts(self):
        g = nx.DiGraph()
        g.add_edge("x", "y")
        result = _call(g)
        self.assertEqual(result["node_count"], 2)
        self.assertEqual(result["edge_count"], 1)

    def test_multi_edge_counts_match_graph(self):
        g = nx.DiGraph()
        g.add_edges_from([("a", "b"), ("b", "c"), ("a", "d"), ("d", "e")])
        result = _call(g)
        self.assertEqual(result["node_count"], g.number_of_nodes())
        self.assertEqual(result["edge_count"], g.number_of_edges())

    def test_isolated_node_counted(self):
        g = nx.DiGraph()
        g.add_node("lonely")
        result = _call(g)
        self.assertEqual(result["node_count"], 1)
        self.assertEqual(result["edge_count"], 0)


# ---------------------------------------------------------------------------
# top_nodes shape and ordering
# ---------------------------------------------------------------------------

class TestTopNodes(unittest.TestCase):

    def test_empty_graph_top_nodes_is_empty_list(self):
        result = _call(nx.DiGraph())
        self.assertIsInstance(result["top_nodes"], list)
        self.assertEqual(result["top_nodes"], [])

    def test_top_nodes_is_list_of_pairs(self):
        g = _three_node_chain()
        result = _call(g)
        top = result["top_nodes"]
        self.assertIsInstance(top, list)
        for item in top:
            self.assertIsInstance(item, (tuple, list),
                                  "each top_nodes entry must be a (node_id, degree) pair")
            self.assertEqual(len(item), 2)

    def test_top_nodes_sorted_by_degree_descending(self):
        """Highest out-degree node must appear first."""
        g = nx.DiGraph()
        # 'hub' has out-degree 3; all others have out-degree 0
        g.add_edges_from([("hub", "x"), ("hub", "y"), ("hub", "z")])
        result = _call(g)
        top = result["top_nodes"]
        degrees = [pair[1] for pair in top]
        self.assertEqual(degrees, sorted(degrees, reverse=True),
                         "top_nodes must be sorted by degree descending")

    def test_highest_degree_node_is_first(self):
        g = nx.DiGraph()
        g.add_edges_from([("hub", "x"), ("hub", "y"), ("hub", "z")])
        result = _call(g)
        self.assertEqual(result["top_nodes"][0][0], "hub")
        self.assertEqual(result["top_nodes"][0][1], 3)

    def test_top_nodes_capped_at_ten(self):
        """With more than 10 nodes, top_nodes must return at most 10 entries."""
        g = nx.DiGraph()
        for i in range(20):
            g.add_edge(f"src_{i}", f"dst_{i}")
        result = _call(g)
        self.assertLessEqual(len(result["top_nodes"]), 10)

    def test_node_ids_are_strings(self):
        g = nx.DiGraph()
        g.add_edges_from([(1, 2), (2, 3)])  # integer node IDs
        result = _call(g)
        for node_id, _ in result["top_nodes"]:
            self.assertIsInstance(node_id, str,
                                  "node IDs in top_nodes must be coerced to str")


# ---------------------------------------------------------------------------
# communities shape and semantics
# ---------------------------------------------------------------------------

class TestCommunities(unittest.TestCase):

    def test_empty_graph_communities_is_empty_list(self):
        result = _call(nx.DiGraph())
        self.assertIsInstance(result["communities"], list)
        self.assertEqual(result["communities"], [])

    def test_connected_graph_has_one_community(self):
        g = _three_node_chain()
        result = _call(g)
        self.assertEqual(len(result["communities"]), 1)

    def test_disconnected_graph_community_count(self):
        g = nx.DiGraph()
        g.add_edge("a", "b")   # component 1
        g.add_edge("c", "d")   # component 2 (disconnected)
        result = _call(g)
        self.assertEqual(len(result["communities"]), 2,
                         "two disconnected sub-graphs → two communities")

    def test_communities_cover_all_nodes(self):
        g = nx.DiGraph()
        g.add_edges_from([("a", "b"), ("c", "d"), ("e", "f")])
        result = _call(g)
        all_community_nodes = {n for comm in result["communities"] for n in comm}
        expected_nodes = {str(v) for v in g.nodes()}
        self.assertEqual(all_community_nodes, expected_nodes,
                         "every graph node must appear in exactly one community")

    def test_community_members_are_strings(self):
        g = nx.DiGraph()
        g.add_edges_from([(1, 2), (3, 4)])  # integer node IDs
        result = _call(g)
        for comm in result["communities"]:
            for member in comm:
                self.assertIsInstance(member, str,
                                      "community member IDs must be str")


# ---------------------------------------------------------------------------
# Module-level shim
# ---------------------------------------------------------------------------

class TestModuleLevelShim(unittest.TestCase):
    """The module-level ``get_advanced_graph_metrics`` delegates to the controller."""

    def test_shim_calls_controller_method(self):
        import layer0.app_main as app_main_mod
        mock_ctrl = mock.MagicMock()
        mock_ctrl.get_advanced_graph_metrics.return_value = {
            "node_count": 5,
            "edge_count": 7,
            "top_nodes": [("n1", 3)],
            "communities": [["n1", "n2"]],
        }
        with mock.patch.object(app_main_mod, "_layer0_controller", mock_ctrl):
            result = app_main_mod.get_advanced_graph_metrics()
        mock_ctrl.get_advanced_graph_metrics.assert_called_once()
        self.assertEqual(result["node_count"], 5)

    def test_shim_returns_required_keys(self):
        import layer0.app_main as app_main_mod
        mock_ctrl = mock.MagicMock()
        mock_ctrl.get_advanced_graph_metrics.return_value = {
            "node_count": 0,
            "edge_count": 0,
            "top_nodes": [],
            "communities": [],
        }
        with mock.patch.object(app_main_mod, "_layer0_controller", mock_ctrl):
            result = app_main_mod.get_advanced_graph_metrics()
        self.assertTrue(REQUIRED_KEYS.issubset(result.keys()))

    def test_shim_result_is_not_empty_dict(self):
        import layer0.app_main as app_main_mod
        mock_ctrl = mock.MagicMock()
        mock_ctrl.get_advanced_graph_metrics.return_value = {
            "node_count": 0,
            "edge_count": 0,
            "top_nodes": [],
            "communities": [],
        }
        with mock.patch.object(app_main_mod, "_layer0_controller", mock_ctrl):
            result = app_main_mod.get_advanced_graph_metrics()
        self.assertNotEqual(result, {})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _three_node_chain() -> nx.DiGraph:
    g = nx.DiGraph()
    g.add_edges_from([("n1", "n2"), ("n2", "n3")])
    return g


if __name__ == "__main__":
    unittest.main()
