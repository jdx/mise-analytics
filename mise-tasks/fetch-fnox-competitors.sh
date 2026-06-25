#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DATE=$(date '+%Y-%m-%d')
OUTPUT_FILE="$REPO_ROOT/fnox-competitors.csv"

AUTH_ARGS=()
if [ -n "${GITHUB_TOKEN:-}" ]; then
    AUTH_ARGS=(-H "Authorization: Bearer $GITHUB_TOKEN")
fi

# Initialize CSV if it doesn't exist
if [ ! -f "$OUTPUT_FILE" ]; then
    echo "date,fnox_stars,sops_stars" > "$OUTPUT_FILE"
fi

fetch_stars() {
    curl -fsS "${AUTH_ARGS[@]}" "https://api.github.com/repos/$1" | \
        jq -er '.stargazers_count'
}

# Fetch GitHub stars for fnox and its competitors
FNOX_STARS=$(fetch_stars jdx/fnox)
SOPS_STARS=$(fetch_stars getsops/sops)

# Append to CSV
echo "$DATE,$FNOX_STARS,$SOPS_STARS" >> "$OUTPUT_FILE"

# Deduplicate entries (keep only latest entry per day)
TEMP_FILE="$(mktemp)"
awk -F',' '
    NR == 1 { print; next }
    {
        rows[$1] = $0
        if (!seen[$1]++) {
            dates[++date_count] = $1
        }
    }
    END {
        for (i = 1; i <= date_count; i++) {
            print rows[dates[i]]
        }
    }
' "$OUTPUT_FILE" > "$TEMP_FILE" && mv "$TEMP_FILE" "$OUTPUT_FILE"
