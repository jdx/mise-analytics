#!/usr/bin/env bash
set -exuo pipefail

DATE=$(date '+%Y-%m-%d')

# Fetch GitHub stars for competitors
MISE_STARS=$(curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
       https://api.github.com/repos/jdx/mise | \
       jq '.stargazers_count')

ASDF_STARS=$(curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
       https://api.github.com/repos/asdf-vm/asdf | \
       jq '.stargazers_count')

HK_STARS=$(curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
       https://api.github.com/repos/jdx/hk | \
       jq '.stargazers_count')

NIXPKGS_STARS=$(curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
       https://api.github.com/repos/NixOS/nixpkgs | \
       jq '.stargazers_count')

# Create or append to competitors.csv
if [ ! -f competitors.csv ]; then
    echo "date,mise_stars,asdf_stars,hk_stars,nixpkgs_stars" > competitors.csv
fi

echo "$DATE,$MISE_STARS,$ASDF_STARS,$HK_STARS,$NIXPKGS_STARS" >> competitors.csv
uniq=uniq
if command -v guniq &> /dev/null; then
    uniq=guniq
fi
"$uniq" -w 10 competitors.csv > /tmp/competitors.csv && mv /tmp/competitors.csv competitors.csv 
