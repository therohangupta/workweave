from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from ..settings import settings
from .queries import SEARCH_PRS_QUERY


class GitHubGraphQLClient:
    def __init__(self, token: str) -> None:
        self.url = "https://api.github.com/graphql"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def execute(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        retries = 3
        for attempt in range(1, retries + 1):
            response = requests.post(
                self.url,
                headers=self.headers,
                json={"query": query, "variables": variables},
                timeout=60,
            )
            if response.status_code >= 500 and attempt < retries:
                time.sleep(1.5 * attempt)
                continue
            response.raise_for_status()
            payload = response.json()
            if "errors" in payload:
                raise RuntimeError(f"GitHub GraphQL errors: {payload['errors']}")
            return payload["data"]
        raise RuntimeError("Failed to execute GitHub query after retries.")

    def fetch_pull_requests(self, days: int, max_prs: int) -> list[dict[str, Any]]:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
        query_string = (
            f"repo:{settings.owner}/{settings.repo} is:pr created:>={cutoff} sort:created-desc"
        )
        cursor: str | None = None
        prs: list[dict[str, Any]] = []

        while len(prs) < max_prs:
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

        return prs[:max_prs]
