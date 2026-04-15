from __future__ import annotations

from typing import Any

import pandas as pd


def _safe_login(author_obj: dict[str, Any] | None) -> str:
    if not author_obj:
        return "unknown"
    return author_obj.get("login") or "unknown"


def _directories(paths: list[str]) -> list[str]:
    dirs: set[str] = set()
    for path in paths:
        parts = path.split("/")
        dirs.add(parts[0] if parts else "root")
    return sorted(dirs)


def normalize_prs(raw_prs: list[dict[str, Any]]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    pr_rows: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []
    comment_rows: list[dict[str, Any]] = []

    for pr in raw_prs:
        pr_number = pr["number"]
        file_nodes = (pr.get("files") or {}).get("nodes") or []
        file_paths = [node["path"] for node in file_nodes if node and node.get("path")]
        labels = [(node.get("name") or "").lower() for node in (pr.get("labels") or {}).get("nodes", [])]

        pr_rows.append(
            {
                "pr_number": pr_number,
                "title": pr.get("title", ""),
                "author": _safe_login(pr.get("author")),
                "created_at": pr.get("createdAt"),
                "merged_at": pr.get("mergedAt"),
                "closed_at": pr.get("closedAt"),
                "state": pr.get("state"),
                "url": pr.get("url"),
                "labels": labels,
                "additions": pr.get("additions") or 0,
                "deletions": pr.get("deletions") or 0,
                "changed_files": pr.get("changedFiles") or len(file_paths),
                "file_paths": file_paths,
                "directories_touched": _directories(file_paths),
            }
        )

        for review in (pr.get("reviews") or {}).get("nodes", []):
            if not review:
                continue
            review_rows.append(
                {
                    "pr_number": pr_number,
                    "reviewer": _safe_login(review.get("author")),
                    "review_state": review.get("state"),
                    "created_at": review.get("createdAt"),
                    "merged_at": pr.get("mergedAt"),
                }
            )

        for comment in (pr.get("comments") or {}).get("nodes", []):
            if not comment:
                continue
            comment_rows.append(
                {
                    "pr_number": pr_number,
                    "commenter": _safe_login(comment.get("author")),
                    "created_at": comment.get("createdAt"),
                    "type": "general",
                }
            )

    return pd.DataFrame(pr_rows), pd.DataFrame(review_rows), pd.DataFrame(comment_rows)
