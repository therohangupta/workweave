from __future__ import annotations

import pandas as pd


def _top_contribution_type(row: pd.Series) -> str:
    scores = {
        "shipping code": row["product_score"],
        "reviewing & unblocking others": row["team_score"],
        "technical health (bugs, infra, refactors)": row["technical_score"],
    }
    return max(scores, key=scores.get)


def _summary(row: pd.Series) -> str:
    parts: list[str] = []

    merged = int(row["merged_prs"])
    if merged > 0:
        cycle = row["avg_cycle_time_hours"]
        cycle_str = f"{cycle:.0f}h" if cycle < 48 else f"{cycle / 24:.1f}d"
        parts.append(f"Shipped {merged} merged PR{'s' if merged != 1 else ''} (avg cycle time {cycle_str})")

    complex_count = int(row.get("complex_pr_count", 0))
    if complex_count > 0:
        parts.append(f"including {complex_count} complex cross-directory change{'s' if complex_count != 1 else ''}")

    reviews = int(row["reviews_given"])
    if reviews > 0:
        helped = int(row["distinct_engineers_helped"])
        unblocks = int(row["unblocks"])
        review_parts = [f"Reviewed {reviews} PR{'s' if reviews != 1 else ''}"]
        if helped > 0:
            review_parts.append(f"across {helped} contributor{'s' if helped != 1 else ''}")
        if unblocks > 0:
            review_parts.append(f"unblocking {unblocks} merge{'s' if unblocks != 1 else ''}")
        parts.append(", ".join(review_parts))

    bugfixes = int(row["bug_fix_prs"])
    core = int(row["core_area_touch_count"])
    tech_bits: list[str] = []
    if bugfixes > 0:
        tech_bits.append(f"{bugfixes} bug fix{'es' if bugfixes != 1 else ''}")
    if core > 0:
        tech_bits.append(f"{core} core-area touch{'es' if core != 1 else ''}")
    if tech_bits:
        parts.append("Technical: " + ", ".join(tech_bits))

    top_type = _top_contribution_type(row)
    parts.append(f"Strongest signal: {top_type}")

    return ". ".join(parts) + "."


def add_summaries(metrics: pd.DataFrame) -> pd.DataFrame:
    df = metrics.copy()
    df["summary"] = df.apply(_summary, axis=1)
    return df
