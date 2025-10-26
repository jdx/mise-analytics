#!/usr/bin/env -S uv run
import os
import csv
import asyncio
import aiohttp
from datetime import datetime, timezone
from collections import defaultdict
from tqdm import tqdm

# hk was released on 2025-01-26, so we only fetch competitor history up to that date
HK_RELEASE_DATE = '2025-01-26'
# Only keep data from 2023 onwards (matches the filter in plot-hk-stats.py)
START_DATE = '2023-01-01'

async def fetch_stargazer_history(owner, repo, session, pbar, cutoff_date):
    """Fetch stargazer history for a single repo up to cutoff date"""
    daily_stars = defaultdict(int)

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
            print(f"Warning: Could not fetch data for {owner}/{repo}")
            pbar.total = 0
            return daily_stars

        total_stars = repo_data['stargazers_count']
        pbar.total = total_stars
        pbar.set_description(f"Fetching {owner}/{repo}")

    # Fetch all stargazers with timestamps up to cutoff date
    page = 1
    cutoff_dt = datetime.strptime(cutoff_date, '%Y-%m-%d').replace(tzinfo=timezone.utc)

    while True:
        async with session.get(
            f'https://api.github.com/repos/{owner}/{repo}/stargazers'
            f'?page={page}&per_page=100',
            headers=headers
        ) as response:
            stars = await response.json()

            if not stars or not isinstance(stars, list):
                break

            # Check if we've passed the cutoff date
            stop_fetching = False
            for star in stars:
                if 'starred_at' not in star:
                    continue

                starred_at = datetime.strptime(
                    star['starred_at'],
                    '%Y-%m-%dT%H:%M:%SZ'
                ).replace(tzinfo=timezone.utc)

                # Stop if we've reached stars after cutoff
                if starred_at > cutoff_dt:
                    stop_fetching = True
                    continue

                date = starred_at.strftime('%Y-%m-%d')
                daily_stars[date] += 1
                pbar.update(1)

            if stop_fetching:
                pbar.set_description(f"Reached cutoff for {owner}/{repo}")
                break

            page += 1

            # Check rate limit
            remaining = response.headers.get('X-RateLimit-Remaining')
            if remaining and int(remaining) <= 1:
                reset_time = int(response.headers['X-RateLimit-Reset'])
                wait_time = reset_time - datetime.now().timestamp()
                if wait_time > 0:
                    pbar.set_description(f"Rate limited, waiting {int(wait_time)}s...")
                    await asyncio.sleep(wait_time + 1)
                    pbar.set_description(f"Fetching {owner}/{repo}")

    return daily_stars

async def fetch_all_competitors(competitors, cutoff_date):
    """Fetch stargazer history for all competitors in parallel"""
    async with aiohttp.ClientSession() as session:
        pbars = [tqdm(position=i, desc=f"{owner}/{repo}")
                for i, (owner, repo, _) in enumerate(competitors)]
        tasks = [fetch_stargazer_history(owner, repo, session, pbar, cutoff_date)
                for (owner, repo, _), pbar in zip(competitors, pbars)]
        results = await asyncio.gather(*tasks)
        for pbar in pbars:
            pbar.close()
    return results

def main():
    # Define competitors: (owner, repo, column_name)
    competitors = [
        ('pre-commit', 'pre-commit', 'precommit'),
        ('j178', 'prek', 'prek'),
        ('evilmartians', 'lefthook', 'lefthook')
    ]

    print(f"Fetching competitor stargazer history up to {HK_RELEASE_DATE}...")
    print(f"(Will only keep data from {START_DATE} onwards in output)")
    star_histories = asyncio.run(fetch_all_competitors(competitors, HK_RELEASE_DATE))

    # Read existing hk-competitors.csv data
    existing_data = {}
    try:
        with open('hk-competitors.csv', 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_data[row['date']] = row
    except FileNotFoundError:
        print("No existing hk-competitors.csv found, creating new file")

    # Collect all unique dates across all competitors
    all_dates = set()
    for star_history in star_histories:
        all_dates.update(star_history.keys())
    all_dates = sorted(all_dates)

    print(f"\nProcessing data for {len(all_dates)} unique dates...")

    # Build complete dataset with cumulative stars
    output_data = []
    cumulative_stars = {comp[2]: 0 for comp in competitors}

    for date in all_dates:
        # Update cumulative counts for each competitor
        for (_, _, col_name), star_history in zip(competitors, star_histories):
            cumulative_stars[col_name] += star_history.get(date, 0)

        # Only output dates from START_DATE onwards
        if date < START_DATE:
            continue

        # Check if we have existing data for this date
        if date in existing_data:
            # Use existing hk data, update competitor stars
            row = existing_data[date].copy()
            row['precommit_stars'] = str(cumulative_stars['precommit'])
            row['prek_stars'] = str(cumulative_stars['prek'])
            row['lefthook_stars'] = str(cumulative_stars['lefthook'])
        else:
            # Create new row with only competitor star data
            row = {
                'date': date,
                'hk_stars': '0',  # hk didn't exist yet
                'precommit_stars': str(cumulative_stars['precommit']),
                'prek_stars': str(cumulative_stars['prek']),
                'lefthook_stars': str(cumulative_stars['lefthook'])
            }

        output_data.append(row)

    # Merge with any existing data after the cutoff date
    for date, row in existing_data.items():
        if date > HK_RELEASE_DATE:
            output_data.append(row)

    # Sort by date
    output_data.sort(key=lambda x: x['date'])

    # Write updated hk-competitors.csv
    fieldnames = ['date', 'hk_stars', 'precommit_stars', 'prek_stars', 'lefthook_stars']
    with open('hk-competitors.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_data)

    print(f"\nSuccessfully wrote {len(output_data)} rows to hk-competitors.csv")
    print(f"Date range: {output_data[0]['date']} to {output_data[-1]['date']}")
    print(f"Final competitor star counts as of {HK_RELEASE_DATE}:")
    for comp_name in ['precommit', 'prek', 'lefthook']:
        print(f"  {comp_name}: {cumulative_stars[comp_name]:,}")

if __name__ == '__main__':
    main()
