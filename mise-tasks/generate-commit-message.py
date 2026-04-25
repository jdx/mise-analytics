#!/usr/bin/env python3
"""Generate a commit message with top 3 repos' stats."""

import pandas as pd
from datetime import datetime

def main():
    # Read the top repos data
    df = pd.read_csv('top-repos.csv')

    # Get the latest date
    latest_date = df['date'].max()

    # Get data for the latest two dates to calculate delta
    dates = sorted(df['date'].unique())
    if len(dates) < 2:
        print("update stats")
        return

    latest_date = dates[-1]
    prev_date = dates[-2]

    # Pick the 3 repos with the largest day-over-day star gain.
    latest_df = df[df['date'] == latest_date][['repo_name', 'github_stars']]
    prev_df = df[df['date'] == prev_date][['repo_name', 'github_stars']].rename(
        columns={'github_stars': 'prev_stars'}
    )
    merged = latest_df.merge(prev_df, on='repo_name', how='left')
    merged['prev_stars'] = merged['prev_stars'].fillna(merged['github_stars'])
    merged['delta'] = merged['github_stars'] - merged['prev_stars']
    top = merged.sort_values(
        by=['delta', 'github_stars'], ascending=[False, False]
    ).head(3)

    parts = []
    for _, row in top.iterrows():
        stars = int(row['github_stars'])
        delta = int(row['delta'])
        delta_str = f"+{delta}" if delta >= 0 else str(delta)
        parts.append(f"{row['repo_name']}: {stars:,} ({delta_str})")

    # Format the commit message
    message = f"update stats: {', '.join(parts)}"
    print(message)

if __name__ == '__main__':
    main()
