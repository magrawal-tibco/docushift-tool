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
# - Up to SLOTS batches at once (default 3), each holding a lock directory cache/overnight/.lock1..N;
#   a batch started by the older one-slot script (cache/overnight/.lock) counts as one. The same
#   batch file twice is refused. Runs at once are safe: `docushift` saves versions.csv under a lock
#   and keeps the other runs' rows, and a state.db write waits for the other writer (2026-11-14).
# Needs no sign-in: the runs read the public staging site and docs.tibco.com only.
#
# The script is one block, read whole before it starts, so editing this file (a merge, a checkout)
# cannot change a batch that is already running.
{
set -u
cd "$(dirname "$0")/.." || exit 2
batch=$1
name=${batch%.*}
summary=$name.summary
logs=$name.logs
LOW_MB=${LOW_MB:-3000}
WAIT_MAX=${WAIT_MAX:-30}
SLOTS=${SLOTS:-3}
locks=cache/overnight
mkdir -p "$logs" "$locks"

held=()
for dir in "$locks/.lock" "$locks"/.lock[0-9]*; do
  [ -d "$dir" ] && held+=("$dir")
done
for dir in ${held[@]+"${held[@]}"}; do
  if [ "$(cat "$dir/name" 2>/dev/null)" = "$batch" ]; then
    echo "$(date '+%F %T') refused: this batch is already running ($dir); remove it if stale" >> "$summary"
    exit 3
  fi
done
free=$SLOTS
[ -d "$locks/.lock" ] && free=$((SLOTS - 1))    # the one-slot script's batch takes a slot
lock=
for i in $(seq 1 "$free"); do
  if mkdir "$locks/.lock$i" 2>/dev/null; then lock=$locks/.lock$i; break; fi
done
if [ -z "$lock" ]; then
  running=$(for dir in ${held[@]+"${held[@]}"}; do cat "$dir/name" 2>/dev/null; done | paste -sd ' ' -)
  echo "$(date '+%F %T') refused: all $SLOTS slots taken ($running); remove a $locks/.lock* if stale" >> "$summary"
  exit 3
fi
echo "$batch" > "$lock/name"
trap 'rm -rf "$lock"' EXIT

avail_mb() { awk '/^MemAvailable:|^MemFree:/{print int($2/1024); exit}' /proc/meminfo; }

echo "start $(date '+%F %T')  $(avail_mb) MB available  (slot ${lock##*/.lock} of $SLOTS)" >> "$summary"
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
  # Exit 1 is also what a crash returns: a traceback means FAILED, not findings (15 Nov:
  # "database is locked" crashes were counted as ok-findings and skipped on re-run).
  grep -q "^Traceback (most recent call last)" "$log" 2>/dev/null && what="FAILED"
  printf '%03d %-11s %4s min  exit %-3s %5s MB  docushift %s\n' "$n" "$what" "$mins" "$code" "$(avail_mb)" "$args" >> "$summary"
done < "$batch"
echo "DONE $(date '+%F %T')" >> "$summary"
exit
}
