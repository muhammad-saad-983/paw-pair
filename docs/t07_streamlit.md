# T07 — Streamlit UI

## Run

From the repository root with Python 3.10+:

```bash
python -m pip install -r requirements.txt
python run_pipeline.py
streamlit run app.py
```

The first command installs Streamlit and pandas. The mining command reads the three Instacart files in `data/raw/` and generates the input tables under `data/processed/`. The dashboard reads **`dataset_profile.json`, `pet_baskets.csv`, and `item_frequency.csv`**; it does **not** require precomputed rules because sidebar threshold changes mine fresh results.

## Pages

- **Overview:** transactions, unique items, multi-pet-order count, dynamic itemset/rule counts, item frequency chart, rule confidence histogram.
- **Frequent Itemsets:** size filter, per-itemset support/joint counts, generated/pruned/evaluated candidate summary.
- **Rules Explorer:** text search by product name/exact ID, filter rule side, sort by support/confidence/lift.
- **Recommendations:** multi-select basket, ranked and explained suggestions (up to 10), complete supporting-rule evidence, what-if removal and gained/lost/retained comparisons.

## Verify manually

1. Default support = `0.002`, confidence = `0.30`: Overview should show **2,729 baskets, 317 frequent itemsets, 179 rules** using the supplied `order_products__train.csv`.
2. Increase support to `0.003`: rule count should reduce (46 in the supplied data) while CSV files in `data/processed/` remain unchanged.
3. Search `5938` in Rules Explorer; search in *Antecedent*, then *Consequent*, and try sorting by Lift.
4. In Recommendations choose **Load example basket** (`24508`, `5938`); inspect ranked recommendations and their explanations.
5. Preview removing `5938`; verify gained/lost/retained changes without altering the selected basket.
6. Select an item with no matching rules; verify a helpful empty state appears without an ungrounded fallback.
7. Run `python -m unittest discover -s tests -v`.

## Design choices and limits

- Cache keys contain input-file modification times and sizes; new processed data invalidates cached results.
- Slider changes recompute Apriori and rules in memory; persisted files are not modified.
- Support is measured across pet-containing orders, not all Instacart orders.
- The recommended items are observed associations, not product-safety or compatibility advice.
- T08 will add the rule network graph and threshold side-by-side comparison.
