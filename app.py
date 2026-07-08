"""Foreman — demo UI (premium build).

Run:  streamlit run app.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import plotly.graph_objects as go
import streamlit as st

from cascade import run_cascade
from graph import ACTIVITY, MATERIAL, SUPPLIER, build_graph, graph_summary
from risk import risk_radar

# ----------------------------------------------------------------- brand
BG = "#0E0E12"
SURFACE = "rgba(255,255,255,0.03)"
BORDER = "rgba(255,255,255,0.08)"
AMBER = "#FFB800"
RED = "#FF453A"
GREEN = "#32D74B"
TEXT = "#FAFAFA"
MUTED = "#9B9BA8"
DIM_NODE = "#3A3A46"

ICONS = {
    "logo": f'<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="{AMBER}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 20h20"/><path d="M4 20V10l8-6 8 6v10"/><path d="M12 20v-6"/><path d="M9 20v-3h6v3"/></svg>',
    "alert": f'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="{RED}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.46 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>',
    "shield": f'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="{GREEN}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/></svg>',
    "wrench": f'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="{AMBER}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>',
}


def svg(name: str) -> str:
    return ICONS[name]


st.set_page_config(page_title="Foreman — reasoning brain",
                   page_icon="🏗️", layout="wide")

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Inter:wght@400;500;600&display=swap');

.stApp {{ background: radial-gradient(1200px 500px at 20% -10%, rgba(255,184,0,.06), transparent), {BG}; }}
#MainMenu, footer, header {{ visibility: hidden; }}
.block-container {{ padding-top: 2.2rem; max-width: 1150px; }}

html, body, p, span, label, div {{ font-family: 'Inter', sans-serif; color: {TEXT}; }}
h1, h2, h3 {{ font-family: 'Space Grotesk', sans-serif !important; letter-spacing: -0.02em; }}

.fm-wordmark {{ display:flex; align-items:center; gap:.6rem; margin-bottom:.2rem; }}
.fm-wordmark .name {{ font-family:'Space Grotesk'; font-size:1.9rem; font-weight:700; }}
.fm-wordmark .dot  {{ color:{AMBER}; }}
.fm-sub {{ color:{MUTED}; font-size:.92rem; margin-bottom:1.4rem; }}

.kpi-row {{ display:flex; gap:.75rem; flex-wrap:wrap; margin:.4rem 0 1.2rem; }}
.kpi {{ background:{SURFACE}; border:1px solid {BORDER}; border-radius:12px;
        padding:.65rem 1.1rem; min-width:130px; transition:border-color .2s; }}
.kpi:hover {{ border-color: rgba(255,184,0,.35); }}
.kpi .v {{ font-family:'Space Grotesk'; font-size:1.35rem; font-weight:700; }}
.kpi .l {{ color:{MUTED}; font-size:.68rem; text-transform:uppercase; letter-spacing:.12em; }}

.verdict {{ border-radius:14px; padding:1.1rem 1.4rem; margin:.6rem 0 1rem;
            display:flex; align-items:center; gap:.9rem; font-family:'Space Grotesk';
            font-size:1.25rem; font-weight:700; }}
.verdict.breaks {{ background:linear-gradient(90deg, rgba(255,69,58,.16), rgba(255,69,58,.04));
                   border:1px solid rgba(255,69,58,.45); }}
.verdict.safe   {{ background:linear-gradient(90deg, rgba(50,215,75,.13), rgba(50,215,75,.03));
                   border:1px solid rgba(50,215,75,.4); }}
.verdict small {{ display:block; font-family:'Inter'; font-weight:400; font-size:.8rem;
                  color:{MUTED}; margin-top:.15rem; }}

.card {{ background:{SURFACE}; border:1px solid {BORDER}; border-radius:14px;
         padding:1rem 1.2rem; margin-bottom:.8rem; }}
.card .hd {{ font-size:.7rem; letter-spacing:.14em; text-transform:uppercase;
             color:{MUTED}; margin-bottom:.55rem; }}
.mitig {{ border-left:3px solid {AMBER}; }}

.risk-item {{ background:{SURFACE}; border:1px solid {BORDER}; border-radius:14px;
              padding: .9rem 1.1rem; margin-bottom:.65rem; transition:border-color .2s; }}
.risk-item:hover {{ border-color: rgba(255,184,0,.4); }}
.risk-item .t {{ font-weight:600; font-size:1rem; }}
.risk-item .m {{ color:{MUTED}; font-size:.82rem; margin-top:.15rem; }}
.badge {{ display:inline-block; padding:.18rem .6rem; border-radius:999px;
          font-size:.72rem; font-weight:600; letter-spacing:.03em; }}
.badge.red    {{ background:rgba(255,69,58,.15);  color:{RED};   border:1px solid rgba(255,69,58,.4); }}
.badge.orange {{ background:rgba(255,159,10,.15); color:#FF9F0A; border:1px solid rgba(255,159,10,.4); }}
.badge.yellow {{ background:rgba(255,214,10,.12); color:#FFD60A; border:1px solid rgba(255,214,10,.35); }}
.badge.green  {{ background:rgba(50,215,75,.12);  color:{GREEN}; border:1px solid rgba(50,215,75,.35); }}
.meter {{ height:6px; border-radius:999px; background:rgba(255,255,255,.07); margin-top:.55rem; }}
.meter > div {{ height:6px; border-radius:999px; }}

.stTabs [data-baseweb="tab-list"] {{ gap:.4rem; border-bottom:1px solid {BORDER}; }}
.stTabs [data-baseweb="tab"] {{ background:transparent; color:{MUTED};
    font-weight:600; padding:.6rem 1.1rem; }}
.stTabs [aria-selected="true"] {{ color:{AMBER} !important;
    border-bottom:2px solid {AMBER} !important; }}

.stButton > button {{ background:{AMBER}; color:#151515; font-weight:700;
    border:none; border-radius:10px; padding:.55rem 1.3rem; cursor:pointer;
    transition:filter .2s; }}
.stButton > button:hover {{ filter:brightness(1.08); }}
[data-baseweb="select"] {{ cursor:pointer; }}
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------ data
g = build_graph()
s = graph_summary(g)
baseline_handover = run_cascade(g, "MAT-1", 0).baseline_handover

# ---------------------------------------------------------------- header
st.markdown(f"""
<div class="fm-wordmark">{svg("logo")}<span class="name">FOREMAN<span class="dot">.</span></span></div>
<div class="fm-sub">The reasoning brain for construction supply chains ·
<b>{s["project"]}</b> · synthetic demo data</div>
<div class="kpi-row">
  <div class="kpi"><div class="v">{s["materials"]}</div><div class="l">materials</div></div>
  <div class="kpi"><div class="v">{s["suppliers"]}</div><div class="l">suppliers</div></div>
  <div class="kpi"><div class="v">{s["activities"]}</div><div class="l">activities</div></div>
  <div class="kpi"><div class="v">{s["edges"]}</div><div class="l">graph edges</div></div>
  <div class="kpi"><div class="v" style="color:{AMBER}">{baseline_handover}</div><div class="l">planned handover</div></div>
