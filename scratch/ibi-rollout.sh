#!/usr/bin/env bash
# Phase 63 rollout for one ibi family, after reframe: sync, validate, census, R001, verify.
# Usage: scratch/ibi-rollout.sh <family> <repo> [skip-reframe]
# Keeps going past failures; each step's exit code goes to scratch/<family>-rollout-status.txt.
fam=$1; repo=$2; skip=$3
T=C:/github/ibi-docs-aem
cd C:/github/docushift-tool
export PYTHONIOENCODING=utf-8
st=scratch/$fam-rollout-status.txt; : > $st
step() { name=$1; shift; "$@" > scratch/$fam-$name.log 2>&1; echo "$name exit=$?" >> $st; }

[ -z "$skip" ] && step reframe docushift reframe --bu ibi --family $fam
[ "$skip" != resume ] && step sync docushift sync --bu ibi --family $fam --target-dir $T
step census docushift repair census --target-dir $T
prods=$(python -c "
import csv,sys
print(' '.join(sorted({r['slug'] for r in csv.DictReader(open('config/versions.csv',encoding='utf-8-sig')) if r['_bu']=='ibi' and r['_family']=='$fam' and r['_status'] in ('converted','merged')})))")
for p in $prods; do
  step validate-$p docushift validate --target-dir $T --product $p
  step r001-$p docushift repair apply R001 --target-dir $T --product $p
done
step census-after docushift repair census --target-dir $T
for p in $prods; do step verify-$p docushift verify --target-dir $T --product $p --skip-published; done
echo done >> $st
