"""
Hidden Value in E2E Visibility — Capstone Results Dashboard
MIT SCM 2026 | J. Cermeño, R. Rodas

Mobile-responsive Streamlit app for symposium audience access via QR code.
Switches between four focal companies and shows three views per company:
  1. Risk Discovery (Tier-1 disruption probability by visibility level)
  2. Value of Information (VOI cost reduction curve)
  3. Supply Chain Network Topology (D3 force-directed graph)
"""

import json
import os
import sqlite3
import sys
from pathlib import Path
from types import ModuleType

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image

# ---------------------------------------------------------------------------
# PyArrow shim — prevents Streamlit table engine crash in some environments
# ---------------------------------------------------------------------------
if 'pyarrow' not in sys.modules or sys.modules['pyarrow'] is None:
    mock_pa = ModuleType('pyarrow')
    mock_pa.Table = type('Table', (), {})
    mock_pa.ChunkedArray = type('ChunkedArray', (), {})

    class MockArrowError(Exception):
        pass

    mock_pa.ArrowTypeError = MockArrowError
    mock_pa.ArrowInvalid = MockArrowError
    mock_pa.ArrowNotImplementedError = MockArrowError
    sys.modules['pyarrow'] = mock_pa


# ---------------------------------------------------------------------------
# 1. CONFIG & PATHS  (relative — works locally and on Streamlit Cloud)
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "supply_chain.db"
LOGO_PATH = BASE_DIR / "DSCTL_logo.png"
FAVICON_PATH = BASE_DIR / "faviconV2.png"


# Use the custom favicon if present; fall back to a globe emoji.
_page_icon = str(FAVICON_PATH) if FAVICON_PATH.exists() else "🌐"

st.set_page_config(
    page_title="Hidden Value in E2E Visibility",
    page_icon=_page_icon,
    layout="wide",
    initial_sidebar_state="collapsed",  # collapsed by default for mobile
)


