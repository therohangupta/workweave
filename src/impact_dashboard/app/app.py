from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[3]
DATA_PATH = ROOT / "data" / "processed" / "engineer_metrics.json"
META_PATH = ROOT / "data" / "processed" / "metadata.json"

# ---------------------------------------------------------------------------
# Metric deep-dives: what / how / why for every single metric
# ---------------------------------------------------------------------------

METRIC_STORIES = {
    "impact_score": {
        "label": "Impact Score",
        "icon": "🎯",
        "what": "A single number from 0 to 1 that summarizes an engineer's total contribution across three dimensions: shipping, collaboration, and codebase health.",
        "formula": "impact = 0.40 × Product + 0.30 × Team + 0.30 × Technical",
        "why": (
            "Engineering impact can't be captured by a single axis. An engineer who ships tons of code but never reviews "
            "is less valuable than one who ships a moderate amount while also unblocking 10 teammates. A composite score "
            "forces us to reward well-rounded contributors. The 40/30/30 weighting slightly favors shipping — because at "
            "the end of the day, code that reaches production is the most visible form of impact — but ensures that "
            "team multipliers and codebase stewardship are never invisible."
        ),
    },
    "product_score": {
        "label": "Product Score (40% of Impact)",
        "icon": "🚀",
        "what": "How much meaningful work an engineer ships to production, adjusted for complexity and velocity.",
        "formula": "product = 0.50 × norm(weighted_pr_output) + 0.30 × norm(merged_prs) + 0.20 × inv_norm(avg_cycle_time)",
        "why": (
            "Not all PRs are equal. A one-line config tweak is not the same as a cross-directory feature touching 15 files. "
            "Weighted PR output gives proportional credit based on complexity. Raw merged PR count is included as a throughput "
            "baseline, but at 30% weight to avoid rewarding PR-splitting games. Cycle time is inverted (faster = better) because "
            "engineers who get code reviewed and merged quickly are signaling clean, well-scoped work."
        ),
    },
    "team_score": {
        "label": "Team Score (30% of Impact)",
        "icon": "🤝",
        "what": "How much an engineer multiplies the output of everyone around them through code review and unblocking.",
        "formula": "team = 0.45 × norm(unblocks) + 0.30 × norm(reviews_given) + 0.25 × norm(engineers_helped)",
        "why": (
            "The highest-leverage engineers don't just ship their own code — they make everyone else faster. "
            "Unblocks are weighted highest (45%) because a review that leads to a merge within 24 hours is direct, "
            "causal evidence of removing a bottleneck. Raw review count at 30% captures overall review effort. "
            "Distinct engineers helped at 25% rewards breadth — reviewing 20 PRs across 12 people is more impactful "
            "to the organization than reviewing 30 PRs for one person."
        ),
    },
    "technical_score": {
        "label": "Technical Score (30% of Impact)",
        "icon": "🔧",
        "what": "Contributions to codebase reliability, stability, and long-term health.",
        "formula": "technical = 0.40 × norm(bug_fixes) + 0.25 × norm(hotfixes) + 0.20 × norm(core_area_touches) + 0.15 × norm(refactors)",
        "why": (
            "Bug fixes and hotfixes are chronically undervalued in most engineering cultures. They rarely get celebrated but "
            "directly impact production reliability. Bug fixes are weighted highest (40%) because they're the most common form "
            "of quality work. Hotfixes at 25% reward handling production emergencies. Core-area touches (20%) identify engineers "
            "working in the highest-leverage directories — posthog/, frontend/, plugin-server/, ee/, hogql/, rust/. "
            "Refactors at 15% are included because ignoring them would systematically undercount maintenance-oriented engineers, "
            "but weighted lowest because refactor impact is hardest to verify from metadata alone."
        ),
    },
    "merged_prs": {
        "label": "Merged PRs",
        "icon": "📦",
        "what": "Count of pull requests authored and merged during the analysis window.",
        "formula": "count where state = MERGED and author = engineer",
        "why": (
            "The most basic throughput signal. Every merged PR passed code review, CI, and was judged valuable enough to ship. "
            "We weight this at 30% within product score rather than relying on it alone because pure PR count incentivizes "
            "splitting work into tiny PRs."
        ),
    },
    "weighted_pr_output": {
        "label": "Weighted PR Output",
        "icon": "⚖️",
        "what": "Sum of merged PRs, each weighted by complexity. A trivial PR contributes ~1.0; a complex cross-directory change contributes up to ~1.9.",
        "formula": "Σ(1 + complexity) per merged PR, where complexity = 0.35 × norm(files) + 0.35 × norm(lines) + 0.30 × norm(dir_spread)",
        "why": (
            "Corrects for the fact that raw PR count treats a typo fix identically to a major feature. The three complexity "
            "axes — files changed (breadth), lines changed (depth), and directory spread (cross-cutting impact) — are each "
            "min-max normalized across the dataset with 5th/95th percentile clipping to prevent outliers from dominating. "
            "This is the highest-weighted input to product score at 50% because it best captures actual engineering effort."
        ),
    },
    "avg_cycle_time_hours": {
        "label": "Average Cycle Time",
        "icon": "⏱️",
        "what": "Average hours from PR creation to merge for an engineer's merged PRs.",
        "formula": "mean(merged_at − created_at) in hours; inverted for scoring: 1 − norm(value)",
        "why": (
            "Fast cycle times signal well-scoped PRs, responsive handling of review feedback, and code that reviewers "
            "can understand quickly. Very long cycle times often mean over-scoped PRs or abandoned-then-resurrected branches. "
            "Inverted normalization ensures faster engineers score higher. Weighted at 20% within product score — enough to "
            "matter, but not so much that someone who merges one tiny PR in 5 minutes outscores a prolific shipper."
        ),
    },
    "reviews_given": {
        "label": "Reviews Given",
        "icon": "👀",
        "what": "Total PR reviews this engineer submitted. Bot reviewers are excluded.",
        "formula": "count of review records where reviewer = engineer, excluding bots",
        "why": (
            "Code review is the primary mechanism for quality assurance, knowledge transfer, and onboarding. "
            "Engineers who review frequently reduce the entire team's merge latency. We filter out bot reviewers "
            "(greptile-apps, copilot, graphite-app, github-actions, stamphog, chatgpt-codex-connector) because "
            "automated approvals don't represent human judgment."
        ),
    },
    "distinct_engineers_helped": {
        "label": "Engineers Helped",
        "icon": "🌐",
        "what": "Number of distinct PR authors this engineer reviewed, excluding self-reviews.",
        "formula": "count unique pr_author where reviewer ≠ pr_author",
        "why": (
            "Breadth of collaboration matters. Reviewing 30 PRs for one colleague creates a bottleneck dependency. "
            "Reviewing 20 PRs across 12 people builds organizational resilience and cross-team knowledge. "
            "This metric specifically captures how wide an engineer's influence reaches."
        ),
    },
    "unblocks": {
        "label": "Unblocks",
        "icon": "🔓",
        "what": "Reviews where the PR merged within 24 hours afterward — direct evidence of removing a bottleneck.",
        "formula": "count where 0 ≤ (merged_at − review_created_at) ≤ 24 hours",
        "why": (
            "This is the single highest-signal team metric. When someone reviews a PR and it merges soon after, "
            "that reviewer causally contributed to forward progress. It filters out stale reviews on PRs that sat "
            "for days regardless. The 24-hour window is tight enough to suggest real causality but loose enough "
            "that timezone differences don't punish people. Weighted highest (45%) in team score."
        ),
    },
    "bug_fix_prs": {
        "label": "Bug Fix PRs",
        "icon": "🐛",
        "what": "Merged PRs fixing bugs, detected from labels (bug, fix) or title keywords (bug, fix, error, issue).",
        "formula": "label contains 'bug' or 'fix' OR title contains 'bug', 'fix', 'error', 'issue'",
        "why": (
            "Bug fixes are the most immediately valuable form of technical contribution. They directly improve "
            "product reliability for users. Weighted highest (40%) in technical score because this is the most "
            "common and verifiable form of codebase health work."
        ),
    },
    "hotfix_prs": {
        "label": "Hotfix PRs",
        "icon": "🚨",
        "what": "Merged PRs addressing urgent production issues, detected from labels or titles.",
        "formula": "label contains 'hotfix' or 'urgent' OR title contains 'hotfix', 'urgent', 'patch'",
        "why": (
            "Hotfixes represent high-pressure, time-critical incidents. Engineers who step up during production "
            "emergencies are disproportionately valuable to organizational trust and stability. Weighted at 25% — "
            "rarer than bug fixes but higher intensity per incident."
        ),
    },
    "core_area_touch_count": {
        "label": "Core Area Touches",
        "icon": "🏗️",
        "what": "Merged PRs modifying files in high-leverage directories: posthog/, frontend/, plugin-server/, ee/, hogql/, cyclotron/, rust/.",
        "formula": "count merged PRs where any file path starts with a core area prefix",
        "why": (
            "Not all code is equally important. Changes to core product directories carry more risk, require more "
            "context, and have more potential impact than changes to docs or test fixtures. This identifies engineers "
            "working where the stakes are highest."
        ),
    },
    "refactor_prs": {
        "label": "Refactor PRs",
        "icon": "♻️",
        "what": "Merged PRs doing cleanup or restructuring, detected from labels or titles.",
        "formula": "label contains 'refactor' OR title contains 'refactor', 'cleanup'",
        "why": (
            "Refactoring is investment in future velocity. Engineers who proactively reduce technical debt make "
            "the codebase easier for everyone. Weighted lowest (15%) in technical score because refactor quality "
            "is hardest to verify from metadata — but still included because omitting it would systematically "
            "undercount engineers doing essential maintenance work."
        ),
    },
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@st.cache_data
def load_data() -> pd.DataFrame:
    if not DATA_PATH.exists():
        return pd.DataFrame()
    return pd.read_json(DATA_PATH)


@st.cache_data
def load_metadata() -> dict:
    if not META_PATH.exists():
        return {}
    with META_PATH.open() as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# CSS — full override of Streamlit defaults
# ---------------------------------------------------------------------------

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}
.main .block-container {
    max-width: 1080px;
    padding: 1.5rem 1rem 3rem 1rem;
}
h1, h2, h3, h4, h5, h6 { font-family: 'Inter', sans-serif; }

