# PostHog Engineer Impact Dashboard

## Goal
Build a single-page dashboard that identifies the **top 5 most impactful engineers** in the `PostHog/posthog` GitHub repository over the last 90 days and explains **why** they are impactful.

The dashboard should prioritize meaningful engineering impact over vanity metrics. It should help a busy engineering leader quickly understand:

- who is moving important work forward,
- who is unblocking other engineers,
- who is improving the codebase and systems,
- and why each person ranks highly.

The final product should be fast to build, easy to deploy for free, and simple to explain.

---

## Product Definition

### What “impact” means here
Impact is a combination of:

1. **Product impact**
   - shipping meaningful work,
   - getting large or complex work merged,
   - moving issues from open to merged quickly.

2. **Team impact**
   - reviewing PRs,
   - giving useful feedback,
   - unblocking others,
   - collaborating across contributors.

3. **Technical impact**
   - fixing bugs,
   - improving system health,
   - touching high-leverage or core parts of the codebase,
   - making important cross-cutting changes.

This dashboard should not rank people by raw commits, lines of code, or number of files changed alone.

---

## Deliverables

1. A Python data pipeline that pulls data from GitHub and computes engineer-level metrics.
2. A derived metrics dataset saved locally as JSON or CSV.
3. A Streamlit app that loads the metrics dataset and renders a single-page dashboard.
4. A free deployment link.

---

## Recommended Stack

### Best option for this challenge
- **Python** for data collection and analysis
- **Pandas** for metric computation
- **Streamlit** for dashboard UI
- **GitHub API** for source data
- **Streamlit Community Cloud** for free hosting

### Why this stack
- Fastest to implement under the time constraint
- Easy to iterate in Cursor
- Simple deployment path
- Good enough for polished charts, tables, and text summaries

---

## High-Level Architecture

```text
GitHub API
   ↓
Python ingestion script
   ↓
Normalized PR/review dataset
   ↓
Engineer-level metric aggregation
   ↓
Scored rankings + narrative summaries
   ↓
metrics.json / metrics.csv
   ↓
Streamlit app
   ↓
Free deployment on Streamlit Community Cloud
```

The key idea is to **precompute all analysis offline** and make Streamlit only responsible for display.

---

## Data Scope

### Repository
- `https://github.com/PostHog/posthog`

### Time range
- Last **90 days** of activity, minimum.
- Include all PRs created, reviewed, commented on, and merged during the window.

### Primary entities to collect

#### Pull requests
For each PR:
- PR number
- title
- author login
- created_at
- merged_at
- closed_at
- state
- labels
- additions
- deletions
- changed_files
- files changed list if feasible
- reviews
- review comments
- general comments

#### Reviews
For each review:
- reviewer login
- review state
- review created_at
- PR number

#### Comments
For each comment:
- commenter login
- created_at
- PR number
- comment type if possible

#### Optional context
- PR labels that indicate bug / feature / refactor / docs / infra / breaking change / hotfix
- merged-to-open time
- review turnaround time
- contribution concentration by files or directories touched

---

## Data Source Strategy

### Preferred: GitHub GraphQL API
Use GraphQL rather than REST because it is much better for nested PR + review data.

GraphQL should be used to fetch:
- PR metadata
- reviews and reviewers
- comments
- labels
- file counts
- merge timestamps

### Authentication
Use a GitHub personal access token with read access.

Environment variable:
```bash
GITHUB_TOKEN=...
```

### Fallback
If GraphQL becomes annoying for nested fields, use a hybrid approach:
- GraphQL for listing PRs and their metadata
- REST for files / detailed review comments on the PRs that matter

But ideally keep it GraphQL-first.

---

## Metric Design

The dashboard should compute multiple metrics, then combine them into a weighted score.

### 1) Product impact metrics
These measure how much meaningful work an engineer ships.

#### Metrics
- `prs_merged_90d`
- `avg_cycle_time_hours`
- `median_cycle_time_hours`
- `complex_pr_count`
- `weighted_pr_output`

#### Definitions
- `prs_merged_90d`: count of PRs authored and merged in the window.
- `avg_cycle_time_hours`: average time from PR open to merge.
- `complex_pr_count`: number of PRs with many files changed, many lines changed, or cross-directory spread.
- `weighted_pr_output`: PR count weighted by complexity.

