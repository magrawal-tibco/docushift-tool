# Jira Tracking — What Is Logged in DOCOPS

> **Last reconciled:** 2026-10-29, against Jira and `config/versions.csv`.
> Conventions (site, cloud ID, story points, transitions, who owns what) live in
> `C:\github\confluence-mcp\reports\docushift-claude-atlassian-context.md`; this file
> does not repeat them. It answers one question: **is this piece of work in Jira, and where?**

## Handoff — read first, update last

Any session that touches Jira, closes a phase, or lands a run updates this section before it
ends: rewrite **Waiting**, append one line to **Log**, and bump *Last reconciled* above.

**Waiting** (Jira changes due when the event happens):

| When this happens | Do this in Jira |
|---|---|
| Phase 47 re-runs (8 versions) pass | DOCOPS-187 → Done |
| `catalog sitemap` over the whole scope run (StreamBase half done 2026-10-21) | DOCOPS-123 → Done |
| 50 long-path + 8 DITA versions re-run | DOCOPS-188 → Done |
| `sync --bu tibco` + `validate` run | DOCOPS-134, DOCOPS-135; refresh counts in DOCOPS-122, 125–127 |
| A family reassignment is committed | Add a dated line to the progress comment on DOCOPS-120 |
| Family review finished | DOCOPS-120 → Done, then DOCOPS-130 |
| Edit to DOCOPS-217 is allowed (blocked by a permission check on 2026-10-09) | DOCOPS-217: append the 2026-10-09 publish note → Done |
| A follow-up from the BusinessConnect warnings is planned | DOCOPS-220 → In Progress |
| General resources repo created and pushed (4 API references) | DOCOPS-245: dated note → Done |
| `fix-callouts` has run over output/, reframed/ and both repos, pushed, and labels show on staging | DOCOPS-250: dated note → Done |
| Phase 55 pilot reviewed and all ibi products verified | DOCOPS-249 → Done; DOCOPS-150 (ibi staging check): dated note with the verify result |
| An ibi family's versions all read `clean` or `explained` | Its sub-task (DOCOPS-259, 260, 262, 263): dated note → Done |
| An ibi family's R001 is applied, pushed and confirmed by `verify` | Its sub-task (DOCOPS-264–269): dated note → Done |
| Container Editions re-synced | Re-run `repair census`; dated note on DOCOPS-267 with the count |
| Phase 61 or 62 is planned in full and approved | Its sub-task (DOCOPS-272–273) → In Progress |
| AEM owners fix alt text with `/`, `:` or `⌘` and a verify re-run shows none dropped | DOCOPS-255: dated note → Done |
| Phase 58 built (records, triage, selectors) and the first ibi wave summarised | DOCOPS-256 → In Progress while building, then Done |
| stg-docs.tibco.com has real content | DOCOPS-257: run the TIBCO staging probe and staging pilots |
| Staging shows one Japanese and one German WebFOCUS page correctly | DOCOPS-148: dated note → Done |
| Data Virtualization team answers the error report and the corrections are republished (published as-is 2026-10-26) | DOCOPS-254: dated note → Done |
| Staging has rebuilt from `wip` (all five ibi `phase63-*` branches merged 2026-10-26, deleted 2026-10-28) | `verify` with staging per family: DOCOPS-274 note; notes on DOCOPS-259/260/262/263; R001 sub-tasks DOCOPS-264/265/266/267/268 → Done if labels show |
| Phase 63 rolled out and every family re-synced | DOCOPS-274 → Done |
| Translated WebFOCUS layout phase is opened | New sub-task under DOCOPS-11 (deferred from Phase 63) |
| A redirect source is decided for each Go URL with several destinations, and the Go URL redirects are built | DOCOPS-279: dated note → Done |
| A new phase is opened | One sub-task under the matching story, In Progress, no `retro` |
| Phase 66 runs: every synced PDF-only version verified (15 after a re-extract, 3 Omni-Gen after a re-sync) | DOCOPS-285: dated note with the counts → Done; per-BU results on the BU's verify issue |
| Phase 68 built, both BUs re-synced, validated and pushed | DOCOPS-292: dated note with counts → Done |
| Every family in a BU has its source ZIPs backed up | DOCOPS-281 (ibi), DOCOPS-282 (TIBCO), DOCOPS-283 (Spotfire, DataSynapse): dated note with gaps → Done |

**Left alone on purpose:** DOCOPS-8 is a Task where its siblings are Stories.

**Log** (newest first, one line per session):

- 2026-10-29 — DOCOPS-297 → Done, DOCOPS-122 → Done (9 of 9): BPM 4.2.0/4.3.0 help re-merged, synced, validate 0
  errors, pushed to `wip` (bpm-userdocs 98790f5); 311/251 pages shortened, longest 259. Selected TIBCO: 514 synced.
