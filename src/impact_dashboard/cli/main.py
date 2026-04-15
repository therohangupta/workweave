from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

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
    raw_prs = client.fetch_pull_requests(days=days, max_prs=max_prs)
    raw_path = settings.data_raw_dir / "prs_raw.json"
    write_json(raw_path, raw_prs)
    return raw_path


def build() -> Path:
    raw_path = settings.data_raw_dir / "prs_raw.json"
    raw_prs = read_json(raw_path)

    prs, reviews, comments = normalize_prs(raw_prs)
    prs = add_pr_features(prs)
    reviews = add_review_features(reviews)

    metrics = aggregate_engineer_metrics(prs, reviews)
    metrics = score_metrics(metrics)
    metrics = add_summaries(metrics)

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
    fetch_parser.add_argument("--max-prs", type=int, default=settings.max_prs)

    sub.add_parser("build")

    all_parser = sub.add_parser("all")
    all_parser.add_argument("--days", type=int, default=settings.days)
    all_parser.add_argument("--max-prs", type=int, default=settings.max_prs)

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.cmd == "fetch":
        path = fetch(days=args.days, max_prs=args.max_prs)
    elif args.cmd == "build":
        path = build()
    else:
        path = run_all(days=args.days, max_prs=args.max_prs)

    print(f"Wrote output: {path}")


if __name__ == "__main__":
    main()
