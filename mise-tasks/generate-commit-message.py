#!/usr/bin/env python3
"""Generate a commit message with top 5 repos' stats."""

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

    # Get top 5 repos by stars for the latest date
    latest_df = df[df['date'] == latest_date].nlargest(5, 'github_stars')
    prev_df = df[df['date'] == prev_date]

    # Build commit message
    parts = []
    for _, row in latest_df.iterrows():
        repo = row['repo_name']
        stars = int(row['github_stars'])

        # Get previous stars
        prev_row = prev_df[prev_df['repo_name'] == repo]
        if not prev_row.empty:
            prev_stars = int(prev_row.iloc[0]['github_stars'])
            delta = stars - prev_stars
            delta_str = f"+{delta}" if delta > 0 else str(delta)
        else:
            delta_str = "+0"

        parts.append(f"{repo}: {stars:,} ({delta_str})")

    # Format the commit message
    message = f"update stats: {', '.join(parts)}"
    print(message)

if __name__ == '__main__':
    main()
