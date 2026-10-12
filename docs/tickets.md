# PawPair implementation tickets

| ID | Scope | Status |
|---|---|---|
| T01 | PawPair domain + Instacart source selection | Complete (user confirmed) |
| T02 | Real CSV profiling + dataset feasibility | Complete |
| T03 | Pet-product transaction extraction + cleaning audit | Complete |
| T04 | Apriori with threshold controls, candidate join/prune, support metrics | Complete |
| T05 | Directional rule generation with support/confidence/lift | Complete |
| T06 | Smart basket, rule ranking, why/explanations, item exclusions, what-if | Complete |
| T07 | Streamlit dataset, itemsets, rules, recommendations, search/filter pages | Complete (30 tests and user browser checks passed) |
| T08 | Association graph, side-by-side threshold comparison, enhanced visual analytics | Implemented (automated tests passed; browser verification pending) |
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

The `recommend.py` program provides a CLI demonstration. T07 also provides an interactive Streamlit basket (`streamlit run app.py`).

## T07 acceptance criteria (implemented)

- `app.py` provides Overview, Frequent Itemsets, Rules Explorer, and Recommendations pages.
- Minimum support/confidence sliders recompute frequent itemsets, directional rules, and recommendations in memory.
- Overview includes product-frequency and rule-confidence charts.
- Itemsets page displays support and Apriori join/prune counts.
- Rules page searches names/IDs, filters by antecedent/consequent, and sorts results.
- Basket page updates recommendations upon item selection/removal and explains every recommendation, including multiple supporting rules.
- What-if preview does not mutate the actual basket.
- Seven pure-Python dashboard tests added (30 total; run with `python -m unittest discover -s tests -v`).
- UI browser smoke test passed locally (user verified TC01–TC07).

## T08 acceptance criteria (implemented, browser verification pending)

- Directed association graph uses true **one-item antecedent → one-item consequent** rules, with hover evidence, category filtering, and minimum joint-count/lift controls. Multi-item rules are excluded rather than misrepresented as single edges.
- Rules Explorer also plots a support vs. confidence scatter chart, with point size reflecting supporting basket count and color showing lift.
- Comparison page separately controls support and confidence for scenarios A and B while using the **same basket**.
- Shows all frequent-itemset, rule, and eligible recommendation counts, plus recommendations only in A, only in B, and shared by both.
- All slider mining uses existing read-only in-memory computation and caches; comparisons do not mutate data files.
- Eight new pure-Python tests (38 total) cover graph fidelity/filters/plot creation and rule/recommendation comparison.

Detailed instructions and expected results: `docs/t08_analytics.md`.

T09/T10 cover final experiments, manual rule inspection, and the technical report.
