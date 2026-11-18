#!/usr/bin/env bash
# Back up the Spotfire workspace (output/ and reframed/) before tonight's re-conversion
# (DOCOPS-382), so it can be put back if the page lists change. Restore: copy the folders back.
set -eu
cd "$(dirname "$0")/.."
dest=C:/tmp/spotfire-ws-backup-2026-11-18
mkdir -p "$dest/output" "$dest/reframed"
for d in en-us-spotfire-statistica en-us-spotfire-data-virtualization; do
  cp -r "output/$d" "$dest/output/" && cp -r "reframed/$d" "$dest/reframed/"
  echo "backed up $d"
done
