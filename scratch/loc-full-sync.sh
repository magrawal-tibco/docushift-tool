#!/bin/sh
# Phase 57 step 8: sync and validate every converted WebFOCUS language build.
T=C:/github/ibi-docs-aem
s() { .venv/Scripts/python.exe -m docushift.cli --locale "$1" sync --product "$2" --version "$3" --target-dir $T; }
for v in 9.3.0 9.3.5 9.3.6 9.3.7 9.3.8; do s ja-jp ibi-webfocus-client $v; s ja-jp ibi-webfocus-app-studio $v; done
for l in de-de fr-fr es-es; do for v in 9.3.5 9.3.6 9.3.7 9.3.8; do s $l ibi-webfocus-client $v; done; done
