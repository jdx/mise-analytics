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

def fetch_current_stars(owner, repo):
    """Fetch current total star count for a repo"""
    url = f'https://api.github.com/repos/{owner}/{repo}'
    auth_headers = {
        'Authorization': f'Bearer {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    response = requests.get(url, headers=auth_headers)
    return response.json().get('stargazers_count', 0)

def fetch_stargazers_history(owner, repo, start_date=None, end_date=None):
    """Fetch stargazer history for a repo between dates"""
    url = f'https://api.github.com/repos/{owner}/{repo}/stargazers'

    daily_stars = defaultdict(int)
    page = 1
    per_page = 100

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
        time.sleep(0.5)

    return daily_stars

# Backfill from fnox's first star date
START_DATE = '2025-10-20'
END_DATE = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

print(f"Backfilling fnox competitor data from {START_DATE} to {END_DATE}", flush=True)

# Generate date range
start_dt = datetime.strptime(START_DATE, '%Y-%m-%d')
end_dt = datetime.strptime(END_DATE, '%Y-%m-%d')
dates = []
current = start_dt
while current <= end_dt:
    dates.append(current.strftime('%Y-%m-%d'))
    current += timedelta(days=1)

# Fetch stargazer histories
competitors = [
    ('jdx', 'fnox', 'fnox'),
    ('getsops', 'sops', 'sops'),
]

histories = {}
current_totals = {}
for owner, repo, name in competitors:
    histories[name] = fetch_stargazers_history(owner, repo, START_DATE, END_DATE)
    current_totals[name] = fetch_current_stars(owner, repo)
    print(f"  {name} current total: {current_totals[name]}", flush=True)

# Calculate total stars added in window to derive baseline
window_totals = {name: sum(histories[name].values()) for _, _, name in competitors}

# Also count stars after END_DATE up to today
today = datetime.now().strftime('%Y-%m-%d')
stars_after_window = {}
for owner, repo, name in competitors:
    after = fetch_stargazers_history(owner, repo, END_DATE, today)
    # Don't double-count the END_DATE itself
    stars_after_window[name] = sum(v for k, v in after.items() if k > END_DATE)

# Baseline = current total - stars in window - stars after window
baselines = {
    name: current_totals[name] - window_totals[name] - stars_after_window[name]
    for _, _, name in competitors
}

for _, _, name in competitors:
    print(f"  {name} baseline (before {START_DATE}): {baselines[name]}", flush=True)

# Build cumulative counts per day
rows = []
cumulative = dict(baselines)

for date in dates:
    for _, _, name in competitors:
        cumulative[name] += histories[name].get(date, 0)
    rows.append({
        'date': date,
        'fnox_stars': cumulative['fnox'],
        'sops_stars': cumulative['sops'],
    })

df = pd.DataFrame(rows)
df.to_csv('fnox-competitors.csv', index=False)

print(f"\nBackfilled {len(dates)} days of data")
for _, _, name in competitors:
    print(f"Current {name} stars: {cumulative[name]}")
print(f"Total rows in fnox-competitors.csv: {len(df)}")
