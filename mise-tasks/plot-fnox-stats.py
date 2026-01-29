#!/usr/bin/env -S uv run

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
from datetime import datetime
import numpy as np
from scipy import stats

# Read the CSV file
df_comp = pd.read_csv('fnox-competitors.csv')

# Convert date column to datetime
df_comp['date'] = pd.to_datetime(df_comp['date'])

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

fnox_avg = calc_daily_avg(df_comp, 'fnox_stars')
fnox_current = df_comp['fnox_stars'].iloc[-1]

# Define competitors
competitors = {
    'sops': {'color': '#8E44AD'},  # Purple
}

# Filter to only competitors that fnox hasn't passed yet
active_competitors = {}
for name, info in competitors.items():
    col = f'{name}_stars'
    data = df_comp[df_comp[col] > 0]
    if len(data) > 0:
        current_stars = data[col].iloc[-1]
        if current_stars > fnox_current:
            info['data'] = data
            info['avg'] = calc_daily_avg(df_comp, col)
            active_competitors[name] = info

# Plot fnox stars
color2 = '#E67E22'  # Orange
line2 = ax.plot(
    df_comp[df_comp['fnox_stars'] > 0]['date'],
    df_comp[df_comp['fnox_stars'] > 0]['fnox_stars'],
    color=color2,
    linewidth=3,
    label=f'fnox (+{fnox_avg:.1f}/day)'
)

# Plot competitor stars
comp_lines = {}
for name, info in active_competitors.items():
    col = f'{name}_stars'
    line = ax.plot(
        info['data']['date'],
        info['data'][col],
        color=info['color'],
        linestyle='--',
        label=f'{name} (+{info["avg"]:.1f}/day)'
    )
    info['line'] = line
    comp_lines[name] = line

# Calculate crossing points
def predict_crossing(df_comp, tool, days=30):
    cutoff_date = df_comp['date'].max() - pd.Timedelta(days=days)
    recent_data = df_comp[df_comp['date'] >= cutoff_date].copy()

    x = (recent_data['date'] - recent_data['date'].min()).dt.days

    fnox_slope, _, _, _, _ = stats.linregress(x, recent_data['fnox_stars'])
    tool_slope, _, _, _, _ = stats.linregress(x, recent_data[f'{tool}_stars'])

    if fnox_slope <= tool_slope:
        return None

    fnox_current = df_comp['fnox_stars'].iloc[-1]
    tool_current = df_comp[f'{tool}_stars'].iloc[-1]

    if fnox_current >= tool_current:
        return datetime.now(), fnox_slope - tool_slope

    stars_diff = tool_current - fnox_current
    daily_gain = fnox_slope - tool_slope
    days_to_cross = stars_diff / daily_gain if daily_gain > 0 else None

    if days_to_cross is None or days_to_cross < 0:
        return None

    if days_to_cross > 3650:
        return None

    crossing_date = datetime.now() + pd.Timedelta(days=int(days_to_cross))
    return crossing_date, daily_gain

# Calculate predictions for active competitors
prediction_labels = {}
for tool, info in active_competitors.items():
    color = info['color']
    timeframes = [30, 90, 180]
    valid_predictions = []
    daily_gains = []

    for days in timeframes:
        result = predict_crossing(df_comp, tool, days)
        if result:
            cross_date, daily_gain = result
            valid_predictions.append(cross_date)
            daily_gains.append(daily_gain)

    if valid_predictions:
        total_timedelta = sum((d - valid_predictions[0] for d in valid_predictions[1:]), pd.Timedelta(0))
        avg_timedelta = total_timedelta / len(valid_predictions)
        avg_date = valid_predictions[0] + avg_timedelta
        avg_gain = sum(daily_gains) / len(daily_gains)
        days_until = (avg_date - datetime.now()).days
        date_str = avg_date.strftime('%Y-%m-%d')

        prediction_labels[tool] = f" (passes {date_str}, {days_until} days)"

        if days_until > 0:
            ax.axvline(x=avg_date, color=color, linestyle=':', alpha=0.5)
            y_pos = df_comp[f'{tool}_stars'].iloc[-1]
            ax.annotate(f'Passes {tool}',
                       xy=(avg_date, y_pos),
                       xytext=(-50, 20),
                       textcoords='offset points',
                       color=color,
                       fontsize=8,
                       arrowprops=dict(arrowstyle='->',
                                     connectionstyle='arc3,rad=.2',
                                     color=color))

ax.set_ylabel('GitHub Stars', fontsize=12)
ax.set_xlabel('Date', fontsize=12)
ax.grid(True, alpha=0.3)

# Set title and format date
plt.title('fnox: GitHub Stars Over Time', fontsize=14, fontweight='bold')
ax.xaxis.set_major_formatter(DateFormatter('%Y-%m-%d'))
plt.xticks(rotation=45)

# Update labels with predictions and create legend
lines = line2
for name, info in active_competitors.items():
    label = f'{name} (+{info["avg"]:.1f}/day)' + prediction_labels.get(name, '')
    info['line'][0].set_label(label)
    lines = lines + info['line']

labels = [line.get_label() for line in lines]
ax.legend(lines, labels, loc='upper left')

# Adjust layout to prevent label cutoff
plt.tight_layout()

# Save the plot
plt.savefig('charts/fnox_stats.png', dpi=300, bbox_inches='tight')
