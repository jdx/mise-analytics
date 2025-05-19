#!/usr/bin/env -S uv run
import os
import csv
import asyncio
import aiohttp
from datetime import datetime, timezone
from collections import defaultdict
from tqdm import tqdm

async def fetch_stargazer_history(repo, session, pbar):
    daily_stars = defaultdict(int)
    
    # Initialize with current total
    headers = {
        'Authorization': f'Bearer {os.environ["GITHUB_TOKEN"]}',
        'Accept': 'application/vnd.github.v3.star+json'
    }
    
    async with session.get(
        f'https://api.github.com/repos/{repo}',
        headers=headers
    ) as response:
        repo_data = await response.json()
        total_stars = repo_data['stargazers_count']
        pbar.total = total_stars
        pbar.set_description(f"Fetching {repo}")
    
    # Fetch all stargazers with timestamps
    page = 1
    while True:
        async with session.get(
            f'https://api.github.com/repos/{repo}/stargazers'
            f'?page={page}&per_page=100',
            headers=headers
        ) as response:
            stars = await response.json()
            
            if not stars:
                break
                
            for star in stars:
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
            if remaining and int(remaining) == 0:
                reset_time = int(response.headers['X-RateLimit-Reset'])
                wait_time = reset_time - datetime.now().timestamp()
                if wait_time > 0:
                    pbar.set_description(f"Rate limited, waiting {int(wait_time)}s...")
                    await asyncio.sleep(wait_time + 1)
                    pbar.set_description(f"Fetching {repo}")
    
    return daily_stars

async def fetch_all_repos():
    repos = ['jdx/mise', 'asdf-vm/asdf', 'jdx/hk']
    async with aiohttp.ClientSession() as session:
        pbars = [tqdm(position=i) for i in range(len(repos))]
        tasks = [fetch_stargazer_history(repo, session, pbar) 
                for repo, pbar in zip(repos, pbars)]
        results = await asyncio.gather(*tasks)
        for pbar in pbars:
            pbar.close()
    return dict(zip(repos, results))

def main():
    # Fetch star history for all repos in parallel
    star_histories = asyncio.run(fetch_all_repos())
    
    # Read existing mise.csv data
    existing_data = {}
    try:
        with open('mise.csv', 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_data[row['date']] = row
    except FileNotFoundError:
        pass

    # Calculate cumulative stars for mise
    mise_dates = sorted(star_histories['jdx/mise'].keys())
    mise_cumulative = 0
    mise_data = []
    
    for date in mise_dates:
        mise_cumulative += star_histories['jdx/mise'][date]
        if date in existing_data:
            # Use existing brew data
            row = existing_data[date]
            row['github_stars'] = str(mise_cumulative)
            mise_data.append(row)
        else:
            # Add new row with only star data
            mise_data.append({
                'date': date,
                'brew_rank': '',
                'brew_installs': '',
                'brew_pct': '',
                'github_stars': str(mise_cumulative)
            })

    # Write updated mise.csv
    fieldnames = ['date', 'brew_rank', 'brew_installs', 'brew_pct', 'github_stars']
    with open('mise.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(mise_data)

    # Calculate cumulative stars for competitors
    all_dates = sorted(
        set(star_histories['jdx/mise'].keys()) | 
        set(star_histories['asdf-vm/asdf'].keys()) |
        set(star_histories['jdx/hk'].keys()))
    mise_cumulative = asdf_cumulative = hk_cumulative = 0
    competitor_data = []
    
    for date in all_dates:
        mise_cumulative += star_histories['jdx/mise'].get(date, 0)
        asdf_cumulative += star_histories['asdf-vm/asdf'].get(date, 0)
        hk_cumulative += star_histories['jdx/hk'].get(date, 0)
        competitor_data.append({
            'date': date,
            'mise_stars': str(mise_cumulative),
            'asdf_stars': str(asdf_cumulative),
            'hk_stars': str(hk_cumulative)
        })

    # Write competitors.csv
    fieldnames = ['date', 'mise_stars', 'asdf_stars', 'hk_stars']
    with open('competitors.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(competitor_data)

if __name__ == '__main__':
    main() 
