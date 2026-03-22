# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Analytics pipeline that tracks GitHub stars and Homebrew rankings for jdx's open-source projects (mise, hk, fnox). Fetches daily stats, computes growth trends via linear regression, generates charts, and auto-updates the README with predictions (e.g., when mise will surpass asdf in stars).

## Tech Stack

- Python 3.13, managed with `uv`
- Scripts run via `mise` task runner (tasks live in `mise-tasks/`)
- Data stored in CSV files at the repo root
- Charts generated as PNGs in `charts/`

## Running Tasks

All tasks are defined as executable scripts in `mise-tasks/` and run via mise:

```sh
mise run fetch-stats          # Fetch Homebrew analytics + GitHub stars
mise run fetch-competitors    # Fetch mise vs asdf comparison data
mise run fetch-hk-competitors # Fetch hk competitor data
mise run fetch-top-repos      # Fetch top 10 jdx repos
mise run plot-stats           # Generate mise vs competitors chart
mise run plot-hk-stats        # Generate hk chart
mise run plot-fnox-stats      # Generate fnox chart
mise run plot-top-repos       # Generate top repos chart
mise run plot-brew-rankings   # Generate Homebrew rankings chart
mise run plot-mise-brew-rank  # Generate mise Homebrew rank chart
mise run generate-fastest-growing  # Update README with stats/predictions
```

There are no tests or linting configured.

## Architecture

Three-stage pipeline, automated daily via GitHub Actions (`brew.yml` at 8 AM UTC):

1. **Fetch** — Shell scripts call GitHub API and Homebrew analytics; Python async scripts (`aiohttp`) fetch stargazer history with rate-limit handling. Requires `GITHUB_TOKEN` env var.
2. **Plot** — Python scripts read CSVs with `pandas`, compute trends with `scipy` linear regression (30/90/180-day windows), and generate `matplotlib` charts.
3. **Report** — `generate-fastest-growing.py` updates README sections bounded by `<!-- START/END -->` HTML comment markers. `generate-commit-message.py` creates the auto-commit message.

## Key Conventions

- Scripts use `#!/usr/bin/env -S uv run` shebangs with inline dependency declarations
- CSV files are the sole data store — no database
- README sections are programmatically updated via regex between HTML comment markers
- Predictions cap at 10 years (3650 days) to prevent overflow
- Commit messages follow the format: `update stats: mise: X,XXX (+Y), fnox: Z,ZZZ (+W), hk: A,AAA (+B)`
