#!/usr/bin/env bash
set -exuo pipefail

DATE=$(date '+%Y-%m-%d')

# Fetch Homebrew analytics
curl https://formulae.brew.sh/api/analytics/install-on-request/30d.json | \
jq -r '.items[] | select(.formula == "mise")' | \
tee /tmp/analytics.json

# Fetch GitHub stars
STARS=$(curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
       https://api.github.com/repos/jdx/mise | \
       jq '.stargazers_count')

# Convert to CSV format and append to history file
echo "$DATE,$(jq -r '[.number, (.count | gsub(","; "")), .percent] | @csv' /tmp/analytics.json | tr -d '"'),$STARS" >> mise.csv
cat mise.csv
uniq -w 10 mise.csv > /tmp/mise.csv && mv /tmp/mise.csv mise.csv 

# Create a diff CSV showing daily changes
echo "date,rank_change,install_change,star_change" > mise-diff.csv
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
}' mise.csv >> mise-diff.csv

cat mise-diff.csv 
