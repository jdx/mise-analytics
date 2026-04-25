#!/usr/bin/env bash
set -exuo pipefail

DATE=$(date '+%Y-%m-%d')
OUTPUT_FILE="aube-competitors.csv"

# Initialize CSV if it doesn't exist
if [ ! -f "$OUTPUT_FILE" ]; then
    echo "date,aube_stars,vlt_stars,npm_stars,pnpm_stars,yarn_stars,berry_stars,bun_stars,deno_stars" > "$OUTPUT_FILE"
fi

fetch_stars() {
    curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
        "https://api.github.com/repos/$1" | jq '.stargazers_count'
}

AUBE_STARS=$(fetch_stars endevco/aube)
VLT_STARS=$(fetch_stars vltpkg/vltpkg)
NPM_STARS=$(fetch_stars npm/cli)
PNPM_STARS=$(fetch_stars pnpm/pnpm)
YARN_STARS=$(fetch_stars yarnpkg/yarn)
BERRY_STARS=$(fetch_stars yarnpkg/berry)
BUN_STARS=$(fetch_stars oven-sh/bun)
DENO_STARS=$(fetch_stars denoland/deno)

echo "$DATE,$AUBE_STARS,$VLT_STARS,$NPM_STARS,$PNPM_STARS,$YARN_STARS,$BERRY_STARS,$BUN_STARS,$DENO_STARS" >> "$OUTPUT_FILE"

# Deduplicate entries (keep only latest entry per day)
awk -F',' '!seen[$1]++' "$OUTPUT_FILE" > "/tmp/aube-competitors-temp.csv" && mv "/tmp/aube-competitors-temp.csv" "$OUTPUT_FILE"
