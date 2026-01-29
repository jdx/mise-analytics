#!/usr/bin/env -S uv run

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
from datetime import datetime
import numpy as np
from scipy import stats

# Read the CSV file
df_comp = pd.read_csv('hk-competitors.csv')

# Convert date column to datetime
df_comp['date'] = pd.to_datetime(df_comp['date'])

# Filter data from 2023-01-01
start_date = '2023-01-01'
df_comp = df_comp[df_comp['date'] >= start_date]

# Create figure with single axis for GitHub stars
fig, ax = plt.subplots(figsize=(12, 6))

# Calculate daily averages for each repo
def calc_daily_avg(df, col_name):
    """Calculate average stars per day"""
    data = df[df[col_name] > 0]
    if len(data) < 2:
        return 0
    first_stars = data[col_name].iloc[0]
    last_stars = data[col_name].iloc[-1]
    days = (data['date'].iloc[-1] - data['date'].iloc[0]).days
    if days == 0:
        return 0
    return (last_stars - first_stars) / days

hk_avg = calc_daily_avg(df_comp, 'hk_stars')
precommit_avg = calc_daily_avg(df_comp, 'precommit_stars')
prek_avg = calc_daily_avg(df_comp, 'prek_stars')
lefthook_avg = calc_daily_avg(df_comp, 'lefthook_stars')

# Plot hk stars
color2 = '#E67E22'  # Orange
line2 = ax.plot(
    df_comp[df_comp['hk_stars'] > 0]['date'],
    df_comp[df_comp['hk_stars'] > 0]['hk_stars'],
    color=color2,
    linewidth=3,
    label=f'hk (+{hk_avg:.1f}/day)'
)

# Plot competitor stars
color3 = '#8E44AD'  # Purple
color4 = '#F1C40F'  # Yellow
color5 = '#2ECC71'  # Green

# Filter out zero values before plotting
line3 = ax.plot(
    df_comp[df_comp['precommit_stars'] > 0]['date'],
    df_comp[df_comp['precommit_stars'] > 0]['precommit_stars'],
    color=color3,
    label=f'pre-commit (+{precommit_avg:.1f}/day)'
)
line4 = ax.plot(
    df_comp[df_comp['prek_stars'] > 0]['date'],
    df_comp[df_comp['prek_stars'] > 0]['prek_stars'],
    color=color4,
    label=f'prek (+{prek_avg:.1f}/day)'
)
line5 = ax.plot(
    df_comp[df_comp['lefthook_stars'] > 0]['date'],
    df_comp[df_comp['lefthook_stars'] > 0]['lefthook_stars'],
    color=color5,
    label=f'lefthook (+{lefthook_avg:.1f}/day)'
)

# Calculate crossing points
def predict_crossing(df_comp, tool, days=30):
    # Use specified days of data for prediction
    cutoff_date = df_comp['date'].max() - pd.Timedelta(days=days)
    recent_data = df_comp[df_comp['date'] >= cutoff_date].copy()

    # Convert dates to numbers for regression
    x = (recent_data['date'] - recent_data['date'].min()).dt.days

    # Get growth rates
    hk_slope, hk_intercept, _, _, _ = stats.linregress(x, recent_data['hk_stars'])
    tool_slope, tool_intercept, _, _, _ = stats.linregress(x, recent_data[f'{tool}_stars'])

    # Calculate crossing point
    if hk_slope <= tool_slope:
        return None

    # Get current values
    hk_current = df_comp['hk_stars'].iloc[-1]
    tool_current = df_comp[f'{tool}_stars'].iloc[-1]

    # If we're already ahead, return today
    if hk_current >= tool_current:
        return datetime.now(), hk_slope - tool_slope

    # Calculate days until crossing based on recent growth rates
    stars_diff = tool_current - hk_current
    daily_gain = hk_slope - tool_slope
    days_to_cross = stars_diff / daily_gain if daily_gain > 0 else None

    if days_to_cross is None or days_to_cross < 0:
        return None

    # Cap maximum prediction at 10 years to avoid overflow
    if days_to_cross > 3650:  # ~10 years
        return None

    crossing_date = datetime.now() + pd.Timedelta(days=int(days_to_cross))
    return crossing_date, daily_gain

# Add predictions box and markers
predictions = []
for tool, color in [('precommit', color3), ('prek', color4), ('lefthook', color5)]:
    timeframes = [30, 90, 180]
    valid_predictions = []
    daily_gains = []

    # Collect all valid predictions
    for days in timeframes:
        result = predict_crossing(df_comp, tool, days)
        if result:
            cross_date, daily_gain = result
            valid_predictions.append(cross_date)
            daily_gains.append(daily_gain)

    if valid_predictions:
        # Calculate average prediction
        total_timedelta = sum((d - valid_predictions[0] for d in valid_predictions[1:]), pd.Timedelta(0))
        avg_timedelta = total_timedelta / len(valid_predictions)
        avg_date = valid_predictions[0] + avg_timedelta
        avg_gain = sum(daily_gains) / len(daily_gains)
        days_until = (avg_date - datetime.now()).days
        date_str = avg_date.strftime('%Y-%m-%d')

        # Format display name
        display_name = 'pre-commit' if tool == 'precommit' else tool

        # Add prediction text
        predictions.append(f"Will pass {display_name}: {date_str} ({days_until:,} days, +{avg_gain:.1f}/day)")

        # Add marker if in the future
        if days_until > 0:
            ax.axvline(x=avg_date, color=color, linestyle=':', alpha=0.5)
            y_pos = df_comp[f'{tool}_stars'].iloc[-1]
            ax.annotate(f'Passes {display_name}',
                       xy=(avg_date, y_pos),
                       xytext=(-50, 20),
                       textcoords='offset points',
                       color=color,
                       fontsize=8,
                       arrowprops=dict(arrowstyle='->',
                                     connectionstyle='arc3,rad=.2',
                                     color=color))

if predictions:
    # Create text box
    box_text = '\n'.join(['Predictions:'] + predictions)
    props = dict(boxstyle='round', facecolor='white', alpha=0.8, edgecolor='gray')
    ax.text(0.02, 0.98, box_text,
            transform=ax.transAxes,
            fontsize=9,
            verticalalignment='top',
            horizontalalignment='left',
            bbox=props)

ax.set_ylabel('GitHub Stars', fontsize=12)
ax.set_xlabel('Date', fontsize=12)
ax.grid(True, alpha=0.3)

# Set title and format date
plt.title('hk: GitHub Stars Over Time', fontsize=14, fontweight='bold')
ax.xaxis.set_major_formatter(DateFormatter('%Y-%m-%d'))
plt.xticks(rotation=45)

# Add legend
lines = line2 + line3 + line4 + line5
labels = [line.get_label() for line in lines]
ax.legend(lines, labels, loc='upper left')

# Adjust layout to prevent label cutoff
plt.tight_layout()

# Save the plot
plt.savefig('charts/hk_stats.png', dpi=300, bbox_inches='tight')
