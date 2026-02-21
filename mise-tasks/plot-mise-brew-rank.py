#!/usr/bin/env -S uv run

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter

# Read the CSV file
df = pd.read_csv('mise.csv')

# Convert date column to datetime
df['date'] = pd.to_datetime(df['date'])

# Filter to only rows with brew_rank data
df = df[df['brew_rank'].notna()].sort_values('date')

if len(df) == 0:
    print("No Homebrew ranking data available for mise")
    exit(0)

# Create figure
fig, ax = plt.subplots(figsize=(14, 6))

# Plot brew rank
color = '#E67E22'  # Orange - consistent with other mise charts
ax.plot(
    df['date'],
    df['brew_rank'],
    color=color,
    label='mise',
    marker='o',
    markersize=4,
    linewidth=2.5
)

# Invert y-axis (lower rank is better)
ax.invert_yaxis()
# Set y-axis to include 0
current_ylim = ax.get_ylim()
ax.set_ylim(max(current_ylim), 0)
ax.set_ylabel('Homebrew Rank (lower is better)', fontsize=12)
ax.set_xlabel('Date', fontsize=12)
ax.set_title('mise Homebrew Ranking Over Time', fontsize=14, fontweight='bold')
ax.grid(True, alpha=0.3)
ax.xaxis.set_major_formatter(DateFormatter('%Y-%m-%d'))
plt.xticks(rotation=45)

# Plot brew_pct on secondary y-axis
df_pct = df[df['brew_pct'].notna()]
if len(df_pct) > 0:
    ax2 = ax.twinx()
    ax2.plot(
        df_pct['date'],
        df_pct['brew_pct'],
        color='#3498DB',
        label='install %',
        linewidth=2,
        alpha=0.8
    )
    ax2.set_ylabel('Install % (of all Homebrew users)', fontsize=12, color='#3498DB')
    ax2.tick_params(axis='y', labelcolor='#3498DB')
    ax2.set_ylim(0, None)
    ax2.axhline(y=0.76, color='#3498DB', linestyle=':', alpha=0.5)
    ax2.annotate('0.76%', xy=(df_pct['date'].iloc[0], 0.76),
                 xytext=(5, 5), textcoords='offset points',
                 color='#3498DB', fontsize=9, alpha=0.7)

    # Combine legends from both axes
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc='lower left', fontsize=10)
else:
    ax.legend(loc='lower left', fontsize=10)

# Add annotation for current rank
current_rank = df['brew_rank'].iloc[-1]
current_date = df['date'].iloc[-1]
best_rank = df['brew_rank'].min()

stats_text = f'Current Rank: #{int(current_rank)}\nBest: #{int(best_rank)}'
props = dict(boxstyle='round', facecolor='white', alpha=0.9, edgecolor='gray')
ax.text(0.02, 0.02, stats_text,
        transform=ax.transAxes,
        fontsize=10,
        verticalalignment='bottom',
        horizontalalignment='left',
        bbox=props)

# Add callout for best ranking day
best_rank_idx = df['brew_rank'].idxmin()
best_rank_date = df.loc[best_rank_idx, 'date']
best_rank_value = df.loc[best_rank_idx, 'brew_rank']

ax.annotate(f'Best rank: #{int(best_rank_value)}',
           xy=(best_rank_date, best_rank_value),
           xytext=(20, -40),
           textcoords='offset points',
           fontsize=10,
           color='#E67E22',
           fontweight='bold',
           arrowprops=dict(arrowstyle='->',
                          connectionstyle='arc3,rad=.2',
                          color='#E67E22',
                          lw=2))

# Adjust layout
plt.tight_layout()

# Save the plot
plt.savefig('charts/mise_brew_rank.png', dpi=300, bbox_inches='tight')
print(f"Saved mise Homebrew ranking chart to charts/mise_brew_rank.png")
print(f"Current rank: #{int(current_rank)}, Best: #{int(best_rank)}")
