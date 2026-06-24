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

    headers = {
        'Authorization': f'Bearer {os.environ["GITHUB_TOKEN"]}',
        'Accept': 'application/vnd.github+json'
    }

    query = """
    query($owner: String!, $repo: String!, $cursor: String) {
      repository(owner: $owner, name: $repo) {
        stargazers(
          first: 100,
          after: $cursor,
          orderBy: {field: STARRED_AT, direction: ASC}
        ) {
          totalCount
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
    owner, repo_name = repo.split("/", 1)
    cursor = None
    page = 1

    while True:
        async with session.post(
            'https://api.github.com/graphql',
            headers=headers,
            json={
                'query': query,
                'variables': {
                    'owner': owner,
                    'repo': repo_name,
                    'cursor': cursor,
                },
            },
        ) as response:
            payload = await response.json()

            if response.status != 200 or payload.get('errors'):
                raise RuntimeError(f"GitHub GraphQL error for {repo}: {payload}")

            stargazers = payload['data']['repository']['stargazers']
            pbar.total = stargazers['totalCount']
            pbar.set_description(f"Fetching {repo}")
            stars = stargazers['edges']

            if not stars:
                break

            for star in stars:
                starred_at = datetime.strptime(
                    star['starredAt'],
                    '%Y-%m-%dT%H:%M:%SZ'
                ).replace(tzinfo=timezone.utc)

                date = starred_at.strftime('%Y-%m-%d')
                daily_stars[date] += 1
                pbar.update(1)

            page_info = stargazers['pageInfo']
            if not page_info['hasNextPage']:
                break

            cursor = page_info['endCursor']
            page += 1

    return daily_stars

async def fetch_all_repos():
    repos = ['jdx/mise', 'asdf-vm/asdf', 'jdx/hk', 'casey/just', 'Homebrew/brew']
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
        set(star_histories['jdx/hk'].keys()) |
        set(star_histories['casey/just'].keys()) |
        set(star_histories['Homebrew/brew'].keys()))
    mise_cumulative = asdf_cumulative = hk_cumulative = just_cumulative = brew_cumulative = 0
    competitor_data = []
    
    for date in all_dates:
        mise_cumulative += star_histories['jdx/mise'].get(date, 0)
        asdf_cumulative += star_histories['asdf-vm/asdf'].get(date, 0)
        hk_cumulative += star_histories['jdx/hk'].get(date, 0)
        just_cumulative += star_histories['casey/just'].get(date, 0)
        brew_cumulative += star_histories['Homebrew/brew'].get(date, 0)
        competitor_data.append({
            'date': date,
            'mise_stars': str(mise_cumulative),
            'asdf_stars': str(asdf_cumulative),
            'hk_stars': str(hk_cumulative),
            'just_stars': str(just_cumulative),
            'brew_stars': str(brew_cumulative)
        })

    # Write competitors.csv
    fieldnames = ['date', 'mise_stars', 'asdf_stars', 'hk_stars', 'just_stars', 'brew_stars']
    with open('competitors.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(competitor_data)

if __name__ == '__main__':
    main() 
