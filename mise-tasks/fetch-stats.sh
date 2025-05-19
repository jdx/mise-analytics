#!/usr/bin/env bash
set -exuo pipefail

DATE=$(date '+%Y-%m-%d')

# Function to fetch and process formula stats
fetch_formula_stats() {
    local formula=$1
    local output_file=$2

    # Fetch Homebrew analytics
    curl https://formulae.brew.sh/api/analytics/install-on-request/30d.json | \
    jq -r ".items[] | select(.formula == \"$formula\")" | \
    tee "/tmp/${formula}_analytics.json"

    # Fetch GitHub stars
    STARS=$(curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
           "https://api.github.com/repos/jdx/$formula" | \
           jq '.stargazers_count')

    # Convert to CSV format and append to history file
    echo "$DATE,$(jq -r '[.number, (.count | gsub(","; "")), .percent] | @csv' "/tmp/${formula}_analytics.json" | tr -d '"'),$STARS" >> "$output_file"
    uniq -w 10 "$output_file" > "/tmp/${formula}.csv" && mv "/tmp/${formula}.csv" "$output_file"

    # Create a diff CSV showing daily changes
    echo "date,rank_change,install_change,star_change" > "${formula}-diff.csv"
    awk -F',' 'NR>1{
        if (NR>2) {
            rank_change=prev_rank-$2
            install_change=$3-prev_installs
            star_change=$5-prev_stars
            print prev_date "," rank_change "," install_change "," star_change
        }
        prev_date=$1
        prev_rank=$2
        prev_installs=$3
        prev_stars=$5
    }' "$output_file" >> "${formula}-diff.csv"
}

# Process stats for mise
fetch_formula_stats "mise" "mise.csv"

# Process stats for hk
fetch_formula_stats "hk" "hk.csv"
