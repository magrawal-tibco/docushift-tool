# X1 — Stage contracts: findings
Base: review-base-x (30f906b) · Date: 2026-10-05

| S1 | S2 | S3 | S4 |
|---|---|---|---|
| 1 | 1 | 10 | 4 |

Scope: the 94 edge notes in R01–R12, then a writer/reader sweep of `products.csv`, `versions.csv`, every `state.db` table and `version_metadata` key, the `families/` → `output/` → `reframed/` → published path contract, and toc.yml, csh.yml, metadata.yml, version.yml, 301.yml, redirects.yml, rename-map.csv, review-queue.csv and reframe.yml. Batch 4 themes BA–BE are not re-reported.

Real data used (read-only): `config/`, `cache/state.db` (opened `mode=ro`), `families/`, `output/`, `reframed/` (re-converted 2026-10-04), and the published scratch tree `C:\tmp\p35-aem` (sync of 2026-10-02). Scripts are in `C:\tmp\review-X1\` (`c/runs.py`, `roots.py`, `seg.py`, `a/`, `b/`).

## Edge notes settled

Verdict counts: **11 became findings · 28 already fixed · 15 already a finding, deferred or in batch 4 · 29 not a mismatch · 7 belong to X2/X3 · 4 are inside one stage (R8's scope, not a hand-off).**

| note source | verdict | finding id / one-line reason |
|---|---|---|
| R01 `normalize_date` passes non-ISO through | fixed | R1-05. `converter/driver.py:650` uses `release_year`; `sync/versions.py:66` `release_month` reads ISO, month-year and epoch |
| R01 `parse_bool` ignores default for blank | fixed | R1-02. `csvio.py:47-58`: blank falls to `default` |
| R01 `_coerce_enum` silent fallback | known | R2-11, deferred (M) |
| R01 human `bu` edit reverted by fetch | fixed | R2-03. `catalog.py:851-862` moves `bu` only when it still equals the snapshot |
| R01 `publishing_problems` checks declared families only | finding | X1-16 |
| R01 null YAML `business_units:`/`families:` crashes | not a mismatch | Config-parse robustness inside one module, not a hand-off |
| R01 `moved` keyed by output path, `output_map` POSIX | not a mismatch | Both sides are `PurePosixPath` (`converter/driver.py:1089-1096`, `reframe/driver.py:809`). 0 backslashes in `output_map` |
| R01 `page_list` swallows only `SitemapError` | finding | X1-11 |
| R01 262-character reframed path | X2 | Path length |
| R01 `raise_on_status=False` | not a mismatch | Every caller checks `status_code`: `client.py:113,140`, `fetcher.py:295`, `cli.py:2111` |
| R02 `release_date` epoch, bulk date, "June 2023" | fixed | Theme E. 926 rows migrated; convert compares by `release_year` |
| R02 `zip_url` built from the catalog slug; `finalSlug` not captured | finding (part) | X1-09 covers the stage disagreement. `finalSlug` capture is discovery's, unconfirmed (no network) |
| R02 `product_code` + 2-segment `folder_path` fallback | finding | X1-09 |
| R02 path-unsafe slugs and versions as path components | X2 | |
| R02 five `bu` values, not two | not a mismatch | No reader compares `bu` to a literal. Only defaults (`catalog.py:299`, `config.py:872`) |
| R02 gates read only through `iter_versions(eligible_only)` | not a mismatch | Agreed |
| R02 `forget_version` purge | fixed | R3-11. `state.py:194-205` lists all 8 version tables |
| R02 `pages()` returns None for "no leaf" and "file missing" | finding | Folded into X1-11 |
| R03 `extract_zip_checksum` is convert's only currency key | known | Phase 21 carried-forward item (INDEX batch 2: re-convert needs `--force`); R4-03 added the engine |
| R03 recorded roots outrank a re-walk; absent equals empty | finding | X1-15. Values agree today: convert and sync recomputed for all 54 extracted versions, identical |
| R03 `content_root` readers | not a mismatch | Written at `unpacker.py:197`, read through `content_root.of` (`converter/driver.py:962`, `sync/distributor.py:241`). The 6 unrecorded rows fall back to the same answer |
| R03 `csh_source` replaced wholesale by a partial walk | finding | X1-10 |
| R03 `status`/`error` overwritten and stale | fixed | R3-12 (`fetcher.py:241`, `unpacker.py:165-178`). The 4 `ERROR` rows today are current download failures |
| R03 CURRENT test trusts non-blank columns | fixed | R3-03/R3-04 (`unpacker.py:271`, `:431-438`) |
| R03 `roots.py` `iterdir` unguarded | not a mismatch | R04 showed it is guarded |
| R04 root lists stored with `\` | known | R3-13, deferred. Data: 42/42 `output_roots`, 20/20 `api_roots` |
| R04 convert currency = checksum + prefix | known | Phase 21 item; R4-03 fixed the engine half |
| R04 `output_map` stale after a post-swap failure | fixed | R4-08 (`converter/driver.py:436-453`) |
| R04 `csh_source.doc_set` vs `output_map.source` | not a mismatch | Both tree-relative POSIX; 0 backslashes in 59 rows |
| R04 toc.yml `url` raw, bodies encoded | finding | X1-14 |
| R04 staging writes not long-path | X2 | |
| R04 `.part` residue | known | BA (R10-03) and X2 |
| R04 `engine_folder_map` has no reader | known | R4-10 (O2 cleanup) |
| R04 `roots.py` guarded | not a mismatch | |
| R05 `Renderer.list` ignores `start` | fixed | R5-02 |
| R05 pipe tables drop `<caption>` | fixed | R5-05 / R8-06 |
| R05 `span.autonumber` lost outside block position | fixed | R5-03 |
| R05 escaped topic links never reach `AssetCopier` | fixed | R5-08 |
| R05 `Document.anchors` means different things | not a mismatch | No consumer outside the engines (grep). Only reframe's `Page.anchors` is read |
| R05 Flare never sets `Unit.title` | not a mismatch | `navigation.py:531-539` falls back to the landing title. No raw stem label in any output toc.yml |
| R05 localized root reaches CSH | fixed | R5-01; `converter/driver.py:361` drops help maps inside excluded roots |
| R06 `Document.anchors` has no consumer | not a mismatch | Confirmed |
| R06 platform ignores `<a id>`; the driver rewrites | not a mismatch | By design, but the rewrite misplaces marker runs: see X1-01 |
| R06 `TOPIC_LINK_DANGLING` folded | fixed | R6-03/05/14 (theme S) |
| R06 no `output_map` rows for DITA duplicates | known | R6-10, deferred (Z) |
| R06 `context.tree` includes the wrapper | fixed | R6-07 |
| R06 `slugify` has no length cap | X2 | |
| R06 DITA blank `unit.title` | not a mismatch | Same fallback chain, `navigation.py:531-539` |
| R07 `Document.anchors` is not the body's set | not a mismatch | No consumer |
| R07 WebWorks `NavNode.anchor` never reaches the driver | fixed | R7-01 / AA. RA 5.12.2 toc.yml now has 395 anchored entries |
| R07 `Unit.metadata` keys unread | fixed | R7-04: `navigation.py:191-200` reads `collection` and `book_group`. `book_order`/`book_title` remain write-only (cleanup) |
| R07 popup `by_key` first-wins | fixed | R4-01 (P) |
| R07 support/legal `_tail` | fixed | R9-03 (AG); TRA 5.13.0 publishes both under `tibco-runtime-agent/` |
| R07 coordinates | not a mismatch | |
| R07 `units()` `[]` | fixed | R4-06 (`converter/driver.py:383-394`) |
| R08 csh.yml written before the retarget | fixed | R8-04 (`converter/driver.py:428-430`); 0 dead fragments in TRA 5.13.0. Two follow-ons: X1-01, X1-04 |
| R08 percent-encoded fragments | fixed | R8-08 |
| R08 `image()` None drops alt text | inside one stage | Engine-to-walk, inside convert; R8-13's class |
| R08 `link()`/`image()` return encoded URLs | not a mismatch | 0 unparsed links |
| R08 pipe cells skip `block_override` | fixed | R5-03 / R8-02 |
| R08 `rewrite()` ignores overrides | inside one stage | R8-10, deferred (AI) |
| R08 `headings.is_empty` vs the walk | inside one stage | Unmeasured, convert-internal |
| R08 `flattened_links` attribute | inside one stage | |
| R08 WebWorks inline heading markers | fixed | R8-11 |
| R09 multi-root tails | fixed | R9-03 |
| R09 convert csh.yml 154/154 dead | fixed | R8-04: 0 dead. But 19 of 108 land on the wrong section (X1-01) |
| R09 every `.md` under `output/` is a topic | not a mismatch | Only `converter/driver.py` writes under `output_path` |
| R09 262 characters | X2 | |
| R09 carried pages absent from toc.yml | not a mismatch | validate has no online-help reachability check (`artifacts.py:294`) |
| R09 CURRENT ignores rename-map, `--renormalize`, reference | fixed (part) | R9-04 (`reframe/driver.py:360-365`). Reference-version half is R9-07, deferred; X3 |
| R09 `--input` writes no 301.yml | finding | Wrong: it writes from the catalog version's `output_map` and records merge state. X1-02 |
| R10 selection includes archived | known | BA (R10-01) |
| R10 merge currency reads the package checksum | known | BB (R10-06) |
| R10 archive ZIP path rebuilt | known | O4 (R10-14) |
| R10 API URL, convert vs sync | not a mismatch | Recomputed both stages' API roots for all 54 extracted versions: identical (`roots.py`) |
| R10 router walks output roots | known | R10-12 (BF) |
| R10 per-version 301 assembly | known | BA (R10-02) |
| R10 `.part` in 301 | known | BA (R10-03) |
| R10 X3 note | X3 | |
| R10 X2 note | X2 | |
| R11 validate writes dashed versions | not a mismatch | Deliberate (`tree.py:50-56`). No reader joins on `version`: `report.py:120-123` only displays it, and `query_findings` has no version filter |
| R11 two 301.yml shapes; misspelled slug passes | not a mismatch | Two files at two levels. The per-version check is R11-05 (BC) |
| R11 shared anchor algorithm | not a mismatch | Same function by construction |
| R11 Flare csh.yml writes the identifier | fixed | R8-04 (X1-01 caveat) |
| R11 validate writes runs to the configured state.db | finding | X1-13 |
| R11 `.git` walked | not a mismatch | Costs time only |
| R11 TOC dialects, version-root paths | not a mismatch | `artifacts.py:133-153` reads both key sets |
| R12 `ConfigManager` creates dirs in cwd | finding | X1-13 |
| R12 stage `--version` dotted only | not a mismatch | CLI convention; a dashed value fails loudly as an empty selection |
| R12 `iter_versions` lowercases without stripping | not a mismatch | Bites only on quoted padding; cosmetic |
| R12 `catalog enable` silent on closed gates | not a mismatch | CLI UX, R12's scope |
| R12 `status` points at `report --run last` | not a mismatch | Pointer text (R11-10 / BD area) |
| R12 convert that converts nothing has a warning only | known | BD (R12-06 exit 1 on a failed row) |
| R12 `--input` writes catalog state | known | Theme Z for convert. Data: 8 versions (DataSynapse ×6, `spotfire-data-science-author` 1.4.0, AMX PeopleSoft 6.0.0) have `output_map` rows, no convert checksum and no `output/` tree, and `status` counts them as converted. The reframe half is X1-02 |

## Findings

### X1-01 · S1 · A marker that is not the last in a run is retargeted to the previous section, so Help buttons and links open the wrong section
- **Writer:** `src/docushift/transforms/markdown.py:276-279`. The heading hoist joins every marker into one line above the heading; `:375` and `:504` emit runs the same way. Flare puts 3–4 `<a name>` on each heading.
- **Reader:** `src/docushift/transforms/fragments.py:97-104` (`marker_targets`), called from `converter/driver.py:744`. Its output feeds page bodies, toc.yml and csh.yml (`converter/driver.py:428-430`).
- **Disagreement:** The walk emits markers as a run on one line. The fragment pass sends a marker to the next heading only if nothing but whitespace (`_ONLY_BLANK`, `:69`) separates them. The sibling markers count as "something", so every marker except the last in the run goes to the previous heading.
- **Failing scenario:** TRA Runtime Agent 5.13.0, `palette-reference/Transaction_Controls.md`. The marker `aa.txcontrolpool.nullcontrol.helpurl` sits directly above `## Null Control Pool`, yet csh.yml says `#odbc-control-pool`. The same shift hits `dbcontrol`→`#transaction-controls`, `odbccontrol`→`#jdbc-control-pool`, `xacontrol`→`#simple-control-pool` and `mtscontrol`→`#xa-control-pool`. TRA publishes from `output/` (`publish: false`), so these Help buttons ship pointing one section early. `validate` passes them, because the anchor exists (R11-02).
- **Confirmed:** yes. `c/runs.py` compared `marker_targets` with the same rule that ignores sibling markers, over every `.md` in `output/`. 391 of 57,937 markers move. By version: TRA Runtime Agent 5.13.0 has 170 markers and **19 of 108 CSH identifiers** wrong, Administrator 5.13.0 has 12 markers and 1 of 46, each Streaming/Data Streams version has 23–24 markers, each EMS version has 4. Every link to one of these markers lands one section early too.
- **Suggested fix:** In `marker_targets`, strip other markers from the gap before the `_ONLY_BLANK` test. Re-convert TRA, Streaming and EMS with `--force`.

