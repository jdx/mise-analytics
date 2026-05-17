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
        repo_series = repo_series.ffill()

        if repo_series.isna().all():
            continue

        deltas = repo_series.diff().fillna(0)
        observed_values = repo_series.dropna()
        growth = int(observed_values.iloc[-1] - observed_values.iloc[0])

        repo_data[repo] = (repo_series, deltas)
        growth_scores[repo] = growth

    if not repo_data:
        raise SystemExit("No repository data available to build table.")

    top_repos = [
        repo
        for repo, _ in sorted(
            growth_scores.items(), key=lambda item: (-item[1], item[0])
        )[:5]
    ]

    return dates, top_repos, repo_data, growth_scores


def format_table(dates, top_repos, repo_data) -> str:
    header_cells = ["Date"]
    for repo in top_repos:
        header_cells.append(repo)

    lines = ["| " + " | ".join(header_cells) + " |"]
    lines.append("| " + " | ".join(["---"] * len(header_cells)) + " |")
    previous_values = {repo: None for repo in top_repos}

    for date in dates:
        row = [date.strftime("%Y-%m-%d")]
        for repo in top_repos:
            series, _deltas = repo_data[repo]
            stars_value = series.loc[date]
            if pd.isna(stars_value):
                row.append("—")
            else:
                current_value = int(stars_value)
                previous_value = previous_values[repo]
                if previous_value is None:
                    row.append(f"{current_value:,d}")
                else:
                    delta_value = current_value - previous_value
                    row.append(f"{current_value:,d} ({delta_value:+d})")
                previous_values[repo] = current_value
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def predict_crossing(df_comp: pd.DataFrame, focal: str, tool: str, days: int = 90):
    focal_col = f"{focal}_stars"
    tool_col = f"{tool}_stars"
    if df_comp.empty or focal_col not in df_comp.columns or tool_col not in df_comp.columns:
        return None

    cutoff_date = df_comp["date"].max() - pd.Timedelta(days=days)
    recent_data = df_comp[df_comp["date"] >= cutoff_date].copy()

    if recent_data.empty:
        return None

    x = (recent_data["date"] - recent_data["date"].min()).dt.days
    focal_series = recent_data[focal_col].astype(float)
    tool_series = recent_data[tool_col].astype(float)

    if len(x.unique()) < 2 or focal_series.nunique() <= 1 or tool_series.nunique() <= 1:
        return None

    focal_slope, _, _, _, _ = stats.linregress(x, focal_series)
    tool_slope, _, _, _, _ = stats.linregress(x, tool_series)

    if focal_slope <= tool_slope:
        return None

    focal_current = df_comp[focal_col].iloc[-1]
    tool_current = df_comp[tool_col].iloc[-1]

    if focal_current >= tool_current:
        return datetime.now(UTC), focal_slope - tool_slope

    stars_diff = tool_current - focal_current
    daily_gain = focal_slope - tool_slope

    if daily_gain <= 0:
        return None

    days_to_cross = stars_diff / daily_gain

    if days_to_cross < 0 or days_to_cross > 3650:
        return None

    crossing_date = datetime.now(UTC) + timedelta(days=int(days_to_cross))
    return crossing_date, daily_gain


def collect_crossovers(df_comp: pd.DataFrame, focal: str) -> list[dict]:
    focal_col = f"{focal}_stars"
    if df_comp.empty or focal_col not in df_comp.columns:
        return []

    df_comp = df_comp.copy()
    df_comp["date"] = pd.to_datetime(df_comp["date"], errors="coerce")
    df_comp = df_comp.dropna(subset=["date"])

    competitor_cols = [
        col
        for col in df_comp.columns
        if col.endswith("_stars") and col != focal_col
    ]
    competitors = [col.replace("_stars", "") for col in competitor_cols]

    predictions = []

    for comp in competitors:
        timeframes = [30, 90, 180]
        valid_predictions = []
        daily_gains = []

        for days in timeframes:
            result = predict_crossing(df_comp, focal, comp, days=days)
            if result:
                cross_date, daily_gain = result
                valid_predictions.append(cross_date)
                daily_gains.append(daily_gain)

        if not valid_predictions:
            continue

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
                "project": focal,
                "competitor": comp,
                "cross_date": avg_date,
                "days_until": days_until,
                "daily_gain": avg_gain,
            }
        )

    return predictions


def build_upcoming_crossovers(predictions: list[dict]) -> str:
    if not predictions:
        return "No upcoming crossovers predicted."

    predictions = sorted(predictions, key=lambda item: item["cross_date"])

    lines = [
        "| Project | Competitor | Expected Crossover | Days Until | lead gain (stars/day) |",
        "| --- | --- | --- | --- | --- |",
    ]

    for pred in predictions:
        lines.append(
            "| {project} | {competitor} | {date} | {days} | {gain:.1f} |".format(
                project=pred["project"],
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
    predictions = []
    for csv_path, focal in [
        ("competitors.csv", "mise"),
        ("aube-competitors.csv", "aube"),
    ]:
        path = Path(csv_path)
        if not path.exists():
            continue
        predictions.extend(collect_crossovers(pd.read_csv(path), focal))
    crossovers = build_upcoming_crossovers(predictions)
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
