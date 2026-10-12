# PawPair implementation tickets

| ID | Scope | Status |
|---|---|---|
| T01 | PawPair domain + Instacart source selection | Complete (user confirmed) |
| T02 | Real CSV profiling + dataset feasibility | Complete |
| T03 | Pet-product transaction extraction + cleaning audit | Complete |
| T04 | Apriori with threshold controls, candidate join/prune, support metrics | Complete |
| T05 | Directional rule generation with support/confidence/lift | Complete |
| T06 | Smart basket, rule ranking, why/explanations, item exclusions, what-if | Complete (21 tests total) |
| T07 | Streamlit dataset, itemsets, rules, recommendations, search/filter pages | Next |
| T08 | 2+ charts, rule association graph, threshold playground/comparison | Not started |
| T09 | 5+ recommendation examples, 10+ manually classified rules, experiments, limitations | Not started |
| T10 | PDF/DOCX technical report, hand worked example, final submission verification | Not started |

## T06 acceptance criteria (implemented)

- Select one or more products by ID (product-name search resolves IDs) and show recommendations grounded in matching rules.
- No item already in the basket should be recommended.
- Explain exactly which matched rule produced a recommendation and report observed count, support, confidence.
- Handle multiple supporting rules using a documented rank/aggregation method.
- Demonstrate add/remove item (what-if) changes and handle no-match baskets cleanly.
- Unit-test item exclusions, multi-item antecedents, directional confidence and ranking.

### T06 verification

```bash
python -m unittest discover -s tests -v
python recommend.py --search "Ocean Whitefish"
python recommend.py --basket 24508 5938 --remove 5938
python recommend.py --basket 15190
```

The `recommend.py` program is a CLI demonstration. The interactive Streamlit basket is reserved for T07.
