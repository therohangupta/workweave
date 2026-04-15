from __future__ import annotations

import pandas as pd


def _clip_and_norm(series: pd.Series) -> pd.Series:
    if series.empty:
        return series
    lo = series.quantile(0.05)
    hi = series.quantile(0.95)
    clipped = series.clip(lower=lo, upper=hi)
    min_v = clipped.min()
    max_v = clipped.max()
    if max_v == min_v:
        return pd.Series(0.0, index=series.index)
    return (clipped - min_v) / (max_v - min_v)


def score_metrics(metrics: pd.DataFrame) -> pd.DataFrame:
    df = metrics.copy()

    df["weighted_pr_output_norm"] = _clip_and_norm(df["weighted_pr_output"])
    df["merged_prs_norm"] = _clip_and_norm(df["merged_prs"])
    df["avg_cycle_time_hours_inv_norm"] = 1 - _clip_and_norm(df["avg_cycle_time_hours"])

    df["unblocks_norm"] = _clip_and_norm(df["unblocks"])
    df["reviews_given_norm"] = _clip_and_norm(df["reviews_given"])
    df["distinct_engineers_helped_norm"] = _clip_and_norm(df["distinct_engineers_helped"])

    df["bug_fix_prs_norm"] = _clip_and_norm(df["bug_fix_prs"])
    df["hotfix_prs_norm"] = _clip_and_norm(df["hotfix_prs"])
    df["core_area_touch_count_norm"] = _clip_and_norm(df["core_area_touch_count"])
    df["refactor_prs_norm"] = _clip_and_norm(df["refactor_prs"])

    df["product_score"] = (
        0.50 * df["weighted_pr_output_norm"]
        + 0.30 * df["merged_prs_norm"]
        + 0.20 * df["avg_cycle_time_hours_inv_norm"]
    )
    df["team_score"] = (
        0.45 * df["unblocks_norm"]
        + 0.30 * df["reviews_given_norm"]
        + 0.25 * df["distinct_engineers_helped_norm"]
    )
    df["technical_score"] = (
        0.40 * df["bug_fix_prs_norm"]
        + 0.25 * df["hotfix_prs_norm"]
        + 0.20 * df["core_area_touch_count_norm"]
        + 0.15 * df["refactor_prs_norm"]
    )
    df["impact_score"] = 0.40 * df["product_score"] + 0.30 * df["team_score"] + 0.30 * df["technical_score"]
    df = df.sort_values("impact_score", ascending=False).reset_index(drop=True)
    df["impact_rank"] = df.index + 1
    return df
