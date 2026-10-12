# T09 — Evaluation and Interpretation

**Dataset:** Instacart training split; only `cat food care` and `dog food care` items. The denominator is **2,729 pet-containing orders** (including single-pet-item baskets).

**Evaluation type:** Descriptive, **in-sample** rule and recommendation inspection. The same transactions are used to mine rules and count coverage; no held-out recommendation accuracy or user satisfaction has been measured.

## A. Threshold experiments

| Minimum support | Minimum confidence | Joint baskets required | Frequent itemsets | Rules | 1→1 rules | Covered observed baskets | Coverage |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.15% | 30% | 5 | 437 | 329 | 129 | 382/2729 | 14.0% |
| 0.20% | 30% | 6 | 317 | 179 | 85 | 314/2729 | 11.5% |
| 0.30% | 30% | 9 | 178 | 46 | 34 | 228/2729 | 8.4% |
| 0.50% | 30% | 14 | 86 | 6 | 6 | 96/2729 | 3.5% |
| 0.20% | 50% | 6 | 317 | 93 | 37 | 171/2729 | 6.3% |
| 0.20% | 70% | 6 | 317 | 38 | 4 | 50/2729 | 1.8% |
| 0.30% | 50% | 9 | 178 | 28 | 21 | 128/2729 | 4.7% |

**Coverage definition:** Percentage of *observed full baskets* from which at least one mined single-consequent rule recommends a product not already in that basket. This is a descriptive rule-activation/eligibility diagnostic, **not** prediction accuracy, recall, or commercial usefulness.

**Interpretation:** A higher support threshold removes low-frequency itemsets and their rules; a higher confidence threshold filters rules but does not change frequent itemsets. With sparse pet-only baskets, lowering support increases rule availability but also admits weaker evidence.

## B. Recommendation examples

Baseline thresholds: minimum support **0.20%**, minimum confidence **30%**. Shown recommendations are determined by the highest-ranked matching rule; they exclude items already in the basket.

| Basket | Highest-ranked recommendation | Joint orders | Support | Confidence | Lift |
|---|---|---:|---:|---:|---:|
| Prepared Meals Savory Rice & Lamb Stew Dog Food | Prepared Meals Beef Stew Wet Dog Food | 7 | 0.26% | 70.0% | 119.39 |
| Chicken Stew Natural Food for Dogs | Beef Stew Canned Dog Food | 7 | 0.26% | 58.3% | 93.64 |
| Organix Grain Free Turkey & Vegetable Dog Food | Organix Grain Free Chicken & Vegetable Dog Food | 7 | 0.26% | 46.7% | 53.06 |
| Classic Ocean Whitefish & Tuna Feast Cat Food | Classic Seafood Feast Cat Food | 13 | 0.48% | 65.0% | 84.47 |
| Grain Free Turkey Canned Cat Food | Grain Free Chicken Formula Cat Food | 13 | 0.48% | 68.4% | 27.46 |
| Classic Ocean Whitefish & Tuna Feast Cat Food, Savory Salmon | Classic Seafood Feast Cat Food | 7 | 0.26% | 100.0% | 129.95 |
| Grain Free Turkey & Salmon Formula Cat Food, Grain Free Turkey Canned Cat Food | Grain Free Chicken Formula Cat Food | 9 | 0.33% | 90.0% | 36.12 |

The complete top-three recommendations and their supporting product IDs are saved to `data/processed/evaluation/recommendation_examples.json` by `python evaluate.py`.

## C. Manual inspection of discovered rules

The following classifications are **provisional analyst judgments**, based on product labels and observed co-purchases, and should be confirmed by the project group. Each row is matched against a real mined directional rule before the report is generated. ‘Unexpected’ means less obvious *from the product names*, not statistically proven novelty.