# ---------------------------------------------------------------------------
# 2. MOBILE-FRIENDLY CSS
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
      /* Tighten page padding on small screens */
      .block-container {
          padding-top: 1.2rem;
          padding-bottom: 2rem;
          padding-left: 1rem;
          padding-right: 1rem;
          max-width: 1100px;
      }

      /* Header styling */
      .app-header {
          background: linear-gradient(135deg, #1E5DBE 0%, #3B7DD8 100%);
          color: white;
          padding: 1.2rem 1.4rem;
          border-radius: 12px;
          margin-bottom: 1.2rem;
      }
      .app-header h1 {
          color: white;
          margin: 0;
          font-size: 1.4rem;
          font-weight: 700;
          line-height: 1.3;
      }
      .app-header p {
          color: #d6e3f5;
          margin: 0.3rem 0 0 0;
          font-size: 0.85rem;
      }

      /* Section cards */
      .section-title {
          font-size: 1.05rem;
          font-weight: 700;
          color: #1E5DBE;
          margin: 1.5rem 0 0.4rem 0;
      }
      .section-sub {
          font-size: 0.85rem;
          color: #555;
          margin: 0 0 0.8rem 0;
      }

      /* KPI tiles */
      .kpi-row {
          display: flex;
          gap: 0.6rem;
          flex-wrap: wrap;
          margin-bottom: 0.8rem;
      }
      .kpi {
          flex: 1 1 140px;
          background: #f4f7fb;
          border-radius: 8px;
          padding: 0.7rem 0.8rem;
          border-left: 4px solid #1E5DBE;
      }
      .kpi-label {
          font-size: 0.72rem;
          color: #555;
          text-transform: uppercase;
          letter-spacing: 0.4px;
      }
      .kpi-value {
          font-size: 1.25rem;
          font-weight: 700;
          color: #1E5DBE;
          line-height: 1.2;
      }
      .kpi-sub {
          font-size: 0.7rem;
          color: #888;
      }

      /* Segmented company picker — st.radio horizontal layout */
      div[role="radiogroup"] {
          gap: 0.4rem;
          flex-wrap: wrap;
      }
      div[role="radiogroup"] > label {
          background: #f0f3f8;
          border: 1px solid #d6dde6;
          border-radius: 8px;
          padding: 0.45rem 0.9rem;
          margin: 0 !important;
          cursor: pointer;
          font-weight: 600;
          font-size: 0.85rem;
          transition: all 0.15s;
      }
      div[role="radiogroup"] > label:hover {
          background: #e3eaf5;
      }
      div[role="radiogroup"] > label[data-checked="true"],
      div[role="radiogroup"] > label:has(input:checked) {
          background: #1E5DBE;
          color: white;
          border-color: #1E5DBE;
      }
      /* Force white text on the label content (Streamlit wraps it in a child element) */
      div[role="radiogroup"] > label[data-checked="true"] *,
      div[role="radiogroup"] > label:has(input:checked) * {
          color: white !important;
      }
      div[role="radiogroup"] > label > div:first-child { display: none; }  /* hide radio circle */

      /* Tighten on phones */
      @media (max-width: 640px) {
          .app-header h1 { font-size: 1.15rem; }
          .block-container { padding-left: 0.6rem; padding-right: 0.6rem; }
          .kpi { flex: 1 1 100%; }
          div[role="radiogroup"] > label {
              flex: 1 1 45%;
              text-align: center;
              font-size: 0.78rem;
              padding: 0.4rem 0.5rem;
          }
      }

      /* Hide Streamlit footer/menu noise for kiosk feel */
      #MainMenu { visibility: hidden; }
      footer { visibility: hidden; }

      /* Tables: full width, readable on mobile */
      table { width: 100%; font-size: 0.85rem; border-collapse: collapse; }
      th { background: #f0f3f8 !important; color: #1E5DBE !important;
           padding: 8px 10px !important; text-align: left; font-weight: 600;
           border-bottom: 2px solid #d6dde6; }
      td { padding: 7px 10px !important; border-bottom: 1px solid #eef0f3; }
      tbody tr:nth-child(even) { background: #fafbfd; }
      tbody tr:hover { background: #eef3fb; }
      /* Highlight rows explicitly marked as summary (network average) */
      tbody tr.summary-row {
          background: #e8efff !important;
          font-weight: 700;
          border-top: 2px solid #1E5DBE;
          border-bottom: 2px solid #1E5DBE;
      }
      tbody tr.summary-row td { color: #1E5DBE; }
      @media (max-width: 640px) {
          table { font-size: 0.78rem; }
          th, td { padding: 6px 6px !important; }
      }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# 3. DATA HELPERS
# ---------------------------------------------------------------------------
# NOTE: We intentionally do NOT use @st.cache_data here. SQLite reads on a
# ~100MB local DB are millisecond-fast, and caching has bitten us before by
# returning empty results from a prior failed run. If perf ever becomes an
# issue, add caching back deliberately at the call site.

def run_query(query: str, params: tuple = ()):
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql(query, conn, params=params)


def get_companies():
    """Return sorted list of focal companies present in the DB."""
    try:
        df = run_query("SELECT DISTINCT focal_company FROM model_runs ORDER BY focal_company")
        names = df['focal_company'].dropna().tolist()
        if names:
            return names
    except Exception:
        pass
    # Fallback if DB hiccups
    return ["Danone", "Intel Corp", "Mondelez International Inc", "NVIDIA Corp"]


def get_runs_for_company(focal: str):
    """All model_run_ids for a company (typically four safety-stock levels)."""
    df = run_query(
        "SELECT model_run_id FROM model_runs WHERE focal_company = ? ORDER BY model_run_id",
        (focal,),
    )
    return df['model_run_id'].tolist()


def parent_run_id_from_full(rid: str) -> str:
    """
    A full model_run_id is formatted like 'MOND_0507_1642_stan_10':
        PREFIX_DATE_TIME_TYPE_SS
    The parent_run_id used in bbn_p_matrix is just 'MOND_0507_1642'
    (first three underscore-separated tokens).
    """
    parts = rid.split("_")
    return "_".join(parts[:3]) if len(parts) >= 3 else rid


def get_latest_parent_run_id(focal: str):
    """
    Pick the most recent parent_run_id for a company (companies may have
    multiple timestamped runs; newer supersedes older).
    """
    runs = get_runs_for_company(focal)
    if not runs:
        return None
    parents = sorted({parent_run_id_from_full(r) for r in runs})
    # Lexicographic sort on PREFIX_DATE_TIME puts the most recent last.
    return parents[-1]


def get_runs_for_parent(focal: str, parent_run_id: str):
    """All full model_run_ids for a given company AND parent run."""
    runs = get_runs_for_company(focal)
    return [r for r in runs if parent_run_id_from_full(r) == parent_run_id]


def short_label(name: str) -> str:
    """Compact display name for segmented buttons."""
    mapping = {
        "Mondelez International Inc": "Mondelez",
        "NVIDIA Corp": "NVIDIA",
        "Intel Corp": "Intel",
        "Danone": "Danone",
    }
    return mapping.get(name, name.split()[0])


# ---------------------------------------------------------------------------
# 4. HEADER
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="app-header">
        <h1>Hidden Value in End-to-End Supply Chain Visibility</h1>
        <p>MIT SCM 2026 Capstone | J. Cermeño, R. Rodas | Advisors: Dr. M. Saenz, Dr. J. Macias</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# 5. COMPANY PICKER (segmented buttons, tap-friendly)
# ---------------------------------------------------------------------------
companies = get_companies()

# Order to match the deck (Mondelez, Danone, NVIDIA, Intel)
preferred_order = ["Mondelez International Inc", "Danone", "NVIDIA Corp", "Intel Corp"]
companies_sorted = [c for c in preferred_order if c in companies] + \
                   [c for c in companies if c not in preferred_order]

short_to_full = {short_label(c): c for c in companies_sorted}
short_names = list(short_to_full.keys())

picked_short = st.radio(
    "Select Company",
    short_names,
    horizontal=True,
    label_visibility="collapsed",
)
focal = short_to_full[picked_short]


# ---------------------------------------------------------------------------
# 6. SIDEBAR — minimal context (collapsed on mobile)
# ---------------------------------------------------------------------------
with st.sidebar:
    if LOGO_PATH.exists():
        try:
            st.image(Image.open(LOGO_PATH), use_container_width=True)
        except Exception:
            pass

    st.markdown("## Hidden Value in E2E Visibility")
    st.markdown(
        """
        MASc Supply Chain Management<br>
        Spring 2026 Capstone
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <style>
          .li-icon {
              display: inline-block;
              vertical-align: middle;
              margin-left: 3px;
              opacity: 0.75;
              transition: opacity 0.15s;
          }
          .li-icon:hover { opacity: 1; }
        </style>
        <div style="line-height: 1.4; font-size: 14px; margin-top: 0.8rem;">
            <b>Students:</b>
            J. Cermeño
            <a href="https://www.linkedin.com/in/juan-e-cerme%C3%B1o-blondet/" target="_blank" rel="noopener" class="li-icon" title="J. Cermeño on LinkedIn">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="#0A66C2" xmlns="http://www.w3.org/2000/svg"><path d="M20.45 20.45h-3.55v-5.57c0-1.33-.03-3.04-1.85-3.04-1.85 0-2.14 1.45-2.14 2.94v5.67H9.36V9h3.41v1.56h.05c.48-.9 1.64-1.85 3.37-1.85 3.6 0 4.27 2.37 4.27 5.45v6.29zM5.34 7.43a2.06 2.06 0 1 1 0-4.12 2.06 2.06 0 0 1 0 4.12zM7.12 20.45H3.56V9h3.56v11.45zM22.22 0H1.77C.79 0 0 .77 0 1.72v20.56C0 23.23.79 24 1.77 24h20.45c.98 0 1.78-.77 1.78-1.72V1.72C24 .77 23.2 0 22.22 0z"/></svg>
            </a>,
            R. Rodas
            <a href="https://www.linkedin.com/in/rafaelrodas/" target="_blank" rel="noopener" class="li-icon" title="R. Rodas on LinkedIn">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="#0A66C2" xmlns="http://www.w3.org/2000/svg"><path d="M20.45 20.45h-3.55v-5.57c0-1.33-.03-3.04-1.85-3.04-1.85 0-2.14 1.45-2.14 2.94v5.67H9.36V9h3.41v1.56h.05c.48-.9 1.64-1.85 3.37-1.85 3.6 0 4.27 2.37 4.27 5.45v6.29zM5.34 7.43a2.06 2.06 0 1 1 0-4.12 2.06 2.06 0 0 1 0 4.12zM7.12 20.45H3.56V9h3.56v11.45zM22.22 0H1.77C.79 0 0 .77 0 1.72v20.56C0 23.23.79 24 1.77 24h20.45c.98 0 1.78-.77 1.78-1.72V1.72C24 .77 23.2 0 22.22 0z"/></svg>
            </a>
            <br>
            <b>Advisors:</b> Dr. J. Macias, Dr. M. Saenz
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")

    st.markdown("### About this study")
    st.markdown(
        """
        This study measures the value of supply chain visibility.
        By modeling how disruptions cascade through multi‑tier supplier
        networks, we show how much firms can save by mapping beyond
        their direct suppliers.

        **Visibility levels**
        - **S1** — Tier‑1 only
        - **S2** — Tier‑1 & 2
        - **S3** — Tier‑1, 2 & 3
        """
    )

    st.markdown("---")
    st.caption("MIT Digital Supply Chain Transformation Lab · 2026")


# ---------------------------------------------------------------------------
# 7. PULL ALL DATA FOR THIS COMPANY ACROSS SAFETY-STOCK LEVELS
# ---------------------------------------------------------------------------
runs_all = get_runs_for_company(focal)
if not runs_all:
    st.error(f"No model runs found for {focal}.")
    st.stop()

# Companies may have multiple timestamped runs; use the most recent one.
parent_run_id = get_latest_parent_run_id(focal)
runs = get_runs_for_parent(focal, parent_run_id)


def get_voi_by_ss(focal: str, run_ids: tuple):
    """VOI dollars + cost columns by safety-stock level, for % calculation."""
    if not run_ids:
        return pd.DataFrame()
    placeholders = ",".join(["?"] * len(run_ids))
    q = f"""
        SELECT model_run_id,
               voi_s2, voi_s3,
               s1_cost_in_s2, s2_best_cost,
               s2_cost_in_s3, s3_best_cost
        FROM voi_log
        WHERE focal_company = ?
          AND model_run_id IN ({placeholders})
    """
    return run_query(q, (focal,) + tuple(run_ids))


def get_bbn_for_company(focal: str, parent_run_id: str):
    """BBN probabilities for the chosen parent_run_id."""
    q = """
        SELECT supplier_id, p_scenario_1 AS p1, p_scenario_2 AS p2, p_scenario_3 AS p3
        FROM bbn_p_matrix
        WHERE model_run_id = ?
    """
    return run_query(q, (parent_run_id,))


def get_meta(run_id: str):
    df = run_query(
        "SELECT industry_margin, avg_disruption_duration FROM model_runs WHERE model_run_id = ?",
        (run_id,),
    )
    return df.iloc[0].to_dict() if not df.empty else {}


voi_df_all = get_voi_by_ss(focal, tuple(runs))
bbn_df = get_bbn_for_company(focal, parent_run_id)
meta = get_meta(runs[0])


# ---------------------------------------------------------------------------
# Helper: extract safety-stock % from model_run_id suffix (e.g. '..._20' -> 20)
# ---------------------------------------------------------------------------
def ss_from_run_id(rid: str) -> int:
    try:
        return int(rid.split("_")[-1])
    except Exception:
        return 0


# ===========================================================================
# SECTION 1 — RISK DISCOVERY (slide 10 style)
# ===========================================================================
st.markdown(
    f'<div class="section-title">Risk Discovery — {short_label(focal)}</div>'
    f'<div class="section-sub">Average Tier‑1 supplier disruption probability '
    f'revealed at each visibility level. The risk doesn\'t grow — it just becomes visible.</div>',
    unsafe_allow_html=True,
)

if not bbn_df.empty:
    p1_avg = bbn_df['p1'].mean()
    p2_avg = bbn_df['p2'].mean()
    p3_avg = bbn_df['p3'].mean()
    multiplier = (p3_avg / p1_avg) if p1_avg else 0

    # KPI tiles
    st.markdown(
        f"""
        <div class="kpi-row">
            <div class="kpi">
                <div class="kpi-label">Tier‑1 Only (S1)</div>
                <div class="kpi-value">{p1_avg:.1%}</div>
                <div class="kpi-sub">Blind to upstream</div>
            </div>
            <div class="kpi">
                <div class="kpi-label">Tier‑1 &amp; 2 (S2)</div>
                <div class="kpi-value">{p2_avg:.1%}</div>
                <div class="kpi-sub">Partial visibility</div>
            </div>
            <div class="kpi">
                <div class="kpi-label">Tier‑1, 2 &amp; 3 (S3)</div>
                <div class="kpi-value">{p3_avg:.1%}</div>
                <div class="kpi-sub">Full visibility</div>
            </div>
            <div class="kpi" style="border-left-color:#D7263D;">
                <div class="kpi-label">Discovery Multiplier</div>
                <div class="kpi-value">{multiplier:.1f}×</div>
                <div class="kpi-sub">S3 vs S1</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Bar chart — average disruption probability by visibility level
    levels = ["L1 (Tier‑1 Only)", "L2 (Tier‑1 & 2)", "L3 (Tier‑1, 2 & 3)"]
    vals = [p1_avg, p2_avg, p3_avg]
    colors = ["#c9d6ea", "#5d87c4", "#1E5DBE"]

    fig_risk = go.Figure(
        go.Bar(
            x=levels,
            y=vals,
            marker_color=colors,
            text=[f"{v:.1%}" for v in vals],
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>Avg disruption probability: %{y:.2%}<extra></extra>",
        )
    )
    fig_risk.update_layout(
        height=320,
        margin=dict(l=10, r=10, t=20, b=10),
        yaxis=dict(tickformat=".0%", range=[0, max(vals) * 1.25], title=None),
        xaxis=dict(title=None),
        plot_bgcolor="white",
        showlegend=False,
    )
    st.plotly_chart(fig_risk, use_container_width=True, config={"displayModeBar": False})

    # --- BBN supplier-level table ---
    st.markdown(
        '<div style="font-size:0.9rem; font-weight:600; color:#1E5DBE; '
        'margin:0.8rem 0 0.3rem 0;">BBN Probability Matrix — Tier‑1 Suppliers</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Disruption probability per Tier‑1 supplier as visibility deepens. "
        "Each row is one supplier; columns show what the model reveals at each level."
    )

    bbn_tbl = bbn_df.copy()
    bbn_tbl.columns = ["Supplier", "S1 (Tier‑1)", "S2 (+ Tier‑2)", "S3 (+ Tier‑3)"]
    # Sort by S3 descending so the highest-risk suppliers surface first
    bbn_tbl = bbn_tbl.sort_values("S3 (+ Tier‑3)", ascending=False).reset_index(drop=True)

    # Add summary row
    summary_row = pd.DataFrame({
        "Supplier": ["Network Average"],
        "S1 (Tier‑1)": [bbn_tbl["S1 (Tier‑1)"].mean()],
        "S2 (+ Tier‑2)": [bbn_tbl["S2 (+ Tier‑2)"].mean()],
        "S3 (+ Tier‑3)": [bbn_tbl["S3 (+ Tier‑3)"].mean()],
    })

    # Format probabilities as %
    def fmt_pct(x):
        return f"{x:.1%}"

    display_tbl = bbn_tbl.copy()
    for c in ["S1 (Tier‑1)", "S2 (+ Tier‑2)", "S3 (+ Tier‑3)"]:
        display_tbl[c] = display_tbl[c].apply(fmt_pct)

    summary_display = summary_row.copy()
    for c in ["S1 (Tier‑1)", "S2 (+ Tier‑2)", "S3 (+ Tier‑3)"]:
        summary_display[c] = summary_display[c].apply(fmt_pct)

    # Helper: tag the "Network Average" row with a CSS class for styling
    def mark_summary_row(html: str) -> str:
        return html.replace(
            "<tr>\n      <td>Network Average</td>",
            '<tr class="summary-row">\n      <td>Network Average</td>',
            1,
        )

    # Truncate to top 15 by default; expander reveals the REMAINING suppliers only
    n_total = len(display_tbl)
    if n_total > 15:
        top_tbl = pd.concat([summary_display, display_tbl.head(15)], ignore_index=True)
        st.write(
            mark_summary_row(
                top_tbl.to_html(index=False, classes="table", border=0, escape=False)
            ),
            unsafe_allow_html=True,
        )
        with st.expander(f"Show remaining {n_total - 15} Tier‑1 suppliers"):
            rest_tbl = display_tbl.iloc[15:].reset_index(drop=True)
            st.write(
                rest_tbl.to_html(index=False, classes="table", border=0, escape=False),
                unsafe_allow_html=True,
            )
    else:
        full_tbl = pd.concat([summary_display, display_tbl], ignore_index=True)
        st.write(
            mark_summary_row(
                full_tbl.to_html(index=False, classes="table", border=0, escape=False)
            ),
            unsafe_allow_html=True,
        )

    with st.expander("Why looking deeper changes the answer"):
        st.markdown(
            """
            - **Tier‑1 suppliers don't fail in isolation** — they depend on Tier‑2,
              which depends on Tier‑3.
            - Each invisible upstream link is an **independent failure mode** the
              firm wasn't accounting for.
            - Small per‑link failure probabilities **compound multiplicatively**
              when stacked across tiers.
            """
        )
else:
    st.info("No BBN probability data found for this company.")


# ===========================================================================
# SECTION 2 — VALUE OF INFORMATION (slide 14 style)
# ===========================================================================
st.markdown(
    f'<div class="section-title">Value of Information — {short_label(focal)}</div>'
    f'<div class="section-sub">Cost reduction unlocked by deeper visibility, '
    f'measured at four safety‑stock levels.</div>',
    unsafe_allow_html=True,
)

if not voi_df_all.empty:
    voi_df_all = voi_df_all.copy()
    voi_df_all["ss"] = voi_df_all["model_run_id"].apply(ss_from_run_id)

    # Aggregate across iterations within each safety-stock level.
    # VOI % is computed from MEAN costs (matches the deck's expected-value framing):
    #   VOI_S2 % = (mean s1_cost_in_s2 − mean s2_best_cost) / mean s1_cost_in_s2
    #   VOI_S3 % = (mean s2_cost_in_s3 − mean s3_best_cost) / mean s2_cost_in_s3
    agg = (
        voi_df_all.groupby("ss", as_index=False)
        .agg({
            "voi_s2": "mean",          # dollar savings, S1→S2
            "voi_s3": "mean",          # dollar savings, S2→S3
            "s1_cost_in_s2": "mean",
            "s2_best_cost": "mean",
            "s2_cost_in_s3": "mean",
            "s3_best_cost": "mean",
        })
        .sort_values("ss")
    )

    # Guard against zero denominators
    agg["voi_s2_pct"] = (agg["s1_cost_in_s2"] - agg["s2_best_cost"]) / agg["s1_cost_in_s2"].replace(0, pd.NA)
    agg["voi_s3_pct"] = (agg["s2_cost_in_s3"] - agg["s3_best_cost"]) / agg["s2_cost_in_s3"].replace(0, pd.NA)
    agg["voi_s2_pct"] = agg["voi_s2_pct"].fillna(0)
    agg["voi_s3_pct"] = agg["voi_s3_pct"].fillna(0)

    ss_labels = [f"{int(x)}%" for x in agg["ss"]]

    fig_voi = go.Figure()
    fig_voi.add_trace(
        go.Scatter(
            x=ss_labels,
            y=agg["voi_s2_pct"],
            mode="lines+markers+text",
            name="S1 → S2 (add Tier‑2)",
            line=dict(color="#1E5DBE", width=3),
            marker=dict(size=10),
            text=[f"{v:.1%}" for v in agg["voi_s2_pct"]],
            textposition="top center",
            customdata=agg["voi_s2"],
            hovertemplate="SS %{x}<br>VOI: %{y:.2%}<br>Savings: $%{customdata:,.0f}<extra>Tier‑2</extra>",
        )
    )
    fig_voi.add_trace(
        go.Scatter(
            x=ss_labels,
            y=agg["voi_s3_pct"],
            mode="lines+markers+text",
            name="S2 → S3 (add Tier‑3)",
            line=dict(color="#2E9E5B", width=3),
            marker=dict(size=10),
            text=[f"{v:.1%}" for v in agg["voi_s3_pct"]],
            textposition="bottom center",
            customdata=agg["voi_s3"],
            hovertemplate="SS %{x}<br>VOI: %{y:.2%}<br>Savings: $%{customdata:,.0f}<extra>Tier‑3</extra>",
        )
    )
    fig_voi.update_layout(
        height=380,
        margin=dict(l=10, r=10, t=20, b=10),
        yaxis=dict(tickformat=".0%", title="Cost Reduction (VOI %)", rangemode="tozero"),
        xaxis=dict(title="Safety Stock Level"),
        plot_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hovermode="x unified",
    )
    st.plotly_chart(fig_voi, use_container_width=True, config={"displayModeBar": False})

    # Peak VOI summary — both % and $
    peak_s2_pct = agg["voi_s2_pct"].max()
    peak_s3_pct = agg["voi_s3_pct"].max()
    peak_s2_usd = agg["voi_s2"].max()
    peak_s3_usd = agg["voi_s3"].max()

    best_path = "S2 → S3" if peak_s3_pct > peak_s2_pct else "S1 → S2"
    best_pct = max(peak_s2_pct, peak_s3_pct)
    best_usd = peak_s3_usd if peak_s3_pct > peak_s2_pct else peak_s2_usd

    def fmt_usd(x):
        if pd.isna(x) or x == 0:
            return "—"
        if abs(x) >= 1e9:
            return f"${x/1e9:.1f}B"
        if abs(x) >= 1e6:
            return f"${x/1e6:.1f}M"
        if abs(x) >= 1e3:
            return f"${x/1e3:.0f}K"
        return f"${x:,.0f}"

    st.markdown(
        f"""
        <div class="kpi-row">
            <div class="kpi">
                <div class="kpi-label">Peak VOI · S1→S2</div>
                <div class="kpi-value">{peak_s2_pct:.1%}</div>
                <div class="kpi-sub">{fmt_usd(peak_s2_usd)} · add Tier‑2</div>
            </div>
            <div class="kpi">
                <div class="kpi-label">Peak VOI · S2→S3</div>
                <div class="kpi-value">{peak_s3_pct:.1%}</div>
                <div class="kpi-sub">{fmt_usd(peak_s3_usd)} · add Tier‑3</div>
            </div>
            <div class="kpi" style="border-left-color:#2E9E5B;">
                <div class="kpi-label">Best Path</div>
                <div class="kpi-value">{best_path}</div>
                <div class="kpi-sub">{best_pct:.1%} · {fmt_usd(best_usd)}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("Detailed VOI table by safety‑stock level"):
        tbl = agg[["ss", "voi_s2_pct", "voi_s2", "voi_s3_pct", "voi_s3"]].copy()
        tbl.columns = [
            "Safety Stock %",
            "S1→S2 (%)", "S1→S2 ($)",
            "S2→S3 (%)", "S2→S3 ($)",
        ]
        tbl["Safety Stock %"] = tbl["Safety Stock %"].astype(int).astype(str) + "%"
        tbl["S1→S2 (%)"] = tbl["S1→S2 (%)"].apply(lambda x: f"{x:.2%}")
        tbl["S2→S3 (%)"] = tbl["S2→S3 (%)"].apply(lambda x: f"{x:.2%}")
        tbl["S1→S2 ($)"] = tbl["S1→S2 ($)"].apply(fmt_usd)
        tbl["S2→S3 ($)"] = tbl["S2→S3 ($)"].apply(fmt_usd)
        st.write(
            tbl.to_html(index=False, classes="table", border=0),
            unsafe_allow_html=True,
        )
else:
    st.info("No VOI data found for this company.")


# ===========================================================================
# SECTION 3 — NETWORK TOPOLOGY (D3 force-directed)
# ===========================================================================
st.markdown(
    f'<div class="section-title">Supply Chain Network Topology — {short_label(focal)}</div>'
    f'<div class="section-sub">Multi‑tier supplier network. Tap nodes to highlight '
    f'connections; pinch/scroll to zoom.</div>',
    unsafe_allow_html=True,
)

# Build a robust filename lookup
def find_network_file(focal_name: str):
    candidates = [
        f"{focal_name[:4].upper()}_network_map.json",
        f"{short_label(focal_name).upper()}_network_map.json",
        f"{short_label(focal_name).lower()}_network_map.json",
        f"{focal_name.split()[0].upper()}_network_map.json",
    ]
    for c in candidates:
        p = BASE_DIR / c
        if p.exists():
            return p
    return None


HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
  html, body { margin:0; padding:0; background:transparent; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
  #viz-wrapper { position: relative; background:#ffffff; border:1px solid #eee;
                 border-radius:10px; overflow:hidden; }
  #network-viz { width:100%; height:560px; cursor:grab; touch-action: none; }
  .tooltip {
    position:absolute; background:rgba(11,61,145,0.95); color:white;
    padding:6px 10px; border-radius:6px; font-size:12px;
    pointer-events:none; opacity:0; transition: opacity 0.15s;
    box-shadow: 0 2px 8px rgba(0,0,0,0.25);
  }
  .legend {
    position:absolute; top:10px; right:10px;
    background:rgba(255,255,255,0.92); border:1px solid #e0e0e0;
    border-radius:6px; padding:8px 10px; font-size:11px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  }
  .legend-row { display:flex; align-items:center; gap:6px; margin:2px 0; }
  .legend-dot { width:10px; height:10px; border-radius:50%; }
  @media (max-width: 640px) {
    #network-viz { height: 420px; }
    .legend { font-size: 10px; padding: 6px 8px; }
  }
</style>
</head>
<body>
<div id="viz-wrapper">
  <div id="network-viz"></div>
  <div class="legend">
    <div class="legend-row"><span class="legend-dot" style="background:#000000;"></span>Focal</div>
    <div class="legend-row"><span class="legend-dot" style="background:#1E5DBE;"></span>Tier 1</div>
    <div class="legend-row"><span class="legend-dot" style="background:#F18F01;"></span>Tier 2</div>
    <div class="legend-row"><span class="legend-dot" style="background:#A23B72;"></span>Tier 3</div>
  </div>
  <div id="tooltip" class="tooltip"></div>
</div>

<script>
  const nodesData = NODE_DATA_PLACEHOLDER;
  const linksData = EDGE_DATA_PLACEHOLDER;

  const container_el = document.getElementById("network-viz");
  const width  = container_el.clientWidth || 600;
  const height = container_el.clientHeight || 560;

  const svg = d3.select("#network-viz").append("svg")
    .attr("width", "100%").attr("height", height)
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("preserveAspectRatio", "xMidYMid meet");
  const container = svg.append("g");

  svg.call(d3.zoom().scaleExtent([0.15, 6])
    .on("zoom", (e) => container.attr("transform", e.transform)));

  const colorByTier = t => {
    if (t === 0) return "#000000";
    if (t === 1) return "#1E5DBE";
    if (t === 2) return "#F18F01";
    if (t === 3) return "#A23B72";
    return "#999";
  };
  const radiusByTier = t => {
    if (t === 0) return 22;
    if (t === 1) return 11;
    if (t === 2) return 6;
    return 4;
  };

  // Pin the focal company (tier 0) to the center of the canvas so it never drifts.
  nodesData.forEach(n => {
    if (n.tier === 0) {
      n.fx = width / 2;
      n.fy = height / 2;
    }
  });

  const simulation = d3.forceSimulation(nodesData)
    .force("link", d3.forceLink(linksData).id(d => d.id).distance(60).strength(0.7))
    .force("charge", d3.forceManyBody().strength(-180))
    .force("center", d3.forceCenter(width / 2, height / 2))
    .force("collision", d3.forceCollide().radius(d => radiusByTier(d.tier) + 2));

  const link = container.append("g").selectAll("line")
    .data(linksData).join("line")
    .attr("stroke", "#bbb").attr("stroke-opacity", 0.3).attr("stroke-width", 1);

  const node = container.append("g").selectAll("circle")
    .data(nodesData).join("circle")
    .attr("r", d => radiusByTier(d.tier))
    .attr("fill", d => colorByTier(d.tier))
    .attr("stroke", "#fff").attr("stroke-width", 1.5)
    .call(d3.drag().on("start", dragstarted).on("drag", dragged).on("end", dragended))
    .on("mouseover touchstart", (event, d) => {
      const tooltip = d3.select("#tooltip");
      const hovered = d;
      tooltip.style("opacity", 1)
             .html(`<strong>${d.id}</strong><br>Tier: ${d.tier}`)
             .style("left", (event.offsetX + 12) + "px")
             .style("top",  (event.offsetY - 20) + "px");

      link.transition().duration(120)
        .attr("stroke", l => {
          const sId = l.source.id || l.source;
          const tId = l.target.id || l.target;
          return (sId === d.id || tId === d.id) ? "#1E5DBE" : "#ddd";
        })
        .attr("stroke-width", l => {
          const sId = l.source.id || l.source;
          const tId = l.target.id || l.target;
          return (sId === d.id || tId === d.id) ? 3 : 1;
        })
        .attr("stroke-opacity", l => {
          const sId = l.source.id || l.source;
          const tId = l.target.id || l.target;
          return (sId === d.id || tId === d.id) ? 1 : 0.08;
        });

      node.transition().duration(120)
        .attr("opacity", n => {
          if (n === hovered) return 1;
          const connected = linksData.some(l =>
            ((l.source.id || l.source) === d.id && (l.target.id || l.target) === n.id) ||
            ((l.target.id || l.target) === d.id && (l.source.id || l.source) === n.id)
          );
          return connected ? 1 : 0.15;
        });
    })
    .on("mouseout touchend", () => {
      d3.select("#tooltip").style("opacity", 0);
      link.transition().duration(250)
        .attr("stroke", "#bbb").attr("stroke-width", 1).attr("stroke-opacity", 0.3);
      node.transition().duration(250).attr("opacity", 1);
    });

  function dragstarted(event, d) {
    if (!event.active) simulation.alphaTarget(0.3).restart();
    d.fx = d.x; d.fy = d.y;
  }
  function dragged(event, d) { d.fx = event.x; d.fy = event.y; }
  function dragended(event, d) {
    if (!event.active) simulation.alphaTarget(0);
    // Keep focal node pinned to center; release everything else.
    if (d.tier === 0) {
      d.fx = width / 2; d.fy = height / 2;
    } else {
      d.fx = null; d.fy = null;
    }
  }

  simulation.on("tick", () => {
    link.attr("x1", d => d.source.x).attr("y1", d => d.source.y)
        .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
    node.attr("cx", d => d.x).attr("cy", d => d.y);
  });
</script>
</body>
</html>
"""

network_file = find_network_file(focal)
if network_file is None:
    st.warning(
        f"⚠️ Network map not found for **{focal}**. "
        f"Looked for files like `{focal[:4].upper()}_network_map.json` in the app folder."
    )
else:
    try:
        with open(network_file, "r") as f:
            net = json.load(f)
        nodes_json = json.dumps(net.get("nodes", []))
        edges_json = json.dumps(net.get("links", net.get("edges", [])))
        final_html = (
            HTML_TEMPLATE
            .replace("NODE_DATA_PLACEHOLDER", nodes_json)
            .replace("EDGE_DATA_PLACEHOLDER", edges_json)
        )
        # Responsive height: a bit shorter so mobile users see other content
        components.html(final_html, height=600, scrolling=False)
    except Exception as e:
        st.error(f"Could not render network: {e}")


# ---------------------------------------------------------------------------
# FOOTER
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div style="text-align:center; color:#888; font-size:0.75rem; margin-top:1rem;">
        © 2026 MIT Digital Supply Chain Transformation Lab
    </div>
    """,
    unsafe_allow_html=True,
)
