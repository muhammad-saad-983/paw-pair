"""Plotly rendering of T08's directed, single-antecedent association network.

No Streamlit dependency. Data selection happens in analytics.association_edges().
"""
from __future__ import annotations

import math

import networkx as nx
import plotly.graph_objects as go

from .analytics import AssociationEdge


def association_figure(edges: list[AssociationEdge]) -> go.Figure:
    """Create deterministic directed rule graph with separate reciprocal arrows."""
    graph = nx.DiGraph()
    for edge in edges:
        graph.add_edge(edge.source_id, edge.target_id)
    pos = nx.spring_layout(graph, seed=17, iterations=125) if graph.nodes else {}
    fig = go.Figure()
    for edge in edges:
        sx, sy = pos[edge.source_id]
        tx, ty = pos[edge.target_id]
        dx, dy = tx - sx, ty - sy
        norm = math.hypot(dx, dy)
        if norm < 1e-9:
            continue
        # Opposite directions get visually distinct lines and arrowheads.
        offset = 0.055 if graph.has_edge(edge.target_id, edge.source_id) else 0
        nx0, ny0 = -dy / norm * offset, dx / norm * offset
        x0, y0 = sx + dx * .20 + nx0, sy + dy * .20 + ny0
        x1, y1 = sx + dx * .80 + nx0, sy + dy * .80 + ny0
        fig.add_annotation(x=x1, y=y1, ax=x0, ay=y0,
                           xref="x", yref="y", axref="x", ayref="y",
                           text="", showarrow=True, arrowhead=2, arrowsize=.8,
                           arrowwidth=1.6, arrowcolor="#94a3b8")
        hint = (f"{edge.source_name} → {edge.target_name}<br>"
                f"Confidence: {edge.confidence:.1%}<br>"
                f"Support: {edge.support:.2%}<br>"
                f"Lift: {edge.lift:.2f}<br>"
                f"Joint orders: {edge.basket_count}")
        fig.add_trace(go.Scatter(x=[(x0 + x1) / 2], y=[(y0 + y1) / 2],
                                 mode="markers", marker=dict(size=15, opacity=0.02, color="#64748b"),
                                 text=[hint], hovertemplate="%{text}<extra></extra>",
                                 showlegend=False))

    names = {}
    for edge in edges:
        names[edge.source_id] = edge.source_name
        names[edge.target_id] = edge.target_name
    ids = sorted(graph.nodes)
    fig.add_trace(go.Scatter(
        x=[pos[pid][0] for pid in ids], y=[pos[pid][1] for pid in ids],
        mode="markers+text", text=[names[pid][:20] + ("…" if len(names[pid]) > 20 else "")
                                     for pid in ids],
        textposition="top center", textfont=dict(size=10),
        marker=dict(size=[15 + 3 * math.sqrt(graph.degree(pid)) for pid in ids],
                    color="#3478c0", line=dict(width=1.5, color="white")),
        customdata=[f"{names[pid]} (#{pid})<br>Degree: {graph.degree(pid)}" for pid in ids],
        hovertemplate="%{customdata}<extra></extra>", showlegend=False,
    ))
    fig.update_layout(
        height=590, margin=dict(l=15, r=15, t=30, b=15),
        xaxis=dict(visible=False, scaleanchor="y", scaleratio=1),
        yaxis=dict(visible=False), hovermode="closest", dragmode="pan",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig
