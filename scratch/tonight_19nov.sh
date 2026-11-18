#!/usr/bin/env bash
# Night of 18-19 Nov: Spotfire (backup, local checks, DV re-conversion, Statistica scratch
# conversion) and the ibi staging checks that the full disk stopped on 18 Nov. Three slots:
# Spotfire; ibi newest then older part a; ibi older part b. Each batch re-runs its FAILED lines
# and skips finished ones. scratch/overnight.sh waits or stops when the disk runs low.
cd "$(dirname "$0")/.." || exit 2
( bash scratch/spotfire_ws_backup.sh && bash scratch/overnight.sh cache/overnight/spotfire-tonight.txt ) &
sleep 30
( bash scratch/overnight.sh cache/overnight/ibi2-new.txt; bash scratch/overnight.sh cache/overnight/ibi2-a.txt ) &
sleep 30
bash scratch/overnight.sh cache/overnight/ibi2-b.txt &
wait
echo "all done $(date '+%F %T')"
