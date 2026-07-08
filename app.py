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
BG = "#0D0F12"
SURFACE = "rgba(255,255,255,0.04)"
SURFACE_HOVER = "rgba(255,255,255,0.065)"
BORDER = "rgba(255,255,255,0.07)"
AMBER = "#F5A623"
AMBER_DIM = "rgba(245,166,35,0.12)"
RED = "#E05A50"
GREEN = "#3EAF6E"
STEEL = "#6B7D93"
STEEL_BRIGHT = "#8BA3BD"
TEXT = "#F0F0F2"
MUTED = "#8A8FA0"
DIM_NODE = "#2E3440"

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
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700;800&family=Inter:wght@400;500;600;700&display=swap');

/* ===== BASE ===== */
.stApp {{
    background:
        radial-gradient(ellipse 1100px 450px at 18% -8%, rgba(245,166,35,0.05), transparent 70%),
        radial-gradient(ellipse 600px 400px at 85% 10%, rgba(107,125,147,0.04), transparent 70%),
        {BG};
}}
#MainMenu, footer, header {{ visibility: hidden; }}
.block-container {{ padding-top: 2.4rem; max-width: 1160px; }}

html, body, p, span, label, div {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    color: {TEXT};
}}
h1, h2, h3 {{
    font-family: 'Space Grotesk', sans-serif !important;
    font-weight: 700;
    letter-spacing: -0.02em;
}}

/* ===== ANIMATIONS ===== */
@keyframes slideInUp {{
    from {{ opacity: 0; transform: translateY(14px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
}}
@keyframes fadeIn {{
    from {{ opacity: 0; }}
    to   {{ opacity: 1; }}
}}
@keyframes pulse-soft {{
    0%, 100% {{ opacity: 1; }}
    50%      {{ opacity: 0.65; }}
}}
@keyframes glow-ring {{
    0%, 100% {{ box-shadow: 0 0 0 0 rgba(245,166,35,0.15); }}
    50%      {{ box-shadow: 0 0 0 6px rgba(245,166,35,0.04); }}
}}

/* ===== WORDMARK ===== */
.fm-wordmark {{
    display: flex; align-items: center; gap: .65rem;
    margin-bottom: .25rem;
    animation: fadeIn 500ms ease-out;
}}
.fm-wordmark .name {{
    font-family: 'Space Grotesk'; font-size: 1.95rem; font-weight: 800;
    letter-spacing: 0.04em;
}}
.fm-wordmark .dot {{ color: {AMBER}; }}
.fm-sub {{
    color: {MUTED}; font-size: .88rem; margin-bottom: 1.6rem;
    letter-spacing: 0.01em;
}}

/* ===== KPI STAT CARDS ===== */
.kpi-row {{
    display: flex; gap: .85rem; flex-wrap: wrap;
    margin: .5rem 0 2.4rem;   /* extra breathing room below */
}}
.kpi {{
    background: linear-gradient(180deg, rgba(255,255,255,0.045) 0%, rgba(255,255,255,0.015) 100%);
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: .75rem 1.2rem;
    min-width: 135px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.04);
    transition: all 200ms cubic-bezier(0.4, 0, 0.2, 1);
    cursor: default;
}}
.kpi:hover {{
    border-color: rgba(245,166,35,0.35);
    transform: translateY(-2px);
    box-shadow: 0 0 0 1px rgba(245,166,35,0.15), 0 6px 24px rgba(0,0,0,0.45);
}}
.kpi .v {{
    font-family: 'Space Grotesk'; font-size: 1.75rem; font-weight: 800;
    line-height: 1.15;
}}
.kpi .l {{
    color: {MUTED}; font-size: .6rem; font-weight: 600;
    text-transform: uppercase; letter-spacing: .16em;
    margin-top: .2rem;
}}

/* ===== VERDICT BANNER ===== */
.verdict {{
    border-radius: 14px; padding: 1.1rem 1.4rem;
    margin: .8rem 0 1.6rem;   /* more space below before graph */
    display: flex; align-items: center; gap: .9rem;
    font-family: 'Space Grotesk'; font-size: 1.15rem; font-weight: 700;
    animation: slideInUp 400ms ease-out;
    box-shadow: 0 4px 16px rgba(0,0,0,0.3);
}}
.verdict.breaks {{
    background: linear-gradient(100deg, rgba(224,90,80,0.16), rgba(224,90,80,0.04));
    border: 1px solid rgba(224,90,80,0.4);
}}
.verdict.safe {{
    background: linear-gradient(100deg, rgba(62,175,110,0.14), rgba(62,175,110,0.03));
    border: 1px solid rgba(62,175,110,0.35);
}}
.verdict small {{
    display: block; font-family: 'Inter'; font-weight: 500; font-size: .78rem;
    color: {MUTED}; margin-top: .15rem;
}}
.verdict .conf-pulse {{
    animation: pulse-soft 2.5s ease-in-out infinite;
    font-weight: 700;
}}
.verdict svg {{
    flex-shrink: 0;
}}

/* ===== DETAIL CARDS ===== */
.card {{
    background: linear-gradient(180deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.015) 100%);
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 1rem 1.2rem;
    margin-bottom: .8rem;
    box-shadow: 0 2px 10px rgba(0,0,0,0.3);
    transition: border-color 200ms ease;
}}
.card:hover {{
    border-color: rgba(139,163,189,0.25);
}}
.card .hd {{
    font-size: .65rem; font-weight: 700; letter-spacing: .15em;
    text-transform: uppercase; color: {STEEL};
    margin-bottom: .55rem;
}}
.mitig {{
    border-left: 3px solid {AMBER};
}}

/* ===== RISK ITEMS ===== */
.risk-item {{
    background: linear-gradient(180deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.012) 100%);
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: .9rem 1.15rem;
    margin-bottom: .7rem;
    box-shadow: 0 2px 10px rgba(0,0,0,0.3);
    transition: all 200ms cubic-bezier(0.4, 0, 0.2, 1);
    cursor: pointer;
}}
.risk-item:hover {{
    border-color: rgba(245,166,35,0.35);
    transform: translateY(-1px);
    box-shadow: 0 0 0 1px rgba(245,166,35,0.12), 0 6px 20px rgba(0,0,0,0.4);
}}
.risk-item .t {{ font-weight: 600; font-size: 1rem; }}
.risk-item .m {{ color: {MUTED}; font-size: .82rem; margin-top: .15rem; }}

