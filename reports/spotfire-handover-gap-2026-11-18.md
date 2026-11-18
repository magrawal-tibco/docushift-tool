# Spotfire hand-over: what the two repos still lack (18 Nov 2026)

Read-only check, made to plan tomorrow's (19 Nov) hand-over of the two Spotfire repos to Digital Platform.
Scope: Statistica family, 14 versions (12 published online help + 2 PDF-only); Data Virtualization, 3 versions.
The Spotfire site runs on AEM and works like the TIBCO site, so every TIBCO/ibi fix applies wherever its problem is present.
No Spotfire staging pages exist yet, so all checking below is local.

## Where each repo stands

| | Statistica repo | Data Virtualization repo |
|---|---|---|
| Branches | `main` only | `main` only |
| On GitHub | First publish + note labels (22 Oct, `0114ea66`) | First publish "as-is" (26 Oct, `1ac1167a`) |
| Local, not pushed | 1 commit: redirect files in AEM's new shape (5 Nov, `d34eb6cd`, on hold) | nothing |
| Pages | 58,547 Markdown files | 32,067 Markdown files |
| Redirect files (`301.yml`) | New shape (in the unpushed commit) | **Old shape** (published before the 30 Oct change), plus a product-level file AEM no longer wants |
| Last local check | 13 Nov, with the fixed checker (6 versions) | 26 Oct, with the old checker |

`docs/jira.md` still says the Data Virtualization repo is empty (Waiting list); it is not, it was published on 26 Oct.

## Fixes missing

Measured on the repos today. "Workspace" means `output/` and `reframed/`: a `sync` copies them over the repo, so a fix made in the repo only is undone by the next `sync`.

| Fix | Statistica | Data Virtualization | How applied | Effort / time | Risk |
|---|---|---|---|---|---|
| Note labels (R001, DOCOPS-250) | Done (pushed 22 Oct) | Not needed (0 notes in the old form) | – | – | – |
| One note label, not two (Phase 71) | **6 pages** show "Note:" twice | 0 | Edit the 6 lines by hand (workspace too) | 10 min | Low |
| Redirect files in the new shape (Phase 68 + 72) | Done in `d34eb6cd`, not pushed | **Missing**, 3 versions + product-level file | Statistica: push the commit. DV: `docushift sync --product tibco-data-virtualization` (rewrites the published `301.yml`), then `python scratch/check_301_rollout.py` | Statistica 5 min; DV 45 min | Medium for DV: `sync` re-copies the 26 Oct workspace and deletes hand-added files; compare the page list before committing |
| Backslash escapes (R002, DOCOPS-360) | **1,739 files, 5,214 changes** | **2,545 files, 11,520 changes** | `docushift repair census --target-dir C:/github/tibco-docs-aem --repair R002 --product …` then `docushift repair apply R002 --target-dir C:/github/tibco-docs-aem --product …` (repo and workspace together). `scratch/apply_r002_local.py` does the repo only (dry run took 1 min for both) | 15 min | Low (mechanical). Run **after** the DV `sync` |
| Letter case of paths (R004, DOCOPS-374) | 0 (census 17 Nov; 0 case-only link mismatches in 120,022 links) | 0 (0 in 392,884 links) | – | – | – |
| Help menu title `docs_list_title` | **17 menus** still "Online Help" | **3 menus** still "Online Help" | `python scratch/set_list_title.py --root C:/github/tibco-docs-aem/<repo> --root output --root reframed --product <slug> --apply` | 10 min | Low. Feeds the breadcrumb, not the menu heading |
| Doubled headings (DOCOPS-336, Phase 76) | 0 | **161 pages** (e.g. `# Query processing` then `## Query processing`) | Re-run `docushift reframe` for the 3 versions (headings only), compare page list, then `sync` | 1.5 h incl. compare | Medium: must not change the published page list (no regrouping) |
| `<` in menu titles (angle-brackets fix) | 0 | **6 menu entries** with raw `<TDV Host>`, `<cursorName>` | Edit the 6 `toc.yml` lines (`&lt;`), or re-convert | 10 min | Low |
| Split anchors (DOCOPS-343) | 0 | 0 | – | – | – |
| Folder names ≤ 50 characters | All fit (longest 49) | Fits | – | – | – |
| Converter fixes since first conversion: list content kept (DOCOPS-370), topics named default/index kept, heading anchors (DOCOPS-362/363) | **Not measured**; Statistica and DV were not in the 73 versions re-converted for DOCOPS-370 | Same | Re-convert into a scratch folder (`convert --force` on a copy), compare with the published pages; adopt only where the page list is unchanged | 2–3 h overnight, mostly machine time | Medium–high: biggest change, last priority if time runs short |
| Checker fixes (DOCOPS-366, 12–13 Nov) | Used in the 13 Nov checks | **Not used**: DV checked 26 Oct | Re-check (below) | 35 min | – |

## Check findings by kind

**Host:** the checks never reached a staging site. `config/publishing.yaml` has staging hosts for TIBCO and ibi only, so the staging part was skipped for every Spotfire run (0 staging URLs in all 17 reports). What they did check is local and still valid: old pages vs our pages, old menu vs `toc.yml`, documents, a sample of redirect rows, and a sample of live docs.tibco.com pages. Nothing needs setting aside.

