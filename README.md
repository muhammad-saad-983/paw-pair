# PawPair — Pet Care Recommendation System

**Applied Machine Learning | Assignment 01**  
**Implemented:** T02–T05 data mining pipeline; **T06 rule-backed recommendation engine, smart basket and what-if analysis**.  
**Next:** T07 Streamlit application, followed by T08 visual analytics.

## Data source and scope

Instacart Online Grocery Shopping Dataset 2017: https://www.kaggle.com/competitions/instacart-market-basket-analysis/data

PawPair uses products from the `cat food care` and `dog food care` aisles. This is **not a specialist pet-store dataset**. The source is grocery orders, filtered to pet-care products; we mine pet-product combinations within pet-containing grocery orders. The model finds **co-occurrence**, not causation, product compatibility, or veterinary suitability.

### Input files

Place these **unmodified** CSVs in `data/raw/`:

- `aisles.csv` (`aisle_id`, `aisle`)
- `products.csv` (`product_id`, `product_name`, `aisle_id`)
- `order_products__train.csv` (`order_id`, `product_id`)

`order_products__prior.csv` is optional for future expansion (`--include-prior`). Do **not** store raw files in Git; `.gitignore` excludes them. The delivered ZIP also excludes raw data (you already downloaded it).

## Reproduce the results

Python 3.10+; **no third-party packages needed yet**.

From the project root:

```bash
python run_pipeline.py
python -m unittest discover -s tests -v
```

To adjust the rule thresholds:

```bash
python run_pipeline.py --min-support 0.003 --min-confidence 0.5
```

Every run writes fresh outputs to `data/processed/` (old outputs are overwritten).

### Generated files

| File | Description |
|---|---|
| `pet_baskets.csv` | Pet-only item IDs/names grouped by order; includes single-item orders |
| `item_frequency.csv` | Basket-level count and support of each pet product |
| `dataset_profile.json` | Dataset/cleaning audit and co-purchase frequencies |
| `frequent_itemsets.csv` | Apriori output: candidate item IDs/names, counts, support |
| `apriori_summary.json` | Candidates joined/pruned/frequent by itemset size |
| `association_rules.csv` | Directional LHS/RHS and support/confidence/lift |
| `rules_summary.json` | Final rule count and confidence setting |

**Interpretation:** Support counts are divided by the **2,729 orders containing >=1 pet product**, including one-pet-product baskets. General grocery-only orders are excluded; this conditions support on having at least one pet product. Product IDs (not names) are used for identity.

## Verified results from the supplied `train` split

| Metric | Result |
|---|---:|
| Order-product lines read | 1,384,617 |
| Pet item lines after filtering | 4,497 |
| Pet-containing orders | 2,729 |
| Multi-pet-product orders | 851 (31.18%) |
| Unique pet items observed | 755 |
| Distinct co-purchased item pairs | 3,230 |
| Pairs appearing >=5 times | 115 |

Recommended demo defaults: **min_support=0.002** (at least 6 joint orders) and **min_confidence=0.30**. These produce **317 frequent itemsets and 179 directional rules**, including **7 rules involving dog-care products**. At 0.003 support, 46 rules remain but **none** involve dog-care products. Support thresholds should be adapted to dataset sparsity rather than relying on typical default values of 1% or higher.

See `docs/dataset_audit.md` for the cleaning policy, experimental comparison, and limits.

## T06: Get rule-backed recommendations

Run the pipeline first to generate `data/processed/association_rules.csv` and `item_frequency.csv`. Then run from the repository root:

```bash
# Search product names and identify their product IDs.
python recommend.py --search "Classic Ocean Whitefish"

# Use one or more observed product IDs as the basket.
python recommend.py --basket 24508 5938

# Preview what changes if an item is removed (no actual mutation).
python recommend.py --basket 24508 5938 --remove 5938

# Dog example
python recommend.py --basket 15190
```

Search is case-insensitive; an exact product ID also works. For Python integration with Streamlit:

```python
from pathlib import Path
from pawpair.recommender import RecommendationEngine

engine = RecommendationEngine.from_directory(Path("data/processed"))
basket = engine.make_basket(["24508"])
recs = basket.recommendations(limit=5)
basket.add("5938")
preview = basket.preview_remove("5938")
# preview.gained / preview.lost / preview.retained; basket itself stays unchanged
```

When importing from the repository root, add `src` to `PYTHONPATH` or use the `recommend.py` entry point (which sets it automatically).

**Interpretation and ranking.** A rule `A -> {B}` applies only when *all* items in A are in the basket and B is not. We retain and display every matching single-consequent rule for each candidate item. We rank each item by its strongest matching rule, sorting by descending **confidence**, then observed **joint-basket count (support)**, **lift**, and antecedent length; product ID breaks remaining ties. Multiple rules are not treated as independent votes or summed probabilities. Rules with multi-item consequents are intentionally not split into single-product recommendations because their metrics describe an entire RHS bundle. No match means an empty recommendation list, not an ungrounded suggestion.

**What-if analysis** uses the full recommendation set to identify gained/lost/retained items without confusing rank-limit changes for genuine item-set changes. This preview never mutates the basket; `SmartBasket.add()` and `.remove()` do change the basket and recompute recommendations on the next query.

**Important limitations:** The observed training transactions are sparse and mostly associate different flavors/variants of pet food, which are not necessarily complementary. High confidence or lift based on six to seven co-purchases is not proof of usefulness or product suitability. Do not interpret associations as causal or veterinary advice.

A detailed example is in `docs/t06_recommendation_engine.md`.

## How Apriori is implemented

1. Count items and retain **L1** with count >= `ceil(min_support * N)`.
2. Join frequent (k-1)-itemsets to produce candidate **Ck**.
3. **Prune** any candidate for which any (k-1)-subset is not frequent.
4. Scan baskets and count the remaining candidates; retain **Lk** passing minimum support.
5. Generate every nonempty proper partition of each frequent itemset into an **antecedent** and **consequent**; calculate directional confidence and optional lift.

Rule **A → B** is distinct from **B → A**. For instance, a pair bought together 20 times where A appears 33 times and B appears 68 times has confidence 20/33=60.61% for A→B versus 20/68=29.41% for B→A.

## Status

See `docs/tickets.md`. T06 is complete and test-covered. T07–T10 (including Streamlit and final assignment evaluation/report) remain; this is a tested backend milestone, not a finished submission.
