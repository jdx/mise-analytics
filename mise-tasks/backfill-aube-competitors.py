#!/usr/bin/env -S uv run
# /// script
# dependencies = ["pandas", "requests"]
# ///

import pandas as pd
import requests
import os
from datetime import datetime, timedelta, timezone
import time
from collections import defaultdict

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
if not GITHUB_TOKEN:
    raise ValueError("GITHUB_TOKEN environment variable is required")

headers = {
    'Authorization': f'Bearer {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3.star+json'
}


def fetch_current_stars(owner, repo):
    url = f'https://api.github.com/repos/{owner}/{repo}'
    auth_headers = {
        'Authorization': f'Bearer {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    response = requests.get(url, headers=auth_headers)
    return response.json().get('stargazers_count', 0)


def fetch_stargazers_history(owner, repo, start_date, end_date, max_pages=500):
    """Paginate through stargazers (oldest first) and bucket by day within window."""
    url = f'https://api.github.com/repos/{owner}/{repo}/stargazers'
    daily_stars = defaultdict(int)

    start_dt = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
    end_dt = datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc) + timedelta(days=1)

    print(f"Fetching {owner}/{repo} stargazer history...", flush=True)
    page = 1
    while page <= max_pages:
        if page % 25 == 0:
            print(f"  page {page}...", flush=True)
        response = requests.get(
            url, headers=headers,
            params={'per_page': 100, 'page': page}
        )

        if response.status_code != 200:
            print(f"  Error {response.status_code}: {response.text[:200]}", flush=True)
            break

        stars = response.json()
        if not stars or not isinstance(stars, list):
            break

        last_star_dt = None
        for star in stars:
            if 'starred_at' not in star:
                continue
            starred_at = datetime.fromisoformat(star['starred_at'].replace('Z', '+00:00'))
            last_star_dt = starred_at
            if starred_at < start_dt or starred_at >= end_dt:
                continue
            daily_stars[starred_at.strftime('%Y-%m-%d')] += 1

        # Stop early if we've passed the window
        if last_star_dt and last_star_dt >= end_dt:
            break

        remaining = int(response.headers.get('X-RateLimit-Remaining', 5000))
        if remaining < 10:
            reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
            sleep_time = max(0, reset_time - time.time()) + 1
            print(f"  Rate limit low. Sleeping {sleep_time:.0f}s...", flush=True)
            time.sleep(sleep_time)

        page += 1
        time.sleep(0.2)

    return daily_stars


# GitHub stargazer pagination is impractical for very large repos.
# Below this threshold we fetch real history; above it we hold the line flat at
# the current count (the absolute scale dwarfs aube's curve anyway).
PAGINATION_THRESHOLD = 50000

START_DATE = '2025-01-01'
END_DATE = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

competitors = [
    ('endevco', 'aube', 'aube'),
    ('vltpkg', 'vltpkg', 'vlt'),
    ('npm', 'cli', 'npm'),
    ('pnpm', 'pnpm', 'pnpm'),
    ('yarnpkg', 'yarn', 'yarn'),
    ('yarnpkg', 'berry', 'berry'),
    ('oven-sh', 'bun', 'bun'),
    ('denoland', 'deno', 'deno'),
]

print(f"Backfilling aube competitor data from {START_DATE} to {END_DATE}", flush=True)

# Build full date range
start_dt_naive = datetime.strptime(START_DATE, '%Y-%m-%d')
end_dt_naive = datetime.strptime(END_DATE, '%Y-%m-%d')
dates = []
cur = start_dt_naive
while cur <= end_dt_naive:
    dates.append(cur.strftime('%Y-%m-%d'))
    cur += timedelta(days=1)

# Fetch current totals + per-day histories (or skip for huge repos)
current_totals = {}
histories = {}
for owner, repo, name in competitors:
    current_totals[name] = fetch_current_stars(owner, repo)
    print(f"  {name} current: {current_totals[name]:,}", flush=True)
    if current_totals[name] > PAGINATION_THRESHOLD:
        print(f"  {name} exceeds threshold, will hold flat at current count", flush=True)
        histories[name] = defaultdict(int)
    else:
        histories[name] = fetch_stargazers_history(owner, repo, START_DATE, END_DATE)

# Stars added between END_DATE (exclusive) and today (so baseline math is exact)
today_str = datetime.now().strftime('%Y-%m-%d')
stars_after_window = {}
for owner, repo, name in competitors:
    if current_totals[name] > PAGINATION_THRESHOLD:
        stars_after_window[name] = 0
    else:
        after = fetch_stargazers_history(owner, repo, END_DATE, today_str)
        stars_after_window[name] = sum(v for k, v in after.items() if k > END_DATE)

# Baselines (stars before START_DATE)
window_totals = {name: sum(h.values()) for name, h in histories.items()}
baselines = {}
for _, _, name in competitors:
    if current_totals[name] > PAGINATION_THRESHOLD:
        baselines[name] = current_totals[name]
    else:
        baselines[name] = current_totals[name] - window_totals[name] - stars_after_window[name]
    print(f"  {name} baseline (pre-{START_DATE}): {baselines[name]:,}", flush=True)

rows = []
cumulative = dict(baselines)
for date in dates:
    for _, _, name in competitors:
        cumulative[name] += histories[name].get(date, 0)
    rows.append({
        'date': date,
        'aube_stars': cumulative['aube'],
        'vlt_stars': cumulative['vlt'],
        'npm_stars': cumulative['npm'],
        'pnpm_stars': cumulative['pnpm'],
        'yarn_stars': cumulative['yarn'],
        'berry_stars': cumulative['berry'],
        'bun_stars': cumulative['bun'],
        'deno_stars': cumulative['deno'],
    })

df = pd.DataFrame(rows)
df.to_csv('aube-competitors.csv', index=False)

print(f"\nWrote aube-competitors.csv with {len(df)} rows")
for _, _, name in competitors:
    print(f"  {name} final: {cumulative[name]:,}")
