from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..github.client import GitHubGraphQLClient
from ..pipeline.aggregate import aggregate_engineer_metrics
from ..pipeline.features import add_pr_features, add_review_features
from ..pipeline.narrate import add_summaries
from ..pipeline.normalize import normalize_prs
from ..pipeline.score import score_metrics
from ..settings import settings
from ..utils.io import read_json, write_json


def fetch(days: int, max_prs: int) -> Path:
    if not settings.github_token:
        raise RuntimeError("Missing GITHUB_TOKEN in environment/.env.")

    client = GitHubGraphQLClient(settings.github_token)
    print(f"Fetching PRs from {settings.owner}/{settings.repo} (last {days} days)...", file=sys.stderr)
    raw_prs = client.fetch_pull_requests(days=days, max_prs=max_prs)
    raw_path = settings.data_raw_dir / "prs_raw.json"
    write_json(raw_path, raw_prs)
    print(f"Saved {len(raw_prs)} raw PRs to {raw_path}", file=sys.stderr)
    return raw_path


def build() -> Path:
    raw_path = settings.data_raw_dir / "prs_raw.json"
    raw_prs = read_json(raw_path)
    print(f"Building metrics from {len(raw_prs)} raw PRs...", file=sys.stderr)

    prs, reviews, comments = normalize_prs(raw_prs)
    print(f"  After bot filtering: {len(prs)} PRs, {len(reviews)} reviews, {len(comments)} comments", file=sys.stderr)

    prs = add_pr_features(prs)
    reviews = add_review_features(reviews)

    metrics = aggregate_engineer_metrics(prs, reviews)
    metrics = score_metrics(metrics)
    metrics = add_summaries(metrics)

    print(f"  Scored {len(metrics)} engineers", file=sys.stderr)

    write_json(settings.data_interim_dir / "prs.json", prs.to_dict(orient="records"))
    write_json(settings.data_interim_dir / "reviews.json", reviews.to_dict(orient="records"))
    write_json(settings.data_interim_dir / "comments.json", comments.to_dict(orient="records"))

    out_json = settings.data_processed_dir / "engineer_metrics.json"
    write_json(out_json, metrics.to_dict(orient="records"))
    metrics.to_csv(settings.data_processed_dir / "engineer_metrics.csv", index=False)
    return out_json


def run_all(days: int, max_prs: int) -> Path:
    fetch(days=days, max_prs=max_prs)
    return build()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PostHog impact dashboard pipeline")
    sub = parser.add_subparsers(dest="cmd", required=True)

    fetch_parser = sub.add_parser("fetch")
    fetch_parser.add_argument("--days", type=int, default=settings.days)
    fetch_parser.add_argument("--max-prs", type=int, default=0, help="0 = fetch all PRs in window")

    sub.add_parser("build")

    all_parser = sub.add_parser("all")
    all_parser.add_argument("--days", type=int, default=settings.days)
    all_parser.add_argument("--max-prs", type=int, default=0, help="0 = fetch all PRs in window")

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.cmd == "fetch":
        path = fetch(days=args.days, max_prs=args.max_prs)
    elif args.cmd == "build":
        path = build()
    else:
        path = run_all(days=args.days, max_prs=args.max_prs)

    print(f"Done. Output: {path}")


if __name__ == "__main__":
    main()
