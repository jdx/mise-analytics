#!/usr/bin/env bash
set -exuo pipefail

DATE=$(date '+%Y-%m-%d')
OUTPUT_FILE="hk-competitors.csv"

# Initialize CSV if it doesn't exist
if [ ! -f "$OUTPUT_FILE" ]; then
    echo "date,hk_stars,precommit_stars,prek_stars,lefthook_stars" > "$OUTPUT_FILE"
fi

# Fetch GitHub stars for hk and its competitors
HK_STARS=$(curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
           "https://api.github.com/repos/jdx/hk" | \
           jq '.stargazers_count')

PRECOMMIT_STARS=$(curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
           "https://api.github.com/repos/pre-commit/pre-commit" | \
           jq '.stargazers_count')

PREK_STARS=$(curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
           "https://api.github.com/repos/j178/prek" | \
           jq '.stargazers_count')

LEFTHOOK_STARS=$(curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
           "https://api.github.com/repos/evilmartians/lefthook" | \
           jq '.stargazers_count')

# Append to CSV
echo "$DATE,$HK_STARS,$PRECOMMIT_STARS,$PREK_STARS,$LEFTHOOK_STARS" >> "$OUTPUT_FILE"

# Deduplicate entries (keep only latest entry per day)
awk -F',' '!seen[$1]++' "$OUTPUT_FILE" > "/tmp/hk-competitors-temp.csv" && mv "/tmp/hk-competitors-temp.csv" "$OUTPUT_FILE"
