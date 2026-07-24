"""Foreman — demo UI (premium build).

Run:  streamlit run app.py
"""

import base64
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import plotly.graph_objects as go
import streamlit as st
from PIL import Image

LOGO_PATH = Path(__file__).parent / "assets" / "foreman-logo.png"


def _logo_data_uri() -> str:
    b64 = base64.b64encode(LOGO_PATH.read_bytes()).decode()
    return f"data:image/png;base64,{b64}"

try:
    from src.cascade import run_cascade  # type: ignore
    from src.graph import ACTIVITY, MATERIAL, SUPPLIER, build_graph, graph_summary  # type: ignore
    from src.risk import risk_radar  # type: ignore
except ImportError:
    from cascade import run_cascade  # type: ignore
    from graph import ACTIVITY, MATERIAL, SUPPLIER, build_graph, graph_summary  # type: ignore
    from risk import risk_radar  # type: ignore


def _ask_brain(question: str):
    """Lazy bridge to the brain router so the app boots even without a key."""
    try:
        from src.agents.brain import answer  # type: ignore
    except ImportError:
        from agents.brain import answer  # type: ignore
    return answer(question)

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
    "alert": f'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="{RED}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.46 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>',
    "shield": f'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="{GREEN}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/></svg>',
    "wrench": f'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="{AMBER}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>',
    "clock": f'<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></svg>',
    "bell": f'<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="{AMBER}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>',
    "bell-off": f'<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="{MUTED}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M8.7 3A6 6 0 0 1 18 8c0 2.4.6 4.2 1.2 5.5M17.6 17.6C17 18.2 12 21 12 21H6s3-2 3-9c0-.2 0-.5.02-.7"/><line x1="2" y1="2" x2="22" y2="22"/></svg>',
    "check": f'<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="{GREEN}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>',
}


def svg(name: str) -> str:
    return ICONS[name]


st.set_page_config(page_title="Foreman — reasoning brain",
                   page_icon=Image.open(LOGO_PATH), layout="wide")

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
.fm-logo-img {{ width: 34px; height: 34px; object-fit: contain; }}
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

/* ===== GRAPH FILTER TOOLBAR ===== */
.stCheckbox label {{
    font-size: .82rem !important;
    font-weight: 500 !important;
    color: {MUTED} !important;
    transition: color 200ms ease;
}}
.stCheckbox label:hover {{
    color: {TEXT} !important;
}}
.stCheckbox [data-testid="stCheckbox"] {{
    background: rgba(255,255,255,0.03);
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: .3rem .65rem;
    transition: all 200ms ease;
}}
.stCheckbox [data-testid="stCheckbox"]:hover {{
    border-color: rgba(245,166,35,0.25);
    background: rgba(255,255,255,0.05);
}}
/* Search input in toolbar */
.stTextInput input {{
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid {BORDER} !important;
    border-radius: 8px !important;
    color: {TEXT} !important;
    font-size: .82rem !important;
    padding: .35rem .7rem !important;
    transition: border-color 200ms ease !important;
}}
.stTextInput input:focus {{
    border-color: {AMBER} !important;
    box-shadow: 0 0 0 1px rgba(245,166,35,0.15) !important;
}}
.stTextInput input::placeholder {{
    color: rgba(138,143,160,0.6) !important;
}}