- 2026-10-29 — DOCOPS-297 created under DOCOPS-12 (0.5 SP, AI & Content Intelligence, `reframe` `tibco`), In
  Progress: Phase 69, BPM guide folders shortened + reframe limit 259; built, run pending. Component set by edit.
- 2026-10-29 — DOCOPS-292 note: ibi re-sync after unfiled help entries dropped; pushed to `content-fix` (Focus
  e1f1d021, WebFOCUS 95a86c00, RS 4512e1fa). RS 9.2.8 is PDF-only, published. The 2 WebFOCUS Client warnings are 9.1.0/9.1.1 help
  `.war` ZIPs (~500 MB); user kept both versions PDF-only.

- 2026-10-29 — Phase 68 ibi run: maps rooted in 5 repos, pushed to `content-fix` (WFCE d96e0cc, DI/ISM 80247ae, Focus
  44be2105, WebFOCUS f6e0c87e, RS 05ce789c). Left: DI 1.1.0/1.2.0 (stale merge), TIBCO run. No Jira change yet.
- 2026-10-29 — DOCOPS-292 created under DOCOPS-96 (0.5 SP, AI & Content Intelligence), In Progress: Phase 68,
  `301.yml`/`csh.yml` targets as repo-rooted `.md` paths (AEM request); built, sync runs pending. Component set by
  edit; create rejects it.
- 2026-10-29 — TIBCO repos: `wip` pushed (main untouched) in businessevents, tra, bpm, bpm-resources, bw-plugin
  userdocs; Business Studio 5.6.0–5.7.0 case-object page renamed (260 chars); path limit now 259.

- 2026-10-29 — DOCOPS-122 note: Phase 67 built (API refs publish past 260); Service Grid 3.4.3/3.4.4 synced in full.
  8 of 9 resolved; BPM parked. Repo changes uncommitted.

- 2026-10-28 — DOCOPS-122 note: 7 of 9 failed/out-of-date TIBCO versions published (EDI x2; BusinessEvents EE
  6.4.0/6.3.2 and Runtime Agent 5.13.0 via shorter rename-map folders); Service Grid API refs and BPM open.

- 2026-10-28 — DOCOPS-200 → Done: Reporting Server 9.1.0–9.2.7 re-synced (no repo change); all 198 published
  ibi versions synced. `content-fix` pushed in all 8 ibi repos.

- 2026-10-28 — ibi repos: `content-fix` branch created from `wip` in all 8 and checked out; from now on fixes
  go there, never to `wip` directly. No Jira change.

- 2026-10-28 — All ibi repos switched to `wip`; the five merged `phase63-*` branches deleted, local and remote
  (each had 0 commits outside `wip`). No Jira change.

- 2026-10-28 — DOCOPS-200 note: Legacy re-published in the current format (`wip` 9d9f217), 14/14 clean; 9
  unselected Web Query versions removed (dbf87e4). Left: re-sync Reporting Server 9.1.0–9.2.7 (13 out of date
  only from the 27 Oct re-extract). Stays Backlog.

- 2026-10-28 — Verify: a run without `--locale` checks each language on its own state; translated reports
  named per language (Phase 66 follow-up 2, DOCOPS-285). No Jira change.

- 2026-10-28 — Empty version lists left by a withdrawal fixed in sync (Phase 66 follow-up, DOCOPS-285); the three
  Omni user-guides lists removed from Legacy `wip` and pushed. No Jira change.

- 2026-10-28 — Phase 66 verify notes on DOCOPS-259, 260, 262, 263 (stay open: help-page losses); DOCOPS-261
  (Legacy, 14/14 clean) → Done.

- 2026-10-28 — Client 9.3.8 translated menus (~1,069 dead entries per language) triaged as source; open issue
  for the authoring team. No Jira change.

- 2026-10-28 — DOCOPS-258 (Container Editions) → Done: 32/32 clean, help and documents, local check. iWay BAM and
  TPM 8.0.5 clean (already on remote `wip`). Translated folders verified after the fix (23 `lost`, see Verify
  waves). Notes on DOCOPS-259–263 not posted. Pushed: tool 2865b0a (reframe-component), Legacy 46ce249
  (`wip`). iWay BAM/TPM were already on remote `wip` (dabab3e, 26 Oct); the local copy was unfetched.

- 2026-10-27 — Phase 66 runs (no Jira change yet): Omni-Gen/MDM/HealthData 4.3.0 re-synced (release notes to
  release-information, Legacy `wip`, not committed); Reporting Server 9.1.0–9.3.4 and BW EDI 6.3.1 re-extracted;
  ibi verified locally per family (see Verify waves). Notes on DOCOPS-258–263 proposed, not posted.

