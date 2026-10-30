#!/usr/bin/env bash
# Phase 66, second pass: each language checked under its own --locale, English last.
cd C:/github/docushift-tool
while ps -ef | awk '$2==2872' | grep -q .; do sleep 20; done
echo "di-ism finished"
for v in 9.3.1 9.3.2 9.3.3 9.3.4; do
  docushift extract --product ibi-webfocus-reporting-server --version $v >> scratch/phase66-rs-extract-2.log 2>&1
done
echo "rs 9.3.1-9.3.4 extracted exit=$?"
run() {  # locale family
  start=$(date +%s)
  COLUMNS=200 docushift --locale "$1" verify --target-dir C:/github/ibi-docs-aem --bu ibi --family "$2" \
    --skip-published --live-sample 0 > "scratch/phase66-verify-ibi-$2-$1.log" 2>&1
  echo "$2 $1 exit=$? minutes=$(( ($(date +%s) - start) / 60 ))"
}
run ja-jp wf-reporting-server
for l in ja-jp de-de fr-fr es-es; do run $l webfocus; done
run en-us wf-reporting-server
run en-us focus
run en-us webfocus
echo "all families done"
