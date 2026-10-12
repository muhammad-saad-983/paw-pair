"""T07 dashboard adapter integration tests; no Streamlit dependency required."""
from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pawpair.rules import Rule
from pawpair.ui_service import (
    build_dashboard_mining,
    confidence_buckets,
    data_signature,
    filter_rules,
    frequent_itemset_rows,
    load_dashboard_data,
)


class DashboardDataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data_dir = Path(self.tmp.name)
        (self.data_dir / "dataset_profile.json").write_text(
            json.dumps({"pet_containing_orders": 4, "multi_pet_item_orders": 3}),
            encoding="utf-8")
        with (self.data_dir / "pet_baskets.csv").open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["order_id", "product_ids_json"])
            for order_id, ids in enumerate((["a", "b"], ["a", "b"], ["a", "c"], ["c"]), 1):
                writer.writerow([order_id, json.dumps(ids)])
        with (self.data_dir / "item_frequency.csv").open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["product_id", "product_name", "aisle", "basket_count", "support"])
            writer.writerows([["a", "Cat Food", "cat food care", 3, .75],
                              ["b", "Cat Treats", "cat food care", 2, .5],
                              ["c", "Dog Food", "dog food care", 2, .5]])

    def test_missing_processed_files_gives_runnable_guidance(self):
        (self.data_dir / "pet_baskets.csv").unlink()
        with self.assertRaisesRegex(FileNotFoundError, "python run_pipeline.py"):
            data_signature(self.data_dir)

    def test_bad_profile_count_is_detected(self):
        (self.data_dir / "dataset_profile.json").write_text(
            json.dumps({"pet_containing_orders": 99}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "transaction count"):
            load_dashboard_data(self.data_dir)

    def test_slider_recalculation_changes_rule_count_without_touching_files(self):
        data = load_dashboard_data(self.data_dir)
        sig_before = data_signature(self.data_dir)
        initial = build_dashboard_mining(data, .25, .5)
        strict = build_dashboard_mining(data, .75, .5)
        self.assertEqual(len(data.baskets), 4)
        self.assertEqual(len(initial.itemsets.counts), 5)  # a,b,c,ab,ac
        self.assertEqual(len(initial.rules), 3)  # a->b, b->a, c->a excluded at 50%? c->a = 50% yes
        self.assertEqual(len(strict.itemsets.counts), 1)
        self.assertEqual(len(strict.rules), 0)
        self.assertEqual(sig_before, data_signature(self.data_dir))
        self.assertEqual(len(initial.recommender.recommend(["b"])), 1)

    def test_itemsets_table_has_counts_and_support(self):
        data = load_dashboard_data(self.data_dir)
        mined = build_dashboard_mining(data, .25, .5)
        pairs = frequent_itemset_rows(mined, data.catalog, size=2)
        self.assertEqual(len(pairs), 2)
        self.assertEqual(pairs[0]["Products"], "Cat Food, Cat Treats")
        self.assertEqual(pairs[0]["Support"], .5)


class RuleSearchTests(unittest.TestCase):
    def setUp(self):
        self.catalog = {"1": "Cat Food", "2": "Cat Treats", "3": "Dog Food"}
        self.rules = (
            Rule(("1",), ("2",), 10, .10, .8, 2.0),
            Rule(("2",), ("1",), 10, .10, .6, 1.5),
            Rule(("3",), ("2",), 4, .04, .9, 4.0),
        )

    def test_filter_search_by_name_and_exact_id(self):
        self.assertEqual(len(filter_rules(self.rules, self.catalog, "cat", "Consequent")), 3)
        self.assertEqual(len(filter_rules(self.rules, self.catalog, "3", "Antecedent")), 1)
        self.assertEqual(len(filter_rules(self.rules, self.catalog, "dog", "Consequent")), 0)

    def test_sort_by_lift(self):
        rows = filter_rules(self.rules, self.catalog, sort_by="Lift")
        self.assertEqual(rows[0]["Antecedent"], "Dog Food")
        self.assertEqual(rows[0]["Lift"], 4.0)

    def test_confidence_histogram_accounts_for_all_rules(self):
        buckets = confidence_buckets(self.rules)
        self.assertEqual(sum(x["Rules"] for x in buckets), 3)
        self.assertEqual(len(buckets), 10)
        self.assertEqual(buckets[-1]["Rules"], 1)  # 90% belongs to final interval


if __name__ == "__main__":
    unittest.main()
