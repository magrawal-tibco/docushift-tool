#!/usr/bin/env bash
# Phase 66: translated folders, each under its own --locale (fix for the skipped packages).
cd C:/github/docushift-tool
run() {  # locale family
  start=$(date +%s)
  COLUMNS=200 docushift --locale "$1" verify --target-dir C:/github/ibi-docs-aem --bu ibi --family "$2" \
    --skip-published --live-sample 0 > "scratch/phase66-verify-ibi-$2-$1-2.log" 2>&1
  echo "$2 $1 exit=$? minutes=$(( ($(date +%s) - start) / 60 ))"
}
run ja-jp wf-reporting-server
for l in ja-jp de-de fr-fr es-es; do run $l webfocus; done
echo "all languages done"
