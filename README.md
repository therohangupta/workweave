# PostHog Engineer Impact Dashboard

A single-page dashboard that identifies the **top 5 most impactful engineers** in [`PostHog/posthog`](https://github.com/PostHog/posthog) over the last 90 days and explains **why** they rank highly.

Built for a busy engineering leader who needs to quickly understand who is moving important work forward, who is unblocking others, and who is keeping the codebase healthy — without relying on vanity metrics like raw commits or lines of code.

---

## Quick start

```bash
# 1. Activate your environment
conda activate workweave

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add your GitHub token
echo "GITHUB_TOKEN=ghp_..." > .env

# 4. Fetch data and build scores (full 90-day window)
python -m src.impact_dashboard.cli.main all --days 90

# 5. Launch the dashboard
streamlit run src/impact_dashboard/app/app.py
```

---

## Motivation & design philosophy

### What "impact" means here

Impact is deliberately multi-dimensional. This dashboard rejects the idea that engineering value equals output volume. Instead, it measures three axes:

| Dimension | Weight | What it captures |
|-----------|--------|-----------------|
| **Product** | 40% | Shipping meaningful, complex work quickly |
| **Team** | 30% | Unblocking others through reviews, breadth of collaboration |
| **Technical** | 30% | Bug fixes, hotfixes, core-area stewardship, refactoring |

The weighting slightly favors shipping (code that reaches production is the most visible form of impact) but ensures that team multipliers and codebase health are never invisible.

### Why these metrics?

- **Weighted PR output** over raw PR count — because a cross-directory feature isn't the same as a typo fix.
- **Unblocks** over raw review count — because a review that leads to a merge within 24h is direct evidence of removing a bottleneck.
- **Bug fixes and core-area touches** over total lines changed — because production reliability and work in high-leverage directories matter more than volume.
- **Cycle time (inverted)** — because fast merges signal well-scoped, reviewable code.

Every metric is documented with a "what / formula / why" explanation in the dashboard's Methodology tab.

### Key design decisions

- **Precomputed pipeline** — Streamlit only reads processed JSON; it never calls GitHub live. This keeps the dashboard fast and reliable.
- **Bot filtering** — Automated accounts (dependabot, greptile-apps, copilot, graphite-app, github-actions, etc.) are excluded so scores reflect human contribution.
- **Percentile clipping** — All metrics are normalized to 0–1 with 5th/95th percentile clipping so one outlier can't compress everyone else to near-zero.
- **Windowed API fetching** — GitHub's search API caps at 1000 results, so the pipeline fetches in 7-day windows to cover the full 90 days.
- **Narrative summaries** — Each engineer gets a generated explanation citing their specific numbers and strongest contribution type.

---

## Architecture

```text
GitHub GraphQL API
       ↓                    (7-day windowed pagination)
  Raw PR data               data/raw/prs_raw.json
       ↓
  Normalize + filter bots   data/interim/prs.json, reviews.json, comments.json
       ↓
  Feature engineering        complexity scores, unblock signals, label flags
       ↓
  Aggregate by engineer      product / team / technical metrics per person
       ↓
  Score + rank + narrate     data/processed/engineer_metrics.json
       ↓
  Streamlit dashboard        http://localhost:8501
```

---

## Scoring model

### Final impact score

```
impact = 0.40 × product + 0.30 × team + 0.30 × technical
```

### Sub-score formulas

```
product   = 0.50 × norm(weighted_pr_output)
          + 0.30 × norm(merged_prs)
          + 0.20 × inv_norm(avg_cycle_time)

team      = 0.45 × norm(unblocks)
          + 0.30 × norm(reviews_given)
          + 0.25 × norm(distinct_engineers_helped)

technical = 0.40 × norm(bug_fix_prs)
          + 0.25 × norm(hotfix_prs)
          + 0.20 × norm(core_area_touches)
          + 0.15 × norm(refactor_prs)
```

### Complexity heuristic

Each merged PR gets a complexity score:

```
complexity = 0.35 × norm(changed_files) + 0.35 × norm(lines_changed) + 0.30 × norm(directory_spread)
weighted_pr_output = Σ(1 + complexity) for each merged PR
```

### Unblock heuristic

A reviewer gets unblock credit if they reviewed a PR and it merged within 24 hours of the review.

---

## Data model

| Table | Grain | Key columns |
|-------|-------|-------------|
| `prs` | One row per PR | pr_number, author, state, additions, deletions, complexity_score, is_bugfix, is_core_area |
| `reviews` | One row per review | pr_number, reviewer, review_state, counts_as_unblock |
| `comments` | One row per comment | pr_number, commenter, type |
| `engineer_metrics` | One row per engineer | merged_prs, weighted_pr_output, reviews_given, unblocks, impact_score, impact_rank, summary |

---

## Project structure

```
.
├── src/impact_dashboard/
│   ├── github/
│   │   ├── client.py          # GraphQL client, windowed pagination, bot list
│   │   └── queries.py         # PR search query
│   ├── pipeline/
│   │   ├── normalize.py       # Raw → tabular, bot filtering
│   │   ├── features.py        # Complexity, label flags, unblock signal
│   │   ├── aggregate.py       # Engineer-level rollup
│   │   ├── score.py           # Normalization, weighted scoring
│   │   └── narrate.py         # Natural-language summaries
│   ├── app/
│   │   └── app.py             # Streamlit dashboard
│   ├── cli/
│   │   └── main.py            # CLI: fetch / build / all
│   ├── utils/
│   │   └── io.py              # JSON read/write helpers
│   └── settings.py            # Config, paths, env vars
├── data/
│   ├── raw/                   # Cached API responses
│   ├── interim/               # Normalized tables
│   └── processed/             # Final scored output
├── requirements.txt
├── .env                       # GITHUB_TOKEN (not committed)
├── .gitignore
└── README.md
```

---

## CLI commands

| Command | What it does |
|---------|-------------|
| `python -m src.impact_dashboard.cli.main fetch --days 90` | Pull raw PR data from GitHub |
| `python -m src.impact_dashboard.cli.main build` | Normalize, score, and export metrics |
| `python -m src.impact_dashboard.cli.main all --days 90` | Fetch + build in one step |

---

## Stack

| Tool | Role |
|------|------|
| Python | Data collection and analysis |
| Pandas | Metric computation |
| Plotly | Charts |
| Streamlit | Dashboard UI |
| GitHub GraphQL API | Source data |
| Streamlit Community Cloud | Free hosting |

---

## Deployment

1. Push to a **public** GitHub repo.
2. Go to [Streamlit Community Cloud](https://streamlit.io/cloud).
3. Connect the repo and set the main file to `src/impact_dashboard/app/app.py`.
4. Add `GITHUB_TOKEN` as a secret (only needed if re-running the pipeline on the server).
5. Deploy.

The app reads precomputed `data/processed/engineer_metrics.json`, so it loads instantly without any live API calls.

---

## Output files

| Path | Contents |
|------|----------|
| `data/raw/prs_raw.json` | Raw GraphQL responses |
| `data/interim/prs.json` | Normalized PR table |
| `data/interim/reviews.json` | Normalized review table |
| `data/interim/comments.json` | Normalized comment table |
| `data/processed/engineer_metrics.json` | Final scored engineer data (dashboard reads this) |
| `data/processed/engineer_metrics.csv` | Same data in CSV for inspection |
