#!/usr/bin/env -S uv run
import os
import csv
import asyncio
import aiohttp
from datetime import datetime, timezone
from collections import defaultdict
from tqdm import tqdm

# hk was released on 2025-01-26
HK_RELEASE_DATE = '2025-01-26'

async def fetch_hk_stargazer_history():
    """Fetch stargazer history for jdx/hk from release date onwards"""
    daily_stars = defaultdict(int)

    headers = {
        'Authorization': f'Bearer {os.environ["GITHUB_TOKEN"]}',
        'Accept': 'application/vnd.github.v3.star+json'
    }

    async with aiohttp.ClientSession() as session:
        # Get total stars first
        async with session.get(
            'https://api.github.com/repos/jdx/hk',
            headers=headers
        ) as response:
            repo_data = await response.json()
            if 'stargazers_count' not in repo_data:
                print("Error: Could not fetch data for jdx/hk")
                return daily_stars

            total_stars = repo_data['stargazers_count']
            print(f"Fetching stargazer history for jdx/hk ({total_stars} stars)...")

        # Fetch all stargazers with timestamps
        page = 1
        release_dt = datetime.strptime(HK_RELEASE_DATE, '%Y-%m-%d').replace(tzinfo=timezone.utc)

        with tqdm(total=total_stars, desc="Fetching jdx/hk") as pbar:
            while True:
                async with session.get(
                    f'https://api.github.com/repos/jdx/hk/stargazers'
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

                        # Only include stars from release date onwards
                        if starred_at >= release_dt:
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
                            pbar.set_description("Fetching jdx/hk")

    return daily_stars

def main():
    print(f"Fetching hk stargazer history from {HK_RELEASE_DATE} onwards...")
    hk_stars_by_date = asyncio.run(fetch_hk_stargazer_history())

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

    # Get all unique dates from both sources
    all_dates = set(existing_data.keys()) | set(hk_stars_by_date.keys())
    all_dates = sorted([d for d in all_dates if d >= HK_RELEASE_DATE])

    print(f"\nProcessing data for {len(all_dates)} dates from {HK_RELEASE_DATE} onwards...")

    # Build updated dataset with cumulative hk stars
    output_data = []
    cumulative_hk_stars = 0

    for date in all_dates:
        # Update cumulative hk star count
        cumulative_hk_stars += hk_stars_by_date.get(date, 0)

        # Use existing row or create new one
        if date in existing_data:
            row = existing_data[date].copy()
            row['hk_stars'] = str(cumulative_hk_stars)
        else:
            # Get the last known competitor stars (carry forward)
            last_competitor_data = None
            for past_date in sorted(existing_data.keys(), reverse=True):
                if past_date < date:
                    last_competitor_data = existing_data[past_date]
                    break

            if last_competitor_data:
                row = {
                    'date': date,
                    'hk_stars': str(cumulative_hk_stars),
                    'precommit_stars': last_competitor_data['precommit_stars'],
                    'prek_stars': last_competitor_data['prek_stars'],
                    'lefthook_stars': last_competitor_data['lefthook_stars']
                }
            else:
                # Shouldn't happen, but default to 0
                row = {
                    'date': date,
                    'hk_stars': str(cumulative_hk_stars),
                    'precommit_stars': '0',
                    'prek_stars': '0',
                    'lefthook_stars': '0'
                }

        output_data.append(row)

    # Add any data before release date (keep competitor history)
    for date in sorted(existing_data.keys()):
        if date < HK_RELEASE_DATE:
            output_data.insert(0, existing_data[date])

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
    print(f"Final hk star count: {cumulative_hk_stars:,}")

    # Show daily star counts for verification
    if hk_stars_by_date:
        print(f"\nTotal days with stars: {len(hk_stars_by_date)}")
        print("Sample of daily star counts:")
        for date in sorted(hk_stars_by_date.keys())[:5]:
            print(f"  {date}: +{hk_stars_by_date[date]} stars")

if __name__ == '__main__':
    main()
