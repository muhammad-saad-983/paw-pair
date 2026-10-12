"""Profile Instacart's pet-care transaction subset for PawPair (Ticket T02).

Uses only Python's standard library. No association rules are generated here.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path

DEFAULT_AISLES = ("cat food care", "dog food care")
TRAIN_NAMES = ("order_products__train.csv", "order_products_train.csv")


def clean_label(label: str) -> str:
    return " ".join(label.casefold().split())


def csv_rows(path: Path, required: set[str]):
    with path.open("r", newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError(f"Empty CSV: {path}")
        missing = required - set(reader.fieldnames)
        if missing:
            raise ValueError(f"{path.name}: missing columns: {', '.join(sorted(missing))}")
        yield from reader


def select_existing(data_dir: Path, choices: tuple[str, ...]) -> Path:
    for filename in choices:
        candidate = data_dir / filename
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"Expected one of {', '.join(choices)} in {data_dir}. "
        "Download original Instacart CSVs first (see README)."
    )


def load_catalog(data_dir: Path, selected_aisles: tuple[str, ...]):
    aisle_rows = csv_rows(data_dir / "aisles.csv", {"aisle_id", "aisle"})
    aisle_names = {}
    for row in aisle_rows:
        aid = row["aisle_id"].strip()
        if aid in aisle_names:
            raise ValueError(f"Repeated aisle_id: {aid}")
        aisle_names[aid] = row["aisle"].strip()

    selected_normalized = {clean_label(a) for a in selected_aisles}
    found = {clean_label(a) for a in aisle_names.values()} & selected_normalized
    if found != selected_normalized:
        raise ValueError(
            f"Missing aisles: {sorted(selected_normalized - found)}. "
            "Confirm the dataset source and aisle names."
        )

    pet_products = {}
    catalog_size = 0
    for row in csv_rows(data_dir / "products.csv", {"product_id", "product_name", "aisle_id"}):
        pid, name = row["product_id"].strip(), row["product_name"].strip()
        if not pid or not name:
            continue
        if clean_label(aisle_names.get(row["aisle_id"].strip(), "")) not in selected_normalized:
            continue
        catalog_size += 1
        if pid in pet_products:
            raise ValueError(f"Repeated pet product_id: {pid}")
        pet_products[pid] = {"name": name, "aisle": aisle_names[row["aisle_id"].strip()]}
    return pet_products, catalog_size


def resolve_order_files(data_dir: Path, include_prior: bool) -> list[Path]:
    paths = [select_existing(data_dir, TRAIN_NAMES)]
    if include_prior:
        paths.append(select_existing(data_dir, ("order_products__prior.csv", "order_products_prior.csv")))
    return paths


def profile(data_dir: Path, output_dir: Path, include_prior: bool = False,
            selected_aisles: tuple[str, ...] = DEFAULT_AISLES) -> dict:
    pet_catalog, catalog_count = load_catalog(data_dir, selected_aisles)
    order_files = resolve_order_files(data_dir, include_prior)
    baskets: dict[str, set[str]] = defaultdict(set)
    counters = Counter()
    for order_path in order_files:
        for row in csv_rows(order_path, {"order_id", "product_id"}):
            counters["order_product_rows_read"] += 1
            order_id, product_id = row["order_id"].strip(), row["product_id"].strip()
            if not order_id or not product_id:
                counters["rows_missing_order_or_product_id"] += 1
                continue
            if product_id not in pet_catalog:
                counters["rows_not_in_pet_aisles"] += 1
                continue
            if product_id in baskets[order_id]:
                counters["duplicate_pet_product_rows"] += 1
                continue
            baskets[order_id].add(product_id)
            counters["valid_pet_item_rows"] += 1

    item_frequency = Counter()
    pair_frequency = Counter()
    basket_size_distribution = Counter()
    for items in baskets.values():
        basket_size_distribution[len(items)] += 1
        item_frequency.update(items)
        pair_frequency.update(itertools.combinations(sorted(items), 2))

    n = len(baskets)
    summary = {
        "source": "The Instacart Online Grocery Shopping Dataset 2017",
        "subset_definition": "All distinct pet-aisle products within orders that contain >=1 pet-aisle product",
        "support_denominator": "Number of pet-containing orders, including single-pet-item orders",
        "selected_aisles": list(selected_aisles),
        "input_files": [p.name for p in order_files],
        "pet_products_in_catalog": catalog_count,
        "pet_products_observed": len(item_frequency),
        "pet_containing_orders": n,
        "multi_pet_item_orders": sum(count for size, count in basket_size_distribution.items() if size >= 2),
        "multi_pet_item_order_fraction": round(sum(count for size, count in basket_size_distribution.items() if size >= 2) / n, 6) if n else 0,
        "basket_size_distribution": {str(k): v for k, v in sorted(basket_size_distribution.items())},
        "pair_types_observed": len(pair_frequency),
        "pair_types_appearing_at_least_2_times": sum(c >= 2 for c in pair_frequency.values()),
        "pair_types_appearing_at_least_5_times": sum(c >= 5 for c in pair_frequency.values()),
        "pair_types_appearing_at_least_10_times": sum(c >= 10 for c in pair_frequency.values()),
        "counters": dict(counters),
        "most_frequent_pet_products": [
            {"product_id": pid, "product_name": pet_catalog[pid]["name"],
             "aisle": pet_catalog[pid]["aisle"], "basket_count": count,
             "support": round(count / n, 8) if n else 0}
            for pid, count in item_frequency.most_common(20)
        ],
        "most_frequent_pet_pairs": [
            {"product_ids": list(pair), "product_names": [pet_catalog[x]["name"] for x in pair],
             "basket_count": count, "support": round(count / n, 8) if n else 0}
            for pair, count in pair_frequency.most_common(20)
        ],
        "caveat": "Only pet-aisle products are retained. These are pet-focused baskets derived from multi-category grocery orders, not transactions from a specialist pet retailer.",
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "pet_baskets.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["order_id", "product_ids_json", "product_names_json", "basket_size"])
        for order_id, item_ids in sorted(baskets.items(), key=lambda x: x[0]):
            ids = sorted(item_ids)
            writer.writerow([order_id, json.dumps(ids),
                             json.dumps([pet_catalog[pid]["name"] for pid in ids], ensure_ascii=False), len(ids)])

    with (output_dir / "item_frequency.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["product_id", "product_name", "aisle", "basket_count", "support"])
        for pid, count in item_frequency.most_common():
            writer.writerow([pid, pet_catalog[pid]["name"], pet_catalog[pid]["aisle"],
                             count, count / n if n else 0])

    (output_dir / "dataset_profile.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Prepare and profile PawPair Instacart pet baskets")
    parser.add_argument("--data-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--include-prior", action="store_true", help="Add prior order data for more coverage")
    args = parser.parse_args()
    report = profile(args.data_dir, args.output_dir, args.include_prior)
    print(json.dumps({k: report[k] for k in (
        "input_files", "pet_products_in_catalog", "pet_products_observed", "pet_containing_orders",
        "multi_pet_item_orders", "multi_pet_item_order_fraction", "pair_types_observed",
        "pair_types_appearing_at_least_5_times")}, indent=2))
    print(f"Detailed outputs saved to: {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
