"""T09 tests: truthful metrics, inspected rules, reproducible exports."""
from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pawpair.evaluation import (
    evaluate_scenarios, export_evaluation, load_manual_reviews, make_report,
    recommendation_examples,
)
from pawpair.rules import Rule
from pawpair.ui_service import DashboardData, build_dashboard_mining


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.temp = Path(self.tmp.name)
        self.data = DashboardData(
            {"pet_containing_orders": 5},
            tuple(map(frozenset, (("a", "b"), ("a", "b"), ("a", "c"), ("a",), ("c",)))),
            {"a": "Cat Food", "b": "Cat Treats", "c": "Dog Food"},
            (),
        )
        self.base = build_dashboard_mining(self.data, .20, .40)
        self.rule = next(r for r in self.base.rules if r.antecedent == ("a",) and r.consequent == ("b",))

    def _review_file(self, rows):
        path = self.temp / "reviews.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["antecedent_ids_json", "consequent_ids_json", "classification", "rationale"])
            writer.writerows(rows)
        return path

    def _one_row(self, category="Useful", lhs='["a"]', rhs='["b"]'):
        return [lhs, rhs, category, "This classification has an explicit written explanation."]

    def test_support_threshold_reduces_itemsets_rules(self):
        out = evaluate_scenarios(self.data, ((.20, .40), (.60, .40)))
        self.assertEqual(len(out), 2)
        self.assertGreater(out[0].frequent_itemsets, out[1].frequent_itemsets)
        self.assertGreater(out[0].association_rules, out[1].association_rules)
        self.assertEqual(out[0].total_baskets, 5)
        self.assertEqual(out[0].minimum_joint_baskets, 1)

    def test_confidence_changes_rules_not_itemsets(self):
        out = evaluate_scenarios(self.data, ((.20, .40), (.20, .90)))
        self.assertEqual(out[0].frequent_itemsets, out[1].frequent_itemsets)
        self.assertGreater(out[0].association_rules, out[1].association_rules)

    def test_coverage_is_in_sample_and_never_above_total(self):
        metrics = evaluate_scenarios(self.data, ((.20, .40),))[0]
        # a -> b fires for basket {a}; b -> a may fire only if a absent, etc.
        self.assertTrue(0 <= metrics.eligible_baskets <= metrics.total_baskets)
        self.assertAlmostEqual(metrics.eligible_baskets / metrics.total_baskets,
                               metrics.descriptive_coverage)
        self.assertEqual(metrics.eligible_baskets, 3)

    def test_reviews_resolve_real_directional_rules(self):
        path = self._review_file([self._one_row()])
        rows = load_manual_reviews(path, self.base.rules, minimum=1)
        self.assertEqual(rows[0].basket_count, self.rule.basket_count)
        self.assertEqual(rows[0].confidence, self.rule.confidence)
        self.assertEqual(rows[0].category, "Useful")

    def test_reviews_reject_missing_rule(self):
        path = self._review_file([self._one_row(lhs='["c"]', rhs='["b"]')])
        with self.assertRaisesRegex(ValueError, "not found"):
            load_manual_reviews(path, self.base.rules, minimum=1)

    def test_reviews_reject_duplicate_or_invalid_category(self):
        path = self._review_file([self._one_row(), self._one_row()])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            load_manual_reviews(path, self.base.rules, minimum=1)
        path = self._review_file([self._one_row(category="Made Up")])
        with self.assertRaisesRegex(ValueError, "Invalid classification"):
            load_manual_reviews(path, self.base.rules, minimum=1)

    def test_reviews_reject_empty_or_inadequate_rationale(self):
        path = self._review_file([["[\"a\"]", "[\"b\"]", "Useful", "short"]])
        with self.assertRaisesRegex(ValueError, "too short"):
            load_manual_reviews(path, self.base.rules, minimum=1)
        with self.assertRaisesRegex(ValueError, "At least 10"):
            load_manual_reviews(self._review_file([self._one_row()]), self.base.rules)

    def test_examples_only_recommend_unseen_and_preserve_rule_evidence(self):
        examples = recommendation_examples(self.base, self.data.catalog,
                                           (("Example", ("a",)),), top_k=3)
        self.assertEqual(len(examples), 1)
        self.assertGreaterEqual(len(examples[0]["recommendations"]), 1)
        for rec in examples[0]["recommendations"]:
            self.assertNotIn(rec["product_id"], {"a"})
            self.assertEqual(rec["joint_baskets"], 2 if rec["product_id"] == "b" else 1)

    def test_examples_reject_no_matches(self):
        with self.assertRaisesRegex(ValueError, "no applicable recommendations"):
            recommendation_examples(self.base, self.data.catalog, (("Empty", ("a", "b", "c")),))
        with self.assertRaisesRegex(ValueError, "top_k"):
            recommendation_examples(self.base, self.data.catalog, top_k=0)

    def test_exports_consistent_files_and_reports_limitations(self):
        scenarios = evaluate_scenarios(self.data, ((.20, .40),))
        reviews = load_manual_reviews(self._review_file([self._one_row()]), self.base.rules, minimum=1)
        examples = recommendation_examples(self.base, self.data.catalog, (("Example", ("a",)),))
        report = make_report(self.data, scenarios, reviews, examples)
        self.assertIn("in-sample", report)
        self.assertIn("5 pet-containing orders", report)
        self.assertIn("not** prediction", report)
        self.assertIn("Useful", report)
        self.assertIn("No held-out test", report)
        output = self.temp / "output"
        report_path = self.temp / "docs" / "report.md"
        export_evaluation(output, scenarios, reviews, examples, report_path, report)
        self.assertEqual(report_path.read_text(encoding="utf-8"), report)
        with (output / "threshold_experiments.csv").open(newline="") as handle:
            self.assertEqual(len(list(csv.DictReader(handle))), 1)
        saved = json.loads((output / "recommendation_examples.json").read_text())
        self.assertEqual(saved[0]["label"], "Example")
        with (output / "reviewed_rules.csv").open(newline="") as handle:
            self.assertEqual(len(list(csv.DictReader(handle))), 1)


if __name__ == "__main__":
    unittest.main()