### X1-02 · S2 · `reframe --input` records merge state for the catalog version, so sync then publishes a stale merged tree as current
- **Writer:** `src/docushift/reframe/driver.py:610-618` writes `reframe_source_checksum`, `reframe_policy_key` and the rename digest for the catalog's `(slug, version)`. The checksum is `converted_from` (`:352`, passed at `:386`), whatever tree `--input` named. `cli.py:1765-1781` builds the Reframer with the catalog's state for `--input` too. `_write_origins` (`:800-819`) also builds 301.yml from the catalog version's `output_map`.
- **Reader:** `src/docushift/sync/distributor.py:347-355` (`_stale`) treats `reframe_source_checksum == convert_source_checksum` as "the merged tree under `reframed/` is current".
- **Disagreement:** `--input` merges a different tree into a different folder, but it writes the metadata that vouches for `reframed/<…>/<version>`. The docstring at `reframe/driver.py:800` (and R09's note) says an `--input` run writes no 301.yml; it writes one.
- **Failing scenario:** Run `convert --force` on EMS 10.5.1 (new checksum; `reframed/` is now stale and sync would refuse it). Then a scratch run `reframe --product ems --version 10.5.1 --input X --output Y`. Then `sync`. The old merged tree publishes with no `SYNC_MERGE_UNAVAILABLE`. A second `--input` run to the same `--output` also reports CURRENT without reading its input. The review's own "measure on a scratch copy" workflow is exactly this sequence if it runs from the main root.
- **Confirmed:** by code path only; not run against the workspace. This is theme Z (convert's `--input` writes catalog state) carried into reframe, and here it reaches publication.
- **Suggested fix:** Give reframe convert's standalone guard (R4-04): with `--input`, write no `version_metadata`, no catalog columns and no 301.yml, and never return CURRENT.

### X1-03 · S3 · Reframe's working files are published into the AEM docs tree
- **Writer:** `src/docushift/reframe/driver.py:758-779` writes `reframe.yml`, `review-queue.csv` and `rename-map.csv` at the merged tree's root. `REFRAME-REQUIREMENTS.md` placed them in a separate `manifest/` folder; the as-built note moved them into the tree.
- **Reader:** `src/docushift/sync/distributor.py:395` copies the whole version folder (`copytree`) into `online-help/<segment>/`.
- **Disagreement:** These are a writer's worklist and a pin file (the user guide says "open it in a spreadsheet"), not published pages. Sync has no exclusion list, so every merged version ships them, source topic paths included.
- **Failing scenario:** `C:\tmp\p35-aem\en-us-tib-ems-userdocs\en-us\tibco-enterprise-message-service\online-help\10-5-1\` holds `reframe.yml` (225 KB), `rename-map.csv` and `review-queue.csv`.
- **Confirmed:** yes. 36 files (12 merged versions × 3) in `C:\tmp\p35-aem`. Not confirmed: whether AEM ingests non-page files. Rate it S1 if AEM does.
- **Suggested fix:** Have sync skip reframe's working files (`reframe.yml`, `review-queue.csv`, `rename-map.csv`) when it places `online-help`, or have reframe write them beside the version folder.

### X1-04 · S3 · Reframe throws away the heading fragment that convert now writes into csh.yml
- **Writer:** `src/docushift/converter/driver.py:425-430`. Since R8-04, each csh.yml fragment is the heading slug the marker belongs to.
- **Reader:** `src/docushift/reframe/csh.py:86-108` (`_value`) drops the fragment unconditionally and uses the topic's section anchor. Its Phase 29 rationale, "the fragment is an unreachable marker", stopped being true with R8-04. The link path (`reframe/pages.py:270-271`, R9-02) already keeps a fragment that names a heading.
- **Disagreement:** Convert's contract is now "fragment = heading slug"; reframe still reads it as "fragment = dead marker".
- **Failing scenario:** In `reframed/` TRA Runtime Agent 5.13.0, all eight `aa.txcontrolpool.*` identifiers point at `…/transaction-control-and-advisory-reference.md#transaction-controls`, while `output/` gives five distinct sections.
- **Confirmed:** yes (`a/csh2.py`). 27 of 108 identifiers (Runtime Agent 5.13.0) and 6 of 46 (Administrator 5.13.0) lose their section in the merged tree. Not published today: TRA is `publish: false`, and EMS and ActiveSpaces have no csh.yml.
- **Suggested fix:** In `_value`, resolve the fragment with `page.heading(source, fragment)` and fall back to the section anchor, as `pages.py:270` does. Fix X1-01 first, or the wrong section is carried over.

### X1-05 · S3 · Reframe's toc.yml rewrite ignores the converted entry's fragment
- **Writer:** `src/docushift/converter/navigation.py:463-466` writes `doc.md#anchor` for section entries; AA (batch 3) keeps them in Flare and WebWorks.
- **Reader:** `src/docushift/reframe/toc.py:103-110` parses `fragment`, and `:186-195` (`_node`) never uses it. It emits `page.md` or `page.md#<topic anchor>`, and the packer claims entries by path only.
- **Disagreement:** A converted TOC entry can now point at a section; the merge collapses it onto its topic's head.
- **Failing scenario:** A Flare TOC with `a.md#s1` and `a.md#s2` as two entries yields two merged rows pointing at the same anchor.
- **Confirmed:** latent (`a/toc*.py`). In all 14 reframed versions no two converted entries share a path, and every Flare fragment (TRA 637 and 419) is the page's first heading.
- **Suggested fix:** In `_node`, map `entry.fragment` through `page.heading(entry.path, fragment)` when present.

### X1-06 · S3 · A rename-map.csv saved by Excel as ANSI stops the whole reframe run
- **Writer:** `src/docushift/reframe/renames.py:112` writes through `csvio.write_rows` (UTF-8 with BOM, CRLF). A human then edits `new_path` in Excel, as the user guide prescribes.
- **Reader:** `src/docushift/reframe/renames.py:116-131` (`load`) catches only `OSError`. Its call in the currency check, `reframe/driver.py:363`, sits outside the `try` at `:385-391`.
- **Disagreement:** `load` promises that "unreadable or malformed means no overrides". A non-UTF-8 file raises `UnicodeDecodeError` out of `reframe_one`, which is documented never to raise, and `reframe_many` (`:996`) stops at that version.
- **Failing scenario:** Saved as "CSV (Comma delimited)", i.e. cp1252, every one of the 14 real maps fails at the first `™`. TRA Runtime Agent 5.13.0 holds 116 non-ASCII characters.
- **Confirmed:** partly. A cp1252 copy (`b/cp/`) raised `UnicodeDecodeError` in `read_rows` at byte 0x99. Not confirmed: that the user's Excel saves cp1252. This overlaps X2 (CSV encoding round-trips). The catalog CSVs share the reader (`csvio.read_rows`); left to X2.
- **Suggested fix:** Catch `UnicodeDecodeError` and `csv.Error` in `load` and fail that one version, naming the file. Do not fall back to `{}`, which would silently move pinned URLs.

### X1-07 · S3 · A pin whose `old_path` no longer leads a page is dropped and erased from rename-map.csv, silently
- **Writer:** `src/docushift/reframe/renames.py:84-107` rebuilds the file from this run's pages only.
- **Reader:** `src/docushift/reframe/packer.py:790-795` looks pins up by the leading topic's converted path.
- **Disagreement:** A pin is keyed on a converter output path, which lasts only as long as one conversion's naming and packing. An unmatched pin is neither applied nor counted as `RENAME_MAP_REFUSED`. The next write deletes it.
- **Failing scenario:** A re-convert renames a Flare topic (as R4-12 and R5-06 moved paths in batch 2), or a `reframe.yaml` change gives a page a different leading topic. The hand-chosen URL reverts and no finding is raised. The same happens to every pin if the header row is damaged.
- **Confirmed:** no, it is a mechanism only. All 14 current maps' `old_path` values are in `output_map` or are generated pages, and the TRA 5.13.0 pins are applied (`b/rm.py`).
- **Suggested fix:** Count pins that matched no page under a new code, and carry those rows forward rather than deleting them.

### X1-08 · S3 · 301.yml depends on the Coveo cache and origin-urls.yaml, but neither convert's nor reframe's currency key includes them
- **Writer:** `src/docushift/converter/driver.py:466-488` and `reframe/driver.py:783-819` build 301.yml from `config.load_origin_urls()` and `origins.page_list(cache_dir, …)`.
- **Reader (currency):** `converter/driver.py:243-266` and `reframe/driver.py:352-365` key only on checksums, prefix, engine, policy and the rename digest.
- **Disagreement:** After `catalog sitemap` or an `origin-urls.yaml` edit, both stages report CURRENT and keep the old 301.yml, or none. A CURRENT run records no `ORIGIN_*` finding, so the gap stays silent until someone runs with `--force`. The user guide says to run `catalog sitemap` first, and not that a re-run needs `--force`.
- **Confirmed:** not biting today. Every converted or merged version with a cached page list has a 301.yml; the 9 without one have no list.
- **Suggested fix:** Add a digest of the version's declaration and page list to both currency keys, or regenerate 301.yml on the CURRENT path, which is cheap.

### X1-09 · S3 · Two stages read the docsite folder from two places: origins from the `zip_url` column, the downloader from `folder_path`
- **Writer:** discovery writes `versions.csv` `zip_url` (`crawler`) and `version_metadata.folder_path`, the latter only when the record declares 2 segments (`crawler.py:354`, via `cli.py:369`).
- **Readers:** `src/docushift/downloader/fetcher.py:167-187` ignores the active column and derives the URL from `folder_path`, else `product_code/version`. `src/docushift/origins.py:121-138` (`folder_path`), called with `version.zip_url` at `converter/driver.py:482` and `reframe/driver.py:812`, reads the column. Its docstring says the column is "the URL the downloader actually fetched", which `fetcher.py:162-165` says it is not.
- **Disagreement:** For an active version, the folder 301.yml rows are built under can differ from the folder the package came from.
- **Failing scenario:** On `tibco-control-plane` 1.3.0–1.9.0, origins uses `platform-cp/1.9.0/doc/zip` while download uses `platform-cp/1.9.0`. On `tibco-foresight-icd-10-conversion-adapter` 1.2.0/1.3.0, origins uses `foresight/foresight-icd/1.3.0` and download uses `foresight/1.3.0`. A declared template with `{folder_path}` writes wrong `from` URLs; a derived one fails to match and reports `ORIGIN_TEMPLATE_UNDECLARED`.
- **Confirmed:** yes, for the disagreement: 11 of 2,103 active rows differ. 0 of them are converted, so no 301.yml is wrong today. Which side is right for those 11 is unconfirmed (no network).
- **Suggested fix:** Give origins the downloader's folder (`folder_path` metadata, else the same fallback) through one shared helper, and correct the docstring.

### X1-10 · S3 · A partial extract walk blanks the CSV columns but records `csh_source` and `api_roots` from the partial walk, and later stages trust them as complete
- **Writer:** `src/docushift/extractor/unpacker.py:419-426` writes `csh_source`, `asset_inventory` and `api_roots` before the partial check at `:431`. The `INVENTORY_PARTIAL` message (`:436`) says only that "the five inventory columns were left blank".
- **Readers:** `converter/driver.py:1000-1013` uses the recorded help maps and falls back to a walk only when there are none. `converter/driver.py:931-932` and `sync/distributor.py:674-675` use the recorded API roots.
- **Disagreement:** The columns follow R3-04's rule that a partial measurement is no measurement; the three state records, which drive conversion, do not.
- **Failing scenario:** An unreadable folder hides one Flare root's `Alias.xml`. Convert resolves only the recorded maps, the hidden root's identifiers are missing from csh.yml, and no CSH finding names them.
- **Confirmed:** no. 0 `INVENTORY_PARTIAL` findings in `state.db`.
- **Suggested fix:** On a partial walk, delete the version's `csh_source` and `asset_inventory` rows and its `api_roots` key, so readers fall back to their own walk. Say so in the finding.

### X1-11 · S3 · A corrupt Coveo `manifest.json` stops the whole reframe run, and "no leaf" cannot be told from "file missing"
- **Writer:** `catalog sitemap` writes `cache/coveo/manifest.json` and the leaf XML files.
- **Reader:** `src/docushift/origins.py:336-339` (`page_list`) catches only `SitemapError`. `discovery/sitemap.py:207` (`json.loads`) raises `JSONDecodeError`, which `reframe/driver.py:390` (`OSError, UnicodeDecodeError`) does not catch. Convert catches `Exception`, so there only that version fails. `sitemap.py:237-243` returns `None` both for "no leaf matched" and "leaf file missing".
- **Disagreement:** `page_list`'s docstring says "an unreadable cached file is the same as no list". For the manifest it is not, and the two `None`s produce one vague `ORIGIN_SITEMAP_MISSING`. For a declared product, the confirm and unmapped checks are skipped with no note.
- **Confirmed:** no. The manifest is written atomically and parses today.
- **Suggested fix:** Catch `ValueError` and `OSError` in `page_list`, and return a reason with the `None` so the finding can name it.

### X1-12 · S3 · `sync --dry-run` reports the `output/` tree for products that publish from `reframed/`
- **Writer of the decision:** `src/docushift/sync/distributor.py:291-331` (`_source`): `publish: true` means publish `reframed/`, or refuse when it is missing or stale.
- **Reader:** `src/docushift/cli.py:1932` and `:1950`. The dry run's "Converted" column always tests `output_path`.
- **Disagreement:** The preview and the run decide "which tree publishes" separately.
- **Failing scenario:** EMS or ActiveSpaces (`publish: true`) with a stale or missing merge: the dry run says "present", and the real run refuses with `SYNC_MERGE_UNAVAILABLE`.
- **Confirmed:** by code. Both products are `publish: true` in `config/reframe.yaml`.
- **Suggested fix:** Have the dry run call `distributor._source` and show its refusal text.

### X1-13 · S4 · A command run outside the project root builds a fresh workspace and state.db, so `validate`'s run is invisible to the project's `report`
- **Writer:** `src/docushift/config.py:244-270` creates `cache/`, `families/` and `output/` under `--root` or the cwd. `cli.py:2058` (`validate`) and `:2479` (`csh validate`) record runs into `cfg.state_db_path`.
- **Reader:** `cli.py:2693` (`report`), run from the real root.
- **Disagreement:** Nothing checks that `config/` exists before writing state, so the location of `state.db` silently follows the cwd.
- **Confirmed:** by code (R12's note).
- **Suggested fix:** Refuse to start when `config/products.csv` is absent, except for `validate`, which should then skip recording.

### X1-14 · S4 · toc.yml and csh.yml paths are written raw; validate decodes toc.yml paths but nobody else does
- **Writers:** `converter/navigation.py:466`, `reframe/toc.py:195` and `transforms/csh.py:267` write raw relative paths. Page bodies are encoded.
- **Readers:** `validation/artifacts.py:166-171` decodes through `transforms/links.py:91`. `reframe/toc.py:103-104`, `converter/driver.py:776-790` and `validation/csh.py:150` read raw.
- **Disagreement:** A filename containing `%xx` would be a false `LINK_BROKEN` in toc.yml but pass in csh.yml. A `#` or `?` in a name breaks every reader.
- **Confirmed:** latent. 0 of 24,143 `.md` names under `output/` and `reframed/` contain a space, `%`, `#` or `?`.
- **Suggested fix:** Pick one rule (raw is the de-facto one) and make the validator follow it, or refuse those characters in output names.

### X1-15 · S4 · The root lists' `""` ("measured, none") and a missing key read the same everywhere
- **Writer:** `src/docushift/extractor/unpacker.py:384-395` and `:423-426` write `""` deliberately, and their comment says Stages 5 and 7 trust the recorded list over a re-walk.
- **Readers:** `apiref.py:99` returns `[]` for both. `converter/driver.py:932`, `engines/base.py:442` and `sync/distributor.py:675-677` then re-walk.
- **Disagreement:** The distinction R3-05's fix introduced is not consumed, and the docstrings at `converter/driver.py:918-921` and `apiref.py:153-154` overstate the contract.
- **Confirmed:** harmless today. Convert and sync recomputed for all 54 extracted versions give identical API roots (`roots.py`). The backslash separators are R3-13.
- **Suggested fix:** Have `recorded_roots` return `None` for a missing key, and make the re-walk conditional on `None`.

### X1-16 · S4 · `publishing_problems` checks only declared families for shared folders
- **Writer:** `src/docushift/catalog.py:299-300` lowercases `family`. `config.py:283-297` (`repo_slug`) slugifies an undeclared family to its folder token.
- **Reader:** `src/docushift/config.py:578-589` compares tokens of `self.families(bu)`, which holds declared families only.
- **Disagreement:** Two undeclared families that slugify alike (`data management`, `data_management`) share one workspace and one publishing repo with no problem reported.
- **Confirmed:** no collision today: 45 (bu, family-slug) groups over `products.csv`, none with two spellings.
- **Suggested fix:** Iterate the families in use in `products.csv`, not only the declared ones.

## Contract table

| artifact / column | writer | readers | agreed? |
|---|---|---|---|
| `products.csv` slug, bu, family, family_source, in_scope, custom_override | `catalog.py:386-401` (save), humans | `catalog.py:286-309` (load), `config.py` paths, `iter_versions` | yes (unknown tokens: R2-11, deferred) |
| `versions.csv` is_archived, convert_eligible, release_status (gates) | `catalog.py:404-438` | `catalog.py:494-541` `iter_versions` | yes |
| `versions.csv` release_date | crawler → `normalize_date` | `converter/driver.py:650`, `sync/versions.py:66`, `sync/archives.py:106` | yes (theme E) |
| `versions.csv` zip_url (active) | crawler | `origins.py:121` (all rows); `fetcher.py:167` (archived only) | **no: X1-09** |
| `versions.csv` engine, engine_source | `catalog.record_detected_engine` `:1082` | `engine_for`, `convert_engine` key, reframe gate, router | yes |
| `versions.csv` `_has_csh` … `_doc_files` | `catalog.py:1092` via `unpacker.py:440` | `unpacker.py:231`, `:334`; `cli.py:1431` | yes (theme G) |
| `versions.csv` `_md_files`, `_out_files`, `_reframed_*` | convert `driver.py:509`, reframe | each stage's CURRENT path, `cli.py` totals | yes |
| `version_state` status, error, paths | fetcher, unpacker, converter | `unpacker._settle`, `fetcher.py:241`, `state.progress` | yes (absolute paths: R3-10, deferred) |
| `extract_zip_checksum` | `unpacker.py:271`, `:288` | `unpacker.py:220`, `converter/driver.py:243` | yes (Phase 21 limitation known) |
| `output_roots`, `api_roots` | `unpacker.py:392`, `:423` | `apiref.recorded_roots` → `converter/driver.py:321`, `:931`; `sync/distributor.py:674`; `engines/base.py:442` | values yes (54/54); `\` is R3-13; `""` vs absent is X1-15 |
| `content_root` | `unpacker.py:197` | `converter/driver.py:962`, `sync/distributor.py:241` | yes |
| `convert_source_checksum`, `convert_api_prefix`, `convert_engine` | `converter/driver.py:446-453` | `converter/driver.py:243-266`, `reframe/driver.py:352`, `sync/distributor.py:348` | yes (BB: R10-06) |
| `reframe_source_checksum`, `reframe_policy_key`, `reframe_rename_digest` | `reframe/driver.py:613-618` | `reframe/driver.py:352-365`, `sync/distributor.py:347-355` | **no under `--input`: X1-02** |
| `folder_path` | `crawler.py:354` via `cli.py:369` | `fetcher.py:182` | 2 segments only: X1-09 |
| `zip_origin_path`, `engine_generator_raw`, `docsite_slug`, `docsite_id` | `fetcher.py:451`, `unpacker.py:389`, `crawler.py:291-293` | none | write-only (cleanup) |
| `csh_source` | `unpacker.py:419` | `converter/driver.py:1001` | yes; partial walk is X1-10 |
| `asset_inventory`, `engine_folder_map` | unpacker | none | write-only (R3-14, R4-10) |
| `output_map` | `converter/driver.py:441` | `reframe/driver.py:813` → `origins.rows`; `state.progress` | yes, POSIX, 0 backslashes; `--input` rows are theme Z |
| `resolved_snapshot`, `*_snapshot` | `catalog` merge / `state.py:367-447` | `catalog.py:669`, `:837`, `:887`, `:937` | yes (`_as_text` normalizes bools and dates) |
| `findings` stage, version | every stage | `report`, `status` | stage = the code's registered stage by design; version dashed for validate only, never joined |
| `families/` → `output/` → `reframed/` paths | `config.py:347-433` | every stage, through `config` | yes; 0 version-segment collisions per product across the catalog (`seg.py`) |
| toc.yml (`docs_list_title`/`docs`/`title`/`url`/`subfolderlist`) | `navigation.py:433`, `reframe/driver.py:757` | `reframe/toc.py`, `validation/artifacts.py:133-171`, `converter/driver.py:776` | keys yes; fragment X1-05; encoding X1-14 |
| csh.yml (identifier → `path#anchor`, version-root relative) | `transforms/csh.py:267` via `converter/driver.py:430`; `reframe/driver.py:770` | `reframe/csh.py:63`, `validation/csh.py:106` | shape yes; anchor meaning **no: X1-01, X1-04** |
| metadata.yml (`csg-version` dotted, `csg-product` = display_name) | `converter/driver.py:564`; `sync/distributor.py:517`, `:632`, `:747`, `:777` | `validation/artifacts.py:_check_metadata` | yes; reframe copies convert's unchanged (14/14 identical) |
| version.yml (`versions: [{title, path:"/<segment>"}]`) | `sync/versions.py` via `distributor.py:808` | `validation/artifacts.py:check_dropdown` (same `parse`) | yes (archived rows: BA) |
| 301.yml per version (`from` encoded, `to` raw `.md`) | `origins.write` via `converter/driver.py:488`, `reframe/driver.py:819` | sync assembly; validate (R11-05, BC) | yes: 33,795 rows all resolve; lifetime X1-08; `--input` X1-02 |
| redirects.yml | `reframe/driver.py:764` | `sync/redirects.py`, `validation/artifacts.py:208` | yes (same `located` map as 301 `moved`) |
| rename-map.csv | `renames.py:112` | `renames.load` `:116`, `digest` | BOM, CRLF and columns agree; encoding X1-06; key lifetime X1-07. `expected_aem_url` uses `primary_locale` (`reframe/driver.py:715`) where sync uses `config.locale`: equal for en-us only |
| review-queue.csv, reframe.yml | reframe | humans only | published by sync: X1-03 |
| Coveo cache | `catalog sitemap` | `origins.page_list` | X1-11 |

## Checked and fine

- **Root lists, convert vs sync.** For all 54 extracted versions, the converter's output/API root resolution and sync's API root resolution give identical lists (`roots.py`), so cross-tree API links and published `api-references/` folders agree.
- **Published version segments.** `version_segment` yields no collision inside any product across all of `versions.csv`.
- **output_map and csh_source path forms.** POSIX and tree-relative on both sides, with 0 backslashes, as are `asset_inventory.output_root` (601 rows) and `content_root` (48 rows). Only the two root lists use `\` (R3-13).
- **bu values.** No code compares `bu` to a literal business-unit name; publishing tokens come from `taxonomy.yaml` or `slugify`.
- **HTTP status.** Every `build_session` caller checks `status_code`.
- **metadata.yml, version.yml, redirects.yml.** Key names, levels and version forms agree between writers and `validate`. The version-level `csg-version` is dotted at every writer.
- **csh.yml after R8-04.** In `output/`, 0 dead fragments in TRA 5.13.0 (81 + 27, 40 + 6), apart from X1-01's wrong-section cases. WebWorks Runtime Agent 5.12.x still has 1 dead and 18 bare identifiers per version. That is the engine's side, not a contract issue.
- **301.yml.** Every `to` in `output/` is an `output_map` output; every row across `output/` and `reframed/` (33,795) points at an existing page and anchor. Sync's `published()` encodes `to` and swaps `.md`→`.html`; `disk_candidates` reverses both.
- **Navigation titles.** Blank DITA and Flare unit titles fall back to the landing title; no raw subtree stem appears as a top-level label.
- **Catalog merge base.** Snapshots store text; `_as_text` and the `release_date` normalization make the comparison like-for-like.

Not checked: whether AEM ingests non-page files (X1-03); which of the two folders is live for the 11 X1-09 rows (needs the network); Excel's actual save encoding (X1-06). Nothing was run against the main workspace.
