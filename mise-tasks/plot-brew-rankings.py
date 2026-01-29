#!/usr/bin/env -S uv run

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
import numpy as np

# Read the CSV file
df = pd.read_csv('top-repos.csv')

# Convert date column to datetime
df['date'] = pd.to_datetime(df['date'])

# Exclude mise from top-repos (we'll add it separately)
df = df[df['repo_name'] != 'mise']

# Get unique repos sorted by most recent star count
latest_data = df.loc[df.groupby('repo_name')['date'].idxmax()]
repos = latest_data.sort_values('github_stars', ascending=False)['repo_name'].tolist()

# Create figure with single plot
fig, ax = plt.subplots(figsize=(14, 6))

# Define color palette for repos
colors = plt.cm.tab10(np.linspace(0, 1, 10))

# Plot Homebrew Rankings (for repos in homebrew-core)
brew_repos = []
for idx, repo in enumerate(repos[:10]):
    repo_data = df[(df['repo_name'] == repo) & (df['brew_rank'].notna())].sort_values('date')
    if len(repo_data) > 0:
        brew_repos.append(repo)
        # Plot brew rank (inverted axis since lower is better)
        ax.plot(
            repo_data['date'],
            repo_data['brew_rank'],
            color=colors[idx],
            label=repo,
            marker='s',
            markersize=3,
            linewidth=2
        )

# Note: mise has its own dedicated brew ranking chart

if brew_repos:
    ax.invert_yaxis()
    # Set y-axis to include 0
    current_ylim = ax.get_ylim()
    ax.set_ylim(max(current_ylim), 0)
    ax.set_ylabel('Homebrew Rank (lower is better)', fontsize=12)
    ax.set_xlabel('Date', fontsize=12)
    ax.set_title('Homebrew Rankings', fontsize=14, fontweight='bold')
    ax.legend(loc='upper left', ncol=2, fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(DateFormatter('%Y-%m-%d'))
    plt.xticks(rotation=45)
else:
    ax.text(0.5, 0.5, 'No repos in Homebrew yet',
             horizontalalignment='center', verticalalignment='center',
             transform=ax.transAxes, fontsize=14, color='gray')
    ax.set_xticks([])
    ax.set_yticks([])

# Adjust layout to prevent label cutoff
plt.tight_layout()

# Save the plot
plt.savefig('charts/brew_rankings.png', dpi=300, bbox_inches='tight')
print(f"Saved Homebrew rankings to charts/brew_rankings.png")
print(f"Tracking {len(brew_repos)} repos in Homebrew")
