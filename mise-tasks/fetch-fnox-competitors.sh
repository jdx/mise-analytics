#!/usr/bin/env bash
set -exuo pipefail

DATE=$(date '+%Y-%m-%d')
OUTPUT_FILE="fnox-competitors.csv"

# Initialize CSV if it doesn't exist
if [ ! -f "$OUTPUT_FILE" ]; then
    echo "date,fnox_stars,sops_stars" > "$OUTPUT_FILE"
fi

# Fetch GitHub stars for fnox and its competitors
FNOX_STARS=$(curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
           "https://api.github.com/repos/jdx/fnox" | \
           jq '.stargazers_count')

SOPS_STARS=$(curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
           "https://api.github.com/repos/getsops/sops" | \
           jq '.stargazers_count')

# Append to CSV
echo "$DATE,$FNOX_STARS,$SOPS_STARS" >> "$OUTPUT_FILE"

# Deduplicate entries (keep only latest entry per day)
awk -F',' '!seen[$1]++' "$OUTPUT_FILE" > "/tmp/fnox-competitors-temp.csv" && mv "/tmp/fnox-competitors-temp.csv" "$OUTPUT_FILE"
