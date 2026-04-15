from __future__ import annotations

import pandas as pd


def add_summaries(metrics: pd.DataFrame) -> pd.DataFrame:
    df = metrics.copy()

    def _summary(row: pd.Series) -> str:
        return (
            f"Shipped {int(row['merged_prs'])} merged PRs with weighted output {row['weighted_pr_output']:.1f}, "
            f"reviewed {int(row['reviews_given'])} PRs, and unblocked {int(row['unblocks'])} merges. "
            f"Technical contribution includes {int(row['bug_fix_prs'])} bug-fix PRs and "
            f"{int(row['core_area_touch_count'])} core-area touches."
        )

    df["summary"] = df.apply(_summary, axis=1)
    return df
