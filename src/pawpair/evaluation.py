"""T09 reproducible descriptive evaluation of existing PawPair association rules.

Uses the same pet-containing baskets for mining and in-sample diagnostics.
These counts are NOT estimates of held-out recommendation accuracy.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from .rules import Rule
from .ui_service import DashboardData, DashboardMining, build_dashboard_mining


CATEGORIES = frozenset({"Useful", "Obvious / Trivial", "Unexpected", "Weak / Uncertain"})
DEFAULT_SCENARIOS = (
    (0.0015, 0.30),
    (0.0020, 0.30),
    (0.0030, 0.30),
    (0.0050, 0.30),
    (0.0020, 0.50),
    (0.0020, 0.70),
    (0.0030, 0.50),
)
# Both cat and dog examples; include a two-item antecedent example.
DEFAULT_EXAMPLES = (
    ("Dog wet-food pairing", ("15190",)),
    ("Dog stew pairing", ("28331",)),
    ("Dog grain-free pairing", ("25088",)),
    ("Cat seafood pairing", ("24508",)),
    ("Cat grain-free pairing", ("28134",)),
    ("Cat two-item basket", ("24508", "5938")),
    ("Cat alternative formula pairing", ("10863", "28134")),
)


@dataclass(frozen=True)
class ScenarioMetrics:
    min_support: float
    min_confidence: float
    minimum_joint_baskets: int
    frequent_itemsets: int
    association_rules: int
    one_to_one_rules: int
    eligible_baskets: int
    total_baskets: int
    descriptive_coverage: float


@dataclass(frozen=True)
class ReviewedRule:
    antecedent: tuple[str, ...]
    consequent: tuple[str, ...]
    basket_count: int
    support: float
    confidence: float
    lift: float
    category: str
    rationale: str


def _canonical(ids: object, field: str) -> tuple[str, ...]:
    if not isinstance(ids, list) or not ids or not all(isinstance(x, str) and x.strip() for x in ids):
        raise ValueError(f"{field} must be a non-empty JSON list of product IDs")
    if len(set(ids)) != len(ids):
        raise ValueError(f"{field} has duplicate product IDs")
    return tuple(sorted(ids))


def load_manual_reviews(path: Path, rules: Sequence[Rule], *, minimum: int = 10) -> list[ReviewedRule]:
    """Validate manually authored labels against actually mined directional rules."""
    index = {(tuple(sorted(r.antecedent)), tuple(sorted(r.consequent))): r for r in rules}
    reviews: list[ReviewedRule] = []
    seen: set[tuple[tuple[str, ...], tuple[str, ...]]] = set()
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"antecedent_ids_json", "consequent_ids_json", "classification", "rationale"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"Review CSV requires columns: {', '.join(sorted(required))}")
        for row_no, row in enumerate(reader, 2):
            try:
                lhs = _canonical(json.loads(row["antecedent_ids_json"]), "antecedent")
                rhs = _canonical(json.loads(row["consequent_ids_json"]), "consequent")
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                raise ValueError(f"Invalid rule IDs in review CSV row {row_no}: {exc}") from exc
            key = (lhs, rhs)
            category = row["classification"].strip()
            rationale = row["rationale"].strip()
            if key in seen:
                raise ValueError(f"Duplicate rule in review CSV row {row_no}")
            if category not in CATEGORIES:
                raise ValueError(f"Invalid classification in row {row_no}: {category!r}")
            if len(rationale) < 20:
                raise ValueError(f"Rationale too short in review CSV row {row_no}")
            if key not in index:
                raise ValueError(f"Reviewed rule in row {row_no} not found at baseline thresholds: {key}")
            seen.add(key)
            rule = index[key]
            reviews.append(ReviewedRule(lhs, rhs, rule.basket_count, rule.support,
                                        rule.confidence, rule.lift, category, rationale))
    if len(reviews) < minimum:
        raise ValueError(f"At least {minimum} distinct real rule reviews required (found {len(reviews)})")
    return reviews


def evaluate_scenarios(data: DashboardData,
                       scenarios: Iterable[tuple[float, float]] = DEFAULT_SCENARIOS) -> list[ScenarioMetrics]:
    """Compare thresholds using SAME transactions; count in-sample basket coverage.

    Coverage means the percentage of observed complete baskets from which
    a rule suggests at least one item *not already present*; it does NOT
    measure relevance, correctness, recall, or held-out accuracy.
    """
    output: list[ScenarioMetrics] = []
    for support, confidence in scenarios:
        mined = build_dashboard_mining(data, support, confidence)
        # avoid recalculating identical baskets more than once
        unique_baskets = Counter(data.baskets)
        eligible = sum(freq for basket, freq in unique_baskets.items()
                       if mined.recommender.recommend(basket, limit=1))
        count = len(data.baskets)
        output.append(ScenarioMetrics(
            support, confidence, mined.itemsets.min_count, len(mined.itemsets.counts),
            len(mined.rules),
            sum(len(r.antecedent) == 1 and len(r.consequent) == 1 for r in mined.rules),
            eligible, count, eligible / count if count else 0.0,
        ))
    return output


def recommendation_examples(mined: DashboardMining,
                            catalog: Mapping[str, str],
                            cases: Iterable[tuple[str, Sequence[str]]] = DEFAULT_EXAMPLES,
                            *, top_k: int = 3) -> list[dict]:
    if top_k < 1:
        raise ValueError("top_k must be >= 1")
    output = []
    for label, basket in cases:
        selected = mined.recommender.validate_items(basket)
        recommendations = mined.recommender.recommend(selected, limit=None)
        if not recommendations:
            raise ValueError(f"Example {label!r} has no applicable recommendations")
        output.append({
            "label": label,
            "basket_ids": sorted(selected),
            "basket_products": [catalog[pid] for pid in sorted(selected)],
            "eligible_count": len(recommendations),
            "recommendations": [{
                "product_id": rec.product_id,
                "product_name": rec.product_name,
                "antecedent_ids": list(rec.best_rule.antecedent),
                "antecedent_products": [catalog[pid] for pid in rec.best_rule.antecedent],
                "joint_baskets": rec.best_rule.basket_count,
                "support": rec.best_rule.support,
                "confidence": rec.best_rule.confidence,
                "lift": rec.best_rule.lift,
                "supporting_rule_count": rec.supporting_rule_count,
            } for rec in recommendations[:top_k]],
        })
    return output


def _md(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def make_report(data: DashboardData, scenarios: Sequence[ScenarioMetrics],
                reviews: Sequence[ReviewedRule], examples: Sequence[dict],
                *, baseline: tuple[float, float] = (0.002, 0.30)) -> str:
    names = data.catalog
    sections = [
        "# T09 — Evaluation and Interpretation",
        "",
        "**Dataset:** Instacart training split; only `cat food care` and `dog food care` items. "
        f"The denominator is **{len(data.baskets):,} pet-containing orders** "
        "(including single-pet-item baskets).",
        "",
        "**Evaluation type:** Descriptive, **in-sample** rule and recommendation inspection. "
        "The same transactions are used to mine rules and count coverage; no held-out "
        "recommendation accuracy or user satisfaction has been measured.",
        "",
        "## A. Threshold experiments",
        "",
        "| Minimum support | Minimum confidence | Joint baskets required | Frequent itemsets | Rules | 1→1 rules | Covered observed baskets | Coverage |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for m in scenarios:
        sections.append(f"| {m.min_support:.2%} | {m.min_confidence:.0%} | {m.minimum_joint_baskets} | "
                        f"{m.frequent_itemsets} | {m.association_rules} | {m.one_to_one_rules} | "
                        f"{m.eligible_baskets}/{m.total_baskets} | {m.descriptive_coverage:.1%} |")
    sections += [
        "",
        "**Coverage definition:** Percentage of *observed full baskets* from which at least "
        "one mined single-consequent rule recommends a product not already in that basket. "
        "This is a descriptive rule-activation/eligibility diagnostic, **not** prediction "
        "accuracy, recall, or commercial usefulness.",
        "",
        "**Interpretation:** A higher support threshold removes low-frequency itemsets and "
        "their rules; a higher confidence threshold filters rules but does not change "
        "frequent itemsets. With sparse pet-only baskets, lowering support increases "
        "rule availability but also admits weaker evidence.",
        "",
        "## B. Recommendation examples",
        "",
        f"Baseline thresholds: minimum support **{baseline[0]:.2%}**, "
        f"minimum confidence **{baseline[1]:.0%}**. "
        "Shown recommendations are determined by the highest-ranked matching rule; "
        "they exclude items already in the basket.",
        "",
        "| Basket | Highest-ranked recommendation | Joint orders | Support | Confidence | Lift |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for ex in examples:
        first = ex["recommendations"][0]
        sections.append(f"| {_md(', '.join(ex['basket_products']))} | {_md(first['product_name'])} | "
                        f"{first['joint_baskets']} | {first['support']:.2%} | "
                        f"{first['confidence']:.1%} | {first['lift']:.2f} |")
    sections += [
        "",
        "The complete top-three recommendations and their supporting product IDs are "
        "saved to `data/processed/evaluation/recommendation_examples.json` by `python evaluate.py`.",
        "",
        "## C. Manual inspection of discovered rules",
        "",
        "The following classifications are **provisional analyst judgments**, based on "
        "product labels and observed co-purchases, and should be confirmed by the project group. "
        "Each row is matched against a real mined directional rule before the report is generated. "
        "‘Unexpected’ means less obvious *from the product names*, not statistically proven novelty.",
        "",
        "| Antecedent → Consequent | Joint orders | Confidence | Category | Justification |",
        "|---|---:|---:|---|---|",
    ]
    for rv in reviews:
        lhs = ", ".join(names[pid] for pid in rv.antecedent)
        rhs = ", ".join(names[pid] for pid in rv.consequent)
        sections.append(f"| {_md(lhs)} → {_md(rhs)} | {rv.basket_count} | "
                        f"{rv.confidence:.1%} | {_md(rv.category)} | {_md(rv.rationale)} |")
    counts = Counter(rv.category for rv in reviews)
    sections += [
        "",
        "**Classification totals:** " + "; ".join(f"{c}: {counts[c]}" for c in
                  ("Useful", "Obvious / Trivial", "Unexpected", "Weak / Uncertain")) + ".",
        "",
        "## D. Limitations and validity",
        "",
        "1. **Small co-purchase counts.** With support 0.2%, a rule can be based on just "
        "six orders. Even 100% confidence may come from a tiny antecedent sample.",
        "2. **Biased sample and narrow domain.** Pet baskets are filtered from a general "
        "grocery dataset; no specialist pet-shop data or product-care attributes are included.",
        "3. **Co-purchase ≠ compatibility.** Several associations are alternate flavors "
        "of similar foods rather than complementary needs; none establishes pet suitability.",
        "4. **No held-out test or online evaluation.** Rules and coverage are measured "
        "on the same training transactions. They do not demonstrate next-purchase "
        "prediction performance, user usefulness, or commercial uplift.",
        "5. **Popularity and sparsity.** Less common pet items have few or no frequent "
        "associations, so the engine can return no suggestions.",
        "",
        "## E. Reproduction",
        "",
        "```bash",
        "python run_pipeline.py",
        "python evaluate.py",
        "python -m unittest discover -s tests -v",
        "```",
        "",
        "Manual review annotations: `docs/t09_rule_review.csv`. Generated JSON/CSV evidence: "
        "`data/processed/evaluation/` (Git-ignored). For different source files or "
        "baseline thresholds, review and update the annotation list before reporting.",
        "",
    ]
    return "\n".join(sections)


def export_evaluation(output_dir: Path, scenarios: Sequence[ScenarioMetrics],
                      reviews: Sequence[ReviewedRule], examples: Sequence[dict],
                      report_path: Path, report: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "threshold_experiments.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(ScenarioMetrics.__dataclass_fields__))
        writer.writeheader()
        writer.writerows(asdict(row) for row in scenarios)
    (output_dir / "recommendation_examples.json").write_text(
        json.dumps(list(examples), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with (output_dir / "reviewed_rules.csv").open("w", newline="", encoding="utf-8") as fh:
        fieldnames = ["antecedent_ids_json", "consequent_ids_json", "basket_count", "support",
                      "confidence", "lift", "classification", "rationale"]
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for rule in reviews:
            writer.writerow({"antecedent_ids_json": json.dumps(rule.antecedent),
                             "consequent_ids_json": json.dumps(rule.consequent),
                             "basket_count": rule.basket_count, "support": rule.support,
                             "confidence": rule.confidence, "lift": rule.lift,
                             "classification": rule.category, "rationale": rule.rationale})
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