- 2026-10-27 — DOCOPS-285 created under DOCOPS-96 (0.5 SP, AI & Content Intelligence), In Progress: Phase 66,
  `verify` checks PDF-only versions. Built; read-only probe: ibi 84 clean, 3 lost; TIBCO 77 clean. Extended the
  same day to every version's documents (EMS 7/7, WebFOCUS 45/45 clean in a probe). Runs pending.

- 2026-10-27 — ZIP backup tasks DOCOPS-281/282/283 created. ibi downloaded family by family: 181 of 200 ZIPs on disk
  (~21 GB); the 19 hand-obtained ones are not fetched. General has none eligible. DOCOPS-281 not yet noted or closed.

- 2026-10-26 — DOCOPS-254 note: Data Virtualization 8.9.0/8.8.1/8.8.0 published in the TOC layout with the
  source errors as-is, pushed (1ac1167a); stays In Progress for the team's answer. Verify's "lost" is a false alarm.

- 2026-10-26 — DOCOPS-280 created under DOCOPS-96 (0.5 SP, AI & Content Intelligence) and closed the same
  day: Phase 65 overview page with drill-down and Jira work analytics; note with counts.

- 2026-10-26 — Container Editions `phase63-pilot-wfce-938` merged to `wip` by the user (PR #1, 2c31e9f). All five ibi
  families now on `wip`; staging verify not yet run.

- 2026-10-26 — Four ibi phase63 branches fast-forwarded to `wip`; DOCOPS-274 note. Staging verify not yet run.

- 2026-10-26 — DOCOPS-275 → Done (Phase 64 runs pushed); results noted on DOCOPS-262 and 263.

- 2026-10-26 — DOCOPS-279 created under DOCOPS-9 (0.5 SP, Content Migration), In Progress: Go URL list
  (3,557 rows) in reports/redirects/go-urls-2026-10-26.csv; /emp/ vs /pub/ choice open.

- 2026-10-26 — DOCOPS-275 note: Phase 64 built (0d45fbb); re-runs onto phase63 branches pending.

- 2026-10-26 — Phase 64 approved: DOCOPS-275 created under DOCOPS-11 (1 SP, docushift), In Progress.

- 2026-10-25 — Phase 63 rolled out to the rest of ibi (WebFOCUS, Reporting Server, FOCUS, DI-ISM) on
  phase63-<family> branches: notes on DOCOPS-274; R001 notes and In Progress on DOCOPS-264/265/266/268;
  verify notes on DOCOPS-259/260/262/263.

- 2026-10-25 — DOCOPS-267 note: R001 reaches nested notes; the 3 Container Editions notes fixed (pilot branch
  10d3308); same-day apply reports now accumulate.

- 2026-10-25 — Phase 60 built: DOCOPS-271 note → Done; DOCOPS-270 → In Progress. Container Editions rolled out
  on branch phase63-pilot-wfce-938 (22 versions, R001, all verify clean): notes on DOCOPS-274, 267, 258.

- 2026-10-24 — DOCOPS-271 → In Progress: Phase 60 approved (301.yml presence every run, rows by sample of 10,
  plus the two verify false positives from the Phase 63 pilot).

- 2026-10-24 — DOCOPS-274 note: Phase 63 pilot, WFCE 9.3.7 and 9.3.8 on branch phase63-pilot-wfce-938 (not wip);
  155/155 redirects resolve on disk; staging addresses all change under title names; R001 held for verify.

- 2026-10-24 — DOCOPS-274 note: Phase 63 built (cd939ba, 8acf926) incl. automatic name shortening for
  paths past 260 (all 148 fit); stays In Progress for pilot and family rollout.

- 2026-10-23 — DOCOPS-274 (Backlog, 1 SP, under DOCOPS-11): TOC-shaped folders for the 148 unmerged versions
  (ibi, WebWorks, Streaming, Data Virtualization); only reframe builds them today, and reframe would also merge.
  Planned as Phase 63 (reframe with merging off; parent pages link their immediate children). Approved same day:
  title names, translated help deferred; DOCOPS-274 → In Progress.

- 2026-10-23 — Via docops-plan.csv: R001 per ibi family DOCOPS-264–269 (under DOCOPS-144, 0.25 each), ibi redirect
  lists DOCOPS-270 (under DOCOPS-149, 0.5), tool phases 60–62 DOCOPS-271–273 (under DOCOPS-96, 1 each). All Backlog.

- 2026-10-23 — ibi verification split per family: DOCOPS-258–263 under DOCOPS-149 (0.25 SP each, WebFOCUS 0.5),
  via docops-plan.csv. DOCOPS-258 (Container Editions) In Progress: first wave, 20 versions `lost` from a stale publish.

- 2026-10-23 — DOCOPS-256 note: Phase 58 built (9a3af4d); Phase 59 (repairs) built and logged on it, no new task.
  R001 census: 538 versions / 97,694 notes needed, 18 fixed. DOCOPS-256 stays Backlog until the first wave.

- 2026-10-23 — Phase 55 built (422e406): DOCOPS-249 note (pilot: nothing lost; AEM drops 5 alts). DOCOPS-250 note
  (ibi AI Assistant notes fixed, 7cac70dc). New: DOCOPS-255 (AEM alt text, In Progress, 0.25, under DOCOPS-149),
  DOCOPS-256 and DOCOPS-257 (Phase 58 records/triage and TIBCO readiness, Backlog, 0.5 and 1, under DOCOPS-96).

- 2026-10-23 — Phase 57 logged as DOCOPS-253 (Done, 1 SP, under DOCOPS-11). DOCOPS-148 (translated WebFOCUS,
  1 SP) → In Progress, due 28 Oct: all 27 language builds published to both loc- repos, pushed (main + wip);
  staging check left. DOCOPS-254 (Data Virtualization run, In Progress, 0.25 SP, due 28 Oct, under DOCOPS-7).
  DOCOPS-120 comment: GEMS and Graphical Rendezvous not for conversion.

- 2026-10-23 — DOCOPS-251 (Done, 0.25 SP, under DOCOPS-7): Business Studio BPM 5.6.0/5.6.1/5.7.0 online
  help published after 3 approved folder renames; ActiveMatrix BPM 4.2.0 from a repaired package (case clash),
  all but online help published (111 long-path pages, with 4.3.0). Validate: 0 errors for both.

- 2026-10-22 — DOCOPS-250 note: Statistica notes fixed (6,199 labels in output/ and reframed/, 4,175 in
  en-us-spotfire-statistica-userdocs), pushed as 0114ea66; stays In Progress for staging check and other families.

- 2026-10-22 — Phases 55 and 56 logged under DOCOPS-96: DOCOPS-249 (verify against stg-docs.ibi.com,
  In Progress, 1 SP, due 30 Oct) and DOCOPS-250 (note labels + `fix-callouts`, built, In Progress,
  0.5 SP, due 27 Oct; runs pending, Statistica first). DOCOPS-150 left alone, waits on the Phase 55 pilot.

- 2026-10-22 — DOCOPS-248 (Done, 0.25 SP, under DOCOPS-7): AWS Common Services 6.0.0–6.1.0 reframed and
  published; Oracle EBS 6.1.2, Oracle Fusion Cloud 6.0.0, Files 8.3.0 re-run to publish; one Files 8.3.0
  page pinned shorter in rename-map.csv. bw-plugin sync 0 errors; validate clean.

- 2026-10-22 — Statistica run logged on DOCOPS-128 (Done, 0.5 SP, under DOCOPS-7): on dev input
  Statistics Services out of scope and 22 versions ineligible (461168f); 19 published, 0 validate
  errors. DOCOPS-120 comment added. Publish-gap open issue (1cb344b) has no Jira task yet.

- 2026-10-21 — DOCOPS-247 (Done, 0.25 SP, under DOCOPS-7): last 6 download-failed versions published
  from hand-obtained packages (1e077dd); DOCOPS-147 → Done (ibi DSML 1.0.7). DOCOPS-122 note: 0
  download-failed left. DOCOPS-120 comment: B2B 1.1.0 ineligible.

- 2026-10-21 — DOCOPS-246 note: BPM resources repo, empty on GitHub since 19 Oct, first pushed
  (15a525f, 3,626 files); stale local backup folder removed; no validate errors across BPM.

- 2026-10-21 — DOCOPS-246 (Done, 0.25 SP, under DOCOPS-7): Flogo 3.0.1, FormBuilder 5.3.2, PSI 2.1.0
  and Business Studio CE 4.2.0 from hand-obtained packages; BPM docs repo first pushed (4cc5f3a).
  DOCOPS-122 note: 7 download-failed left. DOCOPS-120 comment: Buildpack for PCF 2.2.1 ineligible.

- 2026-10-21 — DOCOPS-123 note: 4 StreamBase FIX Engine versions re-downloaded, PDF-only, published
  (df0b381, d24b83c); stays In Progress for `catalog sitemap`. DOCOPS-122 note: 12 download-failed left.

- 2026-10-21 — DOCOPS-245 note: Health Essentials Cloud and Patterns 5.7.1 made ineligible, 11 of 11
  published (2dc18e1); still waits on the General resources repo. DOCOPS-120 comment added.

- 2026-10-21 — General run logged as DOCOPS-245 (In Progress, 0.25 SP, due 24 Oct, under DOCOPS-7): 11 of 13
  published after 2 folder renames (1c29b02), pushed to en-us-tib-general-userdocs (a7d2916); 2 held
  as open issues. DOCOPS-120 comment: 52 General versions switched off.

- 2026-10-20 — Platform run logged as DOCOPS-244 (Done, 0.25 SP, under DOCOPS-7): 7 of 7 converted and
  published, 4 folders renamed for long paths (9b9f6d1); pushed to en-us-tib-platform-userdocs (0407104).
  DOCOPS-120 comment: OpenSpirit made wholly ineligible.

- 2026-10-20 — DOCOPS-243 → Done: 5 held iProcess online help sets published after approved folder
  renames; Server Objects (Java) 11.9.0 added by hand; Suite 1.0.0 ineligible, suite page only (a370481).
  Pushed to en-us-tib-iprocess-userdocs (126927e); comment added to DOCOPS-243.

- 2026-10-19 — iProcess run logged as DOCOPS-243 (In Progress, 0.25 SP, under DOCOPS-7): 13 of 18
  converted, 8 online help sets published, 5 held on long paths, 2 packages missing (53ba810);
  DOCOPS-120 comment: 19 iProcess and 23 Platform versions ineligible.

- 2026-10-19 — Mainframe run logged as DOCOPS-242 (Done, 0.25 SP, under DOCOPS-7): 11 of 11 converted and
  published across 7 products (80f7f38); DOCOPS-120 comment: 8 versions ineligible, 3 made eligible.

- 2026-10-19 — DOCOPS-241 note: Redtail 7.5.0 Container Edition guide confirmed and renamed (b9fe2b1).

- 2026-10-19 — DOCOPS-241 → Done: Redtail 7.5.0/6.3.1 online help published after three folder renames
  (9a96b26, f3bff8f).

- 2026-10-19 — Hawk run logged as DOCOPS-241 (In Progress, 0.25 SP, under DOCOPS-7): 7 converted and
  pushed, Redtail 7.5.0/6.3.1 online help held on long paths; DOCOPS-120 comment: 4 Hawk versions
  ineligible (62943c2).

- 2026-10-19 — FTL, ActiveSpaces, EMS and Messaging re-run logged as DOCOPS-240 (Done, 0.25 SP,
  under DOCOPS-7): 31 of 35 converted, 5 ActiveSpaces versions pushed (a0267c6); DOCOPS-120
  progress comment: 7 versions ineligible (0db0b7c).

- 2026-10-17 — DOCOPS-120 comment (2026-10-16 Messaging) extended: resources repo holds nothing
  from the removed versions; downloads pages kept, including for products with no version left.

- 2026-10-16 — DOCOPS-120 comment: ActiveSpaces Kafka and Pulsar connector 1.0.0 eligible
  (0cbe145); Kafka connector retired verdict overridden to GA (cbcf82f).

- 2026-10-16 — DOCOPS-120 progress comment: 14 Messaging versions ineligible (7d20e92);
  13 published ones removed from en-us-tib-messaging-userdocs (06cc7ad, pushed 2026-10-17).

- 2026-10-15 — DOCOPS-120 progress comment: 12 Hawk versions ineligible (f298b81).

- 2026-10-15 — DOCOPS-120 progress comment: MDM 10.0.0 and MDM Studio 5.3.0 ineligible
  (fbcd6f6); 12 retired BPM versions switched off (78e02b3).

- 2026-10-15 — DOCOPS-238 and DOCOPS-239 → Done: MDM 11.1.0/11.0.0/9.3.2 help published after
  renames; Phase 54 dropped 913 and 896 copied pages from MDM Studio 6.1.1 and 6.0.0.

- 2026-10-15 — Data Management run logged as DOCOPS-238 (In Progress, 0.5 SP, under DOCOPS-7):
  online help for 6 of 10 published, MDM 11.1.0/11.0.0/9.3.2 wait on renames. Phase 54 opened as
  DOCOPS-239 (In Progress, 0.5 SP).

- 2026-10-14 — DOCOPS-232 → Done: Phase 52 runs passed (PSC 5.1.0 0 image errors, z/Linux 8.1.0
  published).

- 2026-10-14 — Flogo, BusinessWorks, Fulfillment and MFT run logged as DOCOPS-231 (Done, 0.5 SP):
  38 of 43 published. Phase 52 opened as DOCOPS-232 (In Progress, 0.5 SP).

- 2026-10-13 — Phase 51 and the 6 held Foresight versions logged as DOCOPS-229 (Done, 1 SP, under
  DOCOPS-7); correction note on DOCOPS-228; DOCOPS-120 comment: older MFT versions ineligible (398d550).

- 2026-10-13 — Foresight run logged as DOCOPS-228 (Done, 0.5 SP, under DOCOPS-7): 33 of 39
  published, 6 held; DOCOPS-120 progress comment: HIPAA Validator Desktop 9.0.0–9.2.0 eligible.

- 2026-10-12 — EMS, FTL and Messaging run logged as DOCOPS-223 (Done, 0.5 SP, under DOCOPS-7):
  39 of 44 published; 7 leftover issues in docs/open-issues.md.

- 2026-10-12 — DOCOPS-120 progress comment: retired Gemini, FTL and eFTL versions ineligible,
  14 versions (5dc8f76).

- 2026-10-12 — DOCOPS-120 progress comment: legacy Messaging Monitor, Schema Repository and
  Messaging Manager 1.0.0/1.1.0 ineligible, 20 versions (543601e).

- 2026-10-12 — DOCOPS-120 progress comment: Messaging Bridge (Kafka, Pulsar) end of life, 15 versions
  ineligible (86081fd).

- 2026-10-12 — DOCOPS-120 progress comment: LogLogic decommissioned, all 136 versions ineligible
  (e2e1fc1).

- 2026-10-12 — Cloud family run logged as DOCOPS-222 (Done, 0.25 SP, under DOCOPS-7): 5 of 5
  real versions published. DOCOPS-120 progress comment: newest version only for cloud and
  integration platform (42cdaa4, 195 versions ineligible).

- 2026-10-09 — Last 5 BusinessConnect versions re-run and published (44 of 44). DOCOPS-218 and
  DOCOPS-219 → Done (219 now 0.5 SP for the warning check); DOCOPS-220 created (Backlog, 0.25 SP,
  under DOCOPS-101) for three deferred follow-ups. DOCOPS-217 still In Progress: its edit was blocked.

- 2026-10-09 — Phases 49 and 50 (built, runs pending) logged as DOCOPS-217 (under DOCOPS-96) and
  DOCOPS-218 (under DOCOPS-114); the BusinessConnect run as DOCOPS-219 (under DOCOPS-7, 39 of
  44 published). All In Progress, 0.25 SP each.

- 2026-10-09 — Catalog refresh and the 2026-10-09 end-of-support report (5d8b461) logged as
  DOCOPS-215 (Done, 0.25 SP, under DOCOPS-6). Facebook, Marketo and Twitter plug-ins dropped.

- 2026-10-08 — DOCOPS-120 progress comment: added the pre-2016 ineligibility (3fe7d90) and
  the Service Grid + Container Edition move to bpm (73d111c).

- 2026-10-08 — This session's reconcile and handoff work logged as DOCOPS-208 (Done, 0.5 SP,
  under DOCOPS-101). DOCOPS-120 progress comment brought up to 68a9d11 (22 products
  reassigned, empty families dropped, Flogo below 2.26.0 and 90 retired versions disabled).

