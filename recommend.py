"""Explore T06 recommendations: python recommend.py --help."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from pawpair.recommender import RecommendationEngine, Recommendation


def show_recommendations(results: list[Recommendation], max_evidence: int) -> None:
    if not results:
        print("No rule-backed recommendations for this basket at the mined thresholds.")
        return
    for position, rec in enumerate(results, 1):
        print(f"{position}. {rec.product_name} [ID: {rec.product_id}]")
        print(f"   Why: {rec.explanation}")
        if len(rec.evidence) > 1:
            print(f"   {len(rec.evidence)} matching rules support this item; "
                  f"showing up to {max_evidence}.")
            for evidence in rec.evidence[1:max_evidence]:
                print(f"   Also: {evidence.explanation}")


def main() -> None:
    parser = argparse.ArgumentParser(description="PawPair T06 rule-backed basket recommendations")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data" / "processed")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--search", metavar="TEXT", help="Find product IDs by name")
    group.add_argument("--basket", nargs="+", metavar="PRODUCT_ID", help="Basket item IDs")
    parser.add_argument("--remove", metavar="PRODUCT_ID", help="Preview removing this basket item")
    parser.add_argument("--limit", type=int, default=5, help="Max recommendations to print")
    parser.add_argument("--evidence", type=int, default=3, help="Max supporting rules shown per item")
    args = parser.parse_args()
    if args.limit < 1 or args.evidence < 1:
        parser.error("--limit and --evidence must be positive")
    if args.search is not None and args.remove:
        parser.error("--remove only works with --basket")
    try:
        engine = RecommendationEngine.from_directory(args.data_dir)
        if args.search is not None:
            results = engine.search_products(args.search, args.limit)
            for pid, name in results:
                print(f"{pid}\t{name}")
            if not results:
                print("No matching products found.")
            return
        basket = engine.make_basket(args.basket)
        print("Selected:", ", ".join(f"{engine.catalog[i]} [{i}]" for i in basket.items))
        print("\nRecommendations:")
        show_recommendations(basket.recommendations(args.limit), args.evidence)
        if args.remove:
            delta = basket.preview_remove(args.remove)
            print(f"\nWhat-if: remove {engine.catalog[args.remove]} [{args.remove}]")
            print("After removal:")
            show_recommendations(list(delta.after)[:args.limit], args.evidence)
            print("Gained:", [x.product_name for x in delta.gained])
            print("Lost:", [x.product_name for x in delta.lost])
            print("Actual basket unchanged:", basket.items)
    except (ValueError, TypeError, OSError) as exc:
        parser.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
