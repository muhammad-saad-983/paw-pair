"""Generate T09 rule review and threshold evidence. Run: python evaluate.py"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from pawpair.evaluation import (  # noqa: E402
    evaluate_scenarios, export_evaluation, load_manual_reviews,
    make_report, recommendation_examples,
)
from pawpair.ui_service import build_dashboard_mining, load_dashboard_data  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Reproduce PawPair T09 evaluation")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data/processed")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/processed/evaluation")
    parser.add_argument("--reviews", type=Path, default=ROOT / "docs/t09_rule_review.csv")
    parser.add_argument("--report", type=Path, default=ROOT / "docs/t09_evaluation.md")
    args = parser.parse_args()

    data = load_dashboard_data(args.data_dir)
    baseline = build_dashboard_mining(data, 0.002, 0.30)
    reviews = load_manual_reviews(args.reviews, baseline.rules)
    scenarios = evaluate_scenarios(data)
    examples = recommendation_examples(baseline, data.catalog)
    report = make_report(data, scenarios, reviews, examples)
    export_evaluation(args.output_dir, scenarios, reviews, examples, args.report, report)
    print(json.dumps({
        "transactions": len(data.baskets),
        "experiments": len(scenarios),
        "manually_reviewed_rules": len(reviews),
        "recommendation_examples": len(examples),
        "baseline_rules": len(baseline.rules),
        "report": str(args.report),
        "outputs": str(args.output_dir),
    }, indent=2))


if __name__ == "__main__":
    main()
