#!/usr/bin/env -S uv run

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
from datetime import datetime
import numpy as np
from scipy import stats

# Read the CSV files
df = pd.read_csv('mise.csv')
df_comp = pd.read_csv('competitors.csv')

# Convert date columns to datetime
df['date'] = pd.to_datetime(df['date'])
df_comp['date'] = pd.to_datetime(df_comp['date'])

# Filter data from 2023-01-01
start_date = '2023-01-01'
df = df[df['date'] >= start_date]
df_comp = df_comp[df_comp['date'] >= start_date]

# Create figure and axis with two y-axes
fig, ax2 = plt.subplots(figsize=(12, 6))
ax1 = ax2.twinx()

# Plot brew_rank on left y-axis (inverted)
color1 = '#2E86C1'  # Blue
line1 = ax1.plot(df['date'], df['brew_rank'], color=color1, label='Brew Rank')
ax1.set_ylabel('Brew Rank', color=color1)
ax1.tick_params(axis='y', labelcolor=color1)
# Invert the primary y-axis since lower rank is better
ax1.invert_yaxis()
ax1.set_ybound(lower=1, upper=100)

# Plot github_stars on right y-axis
color2 = '#E67E22'  # Orange
line2 = ax2.plot(
    df['date'],
    df['github_stars'],
    color=color2,
    label='mise'
)

# Plot competitor stars
color4 = '#8E44AD'  # Purple
color5 = '#F1C40F'  # Yellow

# Filter out zero values before plotting
line4 = ax2.plot(
    df_comp[df_comp['asdf_stars'] > 0]['date'],
    df_comp[df_comp['asdf_stars'] > 0]['asdf_stars'],
    color=color4,
    linestyle='--',
    label='asdf'
)
line5 = ax2.plot(
    df_comp[df_comp['hk_stars'] > 0]['date'],
    df_comp[df_comp['hk_stars'] > 0]['hk_stars'],
    color=color5,
    linestyle='--',
    label='hk'
)

# Calculate crossing points
def predict_crossing(df_comp, tool, days=30):
    # Use specified days of data for prediction
    cutoff_date = df_comp['date'].max() - pd.Timedelta(days=days)
    recent_data = df_comp[df_comp['date'] >= cutoff_date].copy()
    
    # Convert dates to numbers for regression
    x = (recent_data['date'] - recent_data['date'].min()).dt.days
    
    # Get growth rates
    mise_slope, mise_intercept, _, _, _ = stats.linregress(x, recent_data['mise_stars'])
    tool_slope, tool_intercept, _, _, _ = stats.linregress(x, recent_data[f'{tool}_stars'])
    
    # Calculate crossing point
    if mise_slope <= tool_slope:
        return None
    
    # Get current values
    mise_current = df_comp['mise_stars'].iloc[-1]
    tool_current = df_comp[f'{tool}_stars'].iloc[-1]
    
    # If we're already ahead, return today
    if mise_current >= tool_current:
        return datetime.now(), mise_slope - tool_slope
    
    # Calculate days until crossing based on recent growth rates
    stars_diff = tool_current - mise_current
    daily_gain = mise_slope - tool_slope
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
for tool, color in [('asdf', color4)]:
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
        
        # Add prediction text
        predictions.append(f"Will pass {tool}: {date_str} ({days_until:,} days, +{avg_gain:.1f}/day)")
        
        # Add marker if in the future
        if days_until > 0:
            ax2.axvline(x=avg_date, color=color, linestyle=':', alpha=0.5)
            y_pos = df_comp[f'{tool}_stars'].iloc[-1]
            ax2.annotate(f'Passes {tool}', 
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
    ax1.text(0.02, 0.98, box_text,
             transform=ax1.transAxes,
             fontsize=9,
             verticalalignment='top',
             horizontalalignment='left',
             bbox=props)

ax2.set_ylabel('GitHub Stars', color='black')
ax2.tick_params(axis='y', labelcolor='black')

# Set title and format date
plt.title('mise: Brew Rank vs GitHub Stars Over Time')
ax1.xaxis.set_major_formatter(DateFormatter('%Y-%m-%d'))
plt.xticks(rotation=45)

# Add legend
lines = line1 + line2 + line4 + line5
labels = [line.get_label() for line in lines]
ax1.legend(lines, labels, loc='center left')

# Adjust layout to prevent label cutoff
plt.tight_layout()

# Save the plot
plt.savefig('mise_stats.png', dpi=300, bbox_inches='tight')