/* ---- header bar ---- */
.dash-header {
    background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%);
    border-radius: 16px;
    padding: 2rem 2.2rem;
    color: #fff;
    margin-bottom: 1.5rem;
}
.dash-header h1 {
    font-size: 1.6rem; font-weight: 800; margin: 0 0 0.25rem 0; color: #fff;
}
.dash-header p {
    font-size: 0.92rem; color: #c7d2fe; margin: 0; line-height: 1.5;
}
.dash-header a { color: #a5b4fc; text-decoration: underline; }
.stat-row {
    display: flex; gap: 1.5rem; margin-top: 1.2rem; flex-wrap: wrap;
}
.stat-pill {
    background: rgba(255,255,255,0.1);
    border-radius: 10px;
    padding: 0.55rem 1rem;
    display: flex; flex-direction: column;
}
.stat-pill .stat-val {
    font-size: 1.15rem; font-weight: 700; color: #fff;
}
.stat-pill .stat-lbl {
    font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.06em;
    color: #a5b4fc; margin-top: 0.1rem;
}

/* ---- engineer card ---- */
.eng-card {
    background: #fff;
    border: 1px solid #e5e7eb;
    border-radius: 14px;
    padding: 1.4rem 1.6rem 1.2rem 1.6rem;
    margin-bottom: 1rem;
    transition: box-shadow 0.15s;
}
.eng-card:hover { box-shadow: 0 4px 20px rgba(0,0,0,0.06); }
.eng-card-head {
    display: flex; align-items: center; gap: 0.7rem; margin-bottom: 0.8rem;
}
.eng-rank {
    background: #6366f1; color: #fff; font-weight: 700; font-size: 0.85rem;
    width: 30px; height: 30px; border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
}
.eng-name { font-size: 1.15rem; font-weight: 700; color: #111827; }
.eng-tier {
    font-size: 0.68rem; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.04em; padding: 2px 9px; border-radius: 999px; margin-left: auto;
}
.t-exceptional { background: #ede9fe; color: #6d28d9; }
.t-strong { background: #dbeafe; color: #1d4ed8; }
.t-solid { background: #d1fae5; color: #065f46; }
.t-emerging { background: #f1f5f9; color: #475569; }

.score-row {
    display: flex; gap: 0.6rem; margin-bottom: 0.7rem; flex-wrap: wrap;
}
.score-box {
    flex: 1; min-width: 110px;
    background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px;
    padding: 0.6rem 0.8rem; text-align: center;
}
.score-box .s-val { font-size: 1.3rem; font-weight: 700; }
.score-box .s-lbl {
    font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.05em;
    color: #64748b; margin-top: 0.15rem;
}
.s-impact { color: #6366f1; }
.s-product { color: #8b5cf6; }
.s-team { color: #10b981; }
.s-tech { color: #f59e0b; }

.eng-summary {
    font-size: 0.88rem; color: #4b5563; line-height: 1.55;
    margin-top: 0.2rem;
}

/* ---- metric explainer card ---- */
.mx-card {
    background: #fff; border: 1px solid #e5e7eb; border-radius: 14px;
    padding: 1.3rem 1.5rem; margin-bottom: 1rem;
}
.mx-card h4 {
    font-size: 1rem; font-weight: 700; margin: 0 0 0.9rem 0; color: #111827;
}
.mx-section-lbl {
    font-size: 0.62rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.07em; color: #9ca3af; margin: 0.7rem 0 0.2rem 0;
}
.mx-section-lbl:first-of-type { margin-top: 0; }
.mx-card p {
    font-size: 0.87rem; color: #374151; line-height: 1.6; margin: 0.15rem 0 0 0;
}
.mx-formula {
    background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;
    padding: 0.5rem 0.8rem; font-family: 'SF Mono', 'Fira Code', monospace;
    font-size: 0.8rem; color: #4338ca; margin: 0.3rem 0 0 0;
}

/* ---- misc ---- */
.section-title {
    font-size: 1.1rem; font-weight: 700; color: #111827;
    margin: 1.4rem 0 0.6rem 0; padding-bottom: 0.4rem;
    border-bottom: 2px solid #e5e7eb;
}
</style>
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def tier_for(score: float) -> tuple[str, str]:
    if score >= 0.65:
        return "Exceptional", "t-exceptional"
    if score >= 0.45:
        return "Strong", "t-strong"
    if score >= 0.25:
        return "Solid", "t-solid"
    return "Emerging", "t-emerging"


def fmt_cycle(hours: float) -> str:
    if hours < 1:
        return f"{hours * 60:.0f}m"
    if hours < 48:
        return f"{hours:.1f}h"
    return f"{hours / 24:.1f}d"


# ---------------------------------------------------------------------------
# Rendered components (pure HTML where Streamlit's widgets are ugly)
# ---------------------------------------------------------------------------

def render_header(meta: dict, n_engineers: int) -> None:
    date_from = meta.get("date_from", "?")
    date_to = meta.get("date_to", "?")
    st.markdown(f"""
    <div class="dash-header">
        <h1>PostHog Engineer Impact Dashboard</h1>
        <p>Who are the most impactful engineers in
        <a href="https://github.com/PostHog/posthog" target="_blank">PostHog/posthog</a>
        — and why?<br/>
        Computed from GitHub PR data. Every number is traceable. Open <b>Methodology</b> to see the full story.</p>
        <div class="stat-row">
            <div class="stat-pill">
                <span class="stat-val">{n_engineers}</span>
                <span class="stat-lbl">Engineers</span>
            </div>
            <div class="stat-pill">
                <span class="stat-val">{meta.get('total_prs', '—')}</span>
                <span class="stat-lbl">PRs analyzed</span>
            </div>
            <div class="stat-pill">
                <span class="stat-val">{meta.get('merged_prs', '—')}</span>
                <span class="stat-lbl">Merged</span>
            </div>
            <div class="stat-pill">
                <span class="stat-val">{date_from}  →  {date_to}</span>
                <span class="stat-lbl">Window</span>
            </div>
            <div class="stat-pill">
                <span class="stat-val">{meta.get('days_covered', '—')}</span>
                <span class="stat-lbl">Days covered</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_engineer_html(row: pd.Series, rank: int) -> str:
    tier_label, tier_cls = tier_for(row["impact_score"])
    ct = fmt_cycle(row["avg_cycle_time_hours"])
    return f"""
    <div class="eng-card">
        <div class="eng-card-head">
            <div class="eng-rank">{rank}</div>
            <span class="eng-name">{row['engineer']}</span>
            <span class="eng-tier {tier_cls}">{tier_label}</span>
        </div>
        <div class="score-row">
            <div class="score-box">
                <div class="s-val s-impact">{row['impact_score']:.3f}</div>
                <div class="s-lbl">Impact</div>
            </div>
            <div class="score-box">
                <div class="s-val s-product">{row['product_score']:.3f}</div>
                <div class="s-lbl">Product · 40%</div>
            </div>
            <div class="score-box">
                <div class="s-val s-team">{row['team_score']:.3f}</div>
                <div class="s-lbl">Team · 30%</div>
            </div>
            <div class="score-box">
                <div class="s-val s-tech">{row['technical_score']:.3f}</div>
                <div class="s-lbl">Technical · 30%</div>
            </div>
        </div>
        <div class="eng-summary">{row['summary']}</div>
    </div>
    """


def make_impact_chart(top5: pd.DataFrame) -> go.Figure:
    df = top5.sort_values("impact_score", ascending=True)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=df["engineer"], x=df["product_score"] * 0.40,
        name="Product (40%)", orientation="h",
        marker_color="#8b5cf6", text=df["product_score"].apply(lambda v: f"{v:.2f}"),
        textposition="inside", textfont=dict(color="#fff", size=11),
    ))
    fig.add_trace(go.Bar(
        y=df["engineer"], x=df["team_score"] * 0.30,
        name="Team (30%)", orientation="h",
        marker_color="#10b981", text=df["team_score"].apply(lambda v: f"{v:.2f}"),
        textposition="inside", textfont=dict(color="#fff", size=11),
    ))
    fig.add_trace(go.Bar(
        y=df["engineer"], x=df["technical_score"] * 0.30,
        name="Technical (30%)", orientation="h",
        marker_color="#f59e0b", text=df["technical_score"].apply(lambda v: f"{v:.2f}"),
        textposition="inside", textfont=dict(color="#fff", size=11),
    ))
    fig.update_layout(
        barmode="stack",
        height=280,
        margin=dict(l=0, r=20, t=30, b=20),
        xaxis=dict(title="Weighted contribution to Impact Score", range=[0, 1.05]),
        yaxis=dict(tickfont=dict(size=12)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, font=dict(size=11)),
        plot_bgcolor="#fff",
        paper_bgcolor="#fff",
        font=dict(family="Inter, sans-serif"),
    )
    return fig


def render_metric_card_html(key: str) -> str:
    m = METRIC_STORIES[key]
    return f"""
    <div class="mx-card">
        <h4>{m['icon']}  {m['label']}</h4>
        <div class="mx-section-lbl">What it measures</div>
        <p>{m['what']}</p>
        <div class="mx-section-lbl">Formula</div>
        <div class="mx-formula">{m['formula']}</div>
        <div class="mx-section-lbl">Why this metric matters</div>
        <p>{m['why']}</p>
    </div>
    """


# ---------------------------------------------------------------------------
# Tab: Leaderboard
# ---------------------------------------------------------------------------

def tab_leaderboard(df: pd.DataFrame, top5: pd.DataFrame) -> None:
    for i, (_, row) in enumerate(top5.iterrows(), 1):
        st.markdown(render_engineer_html(row, i), unsafe_allow_html=True)
        with st.expander(f"📋 Evidence for {row['engineer']}"):
            e1, e2, e3 = st.columns(3)
            with e1:
                st.markdown("**Product signals**")
                st.markdown(f"- Merged PRs: **{int(row['merged_prs'])}**")
                st.markdown(f"- Weighted output: **{row['weighted_pr_output']:.1f}**")
                st.markdown(f"- Avg cycle time: **{fmt_cycle(row['avg_cycle_time_hours'])}**")
            with e2:
                st.markdown("**Team signals**")
                st.markdown(f"- Reviews given: **{int(row['reviews_given'])}**")
                st.markdown(f"- PRs reviewed: **{int(row['distinct_prs_reviewed'])}**")
                st.markdown(f"- Engineers helped: **{int(row['distinct_engineers_helped'])}**")
                st.markdown(f"- Unblocks: **{int(row['unblocks'])}**")
            with e3:
                st.markdown("**Technical signals**")
                st.markdown(f"- Bug fixes: **{int(row['bug_fix_prs'])}**")
                st.markdown(f"- Hotfixes: **{int(row['hotfix_prs'])}**")
                st.markdown(f"- Core-area touches: **{int(row['core_area_touch_count'])}**")
                st.markdown(f"- Refactors: **{int(row['refactor_prs'])}**")

    st.markdown('<div class="section-title">Score Breakdown — How Each Engineer\'s Impact Stacks Up</div>', unsafe_allow_html=True)
    st.plotly_chart(make_impact_chart(top5), width="stretch", config={"displayModeBar": False})


# ---------------------------------------------------------------------------
# Tab: Methodology
# ---------------------------------------------------------------------------

def tab_methodology() -> None:
    st.markdown(
        "Every number on this dashboard traces back to a specific GitHub API field and a documented calculation. "
        "Below is the **what**, **formula**, and **reasoning** for every metric."
    )

    st.markdown('<div class="section-title">The Composite Score</div>', unsafe_allow_html=True)
    st.markdown(render_metric_card_html("impact_score"), unsafe_allow_html=True)

    st.markdown('<div class="section-title">The Three Dimensions</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(render_metric_card_html("product_score"), unsafe_allow_html=True)
    with c2:
        st.markdown(render_metric_card_html("team_score"), unsafe_allow_html=True)
    with c3:
        st.markdown(render_metric_card_html("technical_score"), unsafe_allow_html=True)

    st.markdown('<div class="section-title">Product Metrics — Inputs to Product Score</div>', unsafe_allow_html=True)
    p1, p2, p3 = st.columns(3)
    with p1:
        st.markdown(render_metric_card_html("merged_prs"), unsafe_allow_html=True)
    with p2:
        st.markdown(render_metric_card_html("weighted_pr_output"), unsafe_allow_html=True)
    with p3:
        st.markdown(render_metric_card_html("avg_cycle_time_hours"), unsafe_allow_html=True)

    st.markdown('<div class="section-title">Team Metrics — Inputs to Team Score</div>', unsafe_allow_html=True)
    t1, t2, t3 = st.columns(3)
    with t1:
        st.markdown(render_metric_card_html("reviews_given"), unsafe_allow_html=True)
    with t2:
        st.markdown(render_metric_card_html("distinct_engineers_helped"), unsafe_allow_html=True)
    with t3:
        st.markdown(render_metric_card_html("unblocks"), unsafe_allow_html=True)

    st.markdown('<div class="section-title">Technical Metrics — Inputs to Technical Score</div>', unsafe_allow_html=True)
    te1, te2 = st.columns(2)
    with te1:
        st.markdown(render_metric_card_html("bug_fix_prs"), unsafe_allow_html=True)
        st.markdown(render_metric_card_html("core_area_touch_count"), unsafe_allow_html=True)
    with te2:
        st.markdown(render_metric_card_html("hotfix_prs"), unsafe_allow_html=True)
        st.markdown(render_metric_card_html("refactor_prs"), unsafe_allow_html=True)

    st.markdown('<div class="section-title">Normalization & Outlier Handling</div>', unsafe_allow_html=True)
    st.markdown(render_metric_card_html("_normalization"), unsafe_allow_html=True) if "_normalization" in METRIC_STORIES else None
    st.markdown("""
    <div class="mx-card">
        <h4>📐  Normalization</h4>
        <div class="mx-section-lbl">What it does</div>
        <p>Transforms every raw metric to a 0–1 scale so they can be combined into weighted scores.</p>
        <div class="mx-section-lbl">Formula</div>
        <div class="mx-formula">norm(x) = (x − min) / (max − min), after clipping at 5th and 95th percentiles</div>
        <div class="mx-section-lbl">Why this approach</div>
        <p>Min-max normalization is the simplest defensible choice. Percentile clipping at 5th/95th prevents a single
        extreme outlier (e.g., a bot that slipped through or an engineer with 200 PRs) from compressing everyone else
        to near-zero. For metrics where lower is better (cycle time), we invert: <code>1 − norm(value)</code>.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="mx-card">
        <h4>🤖  Bot Filtering</h4>
        <div class="mx-section-lbl">What we filter</div>
        <p>Automated accounts are excluded from <b>both</b> authorship and review metrics.</p>
        <div class="mx-section-lbl">Accounts removed</div>
        <p>dependabot, greptile-apps, copilot-pull-request-reviewer, graphite-app, github-actions, stamphog,
        chatgpt-codex-connector, and any login containing <code>[bot]</code>.</p>
        <div class="mx-section-lbl">Why</div>
        <p>Without filtering, bot reviews inflate team scores for engineers whose PRs happen to attract automated
        reviewers. In this dataset, bots accounted for ~160 review records — enough to materially shift rankings.</p>
    </div>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Tab: Data Evidence
# ---------------------------------------------------------------------------

def tab_data(df: pd.DataFrame, top5: pd.DataFrame) -> None:
    st.markdown(
        "Full transparency — every input that produces the scores above. "
        "Use this to validate any ranking."
    )

    st.markdown('<div class="section-title">Top 5 — Complete Metric Breakdown</div>', unsafe_allow_html=True)
    display_cols = [
        "engineer", "impact_score", "product_score", "team_score", "technical_score",
        "merged_prs", "weighted_pr_output", "avg_cycle_time_hours",
        "reviews_given", "distinct_prs_reviewed", "distinct_engineers_helped", "unblocks",
        "bug_fix_prs", "hotfix_prs", "refactor_prs", "core_area_touch_count",
    ]
    st.dataframe(
        top5[display_cols].style.format({
            "impact_score": "{:.3f}", "product_score": "{:.3f}",
            "team_score": "{:.3f}", "technical_score": "{:.3f}",
            "weighted_pr_output": "{:.1f}", "avg_cycle_time_hours": "{:.1f}",
        }),
        width="stretch",
    )

    st.markdown('<div class="section-title">All Engineers</div>', unsafe_allow_html=True)
    all_cols = [
        "engineer", "impact_score", "merged_prs", "weighted_pr_output",
        "reviews_given", "unblocks", "bug_fix_prs", "core_area_touch_count",
    ]
    st.dataframe(
        df[all_cols].style.format({"impact_score": "{:.3f}", "weighted_pr_output": "{:.1f}"}),
        width="stretch",
        height=500,
    )
    st.caption("Every column header matches a metric explained in the Methodology tab.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(page_title="PostHog Impact Dashboard", page_icon="📊", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)

    df = load_data()
    if df.empty:
        st.error("No data found. Run: `python -m src.impact_dashboard.cli.main all`")
        return

    meta = load_metadata()
    top5 = df.sort_values("impact_score", ascending=False).head(5).copy()

    render_header(meta, n_engineers=int(df["engineer"].nunique()))

    tabs = st.tabs(["Leaderboard", "Methodology", "Data Evidence"])
    with tabs[0]:
        tab_leaderboard(df, top5)
    with tabs[1]:
        tab_methodology()
    with tabs[2]:
        tab_data(df, top5)


if __name__ == "__main__":
    main()
