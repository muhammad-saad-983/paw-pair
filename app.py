"""PawPair Streamlit dashboard (T07–T08). Launch: streamlit run app.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st
import plotly.express as px

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from pawpair.analytics import association_edges, compare_mining  # noqa: E402
from pawpair.network_plot import association_figure  # noqa: E402
from pawpair.ui_service import (  # noqa: E402
    build_dashboard_mining,
    confidence_buckets,
    data_signature,
    filter_rules,
    frequent_itemset_rows,
    load_dashboard_data,
)

PROCESSED = ROOT / "data" / "processed"
PAGE_NAMES = ("Overview", "Frequent Itemsets", "Rules Explorer", "Recommendations",
              "Association Graph", "Threshold Comparison")


@st.cache_data(show_spinner=False)
def cached_data(signature: tuple):
    return load_dashboard_data(PROCESSED)


@st.cache_data(show_spinner="Mining itemsets and rules for selected thresholds...")
def cached_mining(signature: tuple, min_support: float, min_confidence: float):
    return build_dashboard_mining(cached_data(signature), min_support, min_confidence)


def render_overview(data, mined) -> None:
    st.header("Dataset overview")
    profile = data.profile
    a, b, c, d = st.columns(4)
    a.metric("Pet-containing orders", f"{len(data.baskets):,}")
    b.metric("Unique pet products", f"{len(data.catalog):,}")
    c.metric("Orders with 2+ pet items", f"{profile['multi_pet_item_orders']:,}")
    d.metric("Association rules", f"{len(mined.rules):,}")

    st.caption("Support is calculated over orders containing at least one pet-care product, "
               "including single-pet-item orders—not all grocery orders.")
    a, b = st.columns(2)
    a.metric("Frequent itemsets", f"{len(mined.itemsets.counts):,}")
    b.metric("Minimum joint baskets", f"{mined.itemsets.min_count:,}")

    st.subheader("Most frequently purchased products")
    top = sorted(data.item_frequencies, key=lambda r: -r["basket_count"])[:12]
    if top:
        chart_data = pd.DataFrame([
            {"Product": r["product_name"], "Orders": r["basket_count"]} for r in top
        ])
        st.bar_chart(chart_data, x="Product", y="Orders")
        with st.expander("View product counts"):
            st.dataframe(pd.DataFrame(top), hide_index=True, use_container_width=True)

    st.subheader("Association-rule confidence distribution")
    if mined.rules:
        st.bar_chart(pd.DataFrame(confidence_buckets(mined.rules)),
                     x="Confidence range", y="Rules")
    else:
        st.info("No rules satisfy the selected thresholds. Reduce minimum support or confidence.")
    st.caption("Changes to the thresholds in the sidebar recompute the figures and charts above.")


def render_itemsets(data, mined) -> None:
    st.header("Frequent itemsets")
    st.caption(f"Apriori identified {len(mined.itemsets.counts):,} frequent itemsets at "
               f"{mined.itemsets.min_support:.2%} minimum support "
               f"(at least {mined.itemsets.min_count} baskets).")
    if not mined.itemsets.counts:
        st.info("No frequent itemsets. Try a lower support threshold.")
        return
    sizes = sorted({len(itemset) for itemset in mined.itemsets.counts})
    choice = st.selectbox("Itemset size", options=["All"] + sizes)
    rows = frequent_itemset_rows(mined, data.catalog,
                                 size=None if choice == "All" else int(choice))
    st.caption(f"Showing {len(rows):,} itemsets")
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True,
                 column_config={"Support": st.column_config.NumberColumn(format="%.3f")})
    st.subheader("Apriori candidate pruning")
    audit = pd.DataFrame([{
        "Size": level.size,
        "Generated": level.candidates_generated,
        "Pruned": level.candidates_pruned,
        "Evaluated": level.candidates_evaluated,
        "Frequent": level.frequent_itemsets,
    } for level in mined.itemsets.levels])
    st.dataframe(audit, hide_index=True, use_container_width=True)
    st.caption("Candidates are joined from the previous frequent level. "
               "Candidates with any infrequent subset are pruned before support counting.")


def render_rules(data, mined) -> None:
    st.header("Rules explorer")
    st.caption("Search rules by product name or exact product ID; support, confidence, and lift "
               "are computed from the selected pet-containing baskets.")
    a, b, c = st.columns([3, 2, 2])
    query = a.text_input("Search for an item", placeholder="e.g., salmon or 5938")
    side = b.selectbox("Search in", ("Either side", "Antecedent", "Consequent"))
    sort = c.selectbox("Sort descending", ("Confidence", "Support", "Lift"))
    filtered = filter_rules(mined.rules, data.catalog, query, side, sort)
    st.caption(f"{len(filtered):,} matching rules / {len(mined.rules):,} total rules")
    if not filtered:
        st.info("No matching rules. Change the search or lower the mining thresholds.")
        return
    # Avoid rendering thousands of browser rows when the threshold is very low.
    st.dataframe(pd.DataFrame(filtered[:1000]), hide_index=True, use_container_width=True,
                 column_config={
                     "Support": st.column_config.NumberColumn(format="%.4f"),
                     "Confidence": st.column_config.NumberColumn(format="%.2f"),
                     "Lift": st.column_config.NumberColumn(format="%.2f"),
                 })
    if len(filtered) > 1000:
        st.caption("Showing the top 1,000 matching rules; narrow your search for more focused results.")
    st.info("A → B and B → A are different rules: confidence depends on how often the antecedent occurs.")
    st.subheader("Support vs. confidence")
    st.caption("Each dot represents a discovered directional rule. Size indicates joint-basket evidence; color indicates lift.")
    chart_data = pd.DataFrame(filtered[:1000])
    fig = px.scatter(chart_data, x="Support", y="Confidence", color="Lift",
                     size="Joint baskets", hover_data=["Antecedent", "Consequent"],
                     labels={"Support": "Rule support", "Confidence": "Rule confidence"})
    fig.update_layout(height=420)
    st.plotly_chart(fig, use_container_width=True)


def render_recommendations(data, mined) -> None:
    st.header("Smart basket recommendations")
    st.caption("Select one or more pet-care products. Recommendations update automatically; "
               "only rules whose entire antecedent matches your basket are used.")
    catalog = data.catalog
    if st.button("Load example basket"):
        st.session_state["basket_items"] = [pid for pid in ("24508", "5938") if pid in catalog]
    if "basket_items" in st.session_state:
        st.session_state["basket_items"] = [pid for pid in st.session_state["basket_items"]
                                           if pid in catalog]
    selected = st.multiselect("Your basket", options=sorted(catalog, key=lambda pid: catalog[pid].casefold()),
                              format_func=lambda pid: f"{catalog[pid]} (#{pid})",
                              placeholder="Search and add products...", key="basket_items")
    if not selected:
        st.info("Add a product to the basket to see data-backed recommendations.")
        return

    engine = mined.recommender
    recommendations = engine.recommend(selected, limit=10)
    st.subheader(f"Recommended products ({len(recommendations)} shown)")
    if not recommendations:
        st.warning("No applicable rules for this basket at the chosen thresholds. "
                   "Try another item or lower the thresholds.")
    for idx, rec in enumerate(recommendations, start=1):
        rule = rec.best_rule
        with st.container(border=True):
            st.markdown(f"**{idx}. {rec.product_name}**  ·  Product ID `{rec.product_id}`")
            a, b, c = st.columns(3)
            a.metric("Confidence", f"{rule.confidence:.1%}")
            b.metric("Support", f"{rule.support:.2%}")
            c.metric("Joint orders", f"{rule.basket_count:,}")
            st.write(rec.explanation)
            with st.expander(f"Why this recommendation? ({rec.supporting_rule_count} supporting rules)"):
                for ev in rec.evidence:
                    lhs = ", ".join(catalog[pid] for pid in ev.rule.antecedent)
                    st.markdown(f"**{lhs} → {rec.product_name}**")
                    st.caption(f"Confidence {ev.rule.confidence:.1%} · "
                               f"Support {ev.rule.support:.2%} · "
                               f"Lift {ev.rule.lift:.2f} · "
                               f"{ev.rule.basket_count} joint orders")
    st.divider()
    st.subheader("What-if: remove a basket item")
    remove_id = st.selectbox("Preview removing", selected,
                             format_func=lambda pid: f"{catalog[pid]} (#{pid})")
    preview = engine.what_if_remove(selected, remove_id)
    st.caption("This preview does not change your basket. It compares full recommendation sets, "
               "not just the top 10 displayed above.")
    a, b, c = st.columns(3)
    a.metric("Gained", len(preview.gained))
    b.metric("Lost", len(preview.lost))
    c.metric("Retained", len(preview.retained))
    st.write("**Gained:**", ", ".join(r.product_name for r in preview.gained) or "None")
    st.write("**Lost:**", ", ".join(r.product_name for r in preview.lost) or "None")
    st.caption("A product is listed as gained or lost only when its eligibility changes.")



def render_association_graph(data, mined) -> None:
    st.header("Association graph")
    st.caption("Directed arrows represent actual {A} → {B} rules. Multi-item antecedent "
               "or consequent rules are deliberately omitted rather than split into misleading edges.")

    c1, c2, c3, c4 = st.columns(4)
    aisle = c1.selectbox("Product category", ("All", "cat food care", "dog food care"),
                         format_func=lambda x: {"All": "All pet products",
                                                "cat food care": "Cat care",
                                                "dog food care": "Dog care"}[x])
    count = c2.slider("Minimum joint orders", 1, 25, 6, 1)
    lift = c3.slider("Minimum lift", 0.0, 20.0, 1.0, 0.5)
    cap = c4.slider("Maximum arrows", 10, 60, 35, 5)
    aisle_lookup = {row["product_id"]: row["aisle"] for row in data.item_frequencies}
    edges = association_edges(mined.rules, data.catalog, aisle_lookup,
                              aisle=aisle, min_joint_baskets=count,
                              min_lift=lift, max_edges=cap)
    st.metric("Displayed directional rules", len(edges))
    if not edges:
        st.info("No one-to-one associations match these filters. Lower the evidence/lift thresholds "
                "or choose another category.")
        return
    st.plotly_chart(association_figure(edges), use_container_width=True)
    st.caption("Arrows show rule direction, not cause-and-effect. The network is capped for readability; "
               "all mined rules remain accessible in Rules Explorer.")
    with st.expander("Inspect exact rules shown in the graph"):
        st.dataframe(pd.DataFrame([{
            "From": e.source_name, "To": e.target_name,
            "Joint baskets": e.basket_count, "Support": e.support,
            "Confidence": e.confidence, "Lift": e.lift,
        } for e in edges]), hide_index=True, use_container_width=True)


def _recommendation_table(recommendations):
    return pd.DataFrame([{
        "Product": r.product_name,
        "Confidence": r.best_rule.confidence,
        "Joint baskets": r.best_rule.basket_count,
        "Support": r.best_rule.support,
        "Lift": r.best_rule.lift,
    } for r in recommendations])


def render_threshold_comparison(data, signature) -> None:
    st.header("Threshold comparison")
    st.caption("Compare two independent support/confidence settings on the same basket. "
               "Both calculations happen in memory; no data files are overwritten.")

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Scenario A")
        support_a = st.slider("Minimum support — A", .001, .020, .002, .0005, format="%.4f")
        confidence_a = st.slider("Minimum confidence — A", .05, 1.0, .30, .05)
    with col_b:
        st.subheader("Scenario B")
        support_b = st.slider("Minimum support — B", .001, .020, .003, .0005, format="%.4f")
        confidence_b = st.slider("Minimum confidence — B", .05, 1.0, .50, .05)

    example = [pid for pid in ("24508", "5938") if pid in data.catalog]
    basket = st.multiselect("Comparison basket", options=sorted(data.catalog, key=lambda pid: data.catalog[pid].casefold()),
                            default=example, format_func=lambda pid: f"{data.catalog[pid]} (#{pid})",
                            key="t08_comparison_basket")

    scenario_a = cached_mining(signature, support_a, confidence_a)
    scenario_b = cached_mining(signature, support_b, confidence_b)
    compared = compare_mining(scenario_a, scenario_b, basket)
    with col_a:
        st.metric("Frequent itemsets", compared.itemsets_a)
        st.metric("Association rules", compared.rules_a)
        st.metric("Eligible recommendations", len(compared.recommendations_a))
        st.dataframe(_recommendation_table(compared.recommendations_a[:10]),
                     hide_index=True, use_container_width=True)
    with col_b:
        st.metric("Frequent itemsets", compared.itemsets_b)
        st.metric("Association rules", compared.rules_b)
        st.metric("Eligible recommendations", len(compared.recommendations_b))
        st.dataframe(_recommendation_table(compared.recommendations_b[:10]),
                     hide_index=True, use_container_width=True)
    st.caption("Each recommendation is ranked by its strongest applicable rule. "
               "Tables display up to 10 items, but comparisons use the complete recommendation lists.")
    st.divider()
    st.subheader("Recommendation differences")
    a, b, c = st.columns(3)
    a.metric("Only A", len(compared.only_a))
    b.metric("Only B", len(compared.only_b))
    c.metric("Shared", len(compared.shared))
    st.write("**Only with A:**", ", ".join(rec.product_name for rec in compared.only_a) or "None")
    st.write("**Only with B:**", ", ".join(rec.product_name for rec in compared.only_b) or "None")
    st.write("**Present in both:**", ", ".join(rec.product_name for rec in compared.shared) or "None")
    if not basket:
        st.info("Select one or more products to compare actual recommendations. "
                "Itemset and rule counts above remain comparable for an empty basket.")


def main() -> None:
    st.set_page_config(page_title="PawPair | Pet Care Recommendations", page_icon="🐾", layout="wide")
    st.title("PawPair")
    st.caption("Explainable pet-care recommendations using Apriori association rules")

    try:
        signature = data_signature(PROCESSED)
        data = cached_data(signature)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        st.error(f"Processed dataset unavailable or inconsistent: {exc}")
        st.code("python run_pipeline.py", language="bash")
        st.stop()

    with st.sidebar:
        st.header("Navigation")
        page = st.radio("Page", PAGE_NAMES)
        st.divider()
        st.header("Mining thresholds")
        min_support = st.slider("Minimum support", min_value=0.001, max_value=0.020,
                                value=0.002, step=0.0005, format="%.4f")
        min_confidence = st.slider("Minimum confidence", min_value=0.05, max_value=1.0,
                                   value=0.30, step=0.05, format="%.2f")
        st.caption(f"Support: {min_support:.2%} of pet-containing orders")
        st.caption(f"Confidence: {min_confidence:.0%} minimum")

    try:
        mined = cached_mining(signature, min_support, min_confidence)
    except ValueError as exc:
        st.error(f"Could not mine selected data: {exc}")
        st.stop()

    with st.sidebar:
        st.divider()
        st.metric("Frequent itemsets", len(mined.itemsets.counts))
        st.metric("Association rules", len(mined.rules))
        st.caption("Threshold changes recompute results in memory; no CSV files are overwritten.")

    if page == "Overview":
        render_overview(data, mined)
    elif page == "Frequent Itemsets":
        render_itemsets(data, mined)
    elif page == "Rules Explorer":
        render_rules(data, mined)
    elif page == "Recommendations":
        render_recommendations(data, mined)
    elif page == "Association Graph":
        render_association_graph(data, mined)
    else:
        render_threshold_comparison(data, signature)


if __name__ == "__main__":
    main()
