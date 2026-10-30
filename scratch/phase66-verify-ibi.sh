#!/usr/bin/env bash
# Phase 66: local verify of every ibi family, one family at a time.
cd C:/github/docushift-tool
for family in legacy wf-reporting-server container-editions di-ism focus webfocus; do
  start=$(date +%s)
  COLUMNS=200 docushift verify --target-dir C:/github/ibi-docs-aem --bu ibi --family "$family" \
    --skip-published --live-sample 0 > "scratch/phase66-verify-ibi-$family.log" 2>&1
  code=$?
  echo "$family exit=$code minutes=$(( ($(date +%s) - start) / 60 ))"
done
echo "all families done"
