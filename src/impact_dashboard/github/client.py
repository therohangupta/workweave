from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from ..settings import settings
from .queries import SEARCH_PRS_QUERY

BOT_LOGINS = frozenset({
    "dependabot",
    "dependabot[bot]",
    "renovate",
    "renovate[bot]",
    "github-actions",
    "github-actions[bot]",
    "greptile-apps",
    "greptile-apps[bot]",
    "copilot-pull-request-reviewer",
    "copilot-pull-request-reviewer[bot]",
    "graphite-app",
    "graphite-app[bot]",
    "stamphog",
    "stamphog[bot]",
    "chatgpt-codex-connector",
    "chatgpt-codex-connector[bot]",
    "codecov",
    "codecov[bot]",
    "posthog-bot",
    "posthog-bot[bot]",
    "stale",
    "stale[bot]",
})


def is_bot(login: str | None) -> bool:
    if not login:
        return True
    lower = login.lower()
    if lower in BOT_LOGINS:
        return True
    if "[bot]" in lower or lower == "unknown":
        return True
    return False


class GitHubGraphQLClient:
    def __init__(self, token: str) -> None:
        self.url = "https://api.github.com/graphql"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def execute(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        retries = 4
        for attempt in range(1, retries + 1):
            response = requests.post(
                self.url,
                headers=self.headers,
                json={"query": query, "variables": variables},
                timeout=60,
            )
            if response.status_code == 403:
                reset = response.headers.get("X-RateLimit-Reset")
                if reset:
                    wait = max(int(reset) - int(time.time()), 1) + 2
                    print(f"  Rate limited. Waiting {wait}s...", file=sys.stderr)
                    time.sleep(wait)
                    continue
            if response.status_code >= 500 and attempt < retries:
                time.sleep(2 * attempt)
                continue
            response.raise_for_status()
            payload = response.json()
            if "errors" in payload:
                raise RuntimeError(f"GitHub GraphQL errors: {payload['errors']}")
            return payload["data"]
        raise RuntimeError("Failed to execute GitHub query after retries.")

    def _fetch_window(self, date_from: str, date_to: str) -> list[dict[str, Any]]:
        """Fetch all PRs in a single date window (must return < 1000)."""
        query_string = (
            f"repo:{settings.owner}/{settings.repo} is:pr "
            f"created:{date_from}..{date_to} sort:created-desc"
        )
        cursor: str | None = None
        prs: list[dict[str, Any]] = []

        while True:
            data = self.execute(
                SEARCH_PRS_QUERY,
                {"queryString": query_string, "cursor": cursor},
            )
            search = data["search"]
            nodes = search["nodes"] or []
            pr_nodes = [node for node in nodes if node]
            prs.extend(pr_nodes)

            page_info = search["pageInfo"]
            if not page_info["hasNextPage"]:
                break
            cursor = page_info["endCursor"]

        return prs

    def fetch_pull_requests(self, days: int, max_prs: int) -> list[dict[str, Any]]:
        """Fetch PRs using weekly windows to avoid the 1000-result search API limit."""
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=days)
        window_size = timedelta(days=7)

        all_prs: list[dict[str, Any]] = []
        seen_numbers: set[int] = set()

        current = window_start
        window_num = 0
        while current < now:
            window_num += 1
            window_end = min(current + window_size, now)
            date_from = current.strftime("%Y-%m-%d")
            date_to = window_end.strftime("%Y-%m-%d")
            print(
                f"  Window {window_num}: {date_from} to {date_to} (total so far: {len(all_prs)})...",
                file=sys.stderr,
            )

            prs = self._fetch_window(date_from, date_to)
            for pr in prs:
                pr_num = pr.get("number")
                if pr_num and pr_num not in seen_numbers:
                    seen_numbers.add(pr_num)
                    all_prs.append(pr)

            current = window_end

            if max_prs and len(all_prs) >= max_prs:
                all_prs = all_prs[:max_prs]
                break

        print(f"  Fetched {len(all_prs)} unique PRs across {window_num} windows.", file=sys.stderr)
        return all_prs