- 2026-10-08 — Family/catalog gap check. Created DOCOPS-206 (Phase 48, Flogo retirement) and
  DOCOPS-207 (ibi family regroup, 2026-10-05), both Done, no `retro`. Progress comment on
  DOCOPS-120 lists the TIBCO reassignments so far.

- 2026-10-08 — Full reconcile against Jira, `versions.csv`, phase history. Created DOCOPS-192–200,
  fixed counts (122, 125–127, 129), statuses (87, 120, 187), labels on all run tasks, broken
  DOCOPS-20/21 references (14, 15, 17, 19, 76). Retro rule set to "finished before the current
  month"; 27 retro tasks remain. Shared guide in confluence-mcp updated to match.

## How to log work

- **Where:** DOCOPS-74 Docushift, DOCOPS-75 Reframe, DOCOPS-5 TIBCO runs, DOCOPS-139 ibi runs.
  One sub-task per phase (tool work) or per run (migration work).
- **Labels:** `docushift` or `reframe` on everything; add `tibco` / `ibi` on run tasks.
- **`retro`:** only when the work **finished before the current calendar month**, so it is
  not counted in this month's effort. October work logged in October gets no `retro`, however
  late it is logged. A task spanning months is dated by when its last piece finished; a story
  gets `retro` only if every sub-task under it does. On 2026-10-08 that left 27 retro tasks,
  all finished in September (DOCOPS-13–19, 78–82, 85, 88, 89, 92, 97, 98, 108–113, 118, 119, 193).
