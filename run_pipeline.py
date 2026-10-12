"""Run T02-T05 in one command: python run_pipeline.py

Requires `data/raw/{aisles.csv,products.csv,order_products__train.csv}`.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT / 'src'))

from pawpair.profile import profile
from pawpair.apriori import apriori, read_baskets, export_itemsets
from pawpair.rules import generate_rules, export_rules


def main() -> None:
    parser = argparse.ArgumentParser(description="PawPair data -> Apriori -> rules")
    parser.add_argument("--min-support", type=float, default=.002)
    parser.add_argument("--min-confidence", type=float, default=.30)
    parser.add_argument("--include-prior", action="store_true")
    args = parser.parse_args()
    raw = PROJECT / "data/raw"
    processed = PROJECT / "data/processed"
    report = profile(raw, processed, include_prior=args.include_prior)
    baskets = read_baskets(processed / "pet_baskets.csv")
    result = apriori(baskets, args.min_support)
    with (processed / "item_frequency.csv").open(newline="", encoding="utf-8") as fp:
        names = {r["product_id"]:r["product_name"] for r in csv.DictReader(fp)}
    export_itemsets(result, names, processed)
    rules = generate_rules(result, args.min_confidence)
    export_rules(rules, names, processed, args.min_confidence)
    print(json.dumps({
        "pet_containing_orders": report["pet_containing_orders"],
        "multi_pet_item_orders": report["multi_pet_item_orders"],
        "pet_products_observed": report["pet_products_observed"],
        "min_support": args.min_support,
        "min_confidence": args.min_confidence,
        "minimum_order_count": result.min_count,
        "frequent_itemsets": len(result.counts),
        "association_rules": len(rules),
        "results_directory": str(processed),
    }, indent=2))


if __name__ == "__main__":
    main()
