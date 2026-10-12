"""PawPair Streamlit dashboard (T07).

Launch: streamlit run app.py
T08 will add the association network and cross-threshold comparison.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from pawpair.ui_service import (  # noqa: E402
    build_dashboard_mining,
    confidence_buckets,
    data_signature,
    filter_rules,
    frequent_itemset_rows,
    load_dashboard_data,
)

PROCESSED = ROOT / "data" / "processed"
PAGE_NAMES = ("Overview", "Frequent Itemsets", "Rules Explorer", "Recommendations")


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
    else:
        render_recommendations(data, mined)


if __name__ == "__main__":
    main()
