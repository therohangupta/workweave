from __future__ import annotations

import pandas as pd


def aggregate_engineer_metrics(prs: pd.DataFrame, reviews: pd.DataFrame) -> pd.DataFrame:
    authored = prs[prs["is_merged"]].copy()

    product = (
        authored.groupby("author", dropna=False)
        .agg(
            merged_prs=("pr_number", "count"),
            weighted_pr_output=("weighted_pr_output_component", "sum"),
            avg_cycle_time_hours=("cycle_time_hours", "mean"),
            median_cycle_time_hours=("cycle_time_hours", "median"),
            complex_pr_count=("complexity_score", lambda s: int((s >= 0.6).sum())),
        )
        .reset_index()
        .rename(columns={"author": "engineer"})
    )

    technical = (
        authored.groupby("author", dropna=False)
        .agg(
            bug_fix_prs=("is_bugfix", "sum"),
            hotfix_prs=("is_hotfix", "sum"),
            refactor_prs=("is_refactor", "sum"),
            infra_prs=("is_infra", "sum"),
            core_area_touch_count=("is_core_area", "sum"),
        )
        .reset_index()
        .rename(columns={"author": "engineer"})
    )

    if reviews.empty:
        team = pd.DataFrame(
            columns=[
                "engineer",
                "reviews_given",
                "distinct_prs_reviewed",
                "unblocks",
                "review_response_time_hours",
            ]
        )
    else:
        team = (
            reviews.groupby("reviewer", dropna=False)
            .agg(
                reviews_given=("pr_number", "count"),
                distinct_prs_reviewed=("pr_number", "nunique"),
                unblocks=("counts_as_unblock", "sum"),
                review_response_time_hours=("time_to_merge_after_review_hours", "mean"),
            )
            .reset_index()
            .rename(columns={"reviewer": "engineer"})
        )

    review_with_author = reviews.merge(
        prs[["pr_number", "author"]].rename(columns={"author": "pr_author"}),
        on="pr_number",
        how="left",
    )
    distinct_helped = (
        review_with_author[review_with_author["reviewer"] != review_with_author["pr_author"]]
        .groupby("reviewer", dropna=False)["pr_author"]
        .nunique()
        .reset_index()
        .rename(columns={"reviewer": "engineer", "pr_author": "distinct_engineers_helped"})
    )
    team = team.merge(distinct_helped, on="engineer", how="left")

    metrics = product.merge(technical, on="engineer", how="outer").merge(team, on="engineer", how="outer")
    metrics["distinct_engineers_helped"] = metrics["distinct_engineers_helped"].fillna(0)
    return metrics.fillna(0)
