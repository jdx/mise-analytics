#!/usr/bin/env -S uv run

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
import numpy as np

# Read the CSV file
df = pd.read_csv('top-repos.csv')

# Convert date column to datetime
df['date'] = pd.to_datetime(df['date'])

# Filter to last 2 years
from datetime import datetime, timedelta
two_years_ago = datetime.now() - timedelta(days=730)
df = df[df['date'] >= two_years_ago]

# Exclude mise from top-repos visualization (but keep in CSV)
df = df[df['repo_name'] != 'mise']

# Get unique repos sorted by most recent star count
latest_data = df.loc[df.groupby('repo_name')['date'].idxmax()]
repos = latest_data.sort_values('github_stars', ascending=False)['repo_name'].tolist()

# Create figure with single plot
fig, ax = plt.subplots(figsize=(14, 6))

# Define color palette for repos
colors = plt.cm.tab10(np.linspace(0, 1, 10))

# Calculate daily average for a repo
def calc_daily_avg(repo_data):
    """Calculate average stars per day"""
    if len(repo_data) < 2:
        return 0
    first_stars = repo_data['github_stars'].iloc[0]
    last_stars = repo_data['github_stars'].iloc[-1]
    days = (repo_data['date'].iloc[-1] - repo_data['date'].iloc[0]).days
    if days == 0:
        return 0
    return (last_stars - first_stars) / days

# Plot GitHub Stars for all top 10 repos
for idx, repo in enumerate(repos[:10]):
    repo_data = df[df['repo_name'] == repo].sort_values('date')
    if len(repo_data) > 0:
        daily_avg = calc_daily_avg(repo_data)
        ax.plot(
            repo_data['date'],
            repo_data['github_stars'],
            color=colors[idx],
            label=f'{repo} (+{daily_avg:.1f}/day)',
            marker='o',
            markersize=3,
            linewidth=2
        )

ax.set_ylabel('GitHub Stars', fontsize=12)
ax.set_xlabel('Date', fontsize=12)
ax.set_title('Top 10 Repos by GitHub Stars', fontsize=14, fontweight='bold')
ax.legend(loc='upper left', ncol=2, fontsize=9)
ax.grid(True, alpha=0.3)
ax.xaxis.set_major_formatter(DateFormatter('%Y-%m-%d'))
plt.xticks(rotation=45)

# Add summary text box
total_stars = latest_data['github_stars'].sum()
avg_stars = latest_data['github_stars'].mean()
summary_text = f'Total Stars: {total_stars:,}\nAverage: {avg_stars:,.0f}'

props = dict(boxstyle='round', facecolor='white', alpha=0.9, edgecolor='gray')
ax.text(0.98, 0.02, summary_text,
        transform=ax.transAxes,
        fontsize=10,
        verticalalignment='bottom',
        horizontalalignment='right',
        bbox=props)

# Adjust layout to prevent label cutoff
plt.tight_layout()

# Save the plot
plt.savefig('charts/top_repos_stats.png', dpi=300, bbox_inches='tight')
print(f"Saved visualization to charts/top_repos_stats.png")
print(f"Tracking {len(repos)} repos")
