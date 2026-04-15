# PostHog Engineer Impact Dashboard

This project fetches pull request activity from `PostHog/posthog`, computes impact metrics for engineers over a 90-day window, and renders a Streamlit dashboard of the top 5 engineers.

## Quick start

1. Create and activate a virtual environment.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Add your GitHub token in `.env`:
   - `GITHUB_TOKEN=...`
4. Run full pipeline:
   - `python -m src.impact_dashboard.cli.main all --days 90 --max-prs 200`
5. Start app:
   - `streamlit run src/impact_dashboard/app/app.py`

## Commands

- Fetch raw data only:
  - `python -m src.impact_dashboard.cli.main fetch --days 90 --max-prs 200`
- Build processed metrics from fetched data:
  - `python -m src.impact_dashboard.cli.main build`

## Output files

- `data/raw/prs_raw.json`
- `data/interim/prs.json`
- `data/interim/reviews.json`
- `data/interim/comments.json`
- `data/processed/engineer_metrics.json`
