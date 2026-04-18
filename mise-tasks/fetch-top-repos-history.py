#!/usr/bin/env -S uv run
import os
import csv
import asyncio
import aiohttp
from datetime import datetime, timezone
from collections import defaultdict
from tqdm import tqdm

DEFAULT_OWNER = 'jdx'


def resolve_repo(entry):
    """Return (owner, repo, repo_name) for an entry that may be "repo" or "owner/repo"."""
    if '/' in entry:
        owner, repo = entry.split('/', 1)
        repo_name = entry if owner != DEFAULT_OWNER else repo
    else:
        owner, repo = DEFAULT_OWNER, entry
        repo_name = entry
    return owner, repo, repo_name


async def fetch_stargazer_history(entry, session, pbar):
    """Fetch complete stargazer history for a single repo"""
    daily_stars = defaultdict(int)
    owner, repo, _ = resolve_repo(entry)

    headers = {
        'Authorization': f'Bearer {os.environ["GITHUB_TOKEN"]}',
        'Accept': 'application/vnd.github.v3.star+json'
    }

    # Get total stars first
    async with session.get(
        f'https://api.github.com/repos/{owner}/{repo}',
        headers=headers
    ) as response:
        repo_data = await response.json()
        if 'stargazers_count' not in repo_data:
            print(f"Warning: Could not fetch data for {entry}")
            pbar.total = 0
            return daily_stars

        total_stars = repo_data['stargazers_count']
        pbar.total = total_stars
        pbar.set_description(f"Fetching {entry}")

    # Fetch all stargazers with timestamps
    page = 1
    while True:
        async with session.get(
            f'https://api.github.com/repos/{owner}/{repo}/stargazers'
            f'?page={page}&per_page=100',
            headers=headers
        ) as response:
            stars = await response.json()

            if not stars or not isinstance(stars, list):
                break

            for star in stars:
                if 'starred_at' not in star:
                    continue

                starred_at = datetime.strptime(
                    star['starred_at'],
                    '%Y-%m-%dT%H:%M:%SZ'
                ).replace(tzinfo=timezone.utc)

                date = starred_at.strftime('%Y-%m-%d')
                daily_stars[date] += 1
                pbar.update(1)

            page += 1

            # Check rate limit
            remaining = response.headers.get('X-RateLimit-Remaining')
            if remaining and int(remaining) <= 1:
                reset_time = int(response.headers['X-RateLimit-Reset'])
                wait_time = reset_time - datetime.now().timestamp()
                if wait_time > 0:
                    pbar.set_description(f"Rate limited, waiting {int(wait_time)}s...")
                    await asyncio.sleep(wait_time + 1)
                    pbar.set_description(f"Fetching {entry}")

    return daily_stars

async def fetch_all_repos(repos):
    """Fetch stargazer history for all repos in parallel"""
    async with aiohttp.ClientSession() as session:
        pbars = [tqdm(position=i, desc=repo) for i, repo in enumerate(repos)]
        tasks = [fetch_stargazer_history(repo, session, pbar)
                for repo, pbar in zip(repos, pbars)]
        results = await asyncio.gather(*tasks)
        for pbar in pbars:
            pbar.close()
    return dict(zip(repos, results))

def read_tracked_repos():
    """Read list of tracked repos from top-repos-list.txt"""
    repos = []
    with open('top-repos-list.txt', 'r') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if line and not line.startswith('#'):
                repos.append(line)
    return repos

def main():
    print("Reading tracked repos...")
    repos = read_tracked_repos()
    print(f"Found {len(repos)} tracked repos: {', '.join(repos)}")

    # Fetch star history for all repos in parallel
    print("\nFetching stargazer history...")
    star_histories = asyncio.run(fetch_all_repos(repos))

    # Read existing top-repos.csv data
    existing_data = defaultdict(dict)
    try:
        with open('top-repos.csv', 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_data[row['date']][row['repo_name']] = row
    except FileNotFoundError:
        print("No existing top-repos.csv found, creating new file")

    # Collect all unique dates across all repos
    all_dates = set()
    for repo_stars in star_histories.values():
        all_dates.update(repo_stars.keys())
    all_dates = sorted(all_dates)

    print(f"\nProcessing data for {len(all_dates)} unique dates...")

    # Build complete dataset with cumulative stars
    output_data = []
    cumulative_stars = {entry: 0 for entry in repos}

    for date in all_dates:
        for entry in repos:
            _, _, repo_name = resolve_repo(entry)
            # Update cumulative count
            cumulative_stars[entry] += star_histories[entry].get(date, 0)

            # Check if we have existing data for this date/repo
            if date in existing_data and repo_name in existing_data[date]:
                # Use existing brew data, update stars
                row = existing_data[date][repo_name].copy()
                row['github_stars'] = str(cumulative_stars[entry])
            else:
                # Create new row with only star data
                row = {
                    'date': date,
                    'repo_name': repo_name,
                    'github_stars': str(cumulative_stars[entry]),
                    'brew_rank': '',
                    'brew_installs': '',
                    'brew_pct': ''
                }

            output_data.append(row)

    # Write updated top-repos.csv
    fieldnames = ['date', 'repo_name', 'github_stars', 'brew_rank', 'brew_installs', 'brew_pct']
    with open('top-repos.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_data)

    print(f"\nSuccessfully wrote {len(output_data)} rows to top-repos.csv")
    print(f"Date range: {all_dates[0]} to {all_dates[-1]}")

if __name__ == '__main__':
    main()
