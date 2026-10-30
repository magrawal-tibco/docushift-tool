#!/usr/bin/env bash
# The rest of ibi after WebFOCUS, one family at a time (they share state.db and versions.csv).
cd C:/github/docushift-tool
for pair in wf-reporting-server:en-us-ibi-wf-reporting-server-userdocs focus:en-us-ibi-focus-userdocs di-ism:en-us-ibi-di-ism-userdocs; do
  bash scratch/ibi-rollout.sh ${pair%%:*} ${pair#*:}
  echo "== ${pair%%:*}"; cat scratch/${pair%%:*}-rollout-status.txt
done
