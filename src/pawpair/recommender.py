"""Rule-backed recommendations and mutable smart baskets (PawPair ticket T06).

Only SINGLE-CONSEQUENT rules are used to recommend an individual product.
A multi-product consequent is not split into independent one-product rules,
because its confidence/support describe the whole consequent, not each part.

Ranking is deterministic and conservative: the best applicable rule per item
is ranked by confidence, basket count (equivalent to support for a fixed
transaction set), lift, then number of antecedent items; product ID breaks ties.
Other applicable rules are presented as evidence but their confidence values
are NEVER summed or treated as independent probabilities.
"""
from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from .rules import Rule


@dataclass(frozen=True)
class Evidence:
    """One matching rule and an explanation for its observed co-purchase pattern."""

    rule: Rule
    explanation: str


@dataclass(frozen=True)
class Recommendation:
    product_id: str
    product_name: str
    evidence: tuple[Evidence, ...]  # best rule first; ALL applicable rules retained

    @property
    def best_rule(self) -> Rule:
        return self.evidence[0].rule

    @property
    def explanation(self) -> str:
        return self.evidence[0].explanation

    @property
    def supporting_rule_count(self) -> int:
        return len(self.evidence)


@dataclass(frozen=True)
class BasketComparison:
    before_basket: tuple[str, ...]
    after_basket: tuple[str, ...]
    before: tuple[Recommendation, ...]
    after: tuple[Recommendation, ...]
    gained: tuple[Recommendation, ...]  # appears after but not before
    lost: tuple[Recommendation, ...]  # disappears after
    retained: tuple[Recommendation, ...]


def load_catalog(path: Path) -> dict[str, str]:
    """Load observed pet products as product_id -> product_name."""
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not {"product_id", "product_name"}.issubset(reader.fieldnames):
            raise ValueError("item_frequency.csv requires product_id and product_name")
        catalog: dict[str, str] = {}
        for row in reader:
            pid, name = row["product_id"].strip(), row["product_name"].strip()
            if not pid or not name or pid in catalog:
                raise ValueError(f"Invalid or duplicate product in catalog: {pid!r}")
            catalog[pid] = name
    if not catalog:
        raise ValueError("No observed pet products in catalog")
    return catalog


