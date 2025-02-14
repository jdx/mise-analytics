#!/usr/bin/env bash
set -exuo pipefail

DATE=$(date '+%Y-%m-%d')

# Fetch GitHub stars for competitors
MISE_STARS=$(curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
       https://api.github.com/repos/mise-app/mise | \
       jq '.stargazers_count')

NIX_STARS=$(curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
       https://api.github.com/repos/NixOS/nix | \
       jq '.stargazers_count')

ASDF_STARS=$(curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
       https://api.github.com/repos/asdf-vm/asdf | \
       jq '.stargazers_count')

# Create or append to competitors.csv
if [ ! -f competitors.csv ]; then
    echo "date,mise_stars,nix_stars,asdf_stars" > competitors.csv
fi

echo "$DATE,$MISE_STARS,$NIX_STARS,$ASDF_STARS" >> competitors.csv
cat competitors.csv
uniq -w 10 competitors.csv > /tmp/competitors.csv && mv /tmp/competitors.csv competitors.csv 
