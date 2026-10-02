# R1 — Foundations: findings
Base: review-base (7dda975) · Reviewed: utils/anchors.py, csvio.py, http.py, longpath.py, naming.py, slug.py, swap.py, templating.py; models.py; config.py; origins.py · Date: 2026-10-02

| S1 | S2 | S3 | S4 |
|---|---|---|---|
| 1 | 4 | 8 | 2 |

Unit tests for the unit: 197 passed, 1 skipped (`test_slug, test_naming, test_longpath, test_swap, test_csvio, test_config, test_origins`).
Repros: `C:\tmp\review-R1\` (`fallback.py`, `anch.py`, `esc.py`, `lens.py`, plus inline scripts).

## Findings

### R1-01 · S1 · Help and document trees publish paths over 260 characters with no check and no finding
- **Where:** sync/distributor.py:263-270 and :348-372 (`_place`, `copytree(long_path(source), long_path(staging))`); the only ceiling check is sync/distributor.py:544 / :624 (`_overflowing` → `utils/longpath.py:271 over_limit`), and it covers API trees only.
- **What:** Phase 29 put `long_path` on both ends of the help-tree copy to get past the `.part` overflow. That also removes the only thing that stopped a *final* published path over 260 from being written. `over_limit` / `PUBLISHED_PATH_TOO_LONG` is never applied to `online-help` or the document doc-classes. This breaks the rule in architecture.md §4.4: published paths are held to the ceiling, and only staging is lifted.
- **Failing scenario:** `docushift sync --target-dir <a root about 45+ characters long>` on ActiveSpaces 4.10.1 (reframed). The copy succeeds, 4 files land at up to **288** characters, `SYNCED` is reported, and no finding is recorded. Every Windows reader outside the tool then fails on them.
- **Confirmed:** yes. I called `WorkspaceDistributor._place` on the real `reframed/.../tibco-activespaces-enterprise-edition/4.10.1` tree with a 60-character root under C:\tmp\review-R1. It copied 75 files, 4 of them over 260 (max 288), with no exception. The real `C:\tmp\p35-aem` tree already reaches 236 under a 14-character root, so any root longer than about 38 characters crosses the line.
- **Suggested fix:** Run `over_limit(destination, source)` before `_place` for every doc-class, not only API trees, and record `PUBLISHED_PATH_TOO_LONG`. Keep `long_path` for the staging copy. (The code is in R10; it is filed here because it breaks the §4.4 contract this unit owns.)

### R1-02 · S2 · A blank `convert_eligible` cell reads as `false`, ignoring the active/archived default
- **Where:** utils/csvio.py:18 (`""` is in `_FALSE_TOKENS`), :39; used at catalog.py:323 `parse_bool(row.get("convert_eligible"), default=not is_archived)`.
- **What:** `parse_bool` returns `False` for a blank cell before it ever reaches `default`. So the rule "blank means eligible if active" (design.md §1.2, architecture.md §3.2 / §3.7) never applies, and `save()` then writes the blank back as `false`.
- **Failing scenario:** A human adds a version row by hand in Excel (for example a §3.8 manual package) or clears the cell. The active version silently becomes ineligible and is skipped by every stage. `catalog import` warns only if the row is also batch-tagged. catalog.py:296-300 documents exactly this defect and works around it for `in_scope`, but not for `convert_eligible`.
- **Confirmed:** yes for the code path. A repro with `CatalogManager.load()` on `slug,version,is_archived,convert_eligible / foo,2.0,,` gives `eligible False`. No live row is affected: the current versions.csv has 0 blank cells.
- **Suggested fix:** Remove `""` from `_FALSE_TOKENS`, so a blank cell falls through to `default` (`parse_optional_bool` then no longer needs `- {""}`). Update `test_parse_bool_accepts_falsy_spellings`, which currently pins `""` → `False`.

### R1-03 · S2 · Function-name titles are treated as "filenames", so pages publish under MadCap's 20-character truncated stem
- **Where:** utils/naming.py:388-396 (`looks_like_a_filename`: underscore and no space) and :452-455.
- **What:** A real title such as `tibems_SetReconnectAttemptDelay` (a C API name) matches the "forgot to write it out" heuristic. The page is then named from the source stem, which MadCap truncated. That is the exact defect Phase 29 set out to remove.
- **Failing scenario:** The title `tibems_SetReconnectAttemptDelay` publishes as `.../utility-functions/tibems-setreconnecta3.html`. `tibemsConnectionFactory_Create` publishes as `tibemsconnectionfact21`, and `tibemsMsg_Acknowledge` as `tibemsmsg-acknowledg`.
- **Confirmed:** yes. Across `reframed/*/rename-map.csv` there are **66 pages (11 per EMS version × 6 versions)** whose `new_path` stem is not the normalized title. They are flagged only through the `shortened=yes` column of rename-map.csv (all 11 EMS flags per version are this case). None of them is in review-queue.csv.
- **Suggested fix:** Prefer the title whenever the fallback stem is a truncation of it, i.e. `normalize(title)` starts with `normalize(stem)` once a trailing MadCap counter is removed. Alternatively, treat the title as a filename only when the stem is at least as long as the title.

### R1-04 · S2 · Catalog save writes two files non-atomically; a locked `versions.csv` leaves a half-written pair
- **Where:** utils/csvio.py:153-164 (`open(path, "w")` in place); catalog.py:378 then :433.
- **What:** `write_rows` truncates and rewrites the target in place, and `save()` writes products.csv before versions.csv. If the second open fails, or the process dies mid-write, the pair on disk no longer matches. That breaks design.md §11 invariant 3 ("a fetch is all-or-nothing").
- **Failing scenario:** versions.csv is open in Excel (Excel locks it), and the user runs a fetch or `catalog set`. products.csv is rewritten with the new rows, then versions.csv raises `PermissionError`. After a delete, the next load raises `CatalogError: versions.csv references unknown slug`.
- **Confirmed:** yes. In a repro on a copy of the real catalog (C:\tmp\review-R1\lock), with versions.csv set read-only to stand in for Excel's lock, `save()` raised `PermissionError`. products.csv had changed (it held the new slug) and versions.csv had not. Whether state.db snapshots were already committed at that point is for R2/X3.
- **Suggested fix:** Write both files to sibling temp files first, then `swap.replace_file` each into place, and open/lock-check both before replacing either one.

### R1-05 · S2 · `normalize_date` passes non-ISO text through verbatim, and the conversion year check slices it as ISO
- **Where:** utils/csvio.py:104-124 (contract: unparseable text is returned verbatim); consumer converter/driver.py:525-526 `normalize_date(...)[:4]`.
- **What:** The homepage writes `June 2023`. `normalize_date` returns it unchanged, so `[:4]` is `"June"`, and the comparison with the catalog year raises a false `METADATA_MISMATCH`. The driver's docstring says this exact form is handled. The 926 catalog rows with epoch-millisecond dates (R1-11) would give a catalog "year" of `1399`, `1772` and so on in the same check.
- **Failing scenario:** spotfire-data-science-author 1.4.0 gives `homepage release-date June != catalog 2023`, but both say 2023.
- **Confirmed:** yes. The `findings` table in `cache/state.db` (opened read-only) holds that row.
- **Suggested fix:** Give csvio one `release_year()` / `release_month()` helper that understands ISO, `Month YYYY` and epoch-ms (sync/versions.py:73-88 already does most of this), and use it in the driver instead of `[:4]`.

### R1-06 · S3 · `load_reframe` silently drops `publish`, `keep_separate` and `pin_layout_to` from `defaults:`
- **Where:** config.py:502-505 (filters `defaults` to `REFRAME_DEFAULTS` keys = `max_words`, `toc_schema`).
- **What:** The shipped `config/reframe.yaml` declares `publish: false` and `keep_separate: []` under `defaults:`, but those keys never reach `reframe/policy.py:92`. They work today only because the values equal the dataclass defaults.
- **Failing scenario:** A user sets `defaults: publish: true` (or a default `keep_separate`). The setting is ignored with no message, and no product publishes its merged tree unless it overrides the key itself.
- **Confirmed:** n/a (S3). Repro: `policy_for(load_reframe())` returns `publish=False, keep_separate=()` for a file whose defaults say `true` / `["a/b.md"]`.
- **Suggested fix:** Pass through every key that `ReframePolicy` knows, or report unknown/ignored default keys.

### R1-07 · S3 · A malformed declared origin template is silently discarded; the drop finding reuses the wrong code
- **Where:** origins.py:84-96 (`template_for` returns `None` when `{path}` is missing or `drop_segments` is not an int), :338-352, :364-367, :130.
- **What:** A human's declaration that fails validation is treated as no declaration. `build` then falls back to sitemap derivation, and its message says "none is declared in config/origin-urls.yaml". Separately, sources dropped for being shorter than `drop_segments` are reported under `ORIGIN_TEMPLATE_UNDECLARED` with count 1, not `len(dropped)`. A template with any other `{placeholder}` raises `KeyError` from `str.format`.
- **Failing scenario:** `drop_segments: "one"` makes `build` return derived rows with **no finding** naming the rejected declaration (repro in C:\tmp\review-R1).
- **Confirmed:** n/a (S3). The live origin-urls.yaml (EMS only) is well formed.
- **Suggested fix:** Have `template_for` return a reason, and record a distinct finding for a rejected declaration. Count dropped sources under their own code.

### R1-08 · S3 · `over_limit` measures `len(str(destination))`, so a relative `--target-dir` undercounts
- **Where:** utils/longpath.py:291; `--target-dir` is `click.Path(path_type=Path)` without `resolve_path` (cli.py:43, :1875); `ConfigManager(root_dir=root)` likewise.
- **What:** The docstring says the whole absolute path is counted "the way Win32 counts it", but nothing makes `destination` absolute first.
- **Failing scenario:** `sync --target-dir ..\aem` checks API trees short by `len(cwd)+1` characters. A file at 261–285 absolute characters passes the check, and the copy succeeds through `long_path`.
- **Confirmed:** n/a (S3). The real runs used absolute targets (`C:\tmp\p35-aem`).
- **Suggested fix:** `base = len(os.path.abspath(destination))`.

### R1-09 · S3 · `slugify_heading` diverges from the GitHub-style rule it predicts, in three measured ways
- **Where:** utils/anchors.py:59-63, :85-87.
- **What:** (a) NFKD turns `™` into the letters `tm`, so `# TIBCO Runtime Agent™` anchors at `tibco-runtime-agenttm`. slug.py and naming.py both delete the symbol before folding for exactly this reason. (b) `_TAG` strips a backslash-escaped `\<Project>` as if it were HTML, giving `-window` for `\<Project> Window`. (c) The dedupe does not skip an index already taken by a literal heading: `Foo, Foo 1, Foo` gives `foo, foo-1, foo-1`, where github-slugger gives `foo-2`.
- **Failing scenario:** (a) 9 real H1s in `reframed/`. (b) 1 real heading (tra 5.13.0 `view-menu.md`). (c) 0 real pages (anchor scan over 1,492 reframed pages found no collisions). No inbound link targets (a) or (b) today.
- **Confirmed:** n/a (S3). AEM's own handling of `™` and escapes is unverified.
- **Suggested fix:** Delete `™®©℠` before NFKD, unescape Markdown backslash escapes before `_TAG`, and loop while `candidate in seen`.

### R1-10 · S3 · The fallback-stem history strip eats real version and number tokens
- **Where:** utils/naming.py:377 (`_HISTORY`), :455 and :461 (applied a second time after normalize).
- **What:** The second pass runs on the hyphenated slug, so a version's last component, or a leading number, looks like an edit-history token.
- **Failing scenario:** Stem `Upgrading_to_5.13.0` gives `upgrading-to-5-13`, `Release_Notes_6.1` gives `release-notes-6`, `64_bit_Installation` gives `bit-installation`, and `Step_2` gives `step` (while `Chapter_10` keeps `chapter-10`).
- **Confirmed:** n/a (S3). No empty or filename-shaped title in the current `reframed/` ends in a digit.
- **Suggested fix:** Apply `_HISTORY` only to the raw stem, and do not strip a single trailing digit that is preceded by `.`/digit context, or a leading number followed by a unit word.

### R1-11 · S3 · Epoch-millisecond release dates are stored raw in 926 catalog rows
- **Where:** utils/csvio.py:104-124 (no epoch form); discovery/crawler.py:346 / :411 feed it.
- **What:** design.md §1.2 promises one written date form. Yet 926 of 5,181 rows (502 convert-eligible) hold values like `1399420800000`. Each consumer re-parses them on its own: sync/versions.py:76-81 does, and converter/driver.py:526 does not (R1-05).
- **Failing scenario:** The sheet shows unreadable dates. An Excel save rewrites a 13-digit number as `1.39942E+12`, which `release_month` then rejects, giving `VERSION_UNDATED` (that last part is unconfirmed: Excel was not run).
- **Confirmed:** n/a (S3). Measured on `config/versions.csv`.
- **Suggested fix:** Convert epoch-ms (12–13 digits, plausible year range) to ISO in `normalize_date`, and drop the copy in `release_month`.

### R1-12 · S3 · Docs drift: design.md §1.2 boolean rule and §1.3 pre-release ordering
- **Where:** design.md §1.2 vs csvio.py:18 (see R1-02); design.md §1.3 vs csvio.py:127-142.
- **What:** §1.3 says `2.0.0` sorts above `2.0.0-rc1`, but tuple comparison puts the shorter key lower, so descending order gives `['2.0.0-rc1', '2.0.0']`. The same rule puts textual versions above all numeric ones: real versions.csv lists `Server` above `15.0.0` for spotfire-server, and likewise for 4 other spotfire products. sync/versions.py and sync/archives.py split these out first, so only the CSV row order is affected.
- **Confirmed:** n/a (S3). Measured with a repro and on versions.csv.
- **Suggested fix:** Correct the doc, or append a sentinel `(2,)` to numeric-only keys if the documented order is the one wanted.

### R1-13 · S3 · Docs drift: architecture.md §4.4 "only the two writers of a staged tree call it"
- **Where:** architecture.md §4.4 bullet 1 vs actual `long_path` callers: reframe/driver.py:633, :701-703; sync/distributor.py:368, :593-594; validation/artifacts.py:459-463; validation/links.py:128.
- **What:** The prefix is now applied to final writes (the merged pages, the published copy). That is how R1-01 happened unnoticed. The doc still describes a two-call-site policy.
- **Confirmed:** n/a.
- **Suggested fix:** Rewrite §4.4 around the real rule (staging is lifted, final published paths are checked) once R1-01 is fixed.

### R1-14 · S4 · `naming.qualify` and `naming.GENERIC` are dead in src/
- **Where:** utils/naming.py:382-385, :467-480.
- **What:** They are referenced only by tests/unit/test_naming.py. reframe/packer.py:796-806 explains that the doc-set-wide generic prefix was dropped.
- **Suggested fix:** Remove them along with their tests, or mark them as intentionally retained.

### R1-15 · S4 · Date and walk helpers are duplicated outside utils
- **Where:** sync/versions.py:73-88 re-implements date parsing next to `normalize_date`. engines/flare.py:1001 and engines/webworks.py:1424 each define a private `_walk_files` (plain `os.walk`, no prefix) beside `utils/longpath.walk_files`.
- **What:** These are three parallel definitions of things utils claims to own. The engine walkers return unprefixed paths, which cannot open files over 259 characters (families/ holds 18 such files today, all in EMS `api/dotnet` trees that the engines skip).
- **Suggested fix:** Merge them into the utils helpers when R1-05/R1-11 are fixed. Have the engines use `walk_files` (with a directory filter for WebWorks).

## Edge notes (for the cross-stage pass X1)
- `normalize_date` contract: it returns ISO **or the input verbatim**. Callers must not assume ISO (driver.py:526 does; sync/versions.py:82 tolerates it).
- `parse_bool(x, default)` honors `default` only for unrecognised tokens, never for blank. Every other caller (catalog.py:303/318/345/899-940, crawler.py:333) gets `False` for blank. Fine for `is_archived`/`custom_override`, wrong for `convert_eligible` (R1-02).
- `catalog._coerce_enum` (catalog.py:1508) silently maps an unknown enum token to its default. A typo such as `family_source=manul` would demote a manual family to `unclassified`, which a fetch may then overwrite. All 9 enum columns are valid in the live CSVs today. Flagged for R2.
- `ConfigManager.resolve_product_info` matches taxonomy tokens by substring of the display name (config.py:871). Today's accidents (`ftl`⊂`eFTL`, `ems`⊂`GEMS`) resolve to the same bu, so they are harmless. products.csv has no `bu_source`, and catalog.py:783 overwrites `bu` along with `family`. R2 should confirm that a human `bu` edit survives a fetch.
- `publishing_problems` (config.py:568-579) compares raw `repo_slug` tokens of *declared* families only. Two tokens that differ raw but slugify to the same folder, or two undeclared family keys (`data management` / `data_management`), would share a workspace unreported. There are 0 collisions across the 45 live folders.
- `load_taxonomy`/`families`: a YAML `business_units:` or `families:` key with a null value survives `setdefault` and crashes later with `AttributeError`/`TypeError`.
- `origins.rows` keys `moved` by output path and `output_map` sources by POSIX path. state.db `output_map` is 24,688 rows, 0 containing a backslash, so the contract holds today.
- `origins.page_list` swallows only `SitemapError`. Whether `SitemapCache.pages` can raise anything else on a corrupt cache file is for R2.
- `reframed/en-us-tib-tra/tibco-runtime-agent/5.13.0/.../to-create-file-based-repository-domain-using-gui.md` is **262** characters in the workspace. Any reader that does not go through `long_path` fails on it: a plain `open()` after `glob` raised `FileNotFoundError` during this review. Flagged for X2.
- `http.build_session` uses `raise_on_status=False`, so after retries run out the caller receives the last 5xx/429 response and must check the status itself. Callers are in R2/R3.

## Test gaps (real-data paths only)
- No test that a blank `convert_eligible` loads as the active/archived default. test_csvio.py:30 pins blank → `False`.
- No test for `naming.slugify` with an identifier-shaped title and a truncated stem (`tibems_SetReconnectAttemptDelay` + `tibems_SetReconnectA3`). 66 real pages take this path.
- No test for `normalize_date` on epoch-ms (926 real rows) or `Month YYYY` (homepage dates), and none for the driver's year comparison.
- No test that `load_reframe` honors (or rejects) `publish`/`keep_separate` under `defaults:`, which is the shape of the shipped file.
- No test that sync refuses an over-260 *help-tree* path (only the API-tree path is guarded).
- No test that `save()` leaves both CSVs untouched when the second write fails.

## Docs drift
- design.md §1.2: "the default is what carries the rule 'a blank convert_eligible means eligible…'". The code makes blank `false` (R1-02).
- design.md §1.3: "`2.0.0` sorts above `2.0.0-rc1`". It sorts below (R1-12).
- architecture.md §4.4: "Only the two writers of a staged tree call it". At least six other call sites, including final writes (R1-13).
- architecture.md §3.6: "versions by `(slug, version desc)`". catalog.py:396-401 orders versions by the product order `(bu, family, slug)` and then version. That is cosmetic, but a family reassignment moves rows.
- config.py:394 `output_path` docstring says `output/<family>/…`. It is `output/<locale>-<bu>-<family>/…`.
- converter/driver.py:513-516 says the homepage `March 2021` date is compared by year. It is compared as `"Marc"` (R1-05).

## Checked and fine
- **Invariant 1 (load→save byte-identical):** a real products.csv and versions.csv copy round-tripped through `CatalogManager.load(); save()` and came back byte-identical (`cmp`). BOM present, CRLF on all lines.
- **CSV hygiene §3.6:** utf-8-sig read/write, fixed column order, unknown columns dropped, lowercase booleans and ISO dates on write all match the code. `parse_optional_*` keeps blank distinct from 0/false.
- **`natural_version_key`:** no ties and no non-total comparisons across all 5,181 real version keys.
- **`version_segment`:** injective over every real product, including the odd versions `Cloud™`, `(iPaaS)` and `6.0.1.`. A trailing-dot version under `long_path` resolves to the same directory both plain and prefixed (abspath strips the dot), so there is no mismatch.
- **slug.py:** trademark symbols deleted before NFKD, empty-component guard, primary/localized tree names, and resources raising for a non-primary locale all match design.md §1.4. No workspace-folder collisions across the 45 live (bu, family) pairs.
- **longpath:** `long_path` absolutizes before prefixing, is idempotent, and handles UNC. `walk_files` versus a plain walk over families/, output/ and reframed/ gives equal file counts, and no directory reaches the 248-character limit.
- **swap:** retry and raise semantics are as documented. `replace_file` retries only `PermissionError` (WinError 32 maps to it).
- **templating:** StrictUndefined, keep_trailing_newline, autoescape off, one cached environment per directory.
- **models:** every enum value in the live CSVs parses. Inventory fields are nullable as §3.9 requires.
- **config loaders:** scope/eos/migration duplicate-alias and missing-file rules raise as documented. EOS dates use an explicit `%m-%d-%Y`. Unknown EOS statuses and migration tokens are collected for reporting. `_sheet_slug` strips only a matching suffix.
- **origins:** `derive` grouping, the coverage and margin thresholds, the folder guard, and brace escaping were read and look correct. 301.yml `from` URLs in output/ and reframed/ contain no raw spaces.
- **http:** one retry policy (429/5xx, GET only), and Throttle paces request starts across threads. Not exercised, since the review ran with no network access.
