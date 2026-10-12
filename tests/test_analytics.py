"""T08 analytics tests: faithful directed edges and full-set A/B comparisons."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pawpair.analytics import association_edges, compare_mining
from pawpair.network_plot import association_figure
from pawpair.rules import Rule
from pawpair.ui_service import DashboardData, build_dashboard_mining


class GraphTests(unittest.TestCase):
    def setUp(self):
        self.catalog = {"1": "Cat Food", "2": "Cat Treats", "3": "Dog Food", "4": "Dog Treats"}
        self.aisles = {"1": "cat food care", "2": "cat food care",
                       "3": "dog food care", "4": "dog food care"}
        self.rules = (
            Rule(("1",), ("2",), 12, .12, .75, 1.9),
            Rule(("2",), ("1",), 10, .10, .68, 2.1),
            Rule(("1", "2"), ("3",), 14, .14, .95, 3.0),  # not a valid single-item edge
            Rule(("1",), ("2", "3"), 13, .13, .85, 2.5),  # not a valid single-item edge
            Rule(("3",), ("4",), 7, .07, .50, 3.2),
        )

    def test_graph_edges_are_only_genuine_one_to_one_rules(self):
        edges = association_edges(self.rules, self.catalog, self.aisles)
        self.assertEqual([(e.source_id, e.target_id) for e in edges],
                         [("1", "2"), ("2", "1"), ("3", "4")])
        self.assertEqual(edges[0].basket_count, 12)
        self.assertEqual(edges[0].confidence, .75)
        self.assertEqual(edges[0].support, .12)

    def test_category_minimum_evidence_lift_and_cap(self):
        dog = association_edges(self.rules, self.catalog, self.aisles,
                                aisle="dog food care", min_joint_baskets=6)
        self.assertEqual([(e.source_id, e.target_id) for e in dog], [("3", "4")])
        self.assertEqual(association_edges(self.rules, self.catalog, self.aisles,
                                           aisle="dog food care", min_joint_baskets=8), [])
        self.assertEqual(len(association_edges(self.rules, self.catalog, self.aisles,
                                               min_lift=2.0)), 2)
        self.assertEqual(len(association_edges(self.rules, self.catalog, self.aisles,
                                               max_edges=1)), 1)

    def test_invalid_filters_and_catalog_fail_clearly(self):
        for options in ({"aisle": "horses"}, {"max_edges": 0},
                        {"min_joint_baskets": 0}, {"min_lift": -1}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                association_edges(self.rules, self.catalog, self.aisles, **options)
        with self.assertRaisesRegex(ValueError, "catalog"):
            association_edges(self.rules, {"1": "Cat"}, self.aisles)

    def test_plotly_graph_has_directions_and_recipient_names(self):
        edges = association_edges(self.rules, self.catalog, self.aisles)
        figure = association_figure(edges)
        self.assertEqual(len(figure.layout.annotations), len(edges))
        self.assertTrue(all(annotation.showarrow for annotation in figure.layout.annotations))
        self.assertEqual(len(figure.data[-1].x), 4)  # four unique products
        self.assertIn("Cat Treats", str(figure.data[0].text[0]))
        self.assertEqual(len(association_figure([]).layout.annotations), 0)


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.data = DashboardData(
            profile={"pet_containing_orders": 4},
            baskets=tuple(frozenset(b) for b in
                          ({"a", "b"}, {"a", "b"}, {"a", "c"}, {"c"})),
            catalog={"a": "Cat food", "b": "Cat treats", "c": "Dog food"},
            item_frequencies=(),
        )

    def test_comparison_uses_full_recommendation_sets(self):
        a = build_dashboard_mining(self.data, .25, .5)
        b = build_dashboard_mining(self.data, .75, .5)
        comparison = compare_mining(a, b, ["b"])
        self.assertEqual(comparison.itemsets_a, 5)
        self.assertEqual(comparison.itemsets_b, 1)
        self.assertEqual(comparison.rules_a, 3)
        self.assertEqual(comparison.rules_b, 0)
        self.assertEqual([r.product_id for r in comparison.only_a], ["a"])
        self.assertEqual(comparison.only_b, ())
        self.assertEqual(comparison.shared, ())

    def test_identical_scenarios_have_no_gains_or_losses(self):
        a = build_dashboard_mining(self.data, .25, .5)
        comparison = compare_mining(a, a, ["a"])
        self.assertEqual(comparison.only_a, ())
        self.assertEqual(comparison.only_b, ())
        self.assertEqual({r.product_id for r in comparison.shared}, {"b"})
        self.assertEqual([r.product_id for r in comparison.recommendations_a],
                         [r.product_id for r in comparison.recommendations_b])

    def test_support_and_confidence_stricter_rules_are_subsets(self):
        baseline = build_dashboard_mining(self.data, .25, .5)
        higher_support = build_dashboard_mining(self.data, .5, .5)
        higher_confidence = build_dashboard_mining(self.data, .25, .8)
        self.assertLessEqual(len(higher_support.itemsets.counts), len(baseline.itemsets.counts))
        self.assertLessEqual(len(higher_support.rules), len(baseline.rules))
        self.assertLessEqual(len(higher_confidence.rules), len(baseline.rules))
        self.assertEqual(len(higher_confidence.itemsets.counts), len(baseline.itemsets.counts))

    def test_empty_basket_and_unknown_id(self):
        a = build_dashboard_mining(self.data, .25, .5)
        comparison = compare_mining(a, a, [])
        self.assertFalse(comparison.recommendations_a)
        with self.assertRaisesRegex(ValueError, "Unknown"):
            compare_mining(a, a, ["missing"])


if __name__ == "__main__":
    unittest.main()
