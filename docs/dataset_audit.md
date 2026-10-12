# Dataset audit — Instacart train split (T02–T05)

**Source:** Instacart Online Grocery Shopping Dataset 2017, order_products__train.csv, products.csv, aisles.csv (user-provided copies).

## Scope / cleaning decisions

- Load source CSVs and require expected columns. Match aisle names after whitespace/case normalization.
- Keep **only** the `cat food care` and `dog food care` aisles; drop irrelevant grocery items.
- Treat `product_id` as product identity, `order_id` as basket identity; do not merge same-named items automatically.
- Skip order rows missing an order ID or product ID.
- Deduplicate repeated product IDs **within the same order** (Apriori uses presence, not quantity).
- Exclude product catalog rows lacking IDs/names; reject duplicate pet-product IDs or duplicate aisle IDs.
- Group retained products per order and include **singletons** in support denominators.
- Retain human-readable product names only for output/explanations.

## Verified counts

| Audit measurement | Count |
|---|---:|
| Raw order-product rows | 1,384,617 |
| Non-pet order-product rows excluded | 1,380,120 |
| Pet item entries kept | 4,497 |
| Invalid/missing order or product IDs | 0 |
| Duplicate pet product/order rows | 0 |
| Products in selected pet-care aisles (catalog) | 972 |
| Distinct pet products actually purchased | 755 |
| Orders with at least one pet product | 2,729 |
| Pet orders with 2+ distinct products | 851 |
| Pet orders with exactly one product | 1,878 |
| Product pair types observed | 3,230 |
| Pair types observed >=5 orders | 115 |

**Support definition:** `count(itemset) / 2729`. This is a **conditional** view of orders containing pet items, not a proportion of all orders in the original Instacart sample. The original train file has 1,384,617 *line-items*, not that many unique orders.

## Apriori threshold sensitivity (confidence >= 30%)

| Support | Min joint-order count | L1 | L2 | L3 | L4+ | Directional rules |
|---:|---:|---:|---:|---:|---:|---:|
| 0.001 | 3 | 430 | 310 | 337 | 367 | 8,864 |
| 0.002 | 6 | 231 | 68 | 17 | 1 | 179 |
| 0.003 | 9 | 151 | 24 | 3 | 0 | 46 |
| 0.005 | 14 | 82 | 4 | 0 | 0 | 6 |
| 0.010 | 28 | 16 | 0 | 0 | 0 | 0 |

The 0.001 setting creates many high-confidence rules from *only 3 occurrences*; avoid interpreting these as strong evidence. At 0.01, **no co-purchased itemsets** satisfy support, so no rules exist.

**Chosen defaults:** min_support=0.002 (minimum 6 co-purchases), min_confidence=0.30. At these thresholds, **7 dog-product rules** survive. At 0.003 support, there are **zero dog-product rules**, even though cat-product rules still exist. Thus, show observation counts and confidence prominently and do not guarantee dog recommendations for every basket.

## Data-derived example

`Grain Free Turkey Formula Cat Food` and `Grain Free Chicken Formula Cat Food` co-occur in **20** pet-containing orders. The first appears in **33** orders and second in **68** orders. Hence confidence(`Turkey → Chicken`) = 20/33 = 60.61%; confidence(`Chicken → Turkey`) = 20/68 = 29.41%. The joint support is 20/2729 = 0.733%.

## Limitations to state clearly

- The source comes from grocery orders, **not a dedicated pet shop**. Observed tendencies need not generalize to pet-store customers.
- Many mined combinations consist of flavors/variants of cat food; these may be *obvious* rather than surprising or complementary.
- Rare product co-occurrences can yield inflated confidence; minimum counts, support and lift should accompany explanations.
- Co-purchase data alone does not establish pet-health suitability or a customer-specific recommendation. Avoid recommendations framed as veterinary guidance.
