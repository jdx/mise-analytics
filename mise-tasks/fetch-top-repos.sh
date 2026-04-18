#!/usr/bin/env bash
set -exuo pipefail

DATE=$(date '+%Y-%m-%d')
GITHUB_USER="jdx"
OUTPUT_FILE="top-repos.csv"
REPOS_LIST_FILE="top-repos-list.txt"

# Additional repos to always include, outside of jdx's top 10
# Use the form "owner/repo"
PINNED_REPOS=(
    "endevco/aube"
)

# Initialize CSV if it doesn't exist
if [ ! -f "$OUTPUT_FILE" ]; then
    echo "date,repo_name,github_stars,brew_rank,brew_installs,brew_pct" > "$OUTPUT_FILE"
fi

# Get current top repos from GitHub, filtering out archived and old projects
ALL_REPOS=$(curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
    "https://api.github.com/users/$GITHUB_USER/repos?per_page=100&sort=updated")

# Filter: exclude archived repos, forks, sample projects, and those not updated in >1 year
# Calculate cutoff date as 1 year ago from today
CUTOFF_DATE=$(date -u -v-1y '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date -u -d '1 year ago' '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || echo "2024-10-26T00:00:00Z")
CURRENT_TOP_10=$(echo "$ALL_REPOS" | jq -r --arg cutoff "$CUTOFF_DATE" '
    sort_by(-.stargazers_count) |
    .[] |
    select(
        .archived == false and
        .fork == false and
        .pushed_at > $cutoff and
        (.name | test("sample|demo|example"; "i") | not)
    ) |
    .name
' | head -10)

# Replace the entire repos list with current top 10 plus any pinned repos
echo "# Top repos list - automatically managed" > "$REPOS_LIST_FILE"
echo "# This list contains the current top 10 active repos (refreshed regularly)" >> "$REPOS_LIST_FILE"
echo "# Filters: excludes archived repos, forks, sample/demo projects, and repos not updated in >1 year" >> "$REPOS_LIST_FILE"
echo "# Entries may be either \"repo\" (assumed owned by jdx) or \"owner/repo\"" >> "$REPOS_LIST_FILE"
for repo in $CURRENT_TOP_10; do
    echo "$repo" >> "$REPOS_LIST_FILE"
done
for repo in "${PINNED_REPOS[@]}"; do
    echo "$repo" >> "$REPOS_LIST_FILE"
done

# Use current top 10 plus pinned for processing
TRACKED_REPOS="$CURRENT_TOP_10 ${PINNED_REPOS[*]}"

# Fetch Homebrew analytics data once
BREW_DATA=$(curl -s https://formulae.brew.sh/api/analytics/install-on-request/30d.json)

# Process each tracked repo
for entry in $TRACKED_REPOS; do
    # Skip empty lines
    [ -z "$entry" ] && continue

    # Support "owner/repo" entries; default owner to $GITHUB_USER otherwise
    if [[ "$entry" == */* ]]; then
        owner="${entry%%/*}"
        repo="${entry##*/}"
    else
        owner="$GITHUB_USER"
        repo="$entry"
    fi

    # For repos outside the default owner, record as "owner/repo" in the CSV
    if [ "$owner" = "$GITHUB_USER" ]; then
        repo_name="$repo"
    else
        repo_name="$owner/$repo"
    fi

    # Get GitHub stars
    STARS=$(curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
           "https://api.github.com/repos/$owner/$repo" | \
           jq '.stargazers_count')

    # Check if repo exists in Homebrew
    BREW_STATS=$(echo "$BREW_DATA" | jq -r ".items[] | select(.formula == \"$repo\")")

    if [ -n "$BREW_STATS" ]; then
        # Extract Homebrew stats
        BREW_RANK=$(echo "$BREW_STATS" | jq -r '.number')
        BREW_INSTALLS=$(echo "$BREW_STATS" | jq -r '.count' | tr -d ',')
        BREW_PCT=$(echo "$BREW_STATS" | jq -r '.percent')
    else
        # Not in Homebrew
        BREW_RANK=""
        BREW_INSTALLS=""
        BREW_PCT=""
    fi

    # Append to CSV
    echo "$DATE,$repo_name,$STARS,$BREW_RANK,$BREW_INSTALLS,$BREW_PCT" >> "$OUTPUT_FILE"
done

# Deduplicate entries (keep only latest entry per day per repo)
awk -F',' '!seen[$1,$2]++' "$OUTPUT_FILE" > "/tmp/top-repos-temp.csv" && mv "/tmp/top-repos-temp.csv" "$OUTPUT_FILE"
