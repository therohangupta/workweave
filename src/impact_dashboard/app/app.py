from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parents[3]
DATA_PATH = ROOT / "data" / "processed" / "engineer_metrics.json"


@st.cache_data
def load_data() -> pd.DataFrame:
    if not DATA_PATH.exists():
        return pd.DataFrame()
    return pd.read_json(DATA_PATH)


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .main .block-container {padding-top: 1.4rem; padding-bottom: 2.2rem; max-width: 1200px;}
        .ww-chip {
            display: inline-block;
            padding: 0.22rem 0.65rem;
            border-radius: 999px;
            background: #eef2ff;
            color: #3730a3;
            font-size: 0.78rem;
            font-weight: 600;
            margin-right: 0.35rem;
        }
        .ww-card {
            background: linear-gradient(180deg, #ffffff 0%, #fafbff 100%);
            border: 1px solid #e6e9f2;
            border-radius: 14px;
            padding: 1rem 1rem 0.8rem 1rem;
            margin-bottom: 0.8rem;
        }
        .ww-muted { color: #4b5563; font-size: 0.92rem; }
        .ww-formula {
            border-left: 4px solid #4f46e5;
            background: #f7f7ff;
            border-radius: 8px;
            padding: 0.7rem 0.9rem;
            margin: 0.55rem 0 0.8rem 0;
            color: #1f2937;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def show_info_icon(title: str, details: str) -> None:
    if hasattr(st, "popover"):
        with st.popover("ℹ️", use_container_width=False):
            st.markdown(f"**{title}**")
            st.write(details)
    else:
        with st.expander(f"ℹ️ {title}"):
            st.write(details)


def render_methodology() -> None:
    st.subheader("How to read this leaderboard")
    st.markdown(
        """
        <span class="ww-chip">Thoughtfulness</span>
        <span class="ww-chip">Technical execution</span>
        <span class="ww-chip">Communication</span>
        <span class="ww-chip">Pragmatism</span>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="ww-formula">
        <b>Final Impact Score</b><br/>
        impact = 0.40 × Product + 0.30 × Team + 0.30 × Technical
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Product score (40%)**")
        show_info_icon(
            "Product score inputs",
            "Measures shipped work quality and velocity. Uses weighted PR output, merged PR count, "
            "and cycle time (lower cycle time scores higher).",
        )
    with c2:
        st.markdown("**Team score (30%)**")
        show_info_icon(
            "Team score inputs",
            "Measures collaboration leverage. Uses unblocks, total reviews given, and number of distinct "
            "engineers helped through reviews.",
        )
    with c3:
        st.markdown("**Technical score (30%)**")
        show_info_icon(
            "Technical score inputs",
            "Measures codebase health impact. Uses bug-fix PRs, hotfix PRs, core-area touches, and refactors.",
        )

    st.markdown(
        "<p class='ww-muted'>All component metrics are normalized to 0-1 with outlier clipping so one extreme value does not dominate.</p>",
        unsafe_allow_html=True,
    )


def render_card(row: pd.Series) -> None:
    st.markdown("<div class='ww-card'>", unsafe_allow_html=True)
    st.subheader(f"#{int(row['impact_rank'])} {row['engineer']}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Impact", f"{row['impact_score']:.3f}")
    c2.metric("Product", f"{row['product_score']:.3f}")
    c3.metric("Team", f"{row['team_score']:.3f}")
    c4.metric("Technical", f"{row['technical_score']:.3f}")
    st.progress(float(row["impact_score"]))
    st.caption(row["summary"])
    with st.expander("Metric evidence behind this score"):
        ec1, ec2, ec3 = st.columns(3)
        ec1.write(f"- merged_prs: `{int(row['merged_prs'])}`")
        ec1.write(f"- weighted_pr_output: `{row['weighted_pr_output']:.2f}`")
        ec1.write(f"- avg_cycle_time_hours: `{row['avg_cycle_time_hours']:.2f}`")
        ec2.write(f"- reviews_given: `{int(row['reviews_given'])}`")
        ec2.write(f"- distinct_prs_reviewed: `{int(row['distinct_prs_reviewed'])}`")
        ec2.write(f"- unblocks: `{int(row['unblocks'])}`")
        ec3.write(f"- bug_fix_prs: `{int(row['bug_fix_prs'])}`")
        ec3.write(f"- hotfix_prs: `{int(row['hotfix_prs'])}`")
        ec3.write(f"- core_area_touch_count: `{int(row['core_area_touch_count'])}`")
    st.markdown("</div>", unsafe_allow_html=True)


def main() -> None:
    st.set_page_config(page_title="PostHog Impact Dashboard", layout="wide")
    inject_styles()
    st.title("PostHog Engineer Impact Dashboard")
    st.caption(
        "Last 90 days. Fast-loading precomputed analysis from GitHub PR activity. "
        "Use the info icons to understand exactly how scores are calculated."
    )

    df = load_data()
    if df.empty:
        st.warning("No processed dataset found. Run: python -m src.impact_dashboard.cli.main all")
        return

    top5 = df.sort_values("impact_score", ascending=False).head(5).copy()
    top5["impact_score_pct"] = (top5["impact_score"] * 100).round(1)

    tab1, tab2, tab3 = st.tabs(["Leaderboard", "Methodology", "Data Evidence"])
    with tab1:
        m1, m2, m3 = st.columns(3)
        m1.metric("Analyzed Engineers", int(df["engineer"].nunique()))
        m2.metric("Top Score", f"{top5['impact_score'].max():.3f}")
        m3.metric("Window", "90 days")

        left, right = st.columns([1.7, 1.0])
        with left:
            st.subheader("Top 5 Engineers")
            for _, row in top5.iterrows():
                render_card(row)
        with right:
            st.subheader("Impact by Engineer")
            st.bar_chart(top5.set_index("engineer")["impact_score"])
            st.subheader("Component Mix")
            st.bar_chart(
                top5.set_index("engineer")[["product_score", "team_score", "technical_score"]]
            )

    with tab2:
        render_methodology()
        st.markdown("### Validation checklist")
        st.write("- Clear ranking of who is most impactful now.")
        st.write("- Formula and weights are visible.")
        st.write("- Evidence metrics are visible per engineer.")
        st.write("- Inputs are normalized and clipped to reduce outlier bias.")

    with tab3:
        st.subheader("Top 5 detailed metrics")
        st.dataframe(
            top5[
                [
                    "engineer",
                    "impact_rank",
                    "impact_score",
                    "product_score",
                    "team_score",
                    "technical_score",
                    "merged_prs",
                    "weighted_pr_output",
                    "avg_cycle_time_hours",
                    "reviews_given",
                    "distinct_prs_reviewed",
                    "distinct_engineers_helped",
                    "unblocks",
                    "bug_fix_prs",
                    "hotfix_prs",
                    "refactor_prs",
                    "core_area_touch_count",
                ]
            ],
            use_container_width=True,
        )
        st.caption(
            "This table is included so reviewers can validate findings instead of relying on opaque scores."
        )


if __name__ == "__main__":
    main()
