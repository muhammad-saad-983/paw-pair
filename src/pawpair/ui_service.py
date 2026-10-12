"""Read-only dashboard adapters for PawPair's existing T02–T06 backend.

This module contains no Streamlit imports, so view-model and filtering logic
can be unit-tested without the UI runtime.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .apriori import AprioriResult, apriori, read_baskets
from .recommender import RecommendationEngine, load_catalog
from .rules import Rule, generate_rules


REQUIRED_FILES = ("dataset_profile.json", "pet_baskets.csv", "item_frequency.csv")


@dataclass(frozen=True)
class DashboardData:
    profile: dict[str, Any]
    baskets: tuple[frozenset[str], ...]
    catalog: dict[str, str]
    item_frequencies: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class DashboardMining:
    itemsets: AprioriResult
    rules: tuple[Rule, ...]
    recommender: RecommendationEngine


def data_signature(directory: Path) -> tuple[tuple[str, int, int], ...]:
    """Cache key: changing processed input files invalidates derived UI results."""
    missing = [name for name in REQUIRED_FILES if not (directory / name).is_file()]
    if missing:
        raise FileNotFoundError(
            f"Missing {', '.join(missing)} in {directory}. "
            "Run `python run_pipeline.py` from the repository root first."
        )
    return tuple((name, (directory / name).stat().st_mtime_ns,
                  (directory / name).stat().st_size) for name in REQUIRED_FILES)


def load_dashboard_data(directory: Path) -> DashboardData:
    data_signature(directory)
    profile = json.loads((directory / "dataset_profile.json").read_text(encoding="utf-8"))
    baskets = tuple(frozenset(items) for items in read_baskets(directory / "pet_baskets.csv"))
    catalog = load_catalog(directory / "item_frequency.csv")

    with (directory / "item_frequency.csv").open(newline="", encoding="utf-8-sig") as fp:
        reader = csv.DictReader(fp)
        required = {"product_id", "product_name", "basket_count", "support"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("item_frequency.csv lacks required columns")
        frequencies = tuple({
            "product_id": row["product_id"],
            "product_name": row["product_name"],
            "aisle": row.get("aisle", ""),
            "basket_count": int(row["basket_count"]),
            "support": float(row["support"]),
        } for row in reader)

    if int(profile["pet_containing_orders"]) != len(baskets):
        raise ValueError("Profile transaction count differs from pet_baskets.csv; rerun the pipeline")
    if set(catalog) != {r["product_id"] for r in frequencies}:
        raise ValueError("Item frequency table does not match product catalog")
    if any(not 0 < row["support"] <= 1 or row["basket_count"] < 1
           for row in frequencies):
        raise ValueError("Invalid product frequency values")
    if any(not basket.issubset(catalog) for basket in baskets):
        raise ValueError("Basket references product absent from catalog")
    return DashboardData(profile, baskets, catalog, frequencies)


def build_dashboard_mining(data: DashboardData, min_support: float,
                           min_confidence: float) -> DashboardMining:
    """Recompute on slider changes without overwriting persisted CSVs."""
    result = apriori([set(basket) for basket in data.baskets], min_support)
    rules = tuple(generate_rules(result, min_confidence))
    return DashboardMining(result, rules, RecommendationEngine(rules, data.catalog))


def frequent_itemset_rows(mined: DashboardMining, catalog: dict[str, str],
                          size: int | None = None) -> list[dict[str, Any]]:
    output = []
    for itemset, count in mined.itemsets.counts.items():
        if size is not None and len(itemset) != size:
            continue
        output.append({
            "Size": len(itemset),
            "Products": ", ".join(catalog.get(pid, pid) for pid in itemset),
            "Product IDs": ", ".join(itemset),
            "Joint baskets": count,
            "Support": count / mined.itemsets.transaction_count,
        })
    return sorted(output, key=lambda r: (r["Size"], -r["Joint baskets"], r["Product IDs"]))


def filter_rules(rules: tuple[Rule, ...], catalog: dict[str, str],
                 query: str = "", side: Literal["Either side", "Antecedent", "Consequent"] = "Either side",
                 sort_by: Literal["Confidence", "Support", "Lift"] = "Confidence") -> list[dict[str, Any]]:
    """Search item names or exact product IDs on either/both rule sides."""
    if side not in {"Either side", "Antecedent", "Consequent"}:
        raise ValueError("Unrecognized rule search side")
    if sort_by not in {"Confidence", "Support", "Lift"}:
        raise ValueError("Unrecognized sort criterion")
    term = query.strip().casefold()
    output = []
    for rule in rules:
        match_ids = (rule.antecedent if side == "Antecedent" else
                     rule.consequent if side == "Consequent" else
                     rule.antecedent + rule.consequent)
        if term and not any(term in catalog[pid].casefold() or term == pid.casefold()
                            for pid in match_ids):
            continue
        output.append({
            "Antecedent": ", ".join(catalog[pid] for pid in rule.antecedent),
            "Consequent": ", ".join(catalog[pid] for pid in rule.consequent),
            "Joint baskets": rule.basket_count,
            "Support": rule.support,
            "Confidence": rule.confidence,
            "Lift": rule.lift,
            "_tie": (rule.antecedent, rule.consequent),
        })
    metrics = {"Confidence": "Confidence", "Support": "Support", "Lift": "Lift"}
    primary = metrics[sort_by]
    output.sort(key=lambda r: (-r[primary], -r["Joint baskets"], r["_tie"]))
    for row in output:
        del row["_tie"]
    return output


def confidence_buckets(rules: tuple[Rule, ...]) -> list[dict[str, Any]]:
    """Ten fixed-width confidence groups (last bucket includes 100%)."""
    counts = [0] * 10
    for rule in rules:
        counts[min(int(rule.confidence * 10), 9)] += 1
    return [{"Confidence range": f"{i*10}–{(i+1)*10}%", "Rules": n}
            for i, n in enumerate(counts)]
