# Spotfire overnight runs: results for the hand-over (19 Nov 2026, DOCOPS-382)

This is a read-only analysis. Nothing in the repos, config, `output/` or `reframed/` was changed, and nothing was synced, committed, pushed or logged in Jira. `cache/state.db` was opened read-only. Helper scripts are in `C:/tmp/spotfire-overnight` (`sim.py`, `spotfire-triage.yaml`, `cmp.py`, `cls.py`, `dv.py`, `dbl.py`).

The batch is `cache/overnight/spotfire-tonight.txt`. All 42 lines ended `ok` or `ok-findings` (01:49–04:36), with no failures. Data Science Workbench 14.4.0 is left out because it was dropped.

## 1. Local checks (21 versions)

Spotfire has no staging site, so these runs compare the old site's pages, menus, documents and redirect rows with the repos as committed yesterday. The runs are 3155–3176, and each is the latest result for its version.

| Version | Pages | Raw result | After triage | Findings left |
|---|---:|---|---|---|
| Data Virtualization 8.9.0 / 8.8.1 / 8.8.0 | 11,135 / 10,595 / 10,566 | lost | issues | Only menu moves (80 / 82 / 82), from our grouping, by design |
| Statistica 14.4.0 | 14,253 | lost | issues | 1,430 menu moves, 28 order changes (by design) |
| Statistica 14.1.0, Workbench 14.1.0 | 14,531 / 14,530 | lost | issues | 1,415 moves, 28 order (by design). The two give identical results because they publish the same pages twice (open question) |
| DS for Spotfire Analyst 14.1.0 | 328 | lost | issues | 1 menu move |
| The other 14 (DS Author, Life Science Author and Operations, Operations 1.5.0/2.2.0, All Servers 14.1.0/14.4.0, Integration 14.4.0/14.5.0, DS Service 14.1.0, Language Packs 14.1.0) | 4–302 | clean | clean | none |

The triage was applied the same way `verify --retriage` does it (`triage.decide`/`issues.tally`), in memory: today's `config/verify-triage.yaml` plus the 18 entries in `C:/tmp/spotfire-overnight/spotfire-triage.yaml`. Afterwards **0 errors are left**. Menu moves are left untriaged, as in the ibi triage (DOCOPS-375).

**Real problems (ours):**

1. **Statistica 14.4.0, "What's New": 7 of the 9 feature descriptions are missing (25 sentences).**
   - Readers see the 7 feature names but none of their text.
   - This is DOCOPS-370: content written directly inside a list was dropped.
   - Today's converter restores it. The re-converted page (`C:/tmp/stat-reconvert/spotfire-statistica/14.4.0/user-guide/_templates/Whats-New.md`) only adds 40 lines and removes none.
   - **Fix before hand-over:** copy this one page into the repo and into `output/`.
2. **Data Virtualization, all 3 versions, "Text Escaping" page: the escape examples show the wrong characters.**
   - The source shows `&amp;`, `&gt;`, `&quot;`. Our page shows `&`, `>`, `"` in the 5-row table and in the 3 "The replacement results in …" lines.
   - The DV re-conversion (section 3) fixes it.

**Known, from the source, or accepted (nothing to fix):**

- **Greek letters (9 pages per Statistica/Workbench version):** source.
  - The source double-escapes them (`&amp;sigma;`), so the old site showed the text "&sigma;".
  - Our pages show σ, α and ≤, which is better than the old site. The checker counts this as text that was lost.
- **iTrees / C&RT results tabs (3 pages):** checker false alarm. The sentences starting "1) Generates the graph …" are in the Markdown, inside a table cell.
- **Topics missing:**
  - Statistica's "WhenGraphDataChangeAction Enumeration" is not shipped in the package.
  - DV's POSITION, Logging_in_to_TDV_Web_UI and AdapterHelp/CJP/Release_Version_Support are also not in the package.
  - DV's "Running Silent Mode Installation" is linked through a misspelt folder (`BusinessDiirectory`); the page itself is published.
  - DV 8.9.0's Deployment Manager "What's New" is published as the version's top-level `whats-new.md`, with the same text.
- **Menu entries missing (support and legal pages):** a second copy per guide. Each page is published, and `toc.yml` lists one copy at the end, by design (the existing "tail copy" rule).
- **6 redirect rows for old Workbench URLs** that the docsite sitemap does not list. These are harmless rows from yesterday's Workbench drop.

**The 4 Statistica 14.4.0 items flagged before:**

| Item | Outcome |
|---|---|
| Greek letters | Source. Our page reads better than the old one. |
| "What's New", 25 sentences | **Real** (DOCOPS-370). Fix by copying the one page (above). |
| 12 pictures | Checker false alarm, now gone. The 12 animated GIFs on "Distribution Fitting: types of distributions" are in the repo; the old check misread alt text with escaped brackets (fixed in `4e13b8e`). |
| 4 menu entries | Tail copies. Accepted. |

