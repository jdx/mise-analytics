#!/usr/bin/env -S uv run
# /// script
# dependencies = ["requests"]
# ///
import csv
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

DEFAULT_OWNER = "jdx"
CANONICAL_REPOS = {
    "endevco/aube": "jdx/aube",
    "endevco/pitchfork": "jdx/pitchfork",
}
REPO_ROOT = Path(__file__).resolve().parent.parent
REPOS_LIST_FILE = REPO_ROOT / "top-repos-list.txt"
OUTPUT_FILE = REPO_ROOT / "top-repos-downloads.csv"


def canonical_repo_name(owner, repo):
    canonical = CANONICAL_REPOS.get(f"{owner}/{repo}", f"{owner}/{repo}")
    canonical_owner, canonical_repo = canonical.split("/", 1)
    return canonical_repo if canonical_owner == DEFAULT_OWNER else canonical


def resolve_repo(entry):
    if "/" in entry:
        owner, repo = entry.split("/", 1)
        repo_name = canonical_repo_name(owner, repo)
    else:
        owner, repo, repo_name = DEFAULT_OWNER, entry, entry
    return owner, repo, repo_name


def read_tracked_repos():
    repos = []
    with open(REPOS_LIST_FILE) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            repos.append(resolve_repo(line))
    return repos


def fetch_total_downloads(session, owner, name):
    total = 0
    url = f"https://api.github.com/repos/{owner}/{name}/releases"
    params = {"per_page": 100}
    while url:
        resp = session.get(url, params=params, timeout=30)
        if resp.status_code == 404:
            return 0
        resp.raise_for_status()
        for release in resp.json():
            for asset in release.get("assets", []):
                total += asset.get("download_count", 0)
        url = resp.links.get("next", {}).get("url")
        params = None  # next URL already has per_page baked in
    return total


def main():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN env var required")

    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
    )

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    new_file = not OUTPUT_FILE.exists()

    rows = []
    for owner, name, repo_name in read_tracked_repos():
        try:
            total = fetch_total_downloads(session, owner, name)
        except Exception as e:
            print(f"error fetching {owner}/{name}: {e}", file=sys.stderr)
            continue
        print(f"{repo_name}: {total:,} downloads")
        rows.append((today, repo_name, total))

    with OUTPUT_FILE.open("a", newline="") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(["date", "repo_name", "release_downloads"])
        writer.writerows(rows)

    # Dedupe: keep last entry per (date, repo_name)
    seen = {}
    with OUTPUT_FILE.open() as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            seen[(row[0], row[1])] = row
    with OUTPUT_FILE.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for row in seen.values():
            writer.writerow(row)


if __name__ == "__main__":
    main()