| Antecedent → Consequent | Joint orders | Confidence | Category | Justification |
|---|---:|---:|---|---|
| Prepared Meals Savory Rice & Lamb Stew Dog Food → Prepared Meals Beef Stew Wet Dog Food | 7 | 70.0% | Useful | Two wet dog-food stews are a plausible variety-bundle suggestion; suitability still needs checking. |
| Chicken Stew Natural Food for Dogs → Beef Stew Canned Dog Food | 7 | 58.3% | Useful | Dog chicken stew and beef stew can support a variety offer for wet-food shoppers. |
| Organix Grain Free Turkey & Vegetable Dog Food → Organix Grain Free Chicken & Vegetable Dog Food | 7 | 46.7% | Useful | Two Organix grain-free dog recipes may support same-range discovery for shoppers. |
| Grain Free Turkey Canned Cat Food → Grain Free Chicken Formula Cat Food | 13 | 68.4% | Useful | Grain-free turkey and chicken cat formulas may help shoppers discover other varieties. |
| Grilled Turkey Feast in Gravy Cat Food → Grilled Chicken Feast in Gravy Cat Food | 13 | 68.4% | Obvious / Trivial | Turkey and chicken variants from the same gravy cat-food range are an unsurprising pairing. |
| Classic Salmon & Shrimp Feast Cat Food → Classic Ocean Whitefish & Tuna Feast Cat Food | 11 | 64.7% | Obvious / Trivial | Both are classic seafood-flavored cat foods; the pairing adds little novel insight. |
| Grain Free Turkey Formula Cat Food → Grain Free Chicken Formula Cat Food | 20 | 60.6% | Obvious / Trivial | Grain-free turkey and chicken cat food formulas represent expected variety purchasing. |
| Classic Ocean Whitefish & Tuna Feast Cat Food → Classic Seafood Feast Cat Food | 13 | 65.0% | Obvious / Trivial | Seafood cat food recommending another seafood feast is expected rather than novel. |
| Fancy Feast Wet Classic Turkey & Giblets Feast Cat Food → Classic Tender Beef Feast Cat Food | 13 | 50.0% | Unexpected | Turkey-and-giblets cat food linking to a beef recipe is less obvious from product names alone. |
| Classic Pate Mariner's Catch Cat Food → Purina Mixed Grill Classic Pate Cat Food | 8 | 72.7% | Unexpected | A mariners-catch pate paired with mixed-grill pate crosses seafood and meat flavor labels. |
| Classic Ocean Whitefish & Tuna Feast Cat Food, Savory Salmon → Classic Seafood Feast Cat Food | 7 | 100.0% | Weak / Uncertain | Perfect confidence is based on only seven joint orders and cannot establish general reliability. |
| Classic Tender Beef Feast Cat Food, Grilled Chicken Feast in Gravy Cat Food → Grilled Turkey Feast in Gravy Cat Food | 6 | 100.0% | Weak / Uncertain | Only six co-purchases support this multi-item rule despite its perfect confidence. |
| Natural Beef & Chicken Formula Food for Cats → Grain Free Turkey Formula Cat Food | 6 | 75.0% | Weak / Uncertain | The rule appears strong but rests on six co-purchases and may not generalize. |

**Classification totals:** Useful: 4; Obvious / Trivial: 4; Unexpected: 2; Weak / Uncertain: 3.

## D. Limitations and validity

1. **Small co-purchase counts.** With support 0.2%, a rule can be based on just six orders. Even 100% confidence may come from a tiny antecedent sample.
2. **Biased sample and narrow domain.** Pet baskets are filtered from a general grocery dataset; no specialist pet-shop data or product-care attributes are included.
3. **Co-purchase ≠ compatibility.** Several associations are alternate flavors of similar foods rather than complementary needs; none establishes pet suitability.
4. **No held-out test or online evaluation.** Rules and coverage are measured on the same training transactions. They do not demonstrate next-purchase prediction performance, user usefulness, or commercial uplift.
5. **Popularity and sparsity.** Less common pet items have few or no frequent associations, so the engine can return no suggestions.

## E. Reproduction

```bash
python run_pipeline.py
python evaluate.py
python -m unittest discover -s tests -v
```

Manual review annotations: `docs/t09_rule_review.csv`. Generated JSON/CSV evidence: `data/processed/evaluation/` (Git-ignored). For different source files or baseline thresholds, review and update the annotation list before reporting.
