from __future__ import annotations

import numpy as np
import pandas as pd

CORE_AREAS = (
    "posthog/",
    "plugin-server/",
    "frontend/",
    "ee/",
    "hogql/",
    "cyclotron/",
    "rust/",
)


def _has_core_path(paths: list[str]) -> bool:
    return any(any(path.startswith(area) for area in CORE_AREAS) for path in paths)


def add_pr_features(prs: pd.DataFrame) -> pd.DataFrame:
    df = prs.copy()

    df["created_at"] = pd.to_datetime(df["created_at"], utc=True, errors="coerce")
    df["merged_at"] = pd.to_datetime(df["merged_at"], utc=True, errors="coerce")

    df["is_merged"] = df["state"].eq("MERGED") & df["merged_at"].notna()
    df["total_lines_changed"] = df["additions"].fillna(0) + df["deletions"].fillna(0)
    df["directory_spread"] = df["directories_touched"].apply(lambda x: len(x) if isinstance(x, list) else 0)
    df["cycle_time_hours"] = (df["merged_at"] - df["created_at"]).dt.total_seconds() / 3600.0
    df["cycle_time_hours"] = df["cycle_time_hours"].clip(lower=0)

    labels_str = df["labels"].apply(lambda xs: " ".join(xs) if isinstance(xs, list) else "")
    title_str = df["title"].fillna("").astype(str).str.lower()

    df["is_bugfix"] = labels_str.str.contains("bug|fix", regex=True) | title_str.str.contains(
        "bug|fix|error|issue", regex=True
    )
    df["is_hotfix"] = labels_str.str.contains("hotfix|urgent", regex=True) | title_str.str.contains(
        "hotfix|urgent|patch", regex=True
    )
    df["is_refactor"] = labels_str.str.contains("refactor", regex=True) | title_str.str.contains(
        "refactor|cleanup", regex=True
    )
    df["is_infra"] = labels_str.str.contains("infra|ci|devops", regex=True) | title_str.str.contains(
        "infra|ci|pipeline|deploy|tooling", regex=True
    )
    df["is_core_area"] = df["file_paths"].apply(lambda paths: _has_core_path(paths if isinstance(paths, list) else []))

    for col in ("changed_files", "total_lines_changed", "directory_spread"):
        lo = df[col].quantile(0.05)
        hi = df[col].quantile(0.95)
        clipped = df[col].clip(lower=lo, upper=hi)
        min_v = clipped.min()
        max_v = clipped.max()
        if pd.isna(min_v) or pd.isna(max_v) or max_v == min_v:
            df[f"{col}_norm"] = 0.0
        else:
            df[f"{col}_norm"] = (clipped - min_v) / (max_v - min_v)

    df["complexity_score"] = (
        0.35 * df["changed_files_norm"] + 0.35 * df["total_lines_changed_norm"] + 0.30 * df["directory_spread_norm"]
    )
    df["weighted_pr_output_component"] = np.where(df["is_merged"], 1.0 + df["complexity_score"], 0.0)

    return df


def add_review_features(reviews: pd.DataFrame) -> pd.DataFrame:
    if reviews.empty:
        return reviews.assign(
            time_to_merge_after_review_hours=pd.Series(dtype=float),
            counts_as_unblock=pd.Series(dtype=bool),
        )

    df = reviews.copy()
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True, errors="coerce")
    df["merged_at"] = pd.to_datetime(df["merged_at"], utc=True, errors="coerce")
    df["time_to_merge_after_review_hours"] = (df["merged_at"] - df["created_at"]).dt.total_seconds() / 3600.0
    df["counts_as_unblock"] = df["time_to_merge_after_review_hours"].between(0, 24, inclusive="both")
    return df
