"""Apriori correctness against small, hand-verifiable baskets."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from sys import path as sys_path

sys_path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pawpair.apriori import apriori, generate_candidates, read_baskets, export_itemsets


class AprioriTests(unittest.TestCase):
    def setUp(self):
        # A: 4/5; B: 4/5; C: 3/5; AB: 3/5, AC: 2/5, BC: 2/5, ABC: 1/5.
        self.baskets = [set("AB"), set("ABC"), set("AB"), set("AC"), set("BC")]

    def test_counts_and_threshold(self):
        result = apriori(self.baskets, 0.4)
        self.assertEqual(result.min_count, 2)
        self.assertEqual(result.counts[("A",)], 4)
        self.assertEqual(result.counts[("A", "B")], 3)
        self.assertEqual(result.counts[("B", "C")], 2)
        self.assertNotIn(("A", "B", "C"), result.counts)
        self.assertAlmostEqual(result.support(("A", "B")), .6)
        self.assertEqual([v.frequent_itemsets for v in result.levels], [3, 3, 0])

    def test_candidate_pruning(self):
        candidates, joined, pruned = generate_candidates({("A", "B"), ("A", "C")}, 3)
        self.assertEqual(joined, 1)
        self.assertEqual(pruned, 1)
        self.assertEqual(candidates, set())

    def test_singleton_only_at_high_support(self):
        result = apriori(self.baskets, 0.8)
        self.assertEqual(set(result.counts), {("A",), ("B",)})

    def test_invalid_support(self):
        for value in [0, -1, 1.1, float("nan")]:
            with self.assertRaises(ValueError):
                apriori(self.baskets, value)

    def test_export_and_roundtrip(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            result = apriori(self.baskets, 0.4)
            export_itemsets(result, {"A":"Apple", "B":"Banana", "C":"Carrot"}, folder)
            with (folder / "frequent_itemsets.csv").open(newline="", encoding="utf-8") as f:
                records = list(csv.DictReader(f))
            self.assertEqual(len(records), len(result.counts))
            self.assertEqual(json.loads((folder / "apriori_summary.json").read_text())["min_count"], 2)
            with (folder / "pet_baskets.csv").open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["order_id", "product_ids_json"])
                w.writerow(["101", '["A", "B"]'])
            self.assertEqual(read_baskets(folder / "pet_baskets.csv"), [set("AB")])


if __name__ == "__main__":
    unittest.main()