- **Counts drift.** A task title that carries a count (versions merged, failed, out of date)
  is true on the day it was written. Re-read `versions.csv` (`_bu`, `_status`, `_sync_status`)
  before quoting a number, and re-check the open run tasks when a run lands.
- **Bulk changes go through `C:\github\confluence-mcp\jira\docops-plan.csv`**
  (`apply_docops_plan.py --dry-run`, then live). The script matches rows without a `ref`
  by parent and title, so **renaming an issue in Jira alone makes the next run create a
  duplicate.** To rename, put the key in the row's `ref` column and the new title in the CSV.
  The script never removes labels; remove them with the Atlassian MCP and in the CSV.

## Phases → Jira

"Folded" means the phase has no task of its own; its work is counted in the task named.

| Phase | Work | Jira |
|---|---|---|
| 1 | Architecture, docs, scaffolding | DOCOPS-13 |
| 2, 3.5, 3.6 | Catalog CSVs, merge, scope exclusions, slug key | DOCOPS-85 |
| 3, 33 | Discovery, docsite sitemap | DOCOPS-84 |
| 3.7 | End-of-support exclusions | DOCOPS-193 |
| 3.8 | `-userdocs` publishing names | folded: DOCOPS-97 |
| 4 | Download, extract | DOCOPS-88, DOCOPS-89 |
| 5 | Conversion driver, engines, detection | DOCOPS-14, DOCOPS-78–82 |
| 6, 36 | Navigation, `toc.yml`, publishing layout | DOCOPS-93, DOCOPS-97 |
| 7 | CLI, findings, reporting | DOCOPS-15, DOCOPS-98 |
| 8–19, 21, 23, 27 | Conversion fixes (code spans, landing pages, WebWorks links, DocBook, tables, classes) | folded: DOCOPS-16, DOCOPS-17 |
| 20 | Reframe engine | DOCOPS-108–113 |
| 22, 35 | Redirect / cutover maps | DOCOPS-94, DOCOPS-131 |
| 24, 25 | Status rows, migration verdict | folded: DOCOPS-98 |
| 26, 28 | Layout pin, subtree merge | folded: DOCOPS-109 |
| 29 | Filename is the URL | folded: DOCOPS-92 |
| 30 | ~50,000 cross-references repaired | DOCOPS-196 |
| 31 | WebFOCUS split | DOCOPS-142 |
| 32 | Families assigned by hand | DOCOPS-86 |
| 34 | Whole-tool review | DOCOPS-102; deferred findings DOCOPS-106 |
| 37–39 | Family-review columns, status columns, PDF-ready | DOCOPS-194 |
| 40 | Sitemap package names | build DOCOPS-195; runs DOCOPS-123 |
| 41 | Flare source topics in output | DOCOPS-192 |
| 42 | Reframe for Flare + DITA, all TIBCO | build DOCOPS-198; run DOCOPS-129 |
| 43 | Orphan topics out of TOC | build DOCOPS-95; runs DOCOPS-124, DOCOPS-115 |
| 44 | Links around images | DOCOPS-185 |
| 45 | Function catalogs as API reference | DOCOPS-186 |
| 46 | Long-path refusal | build DOCOPS-184; re-runs DOCOPS-188 |
| 47 | Service Grid merges | DOCOPS-187 (in progress) |
| 48 | Flogo connectors retired; VS Code extension to flogo | DOCOPS-206 |
| 49 | Images too long to publish get a shorter name | DOCOPS-217 (in progress) |
| 50 | Per-page names for a topic in two guides | DOCOPS-218 |
| 51 | Merged Flare help systems: subsystem TOCs spliced into the master | DOCOPS-229 |
| 52 | Letter case the source gets wrong: image links, ZIP name clashes | DOCOPS-232 |
| 54 | A release-notes folder that copies the main guides | DOCOPS-239 |
| 55 | `verify`: converted ibi docs against stg-docs.ibi.com | DOCOPS-249 (in progress) |
| 56 | Note labels AEM shows; `fix-callouts` repairs published docs | DOCOPS-250 (in progress) |
| 58 | `verify` results kept, triaged, tracked per version; TIBCO readiness | DOCOPS-256, DOCOPS-257 |
| 59 | Repairs: generic fixes registered, censused and applied per version | folded: DOCOPS-256 |
| 60 | `verify` checks redirects (`301.yml`), ibi and TIBCO (planned) | DOCOPS-271 |
| 61 | Redirect map for CSH (Help button) URLs (planned) | DOCOPS-272 |
| 62 | `verify` checks CSH identifiers, ibi and TIBCO (planned) | DOCOPS-273 |
| 64 | `verify` reads one language; `301.yml` from English pages; `sync` skips archives | DOCOPS-275 (done) |
| 66 | `verify` checks every version's documents, PDF-only versions included | DOCOPS-285 (in progress) |
| 68 | `301.yml` / `csh.yml` targets are repo-rooted `.md` paths (AEM) | DOCOPS-292 (in progress) |
| 69 | ActiveMatrix BPM help fits: short guide folders (`guide_names`), reframe cuts to 259 | DOCOPS-297 (done) |
| 57 | Translated help to the `loc-` tree (`--locale`) | build DOCOPS-253; runs DOCOPS-148 (in progress) |

