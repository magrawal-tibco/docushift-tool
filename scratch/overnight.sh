#!/usr/bin/env bash
# Close-out plan, lane A (docs/closeout-plan.md): one unattended batch of runs, one after another.
#
# Usage: scratch/overnight.sh <batch-file>
#   <batch-file>: one `docushift` argument list per line (blank lines and # comments ignored),
#   usually one product per line so each process is short and gives its memory back.
#   scratch/overnight_batch.py writes these files.
#
# Output, next to the batch file: <name>.summary (one line per run, then DONE) and <name>.logs/NNN.log.
# - A failure does not stop the batch.
# - Re-running the same batch file skips lines already finished (resume after a crash or reboot).
# - Before each run, if the machine has under LOW_MB of memory available, it waits (up to WAIT_MAX
#   minutes) and says so in the summary: overnight runs have hit low memory before.
# - Only one batch at a time: every run writes versions.csv and state.db; a lock refuses a second one.
# Needs no sign-in: the runs read the public staging site and docs.tibco.com only.
set -u
cd "$(dirname "$0")/.." || exit 2
batch=$1
name=${batch%.*}
summary=$name.summary
logs=$name.logs
LOW_MB=${LOW_MB:-3000}
WAIT_MAX=${WAIT_MAX:-30}
lock=cache/overnight/.lock
mkdir -p "$logs" cache/overnight
if ! mkdir "$lock" 2>/dev/null; then
  echo "$(date '+%F %T') refused: another batch is running ($(cat "$lock/name" 2>/dev/null)); remove $lock if stale" >> "$summary"
  exit 3
fi
echo "$batch" > "$lock/name"
trap 'rm -rf "$lock"' EXIT

avail_mb() { awk '/^MemAvailable:|^MemFree:/{print int($2/1024); exit}' /proc/meminfo; }

echo "start $(date '+%F %T')  $(avail_mb) MB available" >> "$summary"
n=0
while IFS= read -r args || [ -n "$args" ]; do
  args=${args%$'\r'}
  case $args in ''|'#'*) continue ;; esac
  n=$((n + 1))
  if grep -qF "  docushift $args" "$summary" && grep -F "  docushift $args" "$summary" | grep -qv FAILED; then
    continue                                    # finished in an earlier attempt
  fi
  waited=0
  while [ "$(avail_mb)" -lt "$LOW_MB" ] && [ "$waited" -lt "$WAIT_MAX" ]; do
    sleep 60; waited=$((waited + 1))
  done
  [ "$waited" -gt 0 ] && echo "     low memory: waited $waited min, now $(avail_mb) MB" >> "$summary"
  log=$(printf '%s/%03d.log' "$logs" "$n")
  start=$(date +%s)
  echo "\$ docushift $args" > "$log"
  # shellcheck disable=SC2086  # args is a word list by design
  .venv/Scripts/docushift $args >> "$log" 2>&1
  code=$?
  mins=$(( ($(date +%s) - start) / 60 ))
  # verify exits 1 when a version has an unexplained finding: a result, not a crash.
  case $code in 0) what=ok ;; 1) what="ok-findings" ;; *) what="FAILED" ;; esac
  printf '%03d %-11s %4s min  exit %-3s %5s MB  docushift %s\n' "$n" "$what" "$mins" "$code" "$(avail_mb)" "$args" >> "$summary"
done < "$batch"
echo "DONE $(date '+%F %T')" >> "$summary"
