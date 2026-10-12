# T08 — Association Graph and Threshold Comparison

## Run

From the repository root, with `.venv` activated and Instacart CSVs already prepared:

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m streamlit run app.py
```

The app uses `dataset_profile.json`, `pet_baskets.csv`, and `item_frequency.csv` from `data/processed/`. If missing, run `python run_pipeline.py` first. The dashboard **never overwrites** the processed CSVs when controls are adjusted.

## New features

- **Association Graph:** A directed graph of genuine single-product LHS → single-product RHS rules. Arrow direction is meaningful. Filters include cat vs. dog products, minimum joint orders, minimum lift, and maximum displayed arrows. Hover an arrow midpoint for confidence/support/lift and joint basket count. An expandable table shows precise displayed rules. **Multi-item antecedent rules are excluded from the graph**, since projecting `{A,B} → C` into `A → C` would be mathematically invalid. All original rules are retained in Rules Explorer.
- **Threshold Comparison:** Adjust support and confidence separately for Scenario A and B. Both use exactly the same selected basket; results show frequent itemsets, directional rules, full eligible recommendation counts, and only-A/only-B/shared recommendations. Tables show up to ten recommendations per scenario, but differences use **all** eligible recommendations, avoiding fake differences from top-N truncation.
- **Support vs Confidence chart:** Rules Explorer now has a scatterplot; point size represents joint order count and color represents lift.

## Manual browser verification

1. At default sidebar support `0.002`, confidence `0.30`, open **Association Graph**. Verify graph displays up to 35 directional arrows by default. Select **Dog care**: expect **7 one-to-one rules** at the default graph filters on the supplied train split.
2. Increase **Minimum joint orders** until the graph shrinks; select a lift cutoff high enough to remove edges. When no edges match, an empty-state message should appear rather than an exception.
3. Open **Rules Explorer**; check the scatterplot, confirm that changing sidebar thresholds and rule filters updates its dots.
4. Open **Threshold Comparison**. With example basket `24508, 5938`, Scenario A support `0.002`/confidence `0.30` and B support `0.003`/confidence `0.50`, expect:

   | Metric | A | B |
   |---|---:|---:|
   | Frequent itemsets | 317 | 178 |
   | Rules | 179 | 28 |
   | Eligible recommendations | 6 | 3 |

   The recommendation overlap is **3 shared, 3 only-A, 0 only-B**. Counts are based on the supplied Instacart training split and will change if input files change.
5. Set A and B to identical thresholds; their counts and recommendations should match, with 0 only-A and 0 only-B. Clear the comparison basket: recommendation lists become empty without breaking rule/itemset statistics.
6. Confirm that original T07 pages still function. Optionally verify the output file checksums before/after changing thresholds.

## Design notes

- The baseline measures support among **pet-containing grocery orders**, not all grocery transactions.
- High lift or confidence based on 6–7 co-purchases may be unstable. Arrows imply association, **not causality**, product suitability, or veterinarian-approved combinations.
- Rendering is capped for readability, not mining: no underlying rules are discarded.
- UI and network layout use Plotly and NetworkX; graph selection/comparison logic is separately unit-tested in `tests/test_analytics.py`.
