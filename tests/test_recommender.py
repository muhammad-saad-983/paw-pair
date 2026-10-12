"""T06 tests: matching, ranking, evidence, smart basket and what-if."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from sys import path as sys_path

sys_path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pawpair.recommender import RecommendationEngine, load_catalog, load_rules
from pawpair.rules import Rule


def rule(lhs, rhs, confidence, count=6, support=.2, lift=2):
    return Rule(tuple(lhs), tuple(rhs), count, support, confidence, lift)


class RecommendationTests(unittest.TestCase):
    def setUp(self):
        self.catalog = {"A": "Cat Food", "B": "Cat Treats", "C": "Cat Litter",
                        "D": "Cat Toy", "E": "Grooming Kit"}
        self.engine = RecommendationEngine([
            rule(["A"], ["B"], .65, 8, .3, 3),
            rule(["A"], ["C"], .6, 12, .4, 4),
            rule(["B"], ["C"], .8, 6, .2, 3),
            rule(["A", "B"], ["C"], .9, 5, .15, 5),
            rule(["A", "B"], ["D"], .7, 7, .1, 2),
            rule(["A"], ["D", "E"], .99, 20, .5, 4),
            rule(["B"], ["A"], .8, 8, .3, 3),
        ], self.catalog)

    def test_match_only_full_antecedent_and_exclude_basket_items(self):
        recs = self.engine.recommend(["A"])
        self.assertEqual([r.product_id for r in recs], ["B", "C"])
        self.assertFalse(any(r.product_id == "A" for r in recs))
        # AB -> C, AB -> D both match only after B is selected.
        with_two = self.engine.recommend(["A", "B"])
        self.assertEqual([r.product_id for r in with_two], ["C", "D"])
        self.assertNotIn("B", [r.product_id for r in with_two])

    def test_best_evidence_and_multiple_rules(self):
        recs = self.engine.recommend(["A", "B"])
        c = recs[0]
        self.assertEqual(c.product_name, "Cat Litter")
        self.assertEqual(c.best_rule.antecedent, ("A", "B"))
        self.assertEqual(c.supporting_rule_count, 3)
        self.assertEqual([e.rule.confidence for e in c.evidence], [.9, .8, .6])
        self.assertIn("5 baskets", c.explanation)
        self.assertIn("90.0%", c.explanation)
        self.assertIn("15.00%", c.explanation)
        self.assertIn("5.00", c.explanation)

    def test_multi_item_consequents_are_not_split(self):
        result = self.engine.recommend(["A"])
        self.assertFalse(any(rec.product_id in ("D", "E") for rec in result))

    def test_tie_breaks_by_joint_count_then_lift_then_id(self):
        engine = RecommendationEngine([
            rule(["A"], ["B"], .5, 7, .1, 1),
            rule(["A"], ["C"], .5, 8, .1, 1),
            rule(["A"], ["D"], .5, 8, .1, 2),
            rule(["A"], ["E"], .5, 8, .1, 2),
        ], self.catalog)
        self.assertEqual([r.product_id for r in engine.recommend(["A"])],
                         ["D", "E", "C", "B"])
        self.assertEqual(len(engine.recommend(["A"], limit=1)), 1)

    def test_smart_basket_add_remove_recompute(self):
        basket = self.engine.make_basket(["A", "A"])
        self.assertEqual(basket.items, ("A",))
        self.assertEqual([r.product_id for r in basket.recommendations()], ["B", "C"])
        basket.add("B")
        self.assertEqual([r.product_id for r in basket.recommendations()], ["C", "D"])
        delta = basket.preview_remove("B")
        self.assertEqual(delta.before_basket, ("A", "B"))
        self.assertEqual(delta.after_basket, ("A",))
        self.assertEqual([r.product_id for r in delta.gained], ["B"])
        self.assertEqual([r.product_id for r in delta.lost], ["D"])
        self.assertEqual([r.product_id for r in delta.retained], ["C"])
        self.assertEqual(basket.items, ("A", "B"), "Preview must not mutate basket")
        basket.remove("B")
        self.assertEqual([r.product_id for r in basket.recommendations()], ["B", "C"])

    def test_no_match_and_invalid_inputs(self):
        self.assertEqual(self.engine.recommend([]), [])
        self.assertEqual(self.engine.recommend(["E"]), [])
        with self.assertRaisesRegex(ValueError, "Unknown product"):
            self.engine.recommend(["missing"])
        with self.assertRaises(TypeError):
            self.engine.recommend("A")
        with self.assertRaisesRegex(ValueError, "not in the basket"):
            self.engine.what_if_remove(["A"], "B")
        with self.assertRaises(ValueError):
            self.engine.recommend(["A"], limit=0)
        with self.assertRaises(ValueError):
            self.engine.search_products("cat", 0)

    def test_lookup_by_id_and_name(self):
        self.assertEqual(self.engine.search_products("TREATS"), [("B", "Cat Treats")])
        self.assertEqual(self.engine.search_products("C"), [("C", "Cat Litter")])  # ID wins
        self.assertEqual(self.engine.search_products("A"), [("A", "Cat Food")])

    def test_comparison_uses_full_sets_by_default(self):
        # Even with a recommendation limit elsewhere, the what-if delta
        # describes changes to the full set, not changes to top-N positions.
        delta = self.engine.compare(["A", "B"], ["A"])
        self.assertEqual(len(delta.before), 2)
        self.assertEqual(len(delta.after), 2)
        self.assertEqual([r.product_id for r in delta.gained], ["B"])


class LoaderTests(unittest.TestCase):
    def test_loader_round_trip_t05_schema(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with (root / "item_frequency.csv").open("w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(["product_id", "product_name", "aisle", "basket_count", "support"])
                writer.writerows([["A", "Cat Food", "cat food care", 10, 1],
                                  ["B", "Cat Treats", "cat food care", 5, .5]])
            from pawpair.rules import export_rules
            export_rules([rule(["A"], ["B"], .5, 5, .5)], {"A": "Cat Food", "B": "Cat Treats"}, root, .3)
            engine = RecommendationEngine.from_directory(root)
            self.assertEqual(engine.catalog, {"A": "Cat Food", "B": "Cat Treats"})
            self.assertEqual(engine.recommend(["A"])[0].product_id, "B")

    def test_malformed_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "item_frequency.csv").write_text("product_id,product_name\nA,Cat Food\nA,Duplicated\n")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                load_catalog(root / "item_frequency.csv")
            (root / "association_rules.csv").write_text(
                'antecedent_ids_json,consequent_ids_json,basket_count,support,confidence,lift\n'
                '"[""A""]","[""A""]",5,0.1,0.7,1.2\n')
            with self.assertRaisesRegex(ValueError, "overlap"):
                load_rules(root / "association_rules.csv")


if __name__ == "__main__":
    unittest.main()
