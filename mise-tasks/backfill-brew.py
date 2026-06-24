#!/usr/bin/env -S uv run

import os
import subprocess
import time
from collections import defaultdict
from datetime import datetime, timezone

import pandas as pd
import requests
from requests import RequestException


GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise ValueError("GITHUB_TOKEN environment variable is required")

OWNER = "Homebrew"
REPO = "brew"
COLUMN = "brew_stars"
OUTPUT = "competitors.csv"

headers = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
}


def refresh_github_token():
    token = subprocess.check_output(
        ["mise", "token", "github", "--oauth", "--raw", "--refresh"],
        text=True,
    ).strip()
    headers["Authorization"] = f"Bearer {token}"


def fetch_stargazers_history(owner, repo, start_date=None, end_date=None):
    """Fetch stargazer history for a repo between dates."""
    url = "https://api.github.com/graphql"
    query = """
    query($owner: String!, $repo: String!, $cursor: String) {
      repository(owner: $owner, name: $repo) {
        stargazers(
          first: 100,
          after: $cursor,
          orderBy: {field: STARRED_AT, direction: ASC}
        ) {
          edges {
            starredAt
          }
          pageInfo {
            hasNextPage
            endCursor
          }
        }
      }
    }
    """

    daily_stars = defaultdict(int)
    page = 1
    cursor = None

    start_dt = (
        datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
        if start_date
        else None
    )
    end_dt = (
        datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc)
        if end_date
        else None
    )

    print(f"Fetching {owner}/{repo} stargazer history...", flush=True)

    while True:
        if page == 1 or page % 25 == 0:
            print(f"  Fetching page {page}...", flush=True)

        for attempt in range(1, 4):
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    json={
                        "query": query,
                        "variables": {
                            "owner": owner,
                            "repo": repo,
                            "cursor": cursor,
                        },
                    },
                    timeout=30,
                )
            except RequestException as err:
                if attempt == 3:
                    raise

                sleep_time = attempt * 5
                print(
                    f"  Page {page} failed with {err.__class__.__name__}; retrying in {sleep_time}s...",
                    flush=True,
                )
                time.sleep(sleep_time)
                continue

            if response.status_code == 200:
                break

            if response.status_code in (401, 403):
                if attempt == 3:
                    print(f"Error: {response.status_code} after refreshing GitHub token")
                    print(response.text)
                    raise SystemExit(1)
                print(
                    f"  Page {page} returned {response.status_code}; refreshing GitHub token...",
                    flush=True,
                )
                refresh_github_token()
                continue

            if attempt == 3:
                print(f"Error: {response.status_code}")
                print(response.text)
                raise SystemExit(1)

            sleep_time = attempt * 5
            print(
                f"  Page {page} returned {response.status_code}; retrying in {sleep_time}s...",
                flush=True,
            )
            time.sleep(sleep_time)

        payload = response.json()
        errors = payload.get("errors")
        if errors:
            print(errors)
            raise SystemExit(1)

        stargazers = payload["data"]["repository"]["stargazers"]
        stars = stargazers["edges"]

        if not stars:
            break

        for star in stars:
            starred_at = datetime.fromisoformat(
                star["starredAt"].replace("Z", "+00:00")
            )

            if start_dt and starred_at < start_dt:
                continue
            if end_dt and starred_at > end_dt:
                continue

            date = starred_at.strftime("%Y-%m-%d")
            daily_stars[date] += 1

        page_info = stargazers["pageInfo"]
        if not page_info["hasNextPage"]:
            break

        cursor = page_info["endCursor"]

        page += 1

    return daily_stars


df = pd.read_csv(OUTPUT)
df["date"] = pd.to_datetime(df["date"])

if COLUMN not in df.columns:
    df[COLUMN] = 0

start_date = df["date"].min().strftime("%Y-%m-%d")
end_date = (df["date"].max() - pd.Timedelta(days=1)).strftime("%Y-%m-%d")

print(f"Backfilling {REPO} data from {start_date} to {end_date}", flush=True)
print("This aligns with existing mise/asdf data for performance", flush=True)

daily_stars = fetch_stargazers_history(OWNER, REPO, start_date, end_date)

sorted_dates = sorted(daily_stars.keys())
cumulative = 0
cumulative_by_date = {}

for date in sorted_dates:
    cumulative += daily_stars[date]
    cumulative_by_date[date] = cumulative

for idx, row in df.iterrows():
    date_str = row["date"].strftime("%Y-%m-%d")
    if date_str in cumulative_by_date:
        df.at[idx, COLUMN] = cumulative_by_date[date_str]
    elif sorted_dates and date_str < sorted_dates[0]:
        df.at[idx, COLUMN] = 0
    else:
        last_known = cumulative_by_date.get(sorted_dates[-1], 0) if sorted_dates else 0
        df.at[idx, COLUMN] = last_known

df = df.sort_values("date")
df.to_csv(OUTPUT, index=False)

print(f"\nBackfilled {len(cumulative_by_date)} days of {REPO} data")
print(f"Current {REPO} stars: {cumulative}")
print(f"Total rows in {OUTPUT}: {len(df)}")
