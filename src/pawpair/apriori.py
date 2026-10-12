"""Transparent Apriori frequent-itemset mining for PawPair (Ticket T04).

Apriori property: every subset of a frequent itemset must be frequent.
Support always uses *all pet-containing baskets*, including singletons.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LevelStats:
    size: int
    candidates_generated: int
    candidates_pruned: int
    candidates_evaluated: int
    frequent_itemsets: int


@dataclass
class AprioriResult:
    transaction_count: int
    min_support: float
    min_count: int
    counts: dict[tuple[str, ...], int]
    levels: list[LevelStats]

    def support(self, itemset: tuple[str, ...]) -> float:
        return self.counts[itemset] / self.transaction_count


def read_baskets(csv_path: Path) -> list[set[str]]:
    """Read the validated T02/T03 basket file; keep product IDs, not labels."""
    baskets = []
    with csv_path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames or not {"order_id", "product_ids_json"}.issubset(reader.fieldnames):
            raise ValueError("pet_baskets.csv must contain order_id and product_ids_json")
        seen_orders = set()
        for row in reader:
            order_id = row["order_id"].strip()
            if not order_id or order_id in seen_orders:
                raise ValueError(f"Duplicate/invalid basket order_id: {order_id!r}")
            seen_orders.add(order_id)
            ids = json.loads(row["product_ids_json"])
            if (not isinstance(ids, list) or not ids
                    or any(not isinstance(pid, str) or not pid.strip() for pid in ids)):
                raise ValueError(f"Invalid product_ids_json for order {order_id}")
            if len(set(ids)) != len(ids):
                raise ValueError(f"Repeated product_id inside basket {order_id}")
            baskets.append(set(ids))
    if not baskets:
        raise ValueError("No pet-containing baskets; cannot mine itemsets")
    return baskets


def generate_candidates(prev_level: set[tuple[str, ...]], size: int) -> tuple[set[tuple[str, ...]], int, int]:
    """Apriori join and prune: returns candidates, joined count, pruned count."""
    if size < 2:
        raise ValueError("Candidate size must be >=2")
    ordered = sorted(prev_level)
    candidates = set()
    joined = 0
    pruned = 0
    for i, a in enumerate(ordered):
        for b in ordered[i+1:]:
            if a[:size-2] != b[:size-2]:
                continue
            candidate = tuple(sorted(set(a) | set(b)))
            if len(candidate) != size:
                continue
            joined += 1
            if any(subset not in prev_level for subset in itertools.combinations(candidate, size - 1)):
                pruned += 1
                continue
            candidates.add(candidate)
    return candidates, joined, pruned


def apriori(baskets: list[set[str]], min_support: float = 0.002) -> AprioriResult:
    """Find frequent itemsets with direct candidate counts and Apriori pruning.

    This assumes a non-empty list of baskets. Values at exactly the minimum
    support qualify (using an exact minimum *count* threshold).
    """
    if not 0 < min_support <= 1 or not math.isfinite(min_support):
        raise ValueError("min_support must be finite and in (0, 1]")
    if not baskets or any(not basket for basket in baskets):
        raise ValueError("Expected a non-empty collection of non-empty baskets")
    n = len(baskets)
    min_count = max(1, math.ceil(min_support * n - 1e-12))
    all_counts: dict[tuple[str, ...], int] = {}
    stats: list[LevelStats] = []

    singletons = Counter((pid,) for basket in baskets for pid in basket)
    prev = {item: count for item, count in singletons.items() if count >= min_count}
    all_counts.update(prev)
    stats.append(LevelStats(1, len(singletons), 0, len(singletons), len(prev)))

    size = 2
    while prev:
        candidates, joined, pruned = generate_candidates(set(prev), size)
        if not candidates:
            if joined:
                stats.append(LevelStats(size, joined, pruned, 0, 0))
            break
        seen: Counter[tuple[str, ...]] = Counter()
        for basket in baskets:
            if len(basket) < size:
                continue
            # Checking only the observed combinations avoids checking every
            # candidate against every basket, which would be prohibitively slow.
            for combo in itertools.combinations(sorted(basket), size):
                if combo in candidates:
                    seen[combo] += 1
        prev = {item: count for item, count in seen.items() if count >= min_count}
        all_counts.update(prev)
        stats.append(LevelStats(size, joined, pruned, len(candidates), len(prev)))
        size += 1
    return AprioriResult(n, min_support, min_count, all_counts, stats)


def export_itemsets(result: AprioriResult, item_names: dict[str, str], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = sorted(result.counts.items(), key=lambda row: (len(row[0]), -row[1], row[0]))
    with (output_dir / "frequent_itemsets.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["itemset_size", "product_ids_json", "product_names_json", "basket_count", "support"])
        for itemset, count in rows:
            writer.writerow([len(itemset), json.dumps(itemset),
                             json.dumps([item_names.get(pid, pid) for pid in itemset], ensure_ascii=False),
                             count, count / result.transaction_count])
    (output_dir / "apriori_summary.json").write_text(json.dumps({
        "transaction_count": result.transaction_count,
        "min_support": result.min_support,
        "min_count": result.min_count,
        "total_frequent_itemsets": len(result.counts),
        "levels": [vars(level) for level in result.levels],
        "interpretation": "Support is conditional on transactions containing >=1 selected pet-care product.",
    }, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Apriori frequent itemsets for PawPair")
    parser.add_argument("--data-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--min-support", type=float, default=0.002)
    args = parser.parse_args()
    baskets = read_baskets(args.data_dir / "pet_baskets.csv")
    with (args.data_dir / "item_frequency.csv").open(newline="", encoding="utf-8") as fh:
        names = {row["product_id"]: row["product_name"] for row in csv.DictReader(fh)}
    result = apriori(baskets, args.min_support)
    export_itemsets(result, names, args.data_dir)
    print(json.dumps({
        "transactions": result.transaction_count,
        "minimum_support": result.min_support,
        "minimum_basket_count": result.min_count,
        "frequent_itemsets": len(result.counts),
        "levels": [vars(level) for level in result.levels],
    }, indent=2))


if __name__ == "__main__":
    main()
