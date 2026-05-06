#!/usr/bin/env -S uv run
# /// script
# dependencies = ["pandas", "matplotlib", "numpy"]
# ///
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.dates import DateFormatter

DEFAULT_OWNER = "jdx"
REPO_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = REPO_ROOT / "top-repos-downloads.csv"
LIST_PATH = REPO_ROOT / "top-repos-list.txt"
OUT_PATH = REPO_ROOT / "charts" / "top_repos_downloads.png"
ROLLING_WINDOW = 7


def read_tracked_repo_names():
    names = []
    with open(LIST_PATH) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "/" in line:
                owner, repo = line.split("/", 1)
                names.append(repo if owner == DEFAULT_OWNER else line)
            else:
                names.append(line)
    return names


def velocity_for_repo(repo_data: pd.DataFrame) -> pd.DataFrame:
    """Daily delta with rolling mean. Drops the first row (no prior to diff against)."""
    s = repo_data.sort_values("date").set_index("date")["release_downloads"]
    daily = s.diff().dropna()
    if daily.empty:
        return pd.DataFrame()
    rolled = daily.rolling(window=ROLLING_WINDOW, min_periods=1).mean()
    return pd.DataFrame({"date": rolled.index, "velocity": rolled.values})


def plot_panel(ax, repos, df, colors, title):
    plotted_any = False
    for idx, repo in enumerate(repos):
        repo_data = df[df["repo_name"] == repo]
        v = velocity_for_repo(repo_data)
        if v.empty:
            continue
        latest = v["velocity"].iloc[-1]
        ax.plot(
            v["date"],
            v["velocity"],
            color=colors[idx % len(colors)],
            label=f"{repo} (~{latest:,.0f}/day)",
            marker="o",
            markersize=3,
            linewidth=2,
        )
        plotted_any = True

    ax.set_ylabel("Downloads / day", fontsize=11)
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.grid(True, alpha=0.3)
    if plotted_any:
        ax.xaxis.set_major_formatter(DateFormatter("%Y-%m-%d"))
        ax.legend(loc="upper left", ncol=2, fontsize=8)
    else:
        ax.set_xticks([])
        ax.set_yticks([])
        ax.text(
            0.5,
            0.5,
            "Collecting data — chart will populate after a few days",
            transform=ax.transAxes,
            ha="center",
            va="center",
            fontsize=11,
            color="gray",
        )


def main():
    df = pd.read_csv(CSV_PATH)
    df["date"] = pd.to_datetime(df["date"])
    df["release_downloads"] = pd.to_numeric(df["release_downloads"], errors="coerce")
    df = df.dropna(subset=["release_downloads"])

    two_years_ago = datetime.now() - timedelta(days=730)
    df = df[df["date"] >= two_years_ago]

    tracked = read_tracked_repo_names()
    df = df[df["repo_name"].isin(tracked)]

    others = [r for r in tracked if r != "mise"]
    others_latest = (
        df[df["repo_name"].isin(others)]
        .loc[lambda d: d.groupby("repo_name")["date"].idxmax()]
        .sort_values("release_downloads", ascending=False)["repo_name"]
        .tolist()
    )

    fig, (ax_mise, ax_others) = plt.subplots(2, 1, figsize=(14, 10))

    mise_colors = ["#1f77b4"]
    other_colors = plt.cm.tab10(np.linspace(0, 1, 10))

    plot_panel(ax_mise, ["mise"], df, mise_colors, "mise — Release Downloads / Day")
    plot_panel(
        ax_others,
        others_latest,
        df,
        other_colors,
        "Other Top Repos — Release Downloads / Day",
    )

    ax_others.set_xlabel("Date", fontsize=11)
    for ax in (ax_mise, ax_others):
        if ax.get_xticks().size:
            plt.setp(ax.get_xticklabels(), rotation=45)

    plt.tight_layout()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(OUT_PATH, dpi=300, bbox_inches="tight")
    print(f"Saved visualization to {OUT_PATH}")


if __name__ == "__main__":
    main()