</div>
""", unsafe_allow_html=True)

tab_sim, tab_radar = st.tabs(["Delay Cascade Simulator", "Risk Radar"])

# ------------------------------------------------------------ simulator
with tab_sim:
    materials = {n: d for n, d in g.nodes(data=True) if d["kind"] == MATERIAL}

    c1, c2 = st.columns([3, 2])
    with c1:
        mat_id = st.selectbox(
            "Which material slips?", list(materials),
            format_func=lambda m: f"{materials[m]['name']}  ({m})")
    with c2:
        delay = st.slider("By how many days?", 1, 30, 5)

    with st.spinner("Reasoning over the graph…"):
        r = run_cascade(g, mat_id, delay)

    if r.handover_slip_days > 0:
        st.markdown(f"""
        <div class="verdict breaks">{svg("alert")}
          <div>HANDOVER BREAKS &nbsp;{r.baseline_handover} → {r.handover_date}
               &nbsp;(+{r.handover_slip_days} days)
            <small>status confidence {r.confidence:.0%} — {r.confidence_source}</small>
          </div></div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="verdict safe">{svg("shield")}
          <div>HANDOVER SAFE — float absorbs this delay
            <small>handover stays {r.baseline_handover} · status confidence
            {r.confidence:.0%} — {r.confidence_source}</small>
          </div></div>""", unsafe_allow_html=True)

    # ------------------------------------------------------------- graph
    slipped_ids = {e["activity"] for e in r.slipped}
    layers = {SUPPLIER: 0, MATERIAL: 1, ACTIVITY: 2}
    pos, counts = {}, {0: 0, 1: 0, 2: 0}
    for n, d in sorted(g.nodes(data=True), key=lambda x: x[0]):
        layer = layers[d["kind"]]
        pos[n] = (layer * 2.4, -counts[layer])
        counts[layer] += 1

    hot = slipped_ids | {mat_id}
    cold_x, cold_y, hot_x, hot_y = [], [], [], []
    for u, v in g.edges():
        seg_x = [pos[u][0], pos[v][0], None]
        seg_y = [pos[u][1], pos[v][1], None]
        if u in hot and v in hot:
            hot_x += seg_x; hot_y += seg_y
        else:
            cold_x += seg_x; cold_y += seg_y

    node_x, node_y, colors, sizes, texts = [], [], [], [], []
    for n, d in g.nodes(data=True):
        node_x.append(pos[n][0]); node_y.append(pos[n][1])
        if n == mat_id:
            colors.append(AMBER); sizes.append(22)
        elif n in slipped_ids:
            colors.append(RED); sizes.append(18)
        elif n == g.graph["handover"] and r.handover_slip_days == 0:
            colors.append(GREEN); sizes.append(18)
        else:
            colors.append(DIM_NODE); sizes.append(13)
        texts.append(f"<b>{n}</b><br>{d.get('name','')}")

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=cold_x, y=cold_y, mode="lines",
                             line=dict(color="#23232C", width=1),
                             hoverinfo="none"))
    fig.add_trace(go.Scatter(x=hot_x, y=hot_y, mode="lines",
                             line=dict(color=RED, width=2.2),
                             hoverinfo="none"))
    fig.add_trace(go.Scatter(
        x=node_x, y=node_y, mode="markers+text",
        marker=dict(size=sizes, color=colors,
                    line=dict(color="rgba(255,255,255,.25)", width=1)),
        text=list(g.nodes()), textposition="middle right",
        textfont=dict(color=MUTED, size=10, family="Inter"),
        hovertext=texts, hoverinfo="text"))
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False, height=470,
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, use_container_width=True,
                    config={"displayModeBar": False})
    st.caption("⬤ amber = delayed material · ⬤ red = slipped activities & cascade path · "
               "⬤ grey = unaffected")

    # ----------------------------------------------------------- details
    cA, cB = st.columns(2)
    with cA:
        rows = "".join(
            f"<div style='margin:.3rem 0'><b>{e['activity']}</b> {e['name']}"
            f"<span style='color:{MUTED}'> · {e['baseline_finish']} → "
            f"{e['new_finish']}</span> <span style='color:{RED};font-weight:600'>"
            f"+{e['slip_days']}d</span></div>"
            for e in r.slipped) or f"<span style='color:{MUTED}'>None — float absorbs everything.</span>"
        st.markdown(f'<div class="card"><div class="hd">activities that slip '
                    f'({len(r.slipped)})</div>{rows}</div>', unsafe_allow_html=True)
    with cB:
        rows = "".join(
            f"<div style='margin:.3rem 0;color:{MUTED}'>{e['activity']} {e['name']}</div>"
            for e in r.absorbed) or f"<span style='color:{MUTED}'>—</span>"
        st.markdown(f'<div class="card"><div class="hd">absorbed by float '
                    f'({len(r.absorbed)})</div>{rows}</div>', unsafe_allow_html=True)

    st.markdown(f'<div class="card mitig"><div class="hd">mitigation</div>'
                f'{svg("wrench")} &nbsp;{r.mitigation}</div>',
                unsafe_allow_html=True)

# ------------------------------------------------------------ risk radar
with tab_radar:
    st.markdown(f"<p style='color:{MUTED};margin-top:.6rem'>Foreman probes every "
                "material's <b>breaking point</b> (minimum slip that kills the "
                "handover) and crosses it with <b>status confidence</b>. "
                "Tight slack + unverified status = the silent killers.</p>",
                unsafe_allow_html=True)

    badge_class = {"🔴": "red", "🟠": "orange", "🟡": "yellow", "🟢": "green"}
    for rr in risk_radar(g):
        cls = badge_class.get(rr.verdict[:1], "green")
        label = rr.verdict[2:].split("—")[0].strip()
        bp_txt = ("no break within 45d" if rr.breaking_point_days is None
                  else f"breaks handover after {rr.breaking_point_days} days")
        pct = 100 if rr.breaking_point_days is None else \
            max(6, int((rr.breaking_point_days / 45) * 100))
        bar_color = {"red": RED, "orange": "#FF9F0A",
                     "yellow": "#FFD60A", "green": GREEN}[cls]
        st.markdown(f"""
        <div class="risk-item">
          <span class="badge {cls}">{label}</span>
          <div class="t" style="margin-top:.45rem">{rr.name}
            <span style="color:{MUTED};font-weight:400"> · {rr.material_id} · {rr.supplier}</span></div>
          <div class="m">{bp_txt} · confidence <b>{rr.confidence:.0%}</b>
            <i>({rr.confidence_source})</i> · risk score <b>{rr.risk_score}</b></div>
          <div class="meter"><div style="width:{pct}%;background:{bar_color}"></div></div>
        </div>""", unsafe_allow_html=True)