Other logged work: Jira reconcile and this handoff DOCOPS-208; stakeholder status page DOCOPS-197; TIBCO family reassignments DOCOPS-120
(in progress, progress kept as comments); ibi family regroup DOCOPS-207; catalog refresh and 2026-10-09 end-of-support report DOCOPS-215; cloud family run DOCOPS-222; EMS, FTL and Messaging run DOCOPS-223; Data Management run DOCOPS-238; FTL, ActiveSpaces, EMS and Messaging re-run DOCOPS-240; Hawk run DOCOPS-241; Mainframe run DOCOPS-242; iProcess run DOCOPS-243; Platform run DOCOPS-244; General run DOCOPS-245; hand-obtained packages and first BPM push DOCOPS-246; last 6 download failures DOCOPS-247; Statistica run DOCOPS-128; Data Virtualization run DOCOPS-254; TIBCO Go URL list for redirects DOCOPS-279 (in progress).

## Open run tasks (as of 2026-10-08)

| Jira | What | `versions.csv` on 2026-10-08 |
|---|---|---|
| DOCOPS-125–127 | TIBCO wave 2a/b/c | 895 TIBCO `not-started` |
| DOCOPS-122 | Failed TIBCO versions | 12 `convert-failed`, 23 `download-failed` |
| DOCOPS-199 | Leftover TIBCO versions | 2 `format-unknown`, 1 `sync-failed` |
| DOCOPS-134 | TIBCO re-sync | 214 `out-of-date` |
| DOCOPS-200 | ibi re-sync | Done 2026-10-28: 0 `out-of-date` (198 synced) |
| DOCOPS-147 | ibi download | 1 `download-failed` |

