"""Pure, testable T08 analytics for the Streamlit association graph and A/B comparison.

The graph deliberately includes only single-item -> single-item rules. Turning
{A,B} -> C into A -> C and B -> C would misrepresent the rule's antecedent.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .recommender import Recommendation
from .rules import Rule
from .ui_service import DashboardMining


@dataclass(frozen=True)
class AssociationEdge:
    source_id: str
    target_id: str
    source_name: str
    target_name: str
    basket_count: int
    support: float
    confidence: float
    lift: float


@dataclass(frozen=True)
class ThresholdComparison:
    """Full A/B result sets. A top-N limit must not change gained/lost labels."""

    itemsets_a: int
    itemsets_b: int
    rules_a: int
    rules_b: int
    recommendations_a: tuple[Recommendation, ...]
    recommendations_b: tuple[Recommendation, ...]
    only_a: tuple[Recommendation, ...]
    only_b: tuple[Recommendation, ...]
    shared: tuple[Recommendation, ...]


def association_edges(
    rules: Sequence[Rule],
    catalog: Mapping[str, str],
    aisles: Mapping[str, str],
    *,
    aisle: str = "All",
    min_joint_baskets: int = 6,
    min_lift: float = 1.0,
    max_edges: int = 35,
) -> list[AssociationEdge]:
    """Select strongest genuine A -> B rules for a directed product network.

    Only one-to-one rules are projected to edges; each returned edge therefore
    has exactly the support, confidence, lift and joint count of that rule.
    Ranking prioritizes joint count before confidence to avoid focusing solely
    on rules with high confidence but very little evidence.
    """
    if min_joint_baskets < 1 or max_edges < 1 or min_lift < 0:
        raise ValueError("min_joint_baskets/max_edges must be positive and min_lift nonnegative")
    allowed = {"All", "cat food care", "dog food care"}
    if aisle not in allowed:
        raise ValueError(f"Unknown aisle filter: {aisle}")

    edges: list[AssociationEdge] = []
    for rule in rules:
        if len(rule.antecedent) != 1 or len(rule.consequent) != 1:
            continue
        source, target = rule.antecedent[0], rule.consequent[0]
        if source not in catalog or target not in catalog:
            raise ValueError("Rule references a product not in the catalog")
        if aisle != "All" and not (aisles.get(source) == aisle and aisles.get(target) == aisle):
            continue
        if rule.basket_count < min_joint_baskets or rule.lift < min_lift:
            continue
        edges.append(AssociationEdge(source, target, catalog[source], catalog[target],
                                     rule.basket_count, rule.support, rule.confidence, rule.lift))
    edges.sort(key=lambda e: (-e.basket_count, -e.confidence, -e.lift,
                              e.source_id, e.target_id))
    return edges[:max_edges]


def compare_mining(
    scenario_a: DashboardMining,
    scenario_b: DashboardMining,
    basket: Sequence[str],
) -> ThresholdComparison:
    """Compare the same basket under two independently mined threshold settings."""
    if scenario_a.itemsets.transaction_count != scenario_b.itemsets.transaction_count:
        raise ValueError("Both scenarios must use the same transaction dataset")
    # Recommend *all* eligible products; a top-10 cutoff would create fake differences.
    rec_a = tuple(scenario_a.recommender.recommend(basket, limit=None))
    rec_b = tuple(scenario_b.recommender.recommend(basket, limit=None))
    ids_a = {rec.product_id for rec in rec_a}
    ids_b = {rec.product_id for rec in rec_b}
    return ThresholdComparison(
        len(scenario_a.itemsets.counts), len(scenario_b.itemsets.counts),
        len(scenario_a.rules), len(scenario_b.rules),
        rec_a, rec_b,
        tuple(rec for rec in rec_a if rec.product_id not in ids_b),
        tuple(rec for rec in rec_b if rec.product_id not in ids_a),
        tuple(rec for rec in rec_b if rec.product_id in ids_a),
    )
