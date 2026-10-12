"""Directional association-rule generation (PawPair T05).

For A -> B:
  support = count(A union B) / transaction_count
  confidence = count(A union B) / count(A)
  lift = confidence / (count(B) / transaction_count)
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
from dataclasses import dataclass
from pathlib import Path

from .apriori import AprioriResult, apriori, read_baskets


@dataclass(frozen=True)
class Rule:
    antecedent: tuple[str, ...]
    consequent: tuple[str, ...]
    basket_count: int
    support: float
    confidence: float
    lift: float


def generate_rules(result: AprioriResult, min_confidence: float = 0.30) -> list[Rule]:
    if not 0 < min_confidence <= 1 or not math.isfinite(min_confidence):
        raise ValueError("min_confidence must be finite and in (0, 1]")
    rules: list[Rule] = []
    for itemset, count in result.counts.items():
        if len(itemset) < 2:
            continue
        for lhs_size in range(1, len(itemset)):
            for lhs in itertools.combinations(itemset, lhs_size):
                lhs_set = set(lhs)
                rhs = tuple(pid for pid in itemset if pid not in lhs_set)
                conf = count / result.counts[lhs]
                if conf + 1e-12 < min_confidence:
                    continue
                rhs_support = result.counts[rhs] / result.transaction_count
                rules.append(Rule(lhs, rhs, count, count / result.transaction_count,
                                  conf, conf / rhs_support))
    return sorted(rules, key=lambda r: (-r.confidence, -r.basket_count, r.antecedent, r.consequent))


def export_rules(rules: list[Rule], names: dict[str, str], output_dir: Path, min_confidence: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "association_rules.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["antecedent_ids_json", "consequent_ids_json", "antecedent_names_json",
                         "consequent_names_json", "basket_count", "support", "confidence", "lift"])
        for rule in rules:
            writer.writerow([json.dumps(rule.antecedent), json.dumps(rule.consequent),
                             json.dumps([names.get(pid, pid) for pid in rule.antecedent], ensure_ascii=False),
                             json.dumps([names.get(pid, pid) for pid in rule.consequent], ensure_ascii=False),
                             rule.basket_count, rule.support, rule.confidence, rule.lift])
    (output_dir / "rules_summary.json").write_text(json.dumps({
        "min_confidence": min_confidence,
        "total_rules": len(rules),
        "note": "Directional rules; confidence(A→B) can differ from confidence(B→A). Lift is descriptive, not causal.",
    }, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate PawPair association rules")
    parser.add_argument("--data-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--min-support", type=float, default=0.002)
    parser.add_argument("--min-confidence", type=float, default=0.30)
    args = parser.parse_args()
    baskets = read_baskets(args.data_dir / "pet_baskets.csv")
    result = apriori(baskets, args.min_support)
    with (args.data_dir / "item_frequency.csv").open(newline="", encoding="utf-8") as fh:
        names = {row["product_id"]: row["product_name"] for row in csv.DictReader(fh)}
    from .apriori import export_itemsets
    export_itemsets(result, names, args.data_dir)
    rules = generate_rules(result, args.min_confidence)
    export_rules(rules, names, args.data_dir, args.min_confidence)
    print(json.dumps({
        "transactions": result.transaction_count,
        "min_support": args.min_support,
        "min_confidence": args.min_confidence,
        "min_basket_count": result.min_count,
        "frequent_itemsets": len(result.counts),
        "association_rules": len(rules),
        "top_rules": [{"if": [names.get(p, p) for p in rule.antecedent],
                       "then": [names.get(p, p) for p in rule.consequent],
                       "joint_baskets": rule.basket_count,
                       "confidence": round(rule.confidence, 4)}
                      for rule in rules[:5]],
    }, indent=2))


if __name__ == "__main__":
    main()
