#!/bin/sh
# Phase 57 step 8: every remaining WebFOCUS Client / App Studio language build.
run() { .venv/Scripts/python.exe -m docushift.cli --locale "$1" convert --product "$2" --version "$3"; }
for v in 9.3.0 9.3.5 9.3.7 9.3.8; do run ja-jp ibi-webfocus-client $v; done
for v in 9.3.0 9.3.5 9.3.6 9.3.7 9.3.8; do run ja-jp ibi-webfocus-app-studio $v; done
for l in de-de fr-fr es-es; do for v in 9.3.5 9.3.6 9.3.7 9.3.8; do run $l ibi-webfocus-client $v; done; done
