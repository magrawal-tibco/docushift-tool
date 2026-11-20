#!/usr/bin/env bash
# Read-only survey for scheduling content-fix -> wip PRs (closeout plan D1).
# Fetches each TIBCO/ibi repo and reports, per repo: commits content-fix is ahead
# of wip, commits wip has that content-fix lacks (needs a real merge), local
# commits not pushed, files changed and version folders touched (= builds queued).
#   scratch/merge_survey.sh > cache/merge-survey.csv
set -u
echo "repo,ahead,wip_only,local_unpushed,files,versions,products,last_cf_commit"
for repo in /c/github/tibco-docs-aem/en-us-tib-* /c/github/ibi-docs-aem/en-us-ibi-*; do
  [ -d "$repo/.git" ] || continue
  name=$(basename "$repo")
  git -C "$repo" fetch -q origin 2>/dev/null || { echo "$name,FETCH_FAIL,,,,,,"; continue; }
  git -C "$repo" rev-parse -q --verify origin/content-fix >/dev/null || { echo "$name,NO_CF,,,,,,"; continue; }
  git -C "$repo" rev-parse -q --verify origin/wip >/dev/null || { echo "$name,NO_WIP,,,,,,"; continue; }
  ahead=$(git -C "$repo" rev-list --count origin/wip..origin/content-fix)
  wiponly=$(git -C "$repo" rev-list --count origin/content-fix..origin/wip)
  unpushed=$(git -C "$repo" rev-list --count origin/content-fix..content-fix 2>/dev/null || echo NA)
  diff=$(git -C "$repo" diff --name-only origin/wip...origin/content-fix)
  files=$(printf '%s' "$diff" | grep -c . || true)
  versions=$(printf '%s\n' "$diff" | awk -F/ 'NF>=5{print $1"/"$2"/"$3"/"$4}' | sort -u | grep -c . || true)
  products=$(printf '%s\n' "$diff" | awk -F/ 'NF>=3{print $2}' | sort -u | tr '\n' ' ' | sed 's/ $//')
  last=$(git -C "$repo" log -1 --format=%cs origin/content-fix)
  echo "$name,$ahead,$wiponly,$unpushed,$files,$versions,\"$products\",$last"
done
