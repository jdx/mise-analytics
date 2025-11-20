#!/usr/bin/env -S uv run

from datetime import UTC, datetime, timedelta
from pathlib import Path
import re

import pandas as pd
from scipy import stats


README_PATH = Path("README.md")
START_MARKER = "<!-- START fastest-growing -->"
END_MARKER = "<!-- END fastest-growing -->"
SECTION_HEADER = "## Fastest Growing jdx Repos (30 Days)"
COMP_SECTION_HEADER = "## Upcoming Crossovers"
COMP_START_MARKER = "<!-- START upcoming-crossovers -->"
COMP_END_MARKER = "<!-- END upcoming-crossovers -->"


def load_repo_history(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    if df.empty:
        raise SystemExit("top-repos.csv is empty; run fetch-top-repos first.")

    if "date" not in df or "repo_name" not in df or "github_stars" not in df:
        raise SystemExit("top-repos.csv is missing required columns.")

    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    df = df.dropna(subset=["date", "repo_name"])
    df["github_stars"] = pd.to_numeric(df["github_stars"], errors="coerce")
    df = df.dropna(subset=["github_stars"])
    df["github_stars"] = df["github_stars"].astype(int)

    return df


def build_repo_windows(df: pd.DataFrame):
    latest_date = df["date"].max()
    if pd.isna(latest_date):
        raise SystemExit("Unable to determine latest date in top-repos.csv.")

    earliest_needed = latest_date - timedelta(days=29)
    window_start = max(earliest_needed, df["date"].min())
    dates = pd.date_range(start=window_start, end=latest_date, freq="D")

    repo_data = {}
    growth_scores = {}

    for repo in sorted(df["repo_name"].unique()):
        repo_series = (
            df.loc[df["repo_name"] == repo, ["date", "github_stars"]]
            .set_index("date")
            .sort_index()["github_stars"]
        )

        if repo_series.empty:
            continue

        repo_series = repo_series.reindex(dates)
        repo_series = repo_series.ffill().bfill()

        if repo_series.isna().all():
            continue

        repo_series = repo_series.astype(int)
        deltas = repo_series.diff().fillna(0).astype(int)
        growth = int(repo_series.iloc[-1] - repo_series.iloc[0])

        repo_data[repo] = (repo_series, deltas)
        growth_scores[repo] = growth

    if not repo_data:
        raise SystemExit("No repository data available to build table.")

    top_repos = [
        repo
        for repo, _ in sorted(
            growth_scores.items(), key=lambda item: (-item[1], item[0])
        )[:3]
    ]

    return dates, top_repos, repo_data, growth_scores


def format_table(dates, top_repos, repo_data) -> str:
    header_cells = ["Date"]
    for repo in top_repos:
        header_cells.append(repo)

    lines = ["| " + " | ".join(header_cells) + " |"]
    lines.append("| " + " | ".join(["---"] * len(header_cells)) + " |")

    for date in dates:
        row = [date.strftime("%Y-%m-%d")]
        for repo in top_repos:
            series, deltas = repo_data[repo]
            stars_value = series.loc[date]
            delta_value = deltas.loc[date]
            row.append(f"{stars_value:,d} ({delta_value:+d})")
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def predict_crossing(df_comp: pd.DataFrame, tool: str, days: int = 90):
    if df_comp.empty or f"{tool}_stars" not in df_comp.columns:
        return None

    cutoff_date = df_comp["date"].max() - pd.Timedelta(days=days)
    recent_data = df_comp[df_comp["date"] >= cutoff_date].copy()

    if recent_data.empty:
        return None

    x = (recent_data["date"] - recent_data["date"].min()).dt.days
    mise_series = recent_data["mise_stars"].astype(float)
    tool_series = recent_data[f"{tool}_stars"].astype(float)

    if len(x.unique()) < 2 or mise_series.nunique() <= 1 or tool_series.nunique() <= 1:
        return None

    mise_slope, _, _, _, _ = stats.linregress(x, mise_series)
    tool_slope, _, _, _, _ = stats.linregress(x, tool_series)

    if mise_slope <= tool_slope:
        return None

    mise_current = df_comp["mise_stars"].iloc[-1]
    tool_current = df_comp[f"{tool}_stars"].iloc[-1]

    if mise_current >= tool_current:
        return datetime.now(UTC), mise_slope - tool_slope

    stars_diff = tool_current - mise_current
    daily_gain = mise_slope - tool_slope

    if daily_gain <= 0:
        return None

    days_to_cross = stars_diff / daily_gain

    if days_to_cross < 0 or days_to_cross > 3650:
        return None

    crossing_date = datetime.now(UTC) + timedelta(days=int(days_to_cross))
    return crossing_date, daily_gain


def build_upcoming_crossovers(df_comp: pd.DataFrame) -> str:
    if df_comp.empty or "mise_stars" not in df_comp.columns:
        return "No competitor data available."

    df_comp = df_comp.copy()
    df_comp["date"] = pd.to_datetime(df_comp["date"], errors="coerce")
    df_comp = df_comp.dropna(subset=["date"])

    competitor_cols = [
        col
        for col in df_comp.columns
        if col.endswith("_stars") and col not in {"mise_stars"}
    ]
    competitors = [col.replace("_stars", "") for col in competitor_cols]

    predictions = []

    for comp in competitors:
        # Calculate predictions for multiple timeframes like the chart does
        timeframes = [30, 90, 180]
        valid_predictions = []
        daily_gains = []

        for days in timeframes:
            result = predict_crossing(df_comp, comp, days=days)
            if result:
                cross_date, daily_gain = result
                valid_predictions.append(cross_date)
                daily_gains.append(daily_gain)

        if not valid_predictions:
            continue

        # Calculate average prediction
        total_timedelta = sum(
            (d - valid_predictions[0] for d in valid_predictions[1:]),
            timedelta(0)
        )
        avg_timedelta = total_timedelta / len(valid_predictions)
        avg_date = valid_predictions[0] + avg_timedelta
        avg_gain = sum(daily_gains) / len(daily_gains)
        days_until = max((avg_date - datetime.now(UTC)).days, 0)

        if avg_date < datetime.now(UTC):
            continue

        predictions.append(
            {
                "competitor": comp,
                "cross_date": avg_date,
                "days_until": days_until,
                "daily_gain": avg_gain,
            }
        )

    if not predictions:
        return "No upcoming crossovers predicted."

    predictions.sort(key=lambda item: item["cross_date"])

    lines = [
        "| Competitor | Expected Crossover | Days Until | mise lead gain (stars/day) |",
        "| --- | --- | --- | --- |",
    ]

    for pred in predictions[:5]:
        lines.append(
            "| {competitor} | {date} | {days} | {gain:.1f} |".format(
                competitor=pred["competitor"],
                date=pred["cross_date"].strftime("%Y-%m-%d"),
                days=pred["days_until"],
                gain=pred["daily_gain"]
            )
        )

    return "\n".join(lines)


def build_sections(
    dates,
    top_repos,
    repo_data,
    growth_scores,
    crossovers_section: str,
) -> tuple[str, str]:
    table = format_table(dates, top_repos, repo_data)
    summary_lines = [
        f"- `{repo}` grew by {growth_scores[repo]:+,d} stars"
        for repo in top_repos
    ]
    summary_text = "\n".join(summary_lines)

    cross_section_lines = [
        COMP_SECTION_HEADER,
        "",
        COMP_START_MARKER,
        "",
        crossovers_section,
        "",
        COMP_END_MARKER,
        "",
    ]

    fastest_section_lines = [
        SECTION_HEADER,
        "",
        START_MARKER,
        "",
        f"Data window: {dates[0].strftime('%Y-%m-%d')} → {dates[-1].strftime('%Y-%m-%d')} (UTC)",
        "",
        table,
        "",
        summary_text,
        "",
        END_MARKER,
        "",
    ]

    return "\n".join(cross_section_lines), "\n".join(fastest_section_lines)


def update_readme(crossover_section: str, fastest_section: str) -> None:
    readme_text = README_PATH.read_text(encoding="utf-8")

    if not readme_text.endswith("\n"):
        readme_text += "\n"

    title_line, sep, remainder = readme_text.partition("\n")

    # Remove old sections
    pattern = re.compile(
        r"\n?## Upcoming Crossovers[\s\S]*?<!-- END upcoming-crossovers -->\s*",
        re.DOTALL,
    )
    remainder = pattern.sub("\n", remainder)
    pattern = re.compile(
        r"\n?## Fastest Growing jdx Repos \(30 Days\)[\s\S]*?<!-- END fastest-growing -->\s*",
        re.DOTALL,
    )
    remainder = pattern.sub("\n", remainder)

    remainder = remainder.lstrip("\n")

    crossover_block = crossover_section.strip()
    fastest_block = fastest_section.strip()

    pieces = [title_line.strip()]
    if crossover_block:
        pieces.append(crossover_block)
    if remainder:
        pieces.append(remainder.rstrip("\n"))
    if fastest_block:
        pieces.append(fastest_block)

    new_text = "\n\n".join(pieces).strip("\n") + "\n"
    README_PATH.write_text(new_text, encoding="utf-8")


def main() -> None:
    df = load_repo_history(Path("top-repos.csv"))
    competitors_df = pd.read_csv("competitors.csv")
    crossovers = build_upcoming_crossovers(competitors_df)
    dates, top_repos, repo_data, growth_scores = build_repo_windows(df)
    crossover_section, fastest_section = build_sections(
        dates, top_repos, repo_data, growth_scores, crossovers
    )
    update_readme(crossover_section, fastest_section)
    print(
        "Updated README with fastest growing repos: "
        + ", ".join(f"{repo} (+{growth_scores[repo]:,d})" for repo in top_repos)
    )


if __name__ == "__main__":
    main()