/* ===== SLIPPED CARD ===== */
@keyframes cardSlideIn {{
    from {{ opacity: 0; transform: translateY(12px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
}}
.slipped-card-container {{
    background: linear-gradient(180deg, rgba(255,255,255,0.045) 0%, rgba(255,255,255,0.015) 100%);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 12px;
    padding: 1.2rem;
    margin-bottom: 1.2rem;
    box-shadow: 0 4px 14px rgba(0,0,0,0.3);
    animation: cardSlideIn 250ms cubic-bezier(0.1, 0.8, 0.2, 1) forwards;
    transition: all 200ms ease;
}}
.slipped-card-container:hover {{
    border-color: rgba(224,90,80,0.3);
    box-shadow: 0 0 0 1px rgba(224,90,80,0.15), 0 6px 22px rgba(0,0,0,0.4);
}}
.pulse-badge {{
    animation: pulse-soft 1.8s ease-in-out infinite;
}}

@property --num {{
    syntax: '<integer>';
    initial-value: 0;
    inherits: false;
}}
@keyframes countUp {{
    from {{ --num: 0; }}
    to   {{ --num: var(--target); }}
}}
.count-up-days {{
    animation: countUp 1.2s cubic-bezier(0.1, 0.8, 0.2, 1) forwards;
    counter-reset: num var(--num);
    display: inline-block;
}}
.count-up-days::after {{
    content: counter(num) " days";
}}

/* ===== ABSORBED ITEM ===== */
.absorbed-item {{
    background: rgba(62,175,110,0.035);
    border: 1px solid rgba(62,175,110,0.12);
    border-radius: 8px;
    padding: 0.65rem 0.85rem;
    margin-bottom: 0.55rem;
    display: flex;
    align-items: center;
    transition: all 200ms ease;
}}
.absorbed-item:hover {{
    background: rgba(62,175,110,0.06);
    border-color: rgba(62,175,110,0.25);
    transform: translateX(2px);
}}

/* ===== EXPANDER OVERRIDES ===== */
.streamlit-expanderHeader {{
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 600;
    color: {TEXT} !important;
}}
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------ data
if "reminders" not in st.session_state:
    st.session_state.reminders = {}

g = build_graph()
s = graph_summary(g)
baseline_handover = run_cascade(g, "MAT-1", 0).baseline_handover

# ---------------------------------------------------------------- header
st.markdown(f"""
<div class="fm-wordmark"><img src="{_logo_data_uri()}" alt="Foreman" class="fm-logo-img"><span class="name">FOREMAN<span class="dot">.</span></span></div>
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

tab_sim, tab_radar, tab_ask = st.tabs(
    ["Delay Cascade Simulator", "Risk Radar", "Ask Foreman"])

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

    # -------------------------------------------------------- graph toolbar
    st.markdown(f"""<div style="display:flex;align-items:center;gap:.5rem;margin:.6rem 0 .3rem">
        <span style="font-size:.65rem;font-weight:700;letter-spacing:.15em;text-transform:uppercase;color:{STEEL}">
        GRAPH CONTROLS</span>
        <span style="flex:1;height:1px;background:{BORDER}"></span>
    </div>""", unsafe_allow_html=True)
    toolbar_cols = st.columns([1.2, 1.2, 1.2, 1.4, 2])
    with toolbar_cols[0]:
        show_suppliers = st.checkbox("Suppliers", value=True, key="gf_sup")
    with toolbar_cols[1]:
        show_materials = st.checkbox("Materials", value=True, key="gf_mat")
    with toolbar_cols[2]:
        show_activities = st.checkbox("Activities", value=True, key="gf_act")
    with toolbar_cols[3]:
        critical_only = st.checkbox("Critical path only", value=False, key="gf_crit")
    with toolbar_cols[4]:
        search_node = st.text_input(
            "Highlight node", placeholder="e.g. MAT-2",
            key="gf_search", label_visibility="collapsed")

    # ------------------------------------------------------------- graph
    slipped_ids = {e["activity"] for e in r.slipped}

    # Determine which nodes are on the critical/cascade path
    hot = slipped_ids | {mat_id}
    # Build full critical connected set including suppliers upstream of mat_id
    critical_set = set(hot)
    for pred in g.predecessors(mat_id):
        critical_set.add(pred)
    for act_id in slipped_ids:
        for pred in g.predecessors(act_id):
            if g.nodes[pred]["kind"] == MATERIAL and pred in hot:
                for pp in g.predecessors(pred):
                    critical_set.add(pp)

    # Build search highlight set
    search_set = set()
    search_q = search_node.strip().upper() if search_node else ""
    if search_q:
        for n in g.nodes():
            if search_q in n.upper() or search_q in g.nodes[n].get("name", "").upper():
                search_set.add(n)
                search_set |= set(g.predecessors(n))
                search_set |= set(g.successors(n))

    # Category visibility filter
    kind_visible = set()
    if show_suppliers:
        kind_visible.add(SUPPLIER)
    if show_materials:
        kind_visible.add(MATERIAL)
    if show_activities:
        kind_visible.add(ACTIVITY)

    # Filter nodes
    visible_nodes = set()
    for n, d in g.nodes(data=True):
        if d["kind"] not in kind_visible:
            continue
        if critical_only and n not in critical_set:
            continue
        visible_nodes.add(n)

    # Layout: normalized coordinates (0..1 x, spaced y) for responsive fit
    layers = {SUPPLIER: 0, MATERIAL: 1, ACTIVITY: 2}
    layer_nodes = {0: [], 1: [], 2: []}
    for n in sorted(visible_nodes):
        d = g.nodes[n]
        layer_nodes[layers[d["kind"]]].append(n)

    max_count = max((len(v) for v in layer_nodes.values()), default=1)
    pos = {}
    # Use 3 evenly spaced columns at x = 0.0, 0.5, 1.0
    for layer_idx, nodes in layer_nodes.items():
        x_pos = layer_idx * 0.5
        n_nodes = len(nodes)
        for i, n in enumerate(nodes):
            # Center vertically with even spacing
            if n_nodes == 1:
                y_pos = 0.0
            else:
                y_pos = -(i - (n_nodes - 1) / 2) * (1.0 / max(max_count - 1, 1))
            pos[n] = (x_pos, y_pos)

    # ---- Edge helpers: bezier curves + color-coding ----
    def bezier_edge(x0, y0, x1, y1, n_pts=20):
        """Generate a smooth cubic bezier curve between two points."""
        cx = (x0 + x1) / 2  # control point at midpoint x
        xs, ys = [], []
        for i in range(n_pts + 1):
            t = i / n_pts
            # Cubic bezier with control points creating a smooth S-curve
            bx = (1-t)**3 * x0 + 3*(1-t)**2*t * cx + 3*(1-t)*t**2 * cx + t**3 * x1
            by = (1-t)**3 * y0 + 3*(1-t)**2*t * (y0 + (y1-y0)*0.15) + 3*(1-t)*t**2 * (y0 + (y1-y0)*0.85) + t**3 * y1
            xs.append(bx)
            ys.append(by)
        xs.append(None); ys.append(None)
        return xs, ys

    # Classify edges into 3 tiers: critical (red), delayed (amber), normal (grey)
    cold_x, cold_y = [], []
    amber_x, amber_y = [], []
    hot_x, hot_y = [], []

    for u, v in g.edges():
        if u not in visible_nodes or v not in visible_nodes:
            continue
        bx, by = bezier_edge(pos[u][0], pos[u][1], pos[v][0], pos[v][1])
        # Determine edge category
        u_hot = u in hot
        v_hot = v in hot
        if u_hot and v_hot:
            hot_x += bx; hot_y += by       # critical path — red
        elif u_hot or v_hot:
            amber_x += bx; amber_y += by   # delayed-adjacent — amber
        else:
            cold_x += bx; cold_y += by      # normal — grey

    # ---- Build node arrays ----
    node_x, node_y = [], []
    node_colors, node_sizes, node_texts, node_borders = [], [], [], []
    node_labels = []
    glow_x, glow_y, glow_colors = [], [], []

    for n in visible_nodes:
        d = g.nodes[n]
        nx_pos, ny_pos = pos[n]
        # Determine if dimmed by search
        is_dimmed = bool(search_set) and n not in search_set

        node_x.append(nx_pos); node_y.append(ny_pos)

        if is_dimmed:
            node_colors.append("rgba(46,52,64,0.35)")
            node_sizes.append(9)
            node_borders.append("rgba(107,125,147,0.1)")
        elif n == mat_id:
            node_colors.append(AMBER); node_sizes.append(26)
            node_borders.append(AMBER)
            glow_x.append(nx_pos); glow_y.append(ny_pos)
            glow_colors.append("rgba(245,166,35,0.18)")
        elif n in slipped_ids:
            node_colors.append(RED); node_sizes.append(20)
            node_borders.append(RED)
            glow_x.append(nx_pos); glow_y.append(ny_pos)
            glow_colors.append("rgba(224,90,80,0.18)")
        elif n == g.graph["handover"] and r.handover_slip_days == 0:
            node_colors.append(GREEN); node_sizes.append(20)
            node_borders.append(GREEN)
            glow_x.append(nx_pos); glow_y.append(ny_pos)
            glow_colors.append("rgba(62,175,110,0.18)")
        else:
            node_colors.append(DIM_NODE); node_sizes.append(13)
            node_borders.append(STEEL)

        kind_label = {"supplier": "SUP", "material": "MAT", "activity": "ACT"}
        short_name = d.get("name", "")
        if len(short_name) > 30:
            short_name = short_name[:28] + "…"
        node_labels.append(n if is_dimmed else n)
        node_texts.append(
            f"<b>{n}</b><br>{d.get('name','')}<br>"
            f"<span style='color:{MUTED}'>{kind_label.get(d['kind'], '')}</span>")

    fig = go.Figure()

    # Layer 0: Normal edges (grey)
    if cold_x:
        fig.add_trace(go.Scatter(
            x=cold_x, y=cold_y, mode="lines",
            line=dict(color="rgba(107,125,147,0.15)", width=1, shape="spline"),
            hoverinfo="none", showlegend=False))

    # Layer 1: Delayed-adjacent edges (amber)
    if amber_x:
        fig.add_trace(go.Scatter(
            x=amber_x, y=amber_y, mode="lines",
            line=dict(color="rgba(245,166,35,0.4)", width=1.8, shape="spline"),
            hoverinfo="none", showlegend=False))

    # Layer 2: Critical path edges (red)
    if hot_x:
        fig.add_trace(go.Scatter(
            x=hot_x, y=hot_y, mode="lines",
            line=dict(color=RED, width=2.8, shape="spline"),
            hoverinfo="none", showlegend=False))

    # Layer 3: Glow rings behind highlighted nodes
    if glow_x:
        fig.add_trace(go.Scatter(
            x=glow_x, y=glow_y, mode="markers",
            marker=dict(size=40, color=glow_colors,
                        line=dict(width=0), opacity=0.5),
            hoverinfo="none", showlegend=False))

    # Layer 4: Nodes
    fig.add_trace(go.Scatter(
        x=node_x, y=node_y, mode="markers+text",
        marker=dict(
            size=node_sizes, color=node_colors,
            line=dict(color=node_borders, width=1.5),
            opacity=0.95),
        text=node_labels, textposition="middle right",
        textfont=dict(color=MUTED, size=10, family="Inter"),
        hovertext=node_texts, hoverinfo="text",
        hoverlabel=dict(
            bgcolor="#1A1D24",
            bordercolor=AMBER,
            font=dict(family="Inter", size=12, color=TEXT)),
        showlegend=False))

    # Column header annotations
    col_headers = []
    if show_suppliers:
        col_headers.append((0.0, "SUPPLIERS"))
    if show_materials:
        col_headers.append((0.5, "MATERIALS"))
    if show_activities:
        col_headers.append((1.0, "ACTIVITIES"))

    annotations = []
    y_max = max((p[1] for p in pos.values()), default=0.5) if pos else 0.5
    for col_x, label in col_headers:
        annotations.append(dict(
            x=col_x, y=y_max + 0.18,
            text=f"<b>{label}</b>",
            showarrow=False,
            font=dict(family="Inter", size=10, color=STEEL,
                      weight=700),
            xanchor="center", yanchor="bottom"))

    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        height=max(380, 48 * max_count + 100),
        xaxis=dict(
            visible=False, range=[-0.12, 1.25],
            constrain="domain", fixedrange=True),
        yaxis=dict(
            visible=False, scaleanchor="x", scaleratio=0.6,
            fixedrange=True),
        margin=dict(l=10, r=10, t=35, b=10),
        hoverdistance=30,
        annotations=annotations,
        dragmode=False)

    # Graph canvas container
    st.markdown('<div class="graph-canvas">', unsafe_allow_html=True)
    st.plotly_chart(fig, use_container_width=True,
                    config={"displayModeBar": False, "staticPlot": False,
                            "scrollZoom": False})
    # Embedded legend
    st.markdown(f"""
    <div class="graph-legend">
        <span style="display:inline-flex;align-items:center;gap:.3rem">
            <span style="color:{AMBER};font-size:.6rem">⬤</span>
            <span>delayed material</span></span>
        <span style="display:inline-flex;align-items:center;gap:.3rem">
            <span style="color:{RED};font-size:.6rem">⬤</span>
            <span>slipped / critical path</span></span>
        <span style="display:inline-flex;align-items:center;gap:.3rem">
            <span style="color:{GREEN};font-size:.6rem">⬤</span>
            <span>safe (handover)</span></span>
        <span style="display:inline-flex;align-items:center;gap:.3rem">
            <span style="color:{DIM_NODE};font-size:.6rem">⬤</span>
            <span>unaffected</span></span>
        <span style="margin-left:.6rem;border-left:1px solid rgba(255,255,255,0.08);padding-left:.8rem;display:inline-flex;align-items:center;gap:.3rem">
            <span style="display:inline-block;width:18px;height:2px;background:rgba(107,125,147,0.3);border-radius:1px"></span>
            <span>normal</span></span>
        <span style="display:inline-flex;align-items:center;gap:.3rem">
            <span style="display:inline-block;width:18px;height:2px;background:rgba(245,166,35,0.5);border-radius:1px"></span>
            <span>delayed</span></span>
        <span style="display:inline-flex;align-items:center;gap:.3rem">
            <span style="display:inline-block;width:18px;height:2.5px;background:{RED};border-radius:1px"></span>
            <span>critical</span></span>
    </div>
    </div>""", unsafe_allow_html=True)

    # ----------------------------------------------------------- details
    cA, cB = st.columns(2)
    with cA:
        st.markdown(f'<div class="hd" style="margin-bottom:0.8rem;">activities that slip ({len(r.slipped)})</div>', unsafe_allow_html=True)
        if not r.slipped:
            st.markdown(f"<span style='color:{MUTED}'>None — float absorbs everything.</span>", unsafe_allow_html=True)
        else:
            for e in r.slipped:
                act_id = e['activity']
                
                # Fetch upstream material confidence and source if available
                act_node = g.nodes[act_id]
                mats = act_node.get("needs_materials", [])
                if mats:
                    mat_conf = g.nodes[mats[0]]["confidence"]
                    mat_source = g.nodes[mats[0]]["confidence_source"]
                else:
                    mat_conf = r.confidence
                    mat_source = r.confidence_source

                # Bell icon toggle state
                bell_key = f"bell_{act_id}"
                if bell_key not in st.session_state:
                    st.session_state[bell_key] = True
                
                bell_active = st.session_state[bell_key]

                # Slipped card HTML container
                st.markdown(f"""
                <div class="slipped-card-container">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
                        <span style="font-family:'Space Grotesk'; font-weight:800; font-size:1.15rem; color:{TEXT};">{act_id}</span>
                        <span class="badge red pulse-badge">CRITICAL SLIP</span>
                    </div>
                    <div style="font-size:0.95rem; font-weight:600; color:{TEXT}; margin-bottom:0.7rem; line-height:1.2;">{e['name']}</div>
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:1rem; border-top:1px solid rgba(255,255,255,0.06); padding-top:0.7rem; margin-bottom:0.7rem;">
                        <div>
                            <div style="font-size:0.6rem; color:{MUTED}; text-transform:uppercase; letter-spacing:0.12em; margin-bottom:0.1rem;">Delay Duration</div>
                            <div class="count-up-days" style="--target:{e['slip_days']}; font-family:'Space Grotesk'; font-weight:800; font-size:1.15rem; color:{RED};"></div>
                        </div>
                        <div>
                            <div style="font-size:0.6rem; color:{MUTED}; text-transform:uppercase; letter-spacing:0.12em; margin-bottom:0.1rem;">Confidence</div>
                            <div style="font-family:'Space Grotesk'; font-weight:800; font-size:1.15rem; color:{TEXT};">{mat_conf:.0%}</div>
                        </div>
                    </div>
                    <div style="font-size:0.78rem; color:{MUTED}; border-top:1px solid rgba(255,255,255,0.06); padding-top:0.6rem; line-height:1.35; margin-bottom:0.6rem;">
                        <strong>Source:</strong> {mat_source}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Set Reminder Controls / Bell icon
                action_col1, action_col2 = st.columns([4, 1])
                with action_col1:
                    reminder_data = st.session_state.reminders.get(act_id)
                    if reminder_data:
                        note_text = reminder_data['note']
                        note_short = f" ({note_text[:12]}...)" if note_text else ""
                        st.markdown(f"""
                        <div style="display:inline-flex; align-items:center; gap:.4rem; background:rgba(245,166,35,0.08); border:1px solid rgba(245,166,35,0.25); border-radius:6px; padding:0.25rem 0.6rem; font-size:0.78rem; color:{AMBER}; font-weight:600; margin-bottom:0.5rem; width:100%;">
                            {svg("bell")} Reminder: {reminder_data['date'].strftime('%b %d')} @ {reminder_data['time'].strftime('%H:%M')}{note_short}
                        </div>
                        """, unsafe_allow_html=True)

                        btn_col1, btn_col2 = st.columns(2)
                        with btn_col1:
                            if st.button("Edit", key=f"edit_btn_{act_id}", use_container_width=True):
                                st.session_state[f"show_form_{act_id}"] = True
                                st.rerun()
                        with btn_col2:
                            if st.button("Dismiss", key=f"dismiss_btn_{act_id}", use_container_width=True):
                                st.session_state.reminders.pop(act_id, None)
                                st.rerun()
                    else:
                        if not st.session_state.get(f"show_form_{act_id}"):
                            if st.button("Set Reminder", key=f"set_btn_{act_id}", use_container_width=True):
                                st.session_state[f"show_form_{act_id}"] = True
                                st.rerun()

                with action_col2:
                    if st.button("On" if bell_active else "Off", key=f"bell_btn_{act_id}", use_container_width=True, help="Toggle notifications"):
                        st.session_state[bell_key] = not bell_active
                        st.rerun()

                # Form render
                if st.session_state.get(f"show_form_{act_id}"):
                    with st.form(key=f"reminder_form_el_{act_id}"):
                        st.markdown(f"<div style='font-size:0.85rem; font-weight:700; color:{AMBER}; margin-bottom:0.5rem;'>Set Reminder for {act_id}</div>", unsafe_allow_html=True)
                        default_date = datetime.date.today()
                        default_time = datetime.time(9, 0)
                        default_note = ""
                        if reminder_data:
                            default_date = reminder_data["date"]
                            default_time = reminder_data["time"]
                            default_note = reminder_data["note"]

                        r_date = st.date_input("Reminder Date", value=default_date, key=f"r_date_{act_id}")
                        r_time = st.time_input("Reminder Time", value=default_time, key=f"r_time_{act_id}")
                        r_note = st.text_input("Notes", value=default_note, placeholder="Action item...", key=f"r_note_{act_id}")
                        
                        f_col1, f_col2 = st.columns(2)
                        with f_col1:
                            if st.form_submit_button("Save", use_container_width=True):
                                st.session_state.reminders[act_id] = {
                                    "date": r_date,
                                    "time": r_time,
                                    "note": r_note
                                }
                                st.session_state[f"show_form_{act_id}"] = False
                                st.rerun()
                        with f_col2:
                            if st.form_submit_button("Cancel", use_container_width=True):
                                st.session_state[f"show_form_{act_id}"] = False
                                st.rerun()
                
                st.markdown("<div style='margin-bottom:1.5rem; border-bottom:1px solid rgba(255,255,255,0.04);'></div>", unsafe_allow_html=True)
    with cB:
        st.markdown(f'<div class="hd" style="margin-bottom:0.8rem;">absorbed by float ({len(r.absorbed)})</div>', unsafe_allow_html=True)
        if not r.absorbed:
            st.markdown(f"<span style='color:{MUTED}'>—</span>", unsafe_allow_html=True)
        else:
            for e in r.absorbed:
                st.markdown(f"""
                <div class="absorbed-item">
                    <span style="font-family:'Space Grotesk'; font-weight:700; color:{GREEN}; font-size:1.05rem; display:inline-flex; align-items:center; gap:0.35rem; width:80px; flex-shrink:0;">
                        {svg("check")} {e['activity']}
                    </span>
                    <span style="color:{TEXT}; font-size:0.88rem; font-weight:500; line-height:1.2;">
                        {e['name']}
                    </span>
                </div>
                """, unsafe_allow_html=True)

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


# ------------------------------------------------------------------ Ask Foreman
with tab_ask:
    st.markdown(
        f'<div style="color:{MUTED};font-size:.9rem;margin:.2rem 0 1rem">'
        f'Ask about the project in plain English. Foreman writes a Cypher query '
        f'against the knowledge graph, runs it, and answers — you can watch every '
        f'step it takes.</div>', unsafe_allow_html=True)

    examples = [
        "Which materials have confidence below 0.75?",
        "If the diesel generators are delayed, what activities are affected?",
        "Who supplies the switchgear and when does it arrive?",
    ]
    st.markdown(
        '<div style="color:#6B7D93;font-size:.72rem;text-transform:uppercase;'
        'letter-spacing:.14em;margin-bottom:.4rem">try asking</div>',
        unsafe_allow_html=True)
    ex_cols = st.columns(len(examples))
    picked = None
    for col, ex in zip(ex_cols, examples):
        if col.button(ex, key=f"ex_{ex}"):
            picked = ex

    if "chat" not in st.session_state:
        st.session_state.chat = []

    typed = st.chat_input("Ask Foreman about the project…")
    question = picked or typed

    # Render history first (older on top).
    for turn in st.session_state.chat:
        with st.chat_message("user"):
            st.markdown(turn["q"])
        with st.chat_message("assistant"):
            st.markdown(turn["answer"])
            if turn.get("citations"):
                chips = " ".join(
                    f'<span class="badge orange">{c}</span>' for c in turn["citations"])
                st.markdown(f'<div style="margin-top:.4rem">{chips}</div>',
                            unsafe_allow_html=True)
            with st.expander("🧠 reasoning trace"):
                for step in turn["trace"]:
                    st.markdown(
                        f'<div class="card" style="margin-bottom:.4rem"><div class="hd">'
                        f'{step["step"]}</div><code style="color:#8BA3BD;font-size:.8rem;'
                        f'white-space:pre-wrap">{step["detail"]}</code></div>',
                        unsafe_allow_html=True)

    if question:
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            try:
                with st.spinner("reasoning over the graph…"):
                    res = _ask_brain(question)
                st.markdown(res["answer"])
                if res.get("citations"):
                    chips = " ".join(
                        f'<span class="badge orange">{c}</span>' for c in res["citations"])
                    st.markdown(f'<div style="margin-top:.4rem">{chips}</div>',
                                unsafe_allow_html=True)
                with st.expander("🧠 reasoning trace", expanded=True):
                    for step in res.get("trace", []):
                        st.markdown(
                            f'<div class="card" style="margin-bottom:.4rem"><div class="hd">'
                            f'{step["step"]}</div><code style="color:#8BA3BD;font-size:.8rem;'
                            f'white-space:pre-wrap">{step["detail"]}</code></div>',
                            unsafe_allow_html=True)
                st.session_state.chat.append({
                    "q": question, "answer": res["answer"],
                    "citations": res.get("citations", []), "trace": res.get("trace", []),
                })
            except Exception as e:
                st.error(
                    "The reasoning agent isn't available. Make sure GEMINI_API_KEY "
                    f"is set in .env and Neo4j is running.\n\n{e}")
