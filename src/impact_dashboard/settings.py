from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    owner: str = "PostHog"
    repo: str = "posthog"
    days: int = 90
    max_prs: int = 200
    github_token: str | None = os.getenv("GITHUB_TOKEN")
    root_dir: Path = Path(__file__).resolve().parents[2]

    @property
    def data_raw_dir(self) -> Path:
        return self.root_dir / "data" / "raw"

    @property
    def data_interim_dir(self) -> Path:
        return self.root_dir / "data" / "interim"

    @property
    def data_processed_dir(self) -> Path:
        return self.root_dir / "data" / "processed"


settings = Settings()
