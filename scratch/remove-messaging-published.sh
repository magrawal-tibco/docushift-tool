#!/usr/bin/env bash
# Removes the 14 Messaging versions made ineligible in 7d20e92 from the published
# Messaging repo, trims the 3 drop-downs that list them, and commits (no push).
set -euo pipefail
cd /c/github/tibco-docs-aem/en-us-tib-messaging-userdocs/en-us
test -z "$(git status --porcelain)" || { echo "repo not clean, stopping"; exit 1; }

git rm -rq \
  tibco-messaging-manager \
  tibco-gemini-powered-by-apache-cassandra \
  tibco-messaging-eclipse-mosquitto-distribution-bridge-enterprise-edition \
  tibco-messaging-eclipse-mosquitto-distribution-core-enterprise-edition \
  tibco-messaging/reference-documents/1-{21,22,24,25,26,27,30}-0 \
  tibco-messaging/release-information/1-{21,22,24,25,26,27,30}-0 \
  tibco-messaging-enterprise-edition/reference-documents/3-3-0

# Drop each removed version's two-line row (title + path) from the drop-downs.
for f in tibco-messaging/reference-documents/version.yml \
         tibco-messaging/release-information/version.yml; do
  sed -i -E '/^- title: "1\.(2[1-7]|30)\.0 /{N;d}' "$f"
done
sed -i -E '/^- title: "3\.3\.0 /{N;d}' tibco-messaging-enterprise-edition/reference-documents/version.yml

git add -A .
git diff --cached --stat | tail -1
git diff --cached -- '*version.yml'
git commit -qm "Remove 14 Messaging versions no longer migrated"
git log --oneline -1