**Recommendation:** Before hand-over, fix the one "What's New" page (Statistica 14.4.0, 10 min). The DV escaping page is fixed by adopting section 3. Everything else can go in the hand-over note as known or source items. The 18 triage entries can be added to `config/verify-triage.yaml` later, if you want the status page to read `issues` instead of `lost`.

## 2. Statistica: is re-conversion needed?

The 15 versions converted last night with today's converter were compared with `output/en-us-spotfire-statistica/<slug>/<version>`. `output/` has the same page list as the repo; I checked this on 3 versions.

- **Page list: identical in all 15 versions.** No page was added, removed or renamed. `toc.yml` is identical too.
- **Content: 13 versions are identical.** Only 3 differ:

| Kind | Statistica 14.4.0 | Statistica 14.1.0 | Integration 14.5.0 | What readers would see |
|---|---:|---:|---:|---|
| Line breaks between HTML list items (Object Model guide: document management system, document types) | 140 | 140 | – | Nothing; the page renders the same |
| Greek letters / symbols written as `&amp;omega;` | 20 | 20 | – | **Worse:** "&omega;" as text, as on the old site, instead of ω |
| List content restored (DOCOPS-370) | 1 ("What's New") | – | 1 | 14.4.0: 7 missing feature descriptions come back. 14.5.0, "Process capability analysis": 4 explanation paragraphs move inside their list item (same words, slightly different indent) |
| Topics named default/index kept | 0 | 0 | 0 | – |
| Heading anchors (DOCOPS-362/363) | 0 | 0 | 0 | – |
| Escapes (R002) | 0 | 0 | 0 | Already applied by repair; the converter now gives the same result |
| Note labels | 0 | 0 | 0 | – |

Example of the Greek-letter kind: `Define &sigma;effect2` (published, shows σ) becomes `Define &amp;sigma;effect2` (re-converted, shows "&sigma;").

**Conclusion:** re-conversion is **not needed** for any Statistica version. It would change almost nothing readers can see, and on 20 pages per 14.x version it would bring back the source's broken Greek letters. The one real gain is the 14.4.0 "What's New" page.

**Recommendation:** Do not re-convert. Copy that single page (section 1). Hand Statistica over as it is, as decided yesterday.

## 3. Data Virtualization re-conversion

`reframed/.../tibco-data-virtualization/<version>` was compared with the repo's `online-help/<segment>`, and with yesterday's workspace backup.

- **Page list: identical** in all 3 versions (11,056 / 10,515 / 10,487 pages). Nothing was split, joined or renamed.
- **Pages that differ from the repo:** 24 / 24 / 18 files, counting `toc.yml` and `301.yml`.
- **Doubled headings: 161 → 143.** This is the same measure as the gap report (55 / 56 / 50 before, 47 / 48 / 48 after).
  - **18 pages are fixed** (8 / 8 / 2): the Microsoft Access function-support pages, Microsoft Access Cache Mapping, and Disabling the Drill Console.
  - The 143 that are left repeat the heading in the source itself: `<h1>Query Processing` then `<h2>Query Processing`, on most CData adapter pages ("Query Processing", "Fine-Tuning Data Access"); 15 of them are under `unfiled/`. The old site showed them the same way. Phase 76 expected these to stay.
- **Also fixed:** the "Text Escaping" page in all 3 versions (section 1).
- **No visible change:** HTML list items split onto separate lines (5 pages per version), and `&p;` → `&amp;p;` (renders the same).
- **Lost, to redo after adopting:**
  - **The 6 menu titles with `<`** (`<TDV Host>`, `DECLARE <cursorName> CURSOR FOR`, 2 per version) are raw again in `toc.yml`. The new run does not escape them, and yesterday's hand edit was in the workspace too. The menu title (`docs_list_title`) is kept.
  - **The 264 restored adapter links** (Google Ads JWT pages and Views, HubSpot Data Model; 7 pages per version) are gone, as expected.
- **Restore-links dry run** (`python scratch/dv_restore_links.py`, no `--apply`): it finds **all 264 links (21 pages) in the new workspace, with 0 misses**.
  - Its repo-side count ("restored: 63", "192 not found exactly once") only reflects that the repo already has the links.
  - **Caution:** if `--apply` runs before the sync, the repo gets 63 extra links on later mentions of the same text. Run it only after the sync.
- **`301.yml`:** the workspace keeps its internal form, and `sync` writes the published form. `redirects.yml` is unchanged.

**What readers gain:** 18 pages without a repeated heading and a correct escaping reference page in each version. It is a small gain, but it is clean: the page list is unchanged and the other differences are known.

**Recommendation: adopt**, in this order:

1. `docushift sync --product tibco-data-virtualization`
2. Check that the page list is unchanged.
3. `python scratch/dv_restore_links.py --apply` (expect 264 restored, 0 problems).
4. Redo the 6 `<` titles in `toc.yml`, in the repo and in `reframed/`.
5. `python scratch/check_301_rollout.py` and `validate`.

After step 4, the repo diff should be about 39 page files (15 / 15 / 9) with no `toc.yml` change; anything more means stop and look. Allow about 45 min. If time is short, hand over without it: list "18 doubled headings and the Text Escaping page" in the note as a follow-up.