#### Suggested complexity heuristic
A PR is more complex if it has one or more of:
- many changed files,
- many added/deleted lines,
- touches multiple top-level directories,
- touches core / high-churn directories.

Use a simple normalized score:

```text
complexity_score =
  0.35 * normalized(changed_files)
+ 0.35 * normalized(total_lines_changed)
+ 0.30 * directory_spread_score
```

Then define:
```text
weighted_pr_output = sum(1 + complexity_score for each merged PR)
```

---

### 2) Team impact metrics
These measure leverage and collaboration.

#### Metrics
- `reviews_given`
- `distinct_prs_reviewed`
- `distinct_engineers_helped`
- `unblocks`
- `review_response_time_hours`

#### Definitions
- `reviews_given`: count of PR reviews authored.
- `distinct_prs_reviewed`: number of unique PRs reviewed.
- `distinct_engineers_helped`: number of distinct PR authors whose PRs were reviewed.
- `unblocks`: count of reviews that were followed by merge shortly afterward.
- `review_response_time_hours`: average time from review request / PR open to first review.

#### Practical unblock heuristic
A reviewer gets “unblock credit” if:
- they submitted a review on a PR,
- the PR merged within 24 hours of that review,
- and the review was not obviously a drive-by approval repeated by multiple reviewers.

A simple first pass:

```text
unblock_credit = 1 if review_time is within 24h before merged_at
```

Aggregate by reviewer.

---

### 3) Technical impact metrics
These measure codebase health and high-leverage work.

#### Metrics
- `bug_fix_prs`
- `hotfix_prs`
- `refactor_prs`
- `infra_prs`
- `core_area_touch_count`
- `reverted_prs_avoided`

#### Definitions
- `bug_fix_prs`: PRs labeled `bug` or `fix` or containing bug-fix semantics in title.
- `hotfix_prs`: PRs labeled `hotfix` or `urgent`.
- `refactor_prs`: PRs labeled `refactor` or with title indicating refactor.
- `infra_prs`: PRs touching infra, deployment, CI, tooling, or platform areas.
- `core_area_touch_count`: PRs that touch key directories or frequently changed files.
- `reverted_prs_avoided`: optional proxy for quality, based on whether the PR was not quickly followed by a revert or bug fix.

#### Suggested quality heuristic
A PR is higher quality if it is not followed by:
- a revert,
- a bug-fix PR in the same files within 7 days,
- repeated back-and-forth churn.

Keep this heuristic light if time is limited.

---

## Final Impact Score

The final score should be a weighted combination of normalized metrics.

### Recommended weighting
- **40% product impact**
- **30% team impact**
- **30% technical impact**

### Example formula
```text
impact_score =
  0.40 * product_score
+ 0.30 * team_score
+ 0.30 * technical_score
```

Where each category score is itself a weighted combination of normalized component metrics.

### Example category formulas
```text
product_score =
  0.50 * normalized(weighted_pr_output)
+ 0.30 * normalized(merged_prs)
+ 0.20 * inverted_normalized(avg_cycle_time_hours)

team_score =
  0.45 * normalized(unblocks)
+ 0.30 * normalized(reviews_given)
+ 0.25 * normalized(distinct_engineers_helped)

technical_score =
  0.40 * normalized(bug_fix_prs)
+ 0.25 * normalized(hotfix_prs)
+ 0.20 * normalized(core_area_touch_count)
+ 0.15 * normalized(refactor_prs)
```

### Important normalization rule
For metrics where lower is better, such as cycle time, use inverted normalization:

```text
inverted_normalized(x) = 1 - normalized(x)
```

### Guardrails
- Cap extreme outliers with percentile clipping before normalization.
- Do not let one metric dominate the total.
- If a contributor has very few PRs, display them only if their score is supported by multiple signals.

---

## Narrative Explanation Layer

The dashboard should not just show numbers. For each engineer, generate a short explanation.

### Example engineer summary
- “Shipped 6 merged PRs in the last 90 days, including 2 complex cross-directory changes. Also reviewed 14 PRs across 9 contributors and unblocked 5 merges.”