def load_rules(path: Path) -> list[Rule]:
    """Read the exact CSV schema written by T05's export_rules()."""
    required = {"antecedent_ids_json", "consequent_ids_json", "basket_count", "support", "confidence", "lift"}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"association_rules.csv is missing: {sorted(required - set(reader.fieldnames or []))}")
        rules: list[Rule] = []
        seen: set[tuple[tuple[str, ...], tuple[str, ...]]] = set()
        for line, row in enumerate(reader, start=2):
            try:
                lhs = json.loads(row["antecedent_ids_json"])
                rhs = json.loads(row["consequent_ids_json"])
                if any(not isinstance(ids, list) or not ids or
                       any(not isinstance(pid, str) or not pid.strip() for pid in ids) or
                       len(ids) != len(set(ids)) for ids in (lhs, rhs)):
                    raise ValueError("invalid item list")
                if set(lhs) & set(rhs):
                    raise ValueError("LHS and RHS overlap")
                key = (tuple(sorted(lhs)), tuple(sorted(rhs)))
                if key in seen:
                    raise ValueError("duplicate rule")
                seen.add(key)
                count = int(row["basket_count"])
                support = float(row["support"])
                confidence = float(row["confidence"])
                lift = float(row["lift"])
                if not (count > 0 and math.isfinite(support) and 0 < support <= 1
                        and math.isfinite(confidence) and 0 < confidence <= 1
                        and math.isfinite(lift) and lift > 0):
                    raise ValueError("invalid rule metrics")
                rules.append(Rule(key[0], key[1], count, support, confidence, lift))
            except (TypeError, KeyError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError(f"Malformed rule on CSV line {line}: {exc}") from exc
    return rules


def _rank(rule: Rule) -> tuple[float, int, float, int]:
    return (rule.confidence, rule.basket_count, rule.lift, len(rule.antecedent))


class RecommendationEngine:
    """Stateless recommendations; ideal for Streamlit reruns in T07.

    Product ID is the identity; labels are displayed only. Unmatched baskets
    return an empty list rather than fabricated fallback recommendations.
    """

    def __init__(self, rules: Iterable[Rule], catalog: Mapping[str, str]):
        self.catalog = dict(catalog)
        self.rules = tuple(rules)
        for rule in self.rules:
            if not set(rule.antecedent + rule.consequent).issubset(self.catalog):
                raise ValueError(f"Rule references missing product ID: {rule}")
        self.single_item_rules = tuple(rule for rule in self.rules if len(rule.consequent) == 1)

    @classmethod
    def from_directory(cls, directory: Path) -> "RecommendationEngine":
        return cls(load_rules(directory / "association_rules.csv"),
                   load_catalog(directory / "item_frequency.csv"))

    def validate_items(self, items: Iterable[str]) -> frozenset[str]:
        if isinstance(items, str):
            raise TypeError("Pass product IDs as a sequence, not a single string")
        selected = frozenset(items)
        unknown = selected.difference(self.catalog)
        if unknown:
            raise ValueError(f"Unknown product ID(s): {', '.join(sorted(unknown))}")
        return selected

    def search_products(self, query: str, limit: int = 20) -> list[tuple[str, str]]:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        term = query.strip().casefold()
        # An exact product ID wins over potentially broad name matches.
        if query.strip() in self.catalog:
            pid = query.strip()
            return [(pid, self.catalog[pid])]
        return [(pid, name) for pid, name in self.catalog.items()
                if term in name.casefold()][:limit]

    def recommend(self, basket: Iterable[str], limit: int | None = 10) -> list[Recommendation]:
        """Recommend products not already selected, using matching A -> {B} rules.

        A rule matches when its FULL antecedent is a subset of the basket.
        Multi-item baskets can match simpler rules as well; all matching rules
        are shown, not treated as independent observations.
        """
        selected = self.validate_items(basket)
        if limit is not None and limit < 1:
            raise ValueError("limit must be >= 1 or None")
        grouped: dict[str, list[Rule]] = {}
        for rule in self.single_item_rules:
            pid = rule.consequent[0]
            if pid not in selected and set(rule.antecedent).issubset(selected):
                grouped.setdefault(pid, []).append(rule)

        recommendations = []
        for pid, evidence_rules in grouped.items():
            evidence_rules.sort(key=lambda r: tuple(-v for v in _rank(r)) + (r.antecedent,))
            evidence = tuple(Evidence(rule, self._explain(rule)) for rule in evidence_rules)
            recommendations.append(Recommendation(pid, self.catalog[pid], evidence))
        recommendations.sort(key=lambda rec:
                             tuple(-v for v in _rank(rec.best_rule)) + (rec.product_id,))
        return recommendations[:limit] if limit is not None else recommendations

    def _explain(self, rule: Rule) -> str:
        lhs = ", ".join(self.catalog[pid] for pid in rule.antecedent)
        rhs = self.catalog[rule.consequent[0]]
        return (f"In this dataset, orders containing [{lhs}] also contained "
                f"[{rhs}] in {rule.basket_count} baskets "
                f"(support {rule.support:.2%}, confidence {rule.confidence:.1%}, "
                f"lift {rule.lift:.2f}).")

    def compare(self, before_basket: Iterable[str], after_basket: Iterable[str],
                limit: int | None = None) -> BasketComparison:
        """Compare full recommendation sets by default, avoiding top-N artifacts."""
        before_ids = self.validate_items(before_basket)
        after_ids = self.validate_items(after_basket)
        before = tuple(self.recommend(before_ids, limit=limit))
        after = tuple(self.recommend(after_ids, limit=limit))
        old = {rec.product_id for rec in before}
        new = {rec.product_id for rec in after}
        return BasketComparison(
            tuple(sorted(before_ids)), tuple(sorted(after_ids)), before, after,
            tuple(rec for rec in after if rec.product_id not in old),
            tuple(rec for rec in before if rec.product_id not in new),
            tuple(rec for rec in after if rec.product_id in old),
        )

    def what_if_remove(self, basket: Iterable[str], product_id: str) -> BasketComparison:
        selected = self.validate_items(basket)
        if product_id not in selected:
            raise ValueError(f"Product {product_id} is not in the basket")
        return self.compare(selected, selected - {product_id})

    def make_basket(self, items: Iterable[str] = ()) -> "SmartBasket":
        return SmartBasket(self, set(self.validate_items(items)))


class SmartBasket:
    """Mutable basket for CLI/apps; recs always recomputed from current items."""

    def __init__(self, engine: RecommendationEngine, items: set[str]):
        self.engine = engine
        self._items = set(engine.validate_items(items))

    @property
    def items(self) -> tuple[str, ...]:
        return tuple(sorted(self._items))

    def add(self, product_id: str) -> None:
        self.engine.validate_items([product_id])
        self._items.add(product_id)

    def remove(self, product_id: str) -> None:
        if product_id not in self._items:
            raise ValueError(f"Product {product_id} is not in the basket")
        self._items.remove(product_id)

    def recommendations(self, limit: int | None = 10) -> list[Recommendation]:
        return self.engine.recommend(self._items, limit)

    def preview_remove(self, product_id: str) -> BasketComparison:
        """Show what would change, without mutating the actual basket."""
        return self.engine.what_if_remove(self._items, product_id)
