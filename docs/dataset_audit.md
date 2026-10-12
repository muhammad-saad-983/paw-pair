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

