"""Foreman — demo UI.

Run:  streamlit run app.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import networkx as nx
import plotly.graph_objects as go
import streamlit as st

from cascade import run_cascade
from graph import ACTIVITY, MATERIAL, SUPPLIER, build_graph, graph_summary
from risk import risk_radar

AMBER = "#FFB800"
RED = "#FF3B30"
DIM = "#4A4A55"
GREEN = "#34C759"

st.set_page_config(page_title="Foreman", page_icon="🏗️", layout="wide")

st.markdown(
    """
    <style>
      .stApp { background-color: #0E0E12; }
      h1, h2, h3, p, span, label { color: #FAFAFA !important; }
      .big-verdict { font-size: 1.6rem; font-weight: 700; padding: 0.8rem 1rem;
                     border-radius: 8px; margin: 0.6rem 0; }
      .breaks { background: rgba(255,59,48,.15); border: 1px solid #FF3B30; }
      .safe   { background: rgba(52,199,89,.12);  border: 1px solid #34C759; }
    </style>
    """,
    unsafe_allow_html=True,
)

g = build_graph()
s = graph_summary(g)

st.title("🏗️ Foreman")
st.caption("The reasoning brain for construction supply chains — "
           f"**{s['project']}** · {s['suppliers']} suppliers · "
           f"{s['materials']} materials · {s['activities']} activities · "
           f"{s['edges']} graph edges · *synthetic demo data*")

tab_cascade, tab_radar = st.tabs(["⚡ Delay Cascade Simulator", "🎯 Risk Radar"])

# ---------------------------------------------------------------- cascade tab
with tab_cascade:
    materials = {n: d for n, d in g.nodes(data=True) if d["kind"] == MATERIAL}

    col1, col2, col3 = st.columns([3, 2, 1])
    with col1:
        mat_id = st.selectbox(
            "Material that slips",
            options=list(materials),
            format_func=lambda m: f"{m} — {materials[m]['name']}",
        )
    with col2:
        delay = st.slider("Delay (days)", 1, 30, 5)
    with col3:
        st.write("")
        run = st.button("Run cascade ⚡", type="primary", use_container_width=True)

    if run or True:  # always show for the selected inputs
        r = run_cascade(g, mat_id, delay)

        if r.handover_slip_days > 0:
            st.markdown(
                f'<div class="big-verdict breaks">🔴 HANDOVER BREAKS: '
                f'{r.baseline_handover} → {r.handover_date} '
                f'(+{r.handover_slip_days} days)</div>',
                unsafe_allow_html=True)
        else:
            st.markdown(
                f'<div class="big-verdict safe">🟢 HANDOVER SAFE — schedule '
                f'float absorbs this delay (stays {r.baseline_handover})</div>',
                unsafe_allow_html=True)

        st.caption(f"Confidence in this material's status: "
                   f"**{r.confidence:.0%}** — {r.confidence_source}")

        cA, cB = st.columns(2)
        with cA:
            st.subheader(f"⛓️ {len(r.slipped)} activities slip")
            for e in r.slipped:
                st.markdown(f"- **{e['activity']} {e['name']}** — "
                            f"{e['baseline_finish']} → {e['new_finish']} "
                            f"(**+{e['slip_days']}d**)")
            if not r.slipped:
                st.markdown("*None — float absorbs everything.*")
        with cB:
            st.subheader(f"🛡️ {len(r.absorbed)} activities absorb (float)")
            for e in r.absorbed:
                st.markdown(f"- {e['activity']} {e['name']}")

        st.info(f"🛠 **Mitigation** — {r.mitigation}")

        # ------------------------------------------------------ graph figure
        slipped_ids = {e["activity"] for e in r.slipped}
        layers = {SUPPLIER: 0, MATERIAL: 1, ACTIVITY: 2}
        pos, counts = {}, {0: 0, 1: 0, 2: 0}
        for n, d in sorted(g.nodes(data=True), key=lambda x: x[0]):
            layer = layers[d["kind"]]
            pos[n] = (layer * 2.2, -counts[layer] * 1.0)
            counts[layer] += 1

        edge_x, edge_y = [], []
        for u, v in g.edges():
            edge_x += [pos[u][0], pos[v][0], None]
            edge_y += [pos[u][1], pos[v][1], None]

        node_x, node_y, colors, texts = [], [], [], []
        for n, d in g.nodes(data=True):
            node_x.append(pos[n][0]); node_y.append(pos[n][1])
            if n == mat_id:
                colors.append(AMBER)
            elif n in slipped_ids:
                colors.append(RED)
            elif n == g.graph["handover"] and r.handover_slip_days == 0:
                colors.append(GREEN)
            else:
                colors.append(DIM)
            texts.append(f"{n}<br>{d.get('name','')}")

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=edge_x, y=edge_y, mode="lines",
                                 line=dict(color="#2A2A33", width=1),
                                 hoverinfo="none"))
        fig.add_trace(go.Scatter(x=node_x, y=node_y, mode="markers+text",
                                 marker=dict(size=18, color=colors),
                                 text=[n for n in g.nodes()],
                                 textposition="middle right",
                                 textfont=dict(color="#8888AA", size=10),
                                 hovertext=texts, hoverinfo="text"))
        fig.update_layout(
            title=f"Delay cascade: {mat_id} +{delay}d (amber = delayed material, "
                  "red = slipped activities)",
            plot_bgcolor="#0E0E12", paper_bgcolor="#0E0E12",
            font=dict(color="#FAFAFA"), showlegend=False, height=520,
            xaxis=dict(visible=False), yaxis=dict(visible=False),
            margin=dict(l=10, r=10, t=50, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------------ risk tab
with tab_radar:
    st.subheader("Which materials could silently kill the handover date?")
    st.caption("Foreman probes every material's **breaking point** (min delay "
               "that slips handover) and crosses it with **status confidence**. "
               "Tight slack + unverified status = chase that vendor today.")
    for rr in risk_radar(g):
        bp = ("never (<45d)" if rr.breaking_point_days is None
              else f"{rr.breaking_point_days} days")
        with st.container(border=True):
            st.markdown(
                f"**{rr.verdict}**  \n"
                f"**{rr.material_id} — {rr.name}** · {rr.supplier}  \n"
                f"breaking point: **{bp}** · confidence **{rr.confidence:.0%}** "
                f"*({rr.confidence_source})* · risk score **{rr.risk_score}**")
