import unittest
from pathlib import Path
from sys import path as sys_path

sys_path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pawpair.apriori import apriori
from pawpair.rules import generate_rules


class RuleTests(unittest.TestCase):
    def setUp(self):
        self.baskets = [set("AB"), set("AB"), set("AB"), set("A"), set("B"), set("BC")]

    def test_directional_confidence(self):
        result = apriori(self.baskets, 0.3)
        rules = generate_rules(result, 0.5)
        a_b = next(r for r in rules if r.antecedent == ("A",) and r.consequent == ("B",))
        b_a = next(r for r in rules if r.antecedent == ("B",) and r.consequent == ("A",))
        self.assertAlmostEqual(a_b.confidence, 3/4)
        self.assertAlmostEqual(b_a.confidence, 3/5)
        self.assertAlmostEqual(a_b.support, 3/6)
        self.assertAlmostEqual(a_b.lift, (3/4) / (5/6))

    def test_rule_respects_min_confidence(self):
        result = apriori(self.baskets, 0.3)
        rules = generate_rules(result, 0.7)
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0].antecedent, ("A",))

    def test_invalid_confidence(self):
        for threshold in [0, 2, float("nan")]:
            with self.assertRaises(ValueError):
                generate_rules(apriori(self.baskets, .2), threshold)


if __name__ == "__main__":
    unittest.main()
