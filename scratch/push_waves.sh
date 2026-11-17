#!/usr/bin/env bash
# Tonight's wip pushes (user, 18 Nov): waves of up to 3 repos, about 75 min apart,
# so staging builds each wave before the next. Fast-forward only: a repo whose wip
# has moved since the plan is skipped and logged, never force-pushed.
#   scratch/push_waves.sh            # run
#   scratch/push_waves.sh --dry-run  # print what each wave would push
set -u
ROOT=/c/github/tibco-docs-aem
LOG=/c/github/docushift-tool/cache/overnight/push-waves.log
GAP=${GAP:-4500}
DRY=${1:-}

WAVES=(
  "en-us-tib-ems-userdocs en-us-tib-messaging-userdocs en-us-tib-mainframe-userdocs"
  "en-us-tib-adapters-userdocs en-us-tib-businessevents-userdocs en-us-tib-scribe-userdocs"
  "en-us-tib-hawk-userdocs en-us-tib-general-userdocs en-us-tib-ftl-userdocs"
  "en-us-tib-cloud-userdocs en-us-tib-iprocess-userdocs en-us-tib-activespaces-userdocs"
  "en-us-tib-data-management-userdocs en-us-tib-bpm-userdocs en-us-tib-foresight-userdocs"
  "en-us-tib-fulfillment-userdocs en-us-tib-mft-userdocs en-us-tib-flogo-userdocs"
  "en-us-tib-tra-userdocs"
)

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG"; }

push_repo() {
  local repo=$ROOT/$1 ref=origin/content-fix
  # Data Management: Digital Platform committed to wip, so push the merge branch.
  [ "$1" = en-us-tib-data-management-userdocs ] && ref=push-wip
  git -C "$repo" fetch -q origin || { log "FAIL fetch $1"; return; }
  local sha files
  sha=$(git -C "$repo" rev-parse "$ref") || { log "FAIL no $ref in $1"; return; }
  if ! git -C "$repo" merge-base --is-ancestor origin/wip "$sha"; then
    log "SKIP $1: wip moved since the plan (not a fast-forward of $ref)"; return
  fi
  files=$(git -C "$repo" diff --name-only origin/wip "$sha" | wc -l)
  [ "$files" -eq 0 ] && { log "NOOP $1: wip already has $ref"; return; }
  if [ "$DRY" = --dry-run ]; then log "DRY  $1: would push ${sha:0:8} ($files files)"; return; fi
  if git -C "$repo" push -q origin "$sha:refs/heads/wip" 2>>"$LOG"; then
    log "OK   $1: pushed ${sha:0:8} to wip ($files files)"
  else
    log "FAIL push $1"
  fi
}

log "start${DRY:+ ($DRY)}: ${#WAVES[@]} waves, gap ${GAP}s"
for i in "${!WAVES[@]}"; do
  log "wave $((i + 1))"
  for r in ${WAVES[$i]}; do push_repo "$r"; done
  if [ $((i + 1)) -lt ${#WAVES[@]} ] && [ "$DRY" != --dry-run ]; then sleep "$GAP"; fi
done
log "DONE"
