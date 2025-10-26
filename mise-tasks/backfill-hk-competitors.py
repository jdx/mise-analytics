#!/usr/bin/env -S uv run
import os
import csv
import asyncio
import aiohttp
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from tqdm import tqdm

# Backfill from day after hk release to yesterday
START_DATE = '2025-01-27'
END_DATE = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

async def fetch_stargazer_history(owner, repo, session, pbar, start_date, end_date):
    """Fetch stargazer history for a repo between start and end dates"""
    daily_stars = defaultdict(int)

    headers = {
        'Authorization': f'Bearer {os.environ["GITHUB_TOKEN"]}',
        'Accept': 'application/vnd.github.v3.star+json'
    }

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

    # Fetch all stargazers with timestamps
    page = 1
    start_dt = datetime.strptime(start_date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    end_dt = datetime.strptime(end_date, '%Y-%m-%d').replace(tzinfo=timezone.utc, hour=23, minute=59, second=59)

    while True:
        async with session.get(
            f'https://api.github.com/repos/{owner}/{repo}/stargazers'
            f'?page={page}&per_page=100',
            headers=headers
        ) as response:
            stars = await response.json()

            if not stars or not isinstance(stars, list):
                break

            found_in_range = False
            for star in stars:
                if 'starred_at' not in star:
                    continue

                starred_at = datetime.strptime(
                    star['starred_at'],
                    '%Y-%m-%dT%H:%M:%SZ'
                ).replace(tzinfo=timezone.utc)

                # Only include stars in the date range
                if start_dt <= starred_at <= end_dt:
                    date = starred_at.strftime('%Y-%m-%d')
                    daily_stars[date] += 1
                    found_in_range = True

                pbar.update(1)

            # If we've gone past the end date, stop
            if stars and 'starred_at' in stars[-1]:
                last_star_date = datetime.strptime(
                    stars[-1]['starred_at'],
                    '%Y-%m-%dT%H:%M:%SZ'
                ).replace(tzinfo=timezone.utc)
                if last_star_date > end_dt:
                    pbar.set_description(f"Completed {owner}/{repo}")
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

async def fetch_all_competitors(competitors, start_date, end_date):
    """Fetch stargazer history for all competitors in parallel"""
    async with aiohttp.ClientSession() as session:
        pbars = [tqdm(position=i, desc=f"{owner}/{repo}")
                for i, (owner, repo, _) in enumerate(competitors)]
        tasks = [fetch_stargazer_history(owner, repo, session, pbar, start_date, end_date)
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

    print(f"Backfilling competitor data from {START_DATE} to {END_DATE}...")
    star_histories = asyncio.run(fetch_all_competitors(competitors, START_DATE, END_DATE))

    # Read existing hk-competitors.csv
    existing_data = {}
    try:
        with open('hk-competitors.csv', 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_data[row['date']] = row
    except FileNotFoundError:
        print("Error: hk-competitors.csv not found")
        return

    # Get baseline star counts from the last historical date (2025-01-26)
    baseline_date = '2025-01-26'
    if baseline_date not in existing_data:
        print(f"Error: baseline date {baseline_date} not found in CSV")
        return

    baseline = existing_data[baseline_date]
    cumulative_stars = {
        'precommit': int(baseline['precommit_stars']),
        'prek': int(baseline['prek_stars']),
        'lefthook': int(baseline['lefthook_stars'])
    }

    print(f"\nBaseline star counts from {baseline_date}:")
    for comp_name, count in cumulative_stars.items():
        print(f"  {comp_name}: {count:,}")

    # Build complete date range
    start_dt = datetime.strptime(START_DATE, '%Y-%m-%d')
    end_dt = datetime.strptime(END_DATE, '%Y-%m-%d')

    all_dates = []
    current = start_dt
    while current <= end_dt:
        all_dates.append(current.strftime('%Y-%m-%d'))
        current += timedelta(days=1)

    print(f"\nProcessing {len(all_dates)} dates...")

    # Update cumulative counts for each date
    for date in all_dates:
        # Add daily stars to cumulative counts
        for (_, _, col_name), star_history in zip(competitors, star_histories):
            cumulative_stars[col_name] += star_history.get(date, 0)

        # Update the existing data
        if date in existing_data:
            existing_data[date]['precommit_stars'] = str(cumulative_stars['precommit'])
            existing_data[date]['prek_stars'] = str(cumulative_stars['prek'])
            existing_data[date]['lefthook_stars'] = str(cumulative_stars['lefthook'])

    # Write updated CSV
    output_data = sorted(existing_data.values(), key=lambda x: x['date'])

    fieldnames = ['date', 'hk_stars', 'precommit_stars', 'prek_stars', 'lefthook_stars']
    with open('hk-competitors.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_data)

    print(f"\nSuccessfully updated hk-competitors.csv")
    print(f"Final competitor star counts as of {END_DATE}:")
    for comp_name in ['precommit', 'prek', 'lefthook']:
        print(f"  {comp_name}: {cumulative_stars[comp_name]:,}")

if __name__ == '__main__':
    main()
