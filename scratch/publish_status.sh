#!/usr/bin/env bash
# Publish reports/conversion-status.html to the Apps Script web app (user, 13 Nov):
# copy it to report.html, `clasp push`, then point the shared deployment at the new
# version so the link others use shows it. Run after scratch/build_conversion_status.py.
#
#   scratch/publish_status.sh
set -euo pipefail
REPO=/c/github/docushift-tool
APP=/c/github/apps-script
DEPLOYMENT=AKfycbyXgSeCKzXxTme07eFmLPV9U8EqZUayVz9Oia1OqURBCxLBARmxs0pLxznNb82qeBk   # "TIBCO++ Docs Migration Status"

cp "$REPO/reports/conversion-status.html" "$APP/report.html"
cd "$APP"
clasp push --force
clasp deploy --deploymentId "$DEPLOYMENT" --description "status $(date '+%Y-%m-%d %H:%M')"