## Verify waves (Phase 58)

One row per `docushift verify` wave. The per-version results are in
`reports/verify/INDEX.html` and `versions.csv` (`_verify_status`); this table only
says which wave covered what and where it is logged. Each ibi family's verification is its
own sub-task under DOCOPS-149: Container Editions DOCOPS-258, Data Intelligence & iWay Service
Manager DOCOPS-259, FOCUS DOCOPS-260, Legacy DOCOPS-261, WebFOCUS DOCOPS-262, WebFOCUS
Reporting Server DOCOPS-263. DOCOPS-256 is the tool, not the waves.
Applying R001 (note labels) to each ibi family is its own sub-task under DOCOPS-144 (ibi: convert
content): WebFOCUS DOCOPS-264, Reporting Server DOCOPS-265, FOCUS DOCOPS-266, Container Editions
DOCOPS-267, Data Intelligence & iWay Service Manager DOCOPS-268, Legacy DOCOPS-269. Checking the
ibi redirect lists is DOCOPS-270 (under DOCOPS-149), and waits on Phase 60.

| Wave | Date | Selection | Versions | Outcome | Jira |
|---|---|---|---|---|---|
| Pilot | 2026-10-23 | ibi™ AI Assistant 9.3.8, local + staging + live | 1 | explained (5 alt texts → DOCOPS-255; 61 note labels → DOCOPS-250) | DOCOPS-249 |
| ibi translated, Phase 66 | 2026-10-28 | `--locale` ja-jp (Reporting Server, WebFOCUS), de-de, fr-fr, es-es (WebFOCUS), local | 23 | all `lost` from page findings; Client 9.3.8 ~1,070 per language are menu entries to pages the language never shipped | DOCOPS-262, 263 |
| ibi, Phase 66 | 2026-10-27 | `--bu ibi` per family, local only; translated folders not checked (open issue) | 196 | PDF-only: 102 of 102 `clean` (iWay BAM and TPM 8.0.5 were on remote `wip` since 26 Oct; the local checkout was behind). No document finding anywhere. Help: Container Editions 32/32 and Legacy clean; `lost` from page findings: WebFOCUS 22, Reporting Server 9, FOCUS 9, DI-ISM 2 | DOCOPS-258, 261 Done; 259, 260, 262, 263 noted, open |
| Container Editions | 2026-10-23 | `--bu ibi --family container-editions`, local + staging + live | 20 | all `lost`: published copy (5 Oct) predates the conversion (7 Oct); front pages and link text are the old copy's losses. Re-sync, then re-check. Staging serves 2 of 20 | DOCOPS-258 |

## Not in Jira, by choice

- Committing and pushing this repo's own branch: part of each phase, not a task.
- The Phase 8–29 fixes listed as folded above.
