#!/usr/bin/env -S uv run
# /// script
# dependencies = ["pandas", "matplotlib", "scipy", "numpy"]
# ///

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
from datetime import datetime
from scipy import stats

df_comp = pd.read_csv('aube-competitors.csv')
df_comp['date'] = pd.to_datetime(df_comp['date'])

fig, ax = plt.subplots(figsize=(12, 6))


def calc_daily_avg(df, col_name, window_days=30):
    """Average stars/day over the most recent `window_days` of nonzero data."""
    data = df[df[col_name] > 0]
    if len(data) < 2:
        return 0
    cutoff = data['date'].max() - pd.Timedelta(days=window_days)
    recent = data[data['date'] >= cutoff]
    if len(recent) < 2:
        recent = data
    days = (recent['date'].iloc[-1] - recent['date'].iloc[0]).days
    if days == 0:
        return 0
    return (recent[col_name].iloc[-1] - recent[col_name].iloc[0]) / days


aube_avg = calc_daily_avg(df_comp, 'aube_stars')
aube_current = df_comp['aube_stars'].iloc[-1]

# (display name, csv column prefix, color)
competitors = {
    'vlt':        {'color': '#9B59B6'},
    'npm':        {'color': '#C0392B'},
    'pnpm':       {'color': '#F1C40F'},
    'yarn':       {'color': '#2980B9'},
    'yarn berry': {'color': '#16A085', 'col': 'berry_stars'},
    'bun':        {'color': '#E84393'},
    'deno':       {'color': '#27AE60'},
}

# Resolve column names + capture per-competitor data
active = {}
for name, info in competitors.items():
    col = info.get('col', f"{name}_stars")
    info['col'] = col
    data = df_comp[df_comp[col] > 0]
    if len(data) == 0:
        continue
    info['data'] = data
    info['avg'] = calc_daily_avg(df_comp, col)
    active[name] = info

# Plot aube
aube_color = '#E67E22'
aube_line = ax.plot(
    df_comp[df_comp['aube_stars'] > 0]['date'],
    df_comp[df_comp['aube_stars'] > 0]['aube_stars'],
    color=aube_color,
    linewidth=3,
    label=f'aube (+{aube_avg:.1f}/day)',
)

# Plot competitors
for name, info in active.items():
    info['line'] = ax.plot(
        info['data']['date'],
        info['data'][info['col']],
        color=info['color'],
        label=f'{name} (+{info["avg"]:.1f}/day)',
    )


def predict_crossing(df, col, days=30):
    cutoff = df['date'].max() - pd.Timedelta(days=days)
    recent = df[df['date'] >= cutoff].copy()
    if len(recent) < 2:
        return None
    x = (recent['date'] - recent['date'].min()).dt.days
    aube_slope, _, _, _, _ = stats.linregress(x, recent['aube_stars'])
    tool_slope, _, _, _, _ = stats.linregress(x, recent[col])
    if aube_slope <= tool_slope:
        return None
    aube_now = df['aube_stars'].iloc[-1]
    tool_now = df[col].iloc[-1]
    if aube_now >= tool_now:
        return datetime.now(), aube_slope - tool_slope
    daily_gain = aube_slope - tool_slope
    days_to_cross = (tool_now - aube_now) / daily_gain
    if days_to_cross < 0 or days_to_cross > 3650:
        return None
    return datetime.now() + pd.Timedelta(days=int(days_to_cross)), daily_gain


predictions = []
prediction_labels = {}
for name, info in active.items():
    # Skip prediction if aube has already surpassed this competitor
    if info['data'][info['col']].iloc[-1] <= aube_current:
        prediction_labels[name] = ' (already passed)'
        continue

    timeframes = [30, 90, 180]
    valid, gains = [], []
    for d in timeframes:
        result = predict_crossing(df_comp, info['col'], d)
        if result:
            valid.append(result[0])
            gains.append(result[1])
    if not valid:
        continue
    avg_dt = valid[0] + sum((d - valid[0] for d in valid[1:]), pd.Timedelta(0)) / len(valid)
    avg_gain = sum(gains) / len(gains)
    days_until = (avg_dt - datetime.now()).days
    date_str = avg_dt.strftime('%Y-%m-%d')

    prediction_labels[name] = f' (passes {date_str}, {days_until} days)'
    predictions.append(f'Will pass {name}: {date_str} ({days_until:,} days, +{avg_gain:.1f}/day)')

    # Only render in-chart markers for crossings within 2 years; far-out
    # predictions still appear in the text box.
    if 0 < days_until <= 730:
        ax.axvline(x=avg_dt, color=info['color'], linestyle=':', alpha=0.5)
        y_pos = df_comp[info['col']].iloc[-1]
        ax.annotate(
            f'Passes {name}',
            xy=(avg_dt, y_pos),
            xytext=(-50, 20),
            textcoords='offset points',
            color=info['color'],
            fontsize=8,
            arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=.2', color=info['color']),
        )

if predictions:
    box_text = '\n'.join(['Predictions:'] + predictions)
    ax.text(
        0.02, 0.98, box_text,
        transform=ax.transAxes,
        fontsize=9,
        verticalalignment='top',
        horizontalalignment='left',
        bbox=dict(boxstyle='round', facecolor='white', alpha=0.8, edgecolor='gray'),
    )

ax.set_ylabel('GitHub Stars', fontsize=12)
ax.set_xlabel('Date', fontsize=12)
ax.set_yscale('log')
ax.grid(True, which='both', alpha=0.3)
ax.set_xlim(df_comp['date'].min(), df_comp['date'].max() + pd.Timedelta(days=730))
plt.title('aube: GitHub Stars vs Package Manager Competitors', fontsize=14, fontweight='bold')
ax.xaxis.set_major_formatter(DateFormatter('%Y-%m-%d'))
plt.xticks(rotation=45)

# Update labels with prediction suffixes and rebuild legend
lines = aube_line
for name, info in active.items():
    label = f'{name} (+{info["avg"]:.1f}/day)' + prediction_labels.get(name, '')
    info['line'][0].set_label(label)
    lines = lines + info['line']
labels = [line.get_label() for line in lines]
ax.legend(lines, labels, loc='lower right', fontsize=8)

plt.tight_layout()
plt.savefig('charts/aube_stats.png', dpi=300, bbox_inches='tight')