The four "lost" results, latest report:

| Kind | Statistica 14.4.0 | Data Science Workbench 14.4.0 | DS for Spotfire Analyst 14.1.0 | Data Virtualization 8.8.0 / 8.8.1 / 8.9.0 (old checker) | Whose |
|---|---|---|---|---|---|
| Sentences missing | 12 | 12 | – | 2 / 2 / 2 | Mostly source (Greek letters the source double-escapes); "What's New" (25 sentences) and one iTrees page to check |
| Pictures missing | 12 | 12 | – | – | To triage |
| Menu entries missing | 4 | 4 | 2 | 3,613 / 3,583 / 3,314 | DV: about 81% are checker false alarms fixed 12 Nov; rest to triage |
| Topics missing | 1 | 1 | – | 2 / 1 / 26 | Statistica: source (triaged). DV: to triage |
| Moved in the menu / order / title (warnings) | 1,430 / 28 / 2 | same | 1 | ~130 | Ours, by design (grouping) |
| Pages under "unfiled" | 319 | 319 | 310 | 917–1,448 | Ours (layout); expected |
| Redirect rows not converted | 23 | 23 | 16 | 25–131 | Ours, to look at |

Statistica 14.4.0 and Data Science Workbench 14.4.0 give identical results: the same 14,250 pages are published under both products. Data Virtualization also has the DV team's own error report open (DOCOPS-254, source).
The other 6 checked Statistica versions are clean.

## Not checked

8 Statistica versions have never been checked: Data Science Author, Life Science Author, Life Science Operations, Operations (all 1.5.0); Statistica 14.1.0; Data Science Workbench 14.1.0; Statistica All Servers 14.1.0; Statistica Integration 14.4.0.
The 3 Data Virtualization versions need a re-check with the current checker.

Timing, from the 13 Nov run (`cache/overnight/batch-fri13.summary`): a 14,000-page version takes 12 minutes; small ones under a minute. So: two 14.1.0 versions about 25 min, DV about 30 min, the rest 5 min. **About 1 hour in one slot, 35 min in two.**

Local checks available:
- `docushift verify --target-dir C:/github/tibco-docs-aem --product <slug> --version <v> --skip-published`: old site vs our pages, menus, documents, redirect rows.
- `docushift validate --target-dir C:/github/tibco-docs-aem/<repo>`: broken links, anchors, images, AEM artefacts (writes only to the findings register). Time not measured; estimate 10–20 min per repo. Today's link scan already shows 801 relative links with no target in DV and 4 in Statistica.
- `scratch/check_301_rollout.py` for the redirect files.

## Open decisions

1. **Statistica's held commit (`d34eb6cd`, new redirect shape).** The new shape is now required, so this should go out. Release the hold?
2. **Which branch to deliver on.** Both repos have only `main`; TIBCO work goes `content-fix` then `wip`, and Digital Platform's build fires from `wip` (GitHub App). Ask Digital Platform which branch the Spotfire build reads. Proposal: our fixes go on a new `content-fix` today, merged to whatever branch they name.
3. **Data Virtualization hand-over as-is, or after the DV team's corrections** (DOCOPS-254, still open)?
4. **Adopt the converter fixes since October** (re-conversion) for the hand-over, or hand over with the in-place fixes only and list the rest?
5. **Statistica 14.4.0 and Workbench 14.4.0 publish the same pages twice.** Keep both?
6. **Jira:** no DOCOPS issue covers the hand-over yet (Jira first). Also fix the stale "repo is empty" line in `docs/jira.md`.

No decision needed on AI grouping: no new Statistica or DV versions are in scope.

## Proposed order

**Today (afternoon, about 3 h):**
1. Decisions 1–3 above; DOCOPS issue for the hand-over (20 min).
2. `content-fix` branch in both repos from `main` (Statistica keeps `d34eb6cd`) (5 min).
3. DV: `sync` for the new redirect shape, compare page list, check with `check_301_rollout.py` (45 min).
4. Escapes (R002) in both repos and workspaces (15 min).
5. Help menu titles, 20 menus (10 min).
6. By hand: 6 doubled note labels (Statistica), 6 menu titles with `<` (DV) (20 min).
7. `validate` both repos; one commit per fix on `content-fix` (45 min).

**Tonight (machine time, about 3–4 h):**
8. Local checks: 8 unchecked Statistica versions + 3 DV re-checks (1 h).
9. DV doubled headings: reframe re-run into a scratch folder and compare (1 h).
10. If decision 4 is yes: scratch re-conversion of Statistica 14.4.0 and DV 8.9.0 to measure what the October converter fixes change (2 h).

**Tomorrow morning (about 2.5 h):**
11. Triage the overnight checks (1 h).
12. Adopt the DV heading fix if the page list is unchanged (`sync`, commit) (30 min).
13. Fetch, compare with GitHub, push `content-fix`; hand-over note to Digital Platform listing what is left (DV team corrections, re-conversion if deferred, triage items) (45 min).
