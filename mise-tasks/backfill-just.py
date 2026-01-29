#!/usr/bin/env -S uv run

import pandas as pd
import requests
import os
from datetime import datetime, timedelta
import time
from collections import defaultdict

# GitHub API token
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
if not GITHUB_TOKEN:
    raise ValueError("GITHUB_TOKEN environment variable is required")

headers = {
    'Authorization': f'Bearer {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3.star+json'
}

def fetch_stargazers_history(owner, repo, start_date=None, end_date=None):
    """Fetch stargazer history for a repo between dates"""
    url = f'https://api.github.com/repos/{owner}/{repo}/stargazers'

    daily_stars = defaultdict(int)
    page = 1
    per_page = 100

    # Parse date strings to timezone-aware datetime objects
    from datetime import timezone
    if start_date:
        start_dt = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
    else:
        start_dt = None
    if end_date:
        end_dt = datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc)
    else:
        end_dt = None

    print(f"Fetching {owner}/{repo} stargazer history...", flush=True)

    while True:
        print(f"  Fetching page {page}...", flush=True)
        response = requests.get(
            url,
            headers=headers,
            params={'per_page': per_page, 'page': page}
        )

        if response.status_code != 200:
            print(f"Error: {response.status_code}")
            print(response.text)
            break

        stars = response.json()

        if not stars:
            break

        for star in stars:
            starred_at = datetime.fromisoformat(star['starred_at'].replace('Z', '+00:00'))

            # Filter by date range if specified
            if start_dt and starred_at < start_dt:
                continue
            if end_dt and starred_at > end_dt:
                continue

            date = starred_at.strftime('%Y-%m-%d')
            daily_stars[date] += 1

        # Check rate limit
        remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
        if remaining < 10:
            reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
            sleep_time = max(0, reset_time - time.time()) + 1
            print(f"  Rate limit low. Sleeping {sleep_time:.0f}s...")
            time.sleep(sleep_time)

        page += 1
        time.sleep(0.5)  # Be nice to the API

    return daily_stars

# Read existing CSV
df = pd.read_csv('competitors.csv')
df['date'] = pd.to_datetime(df['date'])

# Add just_stars column if it doesn't exist
if 'just_stars' not in df.columns:
    df['just_stars'] = 0

# Get date range from existing data (only where we have mise/asdf data)
start_date = df['date'].min().strftime('%Y-%m-%d')
end_date = (df['date'].max() - pd.Timedelta(days=1)).strftime('%Y-%m-%d')  # Yesterday, since today already has data

print(f"Backfilling just data from {start_date} to {end_date}", flush=True)
print(f"This aligns with existing mise/asdf data for performance", flush=True)

# Fetch just stargazer history
daily_stars = fetch_stargazers_history('casey', 'just', start_date, end_date)

# Convert to cumulative counts
sorted_dates = sorted(daily_stars.keys())
cumulative = 0
cumulative_by_date = {}

for date in sorted_dates:
    cumulative += daily_stars[date]
    cumulative_by_date[date] = cumulative

# Update dataframe with just stars
for idx, row in df.iterrows():
    date_str = row['date'].strftime('%Y-%m-%d')
    if date_str in cumulative_by_date:
        df.at[idx, 'just_stars'] = cumulative_by_date[date_str]
    elif date_str < sorted_dates[0] if sorted_dates else '9999-99-99':
        # Before first star
        df.at[idx, 'just_stars'] = 0
    else:
        # After our last fetched date, keep the last known value
        last_known = cumulative_by_date.get(sorted_dates[-1], 0) if sorted_dates else 0
        df.at[idx, 'just_stars'] = last_known

# Sort by date and save
df = df.sort_values('date')
df.to_csv('competitors.csv', index=False)

print(f"\nBackfilled {len(cumulative_by_date)} days of just data")
print(f"Current just stars: {cumulative}")
print(f"Total rows in competitors.csv: {len(df)}")
