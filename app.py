"""
app.py — NovaMind Streamlit Dashboard
Single-page scroll layout: Generate → Distribute → Analyze.
Each section flows into the next to show the full pipeline at a glance.
"""

import json
import os
from datetime import datetime, timezone

import altair as alt
import pandas as pd
import streamlit as st

from pipeline import generate_content, send_campaign, generate_blog, generate_newsletters
from analytics import run_analytics

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="NovaMind",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Session state ─────────────────────────────────────────────────────────────

_DEFAULTS = {
    "pipeline_result":  None,   # set after send_campaign() — holds full sent result
    "analytics_result": None,
    "pipeline_success": None,
    "current_topic":    None,
    # Draft state — set after generate_content(), cleared on new topic
    "draft_blog":        None,
    "draft_newsletters": None,
    "draft_sent":        False,  # True once send_campaign() completes for this draft
    # Version history (separate from pipeline_result — never mutates it)
    "blog_versions":    [],
    "nl_versions":      [],
    "blog_v_idx":       0,
    "nl_v_idx":         0,
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Constants ─────────────────────────────────────────────────────────────────

PERSONAS = ["Agency Founder", "Marketing Manager", "Operations Manager"]

PERSONA_COLORS = {
    "Agency Founder":    "#7C3AED",
    "Marketing Manager": "#059669",
    "Operations Manager":"#D97706",
}

# Short labels used ONLY inside chart axes
SHORT_LABELS = {
    "Agency Founder":    "Founder",
    "Marketing Manager": "Mktg Mgr",
    "Operations Manager":"Ops Mgr",
}

BADGE_CLASS = {
    "Agency Founder":    "badge-founder",
    "Marketing Manager": "badge-marketing",
    "Operations Manager":"badge-ops",
}

CONTACTS_DATA = [
    {"Name": "James Park",   "Email": "james@founderstudio.io",   "Persona": "Agency Founder"},
    {"Name": "Lisa Johnson", "Email": "lisa@studiofounder.co",    "Persona": "Agency Founder"},
    {"Name": "David Chen",   "Email": "david@creativeagency.io",  "Persona": "Agency Founder"},
    {"Name": "Sarah Kim",    "Email": "sarah@growthlab.co",       "Persona": "Marketing Manager"},
    {"Name": "Rachel Wong",  "Email": "rachel@marketingpro.co",   "Persona": "Marketing Manager"},
    {"Name": "Kevin Park",   "Email": "kevin@growthmarketer.io",  "Persona": "Marketing Manager"},
    {"Name": "Mia Lee",      "Email": "mia@opsagency.com",        "Persona": "Operations Manager"},
    {"Name": "Tom Harris",   "Email": "tom@projectops.com",       "Persona": "Operations Manager"},
    {"Name": "Anna Kim",     "Email": "anna@opsmanager.com",      "Persona": "Operations Manager"},
]

# ── Global CSS ────────────────────────────────────────────────────────────────

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

  html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  }

  /* Background */
  .stApp { background: #f8fafc; }
  .block-container { padding: 2rem 2.5rem 4rem; max-width: 1100px; }

  /* Hide sidebar toggle */
  [data-testid="collapsedControl"] { display: none; }

  /* Metric cards */
  .metric-card {
    background: #fff;
    border: 1px solid #e2e8f0;
    border-left: 3px solid #7c3aed;
    border-radius: 10px;
    padding: 14px 18px 12px;
  }
  .metric-value {
    font-size: 1.65rem;
    font-weight: 800;
    color: #0f172a;
    line-height: 1.1;
    letter-spacing: -0.03em;
  }
  .metric-label {
    font-size: 0.7rem;
    font-weight: 600;
    color: #64748b;
    margin-top: 4px;
    text-transform: uppercase;
    letter-spacing: 0.07em;
  }

  /* Section divider label */
  .section-label {
    font-size: 0.65rem;
    font-weight: 700;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin: 2rem 0 0.6rem;
  }

  /* Persona badges */
  .badge {
    display: inline-block;
    padding: 2px 9px;
    border-radius: 10px;
    font-size: 0.7rem;
    font-weight: 600;
    color: #fff;
    white-space: nowrap;
  }
  .badge-founder   { background: #7C3AED; }
  .badge-marketing { background: #059669; }
  .badge-ops       { background: #D97706; }

  /* Version badge */
  .version-badge {
    display: inline-block;
    background: #ede9fe;
    color: #5b21b6;
    border-radius: 6px;
    padding: 2px 9px;
    font-size: 0.73rem;
    font-weight: 700;
  }

  /* Contact table */
  .contact-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
  }
  .contact-table thead tr {
    background: #f8fafc;
    border-bottom: 2px solid #e2e8f0;
  }
  .contact-table th {
    padding: 8px 14px;
    text-align: left;
    font-size: 0.7rem;
    font-weight: 700;
    color: #475569;
    text-transform: uppercase;
    letter-spacing: 0.07em;
  }
  .contact-table tbody tr { border-bottom: 1px solid #f1f5f9; }
  .contact-table tbody tr:hover { background: #f8fafc; }
  .contact-table td { padding: 7px 14px; color: #1e293b; }
  .contact-table td.dim { color: #64748b; font-size: 0.83rem; }

  /* Campaign linked banner */
  .campaign-ref {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 9px 14px;
    font-size: 0.82rem;
    color: #475569;
    margin-bottom: 14px;
  }
  .campaign-ref strong { color: #0f172a; }

  /* Insight card */
  .insight-card {
    background: #fafafa;
    border: 1px solid #e2e8f0;
    border-left: 3px solid #7c3aed;
    border-radius: 8px;
    padding: 14px 18px;
    font-size: 0.88rem;
    color: #1e293b;
    line-height: 1.6;
    margin-bottom: 16px;
  }
  .insight-meta {
    font-size: 0.72rem;
    font-weight: 700;
    color: #7c3aed;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    margin-bottom: 6px;
  }

  /* Empty state */
  .empty-state {
    background: #fff;
    border: 1px dashed #cbd5e1;
    border-radius: 12px;
    padding: 36px 24px;
    text-align: center;
    color: #64748b;
    font-size: 0.9rem;
  }
  .empty-state .icon { font-size: 1.8rem; margin-bottom: 8px; }

  /* Newsletter tab color underlines — order: Agency Founder, Marketing Manager, Ops Manager */
  [data-testid="stTabs"] [role="tablist"] button:nth-child(1)[aria-selected="true"] {
    border-bottom: 2px solid #7C3AED !important; color: #7C3AED !important;
  }
  [data-testid="stTabs"] [role="tablist"] button:nth-child(2)[aria-selected="true"] {
    border-bottom: 2px solid #059669 !important; color: #059669 !important;
  }
  [data-testid="stTabs"] [role="tablist"] button:nth-child(3)[aria-selected="true"] {
    border-bottom: 2px solid #D97706 !important; color: #D97706 !important;
  }

  /* Primary buttons — dark navy, more professional than Streamlit's default red */
  .stButton > button[kind="primary"] {
    background-color: #1e3a5f !important;
    border-color: #1e3a5f !important;
    color: #ffffff !important;
  }
  .stButton > button[kind="primary"]:hover {
    background-color: #16304f !important;
    border-color: #16304f !important;
  }
  .stButton > button[kind="primary"]:active {
    background-color: #112540 !important;
    border-color: #112540 !important;
  }

  /* Headings */
  h1 {
    font-size: 1.55rem !important;
    font-weight: 800 !important;
    color: #0f172a !important;
    letter-spacing: -0.03em !important;
    margin-bottom: 0 !important;
  }
  h2 {
    font-size: 1.05rem !important;
    font-weight: 700 !important;
    color: #0f172a !important;
    margin-top: 0 !important;
  }
  hr { border-color: #e2e8f0 !important; margin: 2rem 0 !important; }
</style>
""", unsafe_allow_html=True)

# ── Utility functions ─────────────────────────────────────────────────────────

def _load_history() -> list:
    if os.path.exists("campaign_history.json"):
        try:
            with open("campaign_history.json") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _load_analytics_history() -> list:
    if os.path.exists("analytics_history.json"):
        try:
            with open("analytics_history.json") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _fmt_date(iso_str: str) -> str:
    """Convert ISO timestamp to readable date string."""
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%b %d, %Y")
    except Exception:
        return iso_str


def _bar_chart(df: pd.DataFrame, y_field: str, height: int = 210) -> alt.Chart:
    """
    Compact Altair bar chart with per-persona colors.
    df columns: Persona, Label (short), <y_field>
    Persona names stay unchanged in data; only the Label column is shown on the axis.
    """
    return (
        alt.Chart(df)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=alt.X("Label:N",
                    sort=list(SHORT_LABELS.values()),
                    axis=alt.Axis(labelAngle=0, title=None, labelColor="#64748b")),
            y=alt.Y(f"{y_field}:Q",
                    axis=alt.Axis(title=y_field, grid=True,
                                  gridColor="#f1f5f9", labelColor="#64748b",
                                  titleColor="#64748b")),
            color=alt.Color(
                "Persona:N",
                scale=alt.Scale(domain=list(PERSONA_COLORS.keys()),
                                range=list(PERSONA_COLORS.values())),
                legend=None,
            ),
            tooltip=[alt.Tooltip("Persona:N"), alt.Tooltip(f"{y_field}:Q", format=".2f")],
        )
        .properties(height=height)
        .configure_view(strokeWidth=0)
    )

# ── Load data used across multiple sections ───────────────────────────────────

history          = _load_history()
analytics_history = _load_analytics_history()
campaigns_sent   = len(history)

# Derive metrics from latest analytics run (if available)
_avg_open = _avg_ctr = None
if st.session_state.analytics_result:
    perf = st.session_state.analytics_result.get("performance", {})
    if perf:
        opens  = [v["open_rate"]  for v in perf.values()]
        clicks = [v["click_rate"] for v in perf.values()]
        _avg_open = sum(opens) / len(opens)
        _avg_ctr  = sum(c / o for c, o in zip(clicks, opens) if o > 0) / len(opens)

# Top segment — persona with highest open rate from most recent analytics run
_top_segment = "Run Analytics"
if st.session_state.analytics_result:
    _perf = st.session_state.analytics_result.get("performance", {})
    if _perf:
        _top_segment = max(_perf, key=lambda p: _perf[p]["open_rate"])

# ── Header ────────────────────────────────────────────────────────────────────

st.markdown(
    "<h1>🧠 NovaMind Content Pipeline</h1>"
    "<p style='color:#64748b; margin:4px 0 20px; font-size:0.88rem;'>"
    "End-to-end content automation: Generate → Distribute → Analyze"
    "</p>",
    unsafe_allow_html=True,
)

# ── Top metrics ───────────────────────────────────────────────────────────────
# Campaigns Sent reflects pipeline activity.
# Avg Open Rate and Avg CTR reflect distribution performance.
# Top Segment surfaces the persona insight directly on the dashboard header.

m1, m2, m3, m4 = st.columns(4)
_metric_specs = [
    (m1, str(campaigns_sent),
     "Campaigns Sent"),
    (m2, f"{_avg_open * 100:.1f}%" if _avg_open is not None else "—",
     "Avg Open Rate"),
    (m3, f"{_avg_ctr * 100:.1f}%"  if _avg_ctr  is not None else "—",
     "Avg CTR (Click-to-Open)"),
    (m4, _top_segment,
     "Top Segment"),
]
for col, value, label in _metric_specs:
    col.markdown(
        f"<div class='metric-card'>"
        f"<div class='metric-value'>{value}</div>"
        f"<div class='metric-label'>{label}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

st.divider()

# ═════════════════════════════════════════════════════════════════════════════
# STEP 1 — GENERATE
# ═════════════════════════════════════════════════════════════════════════════

st.markdown("<p class='section-label'>Step 1 — Generate</p>", unsafe_allow_html=True)
st.header("Campaign Content")

topic = st.text_input(
    "Blog topic",
    placeholder="e.g. How AI is transforming creative agency workflows in 2025",
    # Reset draft state when a new topic is typed
)

# ── Button 1: Generate Content (no HubSpot, no logging) ──────────────────────

if st.button("✍️ Generate Content", type="primary", disabled=not topic.strip()):
    _err = None
    with st.spinner("Generating blog and newsletters with Gemini…"):
        try:
            draft = generate_content(topic.strip())
            # Store as draft — pipeline_result is NOT touched yet
            st.session_state.draft_blog        = draft["blog"]
            st.session_state.draft_newsletters  = draft["newsletters"]
            st.session_state.current_topic      = topic.strip()
            st.session_state.draft_sent         = False
            st.session_state.pipeline_success   = None
            # Initialise version history from this first generation
            st.session_state.blog_versions = [draft["blog"]]
            st.session_state.nl_versions   = [draft["newsletters"]]
            st.session_state.blog_v_idx    = 0
            st.session_state.nl_v_idx      = 0
        except Exception as e:
            _err = str(e)
    if _err:
        st.error(f"Generation error: {_err}")
    else:
        st.rerun()

# ── Draft preview (shown after generation, before or after sending) ───────────

if st.session_state.draft_blog:

    # Sent confirmation banner
    if st.session_state.pipeline_success:
        st.success(st.session_state.pipeline_success)

    # Draft notice — only shown while not yet sent
    if not st.session_state.draft_sent:
        st.markdown(
            "<div style='background:#fffbeb; border:1px solid #fcd34d; border-radius:8px;"
            "padding:10px 14px; font-size:0.83rem; color:#92400e; margin-bottom:12px;'>"
            "📝 <strong>Draft</strong> — Review the content below, regenerate if needed,"
            " then click <strong>Send Campaign</strong> when ready."
            "</div>",
            unsafe_allow_html=True,
        )

    # Regenerate control — only available before sending
    if not st.session_state.draft_sent:
        _regen_col, _sp = st.columns([1.6, 6])
        with _regen_col:
            if st.button("🔄 Regenerate Content"):
                _err = None
                with st.spinner("Regenerating blog and newsletters…"):
                    try:
                        new_blog = generate_blog(st.session_state.current_topic)
                        new_nls  = generate_newsletters(new_blog["title"], new_blog["content"])
                        st.session_state.blog_versions.append(new_blog)
                        st.session_state.nl_versions.append(new_nls)
                        new_idx = len(st.session_state.blog_versions) - 1
                        st.session_state.blog_v_idx        = new_idx
                        st.session_state.nl_v_idx          = new_idx
                        st.session_state.draft_blog        = new_blog
                        st.session_state.draft_newsletters = new_nls
                    except Exception as e:
                        _err = str(e)
                if _err:
                    st.error(f"Error: {_err}")
                else:
                    st.rerun()

    # Blog — current version
    b_idx   = st.session_state.blog_v_idx
    b_total = len(st.session_state.blog_versions)
    blog    = st.session_state.blog_versions[b_idx]

    st.markdown(
        f"<span class='version-badge'>v{b_idx + 1} / {b_total}</span>"
        + (f"<span style='color:#94a3b8; font-size:0.75rem; margin-left:8px;'>"
           f"Previous versions saved in session</span>" if b_total > 1 else ""),
        unsafe_allow_html=True,
    )
    with st.expander("📄 Blog Post", expanded=True):
        st.subheader(blog.get("title", "—"))
        outline = blog.get("outline", [])
        if outline:
            st.markdown("**Outline**")
            st.markdown("\n".join(f"{i}. {s}" for i, s in enumerate(outline, 1)))
            st.markdown("---")
        st.markdown(blog.get("content", ""))

    st.divider()

    # ── Step 2 — Distribute ───────────────────────────────────────────────────
    st.markdown("<p class='section-label'>Step 2 — Distribute</p>", unsafe_allow_html=True)
    st.header("Newsletter Versions")

    newsletters = st.session_state.nl_versions[st.session_state.nl_v_idx]

    tabs = st.tabs(PERSONAS)
    for tab, persona in zip(tabs, PERSONAS):
        with tab:
            nl = newsletters.get(persona, {})
            if nl:
                st.markdown(
                    f"<div style='margin-bottom:8px; font-size:0.88rem;'>"
                    f"<strong>Subject:</strong> {nl.get('subject', '—')}"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                st.info(nl.get("body", "—"))
            else:
                st.info("No newsletter generated for this persona.")

    # ── Button 2: Send Campaign ───────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)

    if not st.session_state.draft_sent:
        st.markdown(
            "<p style='font-size:0.82rem; color:#475569; margin-bottom:8px;'>"
            "Happy with the content? Sync contacts to HubSpot and log this campaign."
            "</p>",
            unsafe_allow_html=True,
        )
        if st.button("🚀 Send Campaign", type="primary"):
            _err = None
            with st.spinner("Syncing contacts to HubSpot and logging campaign…"):
                try:
                    result = send_campaign(
                        st.session_state.blog_versions[st.session_state.blog_v_idx],
                        st.session_state.nl_versions[st.session_state.nl_v_idx],
                    )
                    st.session_state.pipeline_result  = result
                    st.session_state.draft_sent       = True
                    st.session_state.pipeline_success = (
                        f"Campaign **{result['campaign']['campaign_id']}** logged — "
                        f"contacts and notes synced to HubSpot."
                    )
                except Exception as e:
                    _err = str(e)
            if _err:
                st.error(f"Send error: {_err}")
            else:
                st.rerun()

        st.caption("This logs the campaign and syncs contacts and notes to HubSpot.")
    else:
        # Post-send — replace button with a read-only badge
        st.markdown(
            "<div style='display:inline-flex; align-items:center; gap:8px;"
            "background:#f0fdf4; border:1px solid #86efac; border-radius:8px;"
            "padding:9px 16px; font-size:0.85rem; color:#166534;'>"
            "✅ <strong>Campaign sent</strong> — HubSpot synced, campaign logged."
            "</div>",
            unsafe_allow_html=True,
        )

    st.divider()

# ═════════════════════════════════════════════════════════════════════════════
# STEP 3 — ANALYZE
# ═════════════════════════════════════════════════════════════════════════════

st.markdown("<p class='section-label'>Step 3 — Analyze</p>", unsafe_allow_html=True)
st.header("Performance Analytics")

if st.button("📊 Run Analytics", type="secondary"):
    _err = None
    with st.spinner("Simulating performance data and generating AI insights…"):
        try:
            analytics = run_analytics()
            st.session_state.analytics_result = analytics
        except Exception as e:
            _err = str(e)
    if _err:
        st.error(f"Analytics error: {_err}")
    else:
        st.rerun()

if not st.session_state.analytics_result:
    st.markdown(
        "<div class='empty-state'>"
        "<div class='icon'>📈</div>"
        "Click <strong>Run Analytics</strong> above to simulate campaign performance "
        "and generate AI-powered insights."
        "</div>",
        unsafe_allow_html=True,
    )
else:
    analytics   = st.session_state.analytics_result
    performance = analytics.get("performance", {})
    insights    = analytics.get("insights", "")
    topics_rec  = analytics.get("recommended_topics", [])

    # Link analytics to the most recent campaign for context
    if history:
        last = history[-1]
        st.markdown(
            f"<div class='campaign-ref'>"
            f"Simulated performance for: <strong>{last.get('blog_title', '—')}</strong>"
            f" &nbsp;·&nbsp; {_fmt_date(last.get('send_date', ''))}"
            f"</div>",
            unsafe_allow_html=True,
        )

    if performance:
        personas_list = list(performance.keys())
        opens         = [performance[p]["open_rate"]         for p in personas_list]
        clicks        = [performance[p]["click_rate"]        for p in personas_list]
        unsubs        = [performance[p]["unsubscribe_rate"]  for p in personas_list]
        short_labels  = [SHORT_LABELS[p]                     for p in personas_list]

        # ── AI Insight + best segment (merged, front and center) ──────────────
        if insights:
            best_p     = max(performance, key=lambda p: performance[p]["open_rate"])
            best_color = PERSONA_COLORS[best_p]
            best_open  = performance[best_p]["open_rate"]  * 100
            best_click = performance[best_p]["click_rate"] * 100

            st.markdown(
                f"<div class='insight-card'>"
                f"<div class='insight-meta'>AI Insight"
                f"  <span style='background:{best_color}18; color:{best_color};"
                f"  border-radius:5px; padding:1px 8px; margin-left:8px;"
                f"  font-size:0.68rem;'>Highest Engagement: {best_p} "
                f"  ({best_open:.1f}% open · {best_click:.1f}% click)</span>"
                f"</div>"
                f"{insights}"
                f"</div>",
                unsafe_allow_html=True,
            )

        # ── Recommended topics (prominent — most relevant for a content role) ──
        if topics_rec:
            st.markdown(
                "<p style='font-size:0.82rem; font-weight:700; color:#0f172a;"
                "margin:4px 0 8px;'>Recommended Next Topics</p>",
                unsafe_allow_html=True,
            )
            for i, t in enumerate(topics_rec, 1):
                st.markdown(
                    f"<div style='padding:7px 12px; background:#fff; border:1px solid #e2e8f0;"
                    f"border-radius:7px; margin-bottom:6px; font-size:0.875rem; color:#1e293b;'>"
                    f"<span style='color:#7c3aed; font-weight:700; margin-right:8px;'>{i}</span>{t}"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            st.markdown("<br>", unsafe_allow_html=True)

        # ── Three bar charts: Open Rate, Click Rate, Unsubscribe Rate ───────────
        def _make_df(y_vals, y_field):
            return pd.DataFrame({
                "Persona": personas_list,
                "Label":   short_labels,
                y_field:   [round(v * 100, 2) for v in y_vals],
            })

        ch1, ch2, ch3 = st.columns(3)
        _chart_label = "<p style='font-size:0.78rem; font-weight:600; color:#475569; margin-bottom:2px;'>{}</p>"
        with ch1:
            st.markdown(_chart_label.format("OPEN RATE (%)"), unsafe_allow_html=True)
            st.altair_chart(_bar_chart(_make_df(opens,  "Open Rate (%)"),  "Open Rate (%)"),  use_container_width=True)
        with ch2:
            st.markdown(_chart_label.format("CLICK RATE (%)"), unsafe_allow_html=True)
            st.altair_chart(_bar_chart(_make_df(clicks, "Click Rate (%)"), "Click Rate (%)"), use_container_width=True)
        with ch3:
            st.markdown(_chart_label.format("UNSUBSCRIBE RATE (%)"), unsafe_allow_html=True)
            st.altair_chart(_bar_chart(_make_df(unsubs, "Unsub Rate (%)"), "Unsub Rate (%)"), use_container_width=True)

        # ── CTR table (all four metrics in one place) ─────────────────────────
        st.markdown(
            "<p style='font-size:0.82rem; font-weight:700; color:#0f172a; margin:4px 0 8px;'>"
            "Metrics by Persona</p>",
            unsafe_allow_html=True,
        )
        ctr_rows = []
        for p, o, c, u in zip(personas_list, opens, clicks, unsubs):
            ctr = (c / o * 100) if o > 0 else 0.0
            ctr_rows.append({
                "Persona":     p,
                "Open Rate":   f"{o * 100:.1f}%",
                "Click Rate":  f"{c * 100:.1f}%",
                "Unsub Rate":  f"{u * 100:.2f}%",
                "CTR (C÷O)":   f"{ctr:.1f}%",
            })
        st.dataframe(pd.DataFrame(ctr_rows), hide_index=True, use_container_width=True)

        # ── Trend line — only shown when there is enough data to be meaningful ─
        if len(analytics_history) >= 3:
            st.markdown(
                "<p style='font-size:0.82rem; font-weight:700; color:#0f172a;"
                "margin:16px 0 8px;'>Open Rate Trend</p>",
                unsafe_allow_html=True,
            )
            trend_rows = []
            for i, entry in enumerate(analytics_history[-10:], 1):
                for persona, data in entry.get("performance", {}).items():
                    trend_rows.append({
                        "Run":           i,
                        "Persona":       persona,
                        "Open Rate (%)": round(data["open_rate"] * 100, 2),
                    })
            trend_chart = (
                alt.Chart(pd.DataFrame(trend_rows))
                .mark_line(point=alt.OverlayMarkDef(filled=True, size=55))
                .encode(
                    x=alt.X("Run:O", axis=alt.Axis(title="Analytics Run",
                                                    labelColor="#64748b", titleColor="#64748b")),
                    y=alt.Y("Open Rate (%):Q",
                            axis=alt.Axis(title="Open Rate (%)", grid=True,
                                          gridColor="#f1f5f9", labelColor="#64748b",
                                          titleColor="#64748b")),
                    color=alt.Color(
                        "Persona:N",
                        scale=alt.Scale(domain=list(PERSONA_COLORS.keys()),
                                        range=list(PERSONA_COLORS.values())),
                        legend=alt.Legend(title=None, labelColor="#374151"),
                    ),
                    tooltip=["Run:O", "Persona:N",
                             alt.Tooltip("Open Rate (%):Q", format=".2f")],
                )
                .properties(height=240)
                .configure_view(strokeWidth=0)
            )
            st.altair_chart(trend_chart, use_container_width=True)
        elif len(analytics_history) in (1, 2):
            st.caption(
                f"Run analytics {3 - len(analytics_history)} more time(s) to see performance trends."
            )

st.divider()

# ═════════════════════════════════════════════════════════════════════════════
# CONTACTS
# ═════════════════════════════════════════════════════════════════════════════

st.markdown("<p class='section-label'>CRM</p>", unsafe_allow_html=True)
st.header("Contacts")

rows_html = ""
for c in CONTACTS_DATA:
    bc = BADGE_CLASS.get(c["Persona"], "")
    rows_html += (
        f"<tr>"
        f"<td>{c['Name']}</td>"
        f"<td class='dim'>{c['Email']}</td>"
        f"<td><span class='badge {bc}'>{c['Persona']}</span></td>"
        f"</tr>"
    )

st.markdown(
    f"<table class='contact-table'>"
    f"<thead><tr><th>Name</th><th>Email</th><th>Persona</th></tr></thead>"
    f"<tbody>{rows_html}</tbody>"
    f"</table>",
    unsafe_allow_html=True,
)

st.divider()

# ═════════════════════════════════════════════════════════════════════════════
# CAMPAIGN HISTORY
# ═════════════════════════════════════════════════════════════════════════════

_hist_col, _btn_col = st.columns([6, 1])
with _hist_col:
    st.markdown("<p class='section-label'>History</p>", unsafe_allow_html=True)
    st.header("Campaign History")

if history:
    # Clear Test Data button — keeps the 3 most recent campaigns
    with _btn_col:
        st.markdown("<br><br>", unsafe_allow_html=True)
        if len(history) > 3 and st.button("🗑 Clear old", help="Keep only the 3 most recent campaigns"):
            trimmed = history[-3:]
            try:
                with open("campaign_history.json", "w") as _f:
                    json.dump(trimmed, _f, indent=2)
                st.rerun()
            except Exception as _e:
                st.error(f"Could not clear history: {_e}")

    rows = []
    for i, c in enumerate(reversed(history), 1):
        rows.append({
            "#":          len(history) - i + 1,
            "Blog Title": c.get("blog_title", "—"),
            "Date":       _fmt_date(c.get("send_date", "")),
            "Personas":   ", ".join(c.get("personas", [])),
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
else:
    st.markdown(
        "<div class='empty-state'>"
        "<div class='icon'>📭</div>"
        "No campaigns yet. Generate your first campaign above."
        "</div>",
        unsafe_allow_html=True,
    )