### Suggested summary template
For each top engineer, include:
- top contribution type,
- number of merged PRs,
- number of reviews,
- unblock count,
- one notable codebase area they influenced.

This can be templated from the metrics table.

---

## Data Model

Use a tidy tabular schema.

### Table 1: `prs`
One row per PR.

Columns:
- `pr_number`
- `title`
- `author`
- `created_at`
- `merged_at`
- `closed_at`
- `state`
- `labels`
- `additions`
- `deletions`
- `changed_files`
- `directories_touched`
- `is_bugfix`
- `is_hotfix`
- `is_refactor`
- `is_infra`
- `complexity_score`

### Table 2: `reviews`
One row per review.

Columns:
- `pr_number`
- `reviewer`
- `review_state`
- `created_at`
- `merged_at`
- `time_to_merge_after_review_hours`
- `counts_as_unblock`

### Table 3: `comments`
One row per comment.

Columns:
- `pr_number`
- `commenter`
- `created_at`
- `type`

### Table 4: `engineer_metrics`
One row per engineer.

Columns:
- `engineer`
- `merged_prs`
- `weighted_pr_output`
- `avg_cycle_time_hours`
- `reviews_given`
- `distinct_prs_reviewed`
- `distinct_engineers_helped`
- `unblocks`
- `bug_fix_prs`
- `hotfix_prs`
- `refactor_prs`
- `core_area_touch_count`
- `product_score`
- `team_score`
- `technical_score`
- `impact_score`
- `impact_rank`

---

## Data Collection Plan

### Step 1: Fetch PRs
Get all PRs created in the last 90 days.

If the query returns too many PRs, paginate until PRs are older than the cutoff.

### Step 2: Fetch details for each PR
For each PR, collect:
- title
- author
- timestamps
- labels
- additions / deletions / changed files
- reviews
- comments
- file paths

### Step 3: Build normalized records
Flatten GraphQL responses into rows.

### Step 4: Compute helper features
For each PR:
- total lines changed
- directory spread
- label flags
- core-area flags
- review-to-merge intervals

### Step 5: Aggregate by engineer
Group by author for authored PR metrics and by reviewer for review metrics.

### Step 6: Compute scores
Normalize metrics and compute category scores and final impact score.

### Step 7: Export dataset
Write to `data/engineer_metrics.json` or `data/engineer_metrics.csv`.

---

## Implementation Plan

### Recommended folder structure
```text
.
├── app.py
├── fetch_data.py
├── compute_metrics.py
├── github_client.py
├── data/
│   ├── prs.json
│   ├── reviews.json
│   ├── comments.json
│   └── engineer_metrics.json
├── assets/
├── requirements.txt
└── README.md
```

### Alternative simpler structure
If time is tight, use:
```text
.
├── app.py
├── pipeline.py
├── data.json
└── requirements.txt
```

---

## GitHub API Implementation Notes

### Authentication
Read token from env var:
```python
import os
TOKEN = os.environ["GITHUB_TOKEN"]
```

### Client behavior
- Set authorization header.
- Handle rate limits gracefully.
- Add retries for transient failures.
- Save raw responses locally to avoid refetching during development.

### Pagination
Query PRs in pages until:
- there are no more pages, or
- the oldest PR in the page is older than the cutoff date.

### Efficiency
- Pull only necessary fields.
- Cache raw API responses locally.
- Do not over-engineer incremental sync.

---

## Streamlit App Design

The app should fit on one laptop screen and feel executive-friendly.

### Layout
#### Header
- Title: “PostHog Engineer Impact Dashboard”
- Subtitle: “Last 90 days”
- Small note on methodology

#### Main section
A leaderboard showing the top 5 engineers.

Each row or card should show:
- engineer name
- impact score
- product / team / technical breakdown
- short narrative explanation

#### Supporting visuals
- bar chart of impact score by engineer
- stacked bars or small multiples for score components
- optional scatter plot of productivity vs collaboration
- optional trend line for activity over time

#### Details section
A compact table with the full metric breakdown for the top 5.

### Streamlit UI features to use
- `st.metric`
- `st.columns`
- `st.dataframe`
- `st.bar_chart` or Plotly for more control
- expandable explanations with `st.expander`

