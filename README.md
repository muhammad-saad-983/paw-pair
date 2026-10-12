# PawPair — Pet Care Recommendation System

PawPair is an explainable, association rule–based recommendation system for pet-care products. It uses the **Apriori algorithm** to discover products frequently purchased together and recommends additional items based on a customer's basket.

The project includes a reproducible data-mining pipeline, command-line recommendation engine, and an interactive Streamlit dashboard.

## Features

- **Transaction preprocessing:** Extract cat- and dog-care products and organize purchases into baskets.
- **Frequent itemset mining:** Generate frequent itemsets with configurable minimum support using Apriori.
- **Association rules:** Calculate support, confidence, and lift for directional item relationships.
- **Explainable recommendations:** Recommend products not already in the basket and display the supporting rules.
- **Smart basket and what-if analysis:** Add or remove items and compare recommendations before and after changes.
- **Interactive dashboard:** Explore transactions, frequent itemsets, searchable rules, dynamic thresholds, and live recommendations.
- **Automated tests:** Verify preprocessing, mining, rule generation, and recommendation behavior.

## Dataset

**Source:** [Instacart Market Basket Analysis — Kaggle](https://www.kaggle.com/datasets/psparks/instacart-market-basket-analysis/data)

PawPair uses transactions involving products from the `cat food care` and `dog food care` aisles. The source is a general grocery-shopping dataset, **not a dedicated pet-store dataset**.

Download the dataset and place these files in `data/raw/`:

```text
data/raw/
├── aisles.csv
├── products.csv
└── order_products__train.csv
```

The optional `order_products__prior.csv` can also be used with the `--include-prior` argument. Raw and processed data files are excluded from Git.

## Getting Started

**Requirements:** Python 3.10 or later. The mining backend uses the standard library; the dashboard requires Streamlit and pandas.

```bash
git clone https://github.com/muhammad-saad-983/paw-pair.git
cd paw-pair
```

Install dashboard dependencies and place the dataset files in `data/raw/`, then generate frequent itemsets and association rules:

```bash
python -m pip install -r requirements.txt
```

```bash
python run_pipeline.py
```

The generated files, including `frequent_itemsets.csv` and `association_rules.csv`, are saved in `data/processed/`.

You can adjust the mining thresholds:

```bash
python run_pipeline.py --min-support 0.003 --min-confidence 0.5
```

### Run the Streamlit dashboard

```bash
streamlit run app.py
```

Use the sidebar to adjust minimum support/confidence and navigate **Overview**, **Frequent Itemsets**, **Rules Explorer**, and **Recommendations**. Changing the controls recalculates results in memory without overwriting `data/processed/`.

### Generate Recommendations

Run the pipeline first, then use the command-line tool:

```bash
# Find product IDs by name
python recommend.py --search "Classic Ocean Whitefish"

# Recommend items for a basket
python recommend.py --basket 24508 5938

# Preview recommendations after removing an item
python recommend.py --basket 24508 5938 --remove 5938
```

### Run Tests

```bash
python -m unittest discover -s tests -v
```

## Results

Using `order_products__train.csv` with **minimum support = 0.002** and **minimum confidence = 0.30**:

| Metric | Result |
|---|---:|
| Transactions containing pet-care products | 2,729 |
| Unique purchased pet-care products | 755 |
| Transactions with multiple pet-care products | 851 |
| Frequent itemsets | 317 |
| Association rules | 179 |

Support is calculated over the **pet-containing transactions**, not all grocery orders. These figures apply to the training split and stated thresholds; using additional data or different thresholds changes the results.

## Project Structure

```text
paw-pair/
├── data/                  # Raw inputs and generated outputs (Git-ignored)
├── docs/                  # Dataset audit and technical notes
├── src/pawpair/
│   ├── profile.py         # Data preprocessing and profiling
│   ├── apriori.py         # Frequent itemset mining
│   ├── rules.py           # Association rule generation
│   ├── recommender.py     # Recommendations and basket operations
│   └── ui_service.py      # Read-only dashboard data and rule filtering
├── tests/                 # Automated unit tests
├── app.py                 # Streamlit dashboard
├── run_pipeline.py        # Data-mining entry point
├── recommend.py           # Recommendation CLI
└── requirements.txt
```

## Limitations and Status

Recommendations reflect **observed co-purchases**, not product compatibility, causal relationships, or veterinary advice. The pet-care subset is relatively sparse, so some rules rely on a small number of transactions; high confidence alone does not guarantee usefulness.

The preprocessing, Apriori, association-rule, and recommendation backends are implemented. The **Streamlit dashboard** is implemented. The association graph, side-by-side threshold comparison, and final evaluation/report are still in development. See [`docs/tickets.md`](docs/tickets.md) for progress.