/* ===== BADGES ===== */
.badge {{
    display: inline-block; padding: .2rem .65rem; border-radius: 999px;
    font-size: .68rem; font-weight: 700; letter-spacing: .04em;
    text-transform: uppercase;
}}
.badge.red    {{ background: rgba(224,90,80,0.14);  color: {RED};   border: 1px solid rgba(224,90,80,0.35); }}
.badge.orange {{ background: rgba(230,140,30,0.14); color: #E08C1E; border: 1px solid rgba(230,140,30,0.35); }}
.badge.yellow {{ background: rgba(220,190,40,0.12); color: #C9AD28; border: 1px solid rgba(220,190,40,0.3); }}
.badge.green  {{ background: rgba(62,175,110,0.12); color: {GREEN}; border: 1px solid rgba(62,175,110,0.3); }}

/* ===== METER BARS ===== */
.meter {{
    height: 5px; border-radius: 999px;
    background: rgba(255,255,255,0.06);
    margin-top: .55rem;
    overflow: hidden;
}}
.meter > div {{
    height: 5px; border-radius: 999px;
    box-shadow: 0 0 8px rgba(245,166,35,0.15);
    transition: width 400ms ease;
}}

/* ===== TABS — PILL / SEGMENTED CONTROL ===== */
.stTabs [data-baseweb="tab-list"] {{
    background: rgba(255,255,255,0.035);
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 4px;
    gap: 4px;
    border-bottom: none !important;
}}
.stTabs [data-baseweb="tab"] {{
    background: transparent;
    color: {MUTED};
    font-weight: 600;
    font-size: .88rem;
    padding: .55rem 1.4rem;
    border-radius: 10px;
    border-bottom: none !important;
    transition: all 200ms cubic-bezier(0.4, 0, 0.2, 1);
}}
.stTabs [data-baseweb="tab"]:hover {{
    color: {STEEL_BRIGHT};
    background: rgba(255,255,255,0.03);
}}
.stTabs [aria-selected="true"] {{
    color: {AMBER} !important;
    background: {AMBER_DIM} !important;
    border: 1px solid rgba(245,166,35,0.25) !important;
    border-bottom: none !important;
    box-shadow: 0 0 12px rgba(245,166,35,0.08);
}}
/* Remove Streamlit's default tab highlight bar */
.stTabs [data-baseweb="tab-highlight"] {{
    display: none !important;
}}
.stTabs [data-baseweb="tab-border"] {{
    display: none !important;
}}

/* ===== BUTTONS ===== */
.stButton > button {{
    background: linear-gradient(180deg, {AMBER}, #D99020);
    color: #0D0F12;
    font-weight: 700;
    border: none;
    border-radius: 10px;
    padding: .55rem 1.3rem;
    cursor: pointer;
    box-shadow: 0 2px 8px rgba(245,166,35,0.2);
    transition: all 200ms ease;
}}
.stButton > button:hover {{
    filter: brightness(1.1);
    transform: translateY(-1px);
    box-shadow: 0 4px 16px rgba(245,166,35,0.3);
}}

/* ===== SELECTBOX & SLIDER ===== */
[data-baseweb="select"] {{
    cursor: pointer;
}}
[data-baseweb="select"] > div {{
    background: rgba(255,255,255,0.04) !important;
    border-color: {BORDER} !important;
    border-radius: 10px !important;
    transition: border-color 200ms ease;
}}
[data-baseweb="select"] > div:hover {{
    border-color: rgba(245,166,35,0.3) !important;
}}
[data-baseweb="select"] > div:focus-within {{
    border-color: {AMBER} !important;
    box-shadow: 0 0 0 1px rgba(245,166,35,0.2) !important;
}}

/* Slider — larger thumb, amber track */
.stSlider [data-baseweb="slider"] [role="slider"] {{
    width: 22px !important;
    height: 22px !important;
    background: {AMBER} !important;
    border: 2px solid #0D0F12 !important;
    box-shadow: 0 0 10px rgba(245,166,35,0.3), 0 2px 6px rgba(0,0,0,0.4) !important;
    transition: box-shadow 200ms ease, transform 200ms ease !important;
}}
.stSlider [data-baseweb="slider"] [role="slider"]:hover {{
    transform: scale(1.15) !important;
    box-shadow: 0 0 16px rgba(245,166,35,0.45), 0 2px 8px rgba(0,0,0,0.5) !important;
}}
.stSlider [data-baseweb="slider"] div[data-testid="stTickBarMin"],
.stSlider [data-baseweb="slider"] div[data-testid="stTickBarMax"] {{
    color: {MUTED} !important;
    font-size: .75rem !important;
}}

/* ===== GRAPH CANVAS CONTAINER ===== */
.graph-canvas {{
    background:
        radial-gradient(circle at 50% 50%, rgba(107,125,147,0.03) 0%, transparent 70%),
        {BG};
    background-image:
        radial-gradient(circle at 50% 50%, rgba(107,125,147,0.03) 0%, transparent 70%),
        radial-gradient(rgba(255,255,255,0.035) 1px, transparent 1px);
    background-size: 100% 100%, 22px 22px;
    border: 1px solid {BORDER};
    border-radius: 14px;
    padding: 1rem 1rem .6rem;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.03), 0 2px 12px rgba(0,0,0,0.3);
    margin-bottom: .6rem;
}}
.graph-canvas .graph-legend {{
    font-size: .72rem; color: {MUTED};
    padding: .4rem .2rem 0;
    border-top: 1px solid rgba(255,255,255,0.04);
    margin-top: .2rem;
}}
.graph-canvas .graph-legend span {{
    margin-right: 1.2rem;
}}

/* ===== SCROLLBAR ===== */
::-webkit-scrollbar {{ width: 6px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background: rgba(255,255,255,0.1); border-radius: 3px; }}
::-webkit-scrollbar-thumb:hover {{ background: rgba(255,255,255,0.18); }}

/* ===== EXPANDER OVERRIDES ===== */
.streamlit-expanderHeader {{
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 600;
    color: {TEXT} !important;
}}
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
            <small>status confidence <span class="conf-pulse">{r.confidence:.0%}</span> — {r.confidence_source}</small>
          </div></div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="verdict safe">{svg("shield")}
          <div>HANDOVER SAFE — float absorbs this delay
            <small>handover stays {r.baseline_handover} · status confidence
            <span class="conf-pulse">{r.confidence:.0%}</span> — {r.confidence_source}</small>
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

    node_x, node_y, colors, sizes, texts, borders = [], [], [], [], [], []
    for n, d in g.nodes(data=True):
        node_x.append(pos[n][0]); node_y.append(pos[n][1])
        if n == mat_id:
            colors.append(AMBER); sizes.append(24); borders.append(AMBER)
        elif n in slipped_ids:
            colors.append(RED); sizes.append(19); borders.append(RED)
        elif n == g.graph["handover"] and r.handover_slip_days == 0:
            colors.append(GREEN); sizes.append(19); borders.append(GREEN)
        else:
            colors.append(DIM_NODE); sizes.append(13); borders.append(STEEL)
        texts.append(f"<b>{n}</b><br>{d.get('name','')}")

    fig = go.Figure()
    # Cold edges
    fig.add_trace(go.Scatter(
        x=cold_x, y=cold_y, mode="lines",
        line=dict(color="rgba(107,125,147,0.18)", width=1),
        hoverinfo="none"))
    # Hot edges (cascade path)
    fig.add_trace(go.Scatter(
        x=hot_x, y=hot_y, mode="lines",
        line=dict(color=RED, width=2.8),
        hoverinfo="none"))
    # Nodes
    fig.add_trace(go.Scatter(
        x=node_x, y=node_y, mode="markers+text",
        marker=dict(
            size=sizes, color=colors,
            line=dict(color=borders, width=1.5),
            opacity=0.95),
        text=list(g.nodes()), textposition="middle right",
        textfont=dict(color=MUTED, size=10, family="Inter"),
        hovertext=texts, hoverinfo="text",
        hoverlabel=dict(
            bgcolor="#1A1D24",
            bordercolor=AMBER,
            font=dict(family="Inter", size=12, color=TEXT))))
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False, height=470,
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        margin=dict(l=0, r=0, t=10, b=0),
        hoverdistance=20)

    # Graph canvas container
    st.markdown('<div class="graph-canvas">', unsafe_allow_html=True)
    st.plotly_chart(fig, use_container_width=True,
                    config={"displayModeBar": False})
    st.markdown(f"""
    <div class="graph-legend">
        <span>⬤ <span style="color:{AMBER}">amber</span> = delayed material</span>
        <span>⬤ <span style="color:{RED}">red</span> = slipped activities &amp; cascade path</span>
        <span>⬤ <span style="color:{DIM_NODE}">grey</span> = unaffected</span>
    </div>
    </div>""", unsafe_allow_html=True)

    # ----------------------------------------------------------- details
    cA, cB = st.columns(2)
    with cA:
        rows = "".join(
            f"<div style='margin:.35rem 0'><b>{e['activity']}</b> {e['name']}"
            f"<span style='color:{MUTED}'> · {e['baseline_finish']} → "
            f"{e['new_finish']}</span> <span style='color:{RED};font-weight:600'>"
            f"+{e['slip_days']}d</span></div>"
            for e in r.slipped) or f"<span style='color:{MUTED}'>None — float absorbs everything.</span>"
        st.markdown(f'<div class="card"><div class="hd">activities that slip '
                    f'({len(r.slipped)})</div>{rows}</div>', unsafe_allow_html=True)
    with cB:
        rows = "".join(
            f"<div style='margin:.35rem 0;color:{MUTED}'>{e['activity']} {e['name']}</div>"
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
        bar_color = {"red": RED, "orange": "#E08C1E",
                     "yellow": "#C9AD28", "green": GREEN}[cls]
        st.markdown(f"""
        <div class="risk-item">
          <span class="badge {cls}">{label}</span>
          <div class="t" style="margin-top:.45rem">{rr.name}
            <span style="color:{MUTED};font-weight:400"> · {rr.material_id} · {rr.supplier}</span></div>
          <div class="m">{bp_txt} · confidence <b>{rr.confidence:.0%}</b>
            <i>({rr.confidence_source})</i> · risk score <b>{rr.risk_score}</b></div>
          <div class="meter"><div style="width:{pct}%;background:{bar_color}"></div></div>
        </div>""", unsafe_allow_html=True)