### UI priorities
- readable,
- concise,
- visually clean,
- not cluttered,
- optimized for leadership, not engineers.

---

## Streamlit Connection Plan

### Local development
The app should read precomputed metrics from disk.

#### `app.py` flow
1. Load `data/engineer_metrics.json`
2. Sort by `impact_score`
3. Slice top 5 engineers
4. Render cards/charts/tables

### Minimal example structure
```python
import streamlit as st
import pandas as pd

@st.cache_data
def load_data():
    return pd.read_json("data/engineer_metrics.json")

st.set_page_config(page_title="PostHog Impact Dashboard", layout="wide")

df = load_data().sort_values("impact_score", ascending=False)
top5 = df.head(5)

st.title("PostHog Engineer Impact Dashboard")
st.caption("Impact over the last 90 days")

for _, row in top5.iterrows():
    st.subheader(row["engineer"])
    st.metric("Impact Score", f"{row['impact_score']:.2f}")
    st.write(row["summary"])
```

### Recommended runtime behavior
- The Streamlit app should **not** call GitHub live every time it loads.
- It should read the saved dataset.
- The pipeline can be rerun manually if needed.

This makes the app fast and reliable during evaluation.

---

## Free Hosting Plan

### Best option: Streamlit Community Cloud
This is the most straightforward free host for this project.

#### Why use it
- Free for public repos
- Very fast deployment
- Built for Streamlit apps
- No extra infrastructure required

#### Steps
1. Put the code in a GitHub repo.
2. Commit `app.py`, `requirements.txt`, and the data pipeline scripts.
3. Push to GitHub.
4. Go to Streamlit Community Cloud.
5. Connect GitHub.
6. Select the repository.
7. Set the main file to `app.py`.
8. Deploy.

#### Important note
Make sure the repo is public if using the free Streamlit Cloud plan.

### Alternative: Render
Render can also host Streamlit apps, but Streamlit Community Cloud is simpler for this use case.

### Alternative: Hugging Face Spaces
Also free and good for quick demos, but Streamlit Cloud is usually the least friction for this exact project.

### Best practical recommendation
Use **Streamlit Community Cloud** unless something blocks it.

---

## Local and Deployment Environment

### `requirements.txt`
Include:
- `streamlit`
- `pandas`
- `numpy`
- `requests`
- `plotly`
- `python-dateutil`

### Environment variables
- `GITHUB_TOKEN`

### Files that should be committed
- `app.py`
- pipeline scripts
- `requirements.txt`
- `data/*.json` or `data/*.csv` if you want the deployed app to work immediately

### Files that should not be committed
- token files
- private cache files
- large raw response dumps unless necessary

---

## Suggested Build Order

### Phase 1: data access
- verify GitHub token works,
- fetch a handful of PRs,
- confirm the fields you need are available.

### Phase 2: pipeline
- build the PR table,
- compute reviews/comments,
- aggregate engineer metrics.

### Phase 3: scoring
- normalize metrics,
- compute category scores,
- compute final impact score,
- generate summaries.

### Phase 4: dashboard
- render top 5 cards,
- add charts,
- add methodology text.

### Phase 5: deploy
- push to GitHub,
- deploy to Streamlit Community Cloud,
- verify public link.

---

## Acceptance Criteria

The project is successful if:
- it includes data from the last 90 days,
- it uses meaningful metrics beyond raw commits/LOC,
- it identifies and ranks the top 5 engineers,
- it explains why they rank highly,
- it fits comfortably on one laptop screen,
- it is hosted and accessible via a public link.

---

## Notes on Stronger Evaluation

To stand out, emphasize the following in the final product:
- impact is multi-dimensional,
- engineering value is not equal to output volume,
- reviewers who unblock others matter,
- complex cross-cutting work matters,
- bug fixes and infra work are often undercounted,
- the dashboard is designed for leadership consumption.

---

## Final Recommendation

For the fastest and highest-quality implementation:

- use GitHub GraphQL to fetch PRs, reviews, and comments,
- compute a small number of high-signal metrics,
- combine them into a weighted score,
- render the results in Streamlit,
- deploy to Streamlit Community Cloud.

This gives you a credible, explainable, and shippable takehome in the time limit.

