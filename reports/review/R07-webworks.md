# R7 — WebWorks engine: findings

Base: review-base-b3 (a976513) · Reviewed: `src/docushift/engines/webworks.py`, `src/docushift/engines/webworks_toc.py`, `tests/unit/test_webworks.py` · Date: 2026-10-04

| S1 | S2 | S3 | S4 |
|---|---|---|---|
| 4 | 0 | 6 | 1 |

How it was measured. I ran the frozen engine as a library, with an in-memory `FindingsRun` and no state store, writing only under `C:\tmp\review-R7\`. Inputs were the 13 WebWorks versions in `families/en-us-tib-tra/extracted` (TRA 5.12.2/5.12.3/5.12.4, Administrator 5.12.2/5.12.4, Designer Add-in 1.0.0–1.5.0) and a seeded random sample of 30 of the 195 WebWorks versions in `html-to-md/cache/pub`. Raw-text scans covered all 691 corpus books. Output claims were checked against `output/en-us-tib-tra`. The 77 unit tests pass.

## Findings

### R7-01 · S1 · TOC entries that point into their parent's page are deleted, uncounted: nearly half of every WebWorks TOC
- **Where:** `src/docushift/engines/webworks.py:1318-1319` (`_node`). The rule is copied from `engines/flare.py:704-706`.
- **What:** a child node whose page is the parent's page is filtered out whatever its `anchor` is, so every anchored section entry ("Installation Modes" → `5#1812329` under "Installation Modes and Disk Space" → `5`) disappears from the navigation, with no count and no finding.
- **Failing scenario:** TRA 5.12.2 `TIB_TRA_installation/wwhdata/js/toc.js` lists "Installation Modes" and "Disk Space" as children of "Installation Modes and Disk Space". In `output/.../tibco-runtime-agent/5.12.2/toc.yml:265-266` that node has no children. `toc.yml` for all 13 WebWorks TRA versions contains **0** `#fragment` URLs.
- **Confirmed:** yes.
  - Corpus `toc.js`: **32,927 of 68,965 entries (47.7%)** are children on their parent's page, and 5 descendants go with them.
  - TRA, through the engine: 3,055 TOC entries → 1,445 nav nodes. **1,578** were dropped silently (all anchored). Only 32 were reported (`NAV_NODE_DROPPED`).
  - The Phase 5 rule was measured on 30 un-anchored Flare duplicates (`architecture.md:958`). `NavNode.anchor` was added so that same-page children stay distinguishable (`phase-05.md:110`). The `NAV_NODE_DROPPED` register text (`reporting/findings.py:129-131`) claims the same-page child is counted; neither engine counts it.
- **Suggested fix:** drop a same-page child only when it has no anchor (or the parent's anchor). Keep anchored ones. The driver already retargets `toc.yml` fragments onto headings (`converter/driver.py:619-646`). Check the Flare copy of the line at the same time (R5 did not report it).

### R7-02 · S1 · Ordered lists render with the wrong step numbers
- **Where:** `webworks.py:606-612` (a kind change at the same depth opens a new list), `webworks.py:647-654` (`_list_depth`). The renderer always counts from 1 (`transforms/markdown.py:277`), and `_build_list` never carries the first marker's ordinal.
- **What:** a procedure is split, and each fragment restarts at 1, whenever a different list kind sits at the same computed depth. This happens in two cases:
  - `Step 1` → `Bullet` items → `Step 2`, all "depth 0".
  - A kind whose depth `_list_depth` misreads: `Unorderedlist2`, `Orderedlist21`, `ListDash2` and `ListDash3` have no underscore, so they read as level 0.
  It also happens whenever a run that the bridge cannot join opens on a marker other than 1.
- **Failing scenario:**
  - TRA 5.12.2 `TIB_TRA_installation/install.3.07.htm`: the source reads "1. Open… • TIBCO Runtime Agent • TIBCO Rendezvous 2. Extract… 3. Navigate…". `output/.../install.3.07.md:31-41` renders "1. Open… - … 1. Extract… 2. Navigate…", so every later step is off by one.
  - Administrator 5.12.2 `install.2.08.htm`: "8. Click Next" renders as "1." (`install.2.08.md:43`).
- **Confirmed:** yes, by tagging each item with its source marker and comparing it with the rendered position.
  - TRA 13 versions: **214 of 5,717 numbered items (3.7%) in 77 lists** render with a number other than the source's.
  - 30-version corpus sample: **518 of 12,068 (4.3%) in 255 lists**.
- **Suggested fix:** carry the first marker's ordinal as `<ol start>` and have the renderer honour it. Also nest a same-depth run of another kind under the preceding ordered item when the next ordered marker continues its numbering. Read a trailing digit without an underscore as depth too.

### R7-03 · S1 · Headings in the `Heading_N` and `NoTOC` vocabularies come out as body paragraphs
- **Where:** `webworks.py:109` (`_HEADING_CLASS = ^N(\d)(?:Heading|Syntax)$`), `webworks.py:1498-1502`.
- **What:** only `N<d>Heading`, `N<d>Syntax`, `MinorHead` and `Block-title` are headings. Templates that spell headings differently lose every heading on the page, including its `#` title, and nothing reports it.
- **Failing scenario:** `activematrix-adapter-for-osisoft-pi/1.0.0-november-2012/.../tib_adpi_concepts/AdapterComponents.htm`, `<div class="Heading_1">Adapter Components</div>`, renders as the plain line `Adapter Components` with no heading.
- **Confirmed:** yes (rendered through the engine). Corpus topics carrying each class:
  - `Heading_1` **713** (loyalty 528, osisoft-pi 161, 3 more products)
  - `Heading_2` 277
  - `Heading_3` 113
  - `N2HeadingNoTOC` **522** in 94 products (mostly the "Important Information" title of `copyrigh.htm`)
  - `N3HeadingNotInTOC` 23
  - `N2HeadingTOC` 25 elements
  - With no headings on the page, `_retarget_fragments` cannot place any fragment there either.
- **Suggested fix:** widen the class rule to `^(?:N(\d)Heading\w*|Heading_(\d))$` (and `N\dSyntax`), with a test per spelling. Decide separately whether `StepHead`/`ResetStepHead` (799/715 topics) and `AnchorSideHead` (1,459 topics) are headings or bold labels.

### R7-04 · S1 · A version with two collections is named after whichever sorts first, and the collection and BookGroup structure the engine records is never used
- **Where:** `webworks.py:1019` (collections taken in path order), `webworks.py:1407-1421` (`_metadata`). On the consumer side, `converter/navigation.py:491-500` (`_version_label` takes the first `collection_name`). Nothing reads `collection`, `book_group`, `book_order` or `book_title`.
- **What:** TIBCO Runtime Agent ships a `designerhelp/` and a `trahelp/` collection. The version index is titled from `designerhelp` because it sorts first, and the six TRA books sit flat under a node called "TIBCO Designer". Separately, §5.3.3's "emit a BookGroup level when a collection declares more than one" never happens.
- **Failing scenario:** `output/en-us-tib-tra/tibco-runtime-agent/5.12.2/toc.yml:5` and `index.md` show `title: "TIBCO Designer"`, followed by "Installation Guide", "Installing into a Cluster" and the other TRA books. 5.12.4 is the same.
- **Confirmed:** yes.
  - TRA 5.12.2 and 5.12.4 are the only corpus versions with two genuine collections. The other three are R4-01's byte-identical duplicates.
  - **14** corpus collections declare more than one BookGroup, and none gets its level.
- **Suggested fix:** in navigation, add one level per collection when a version has more than one (label `collection_name`, order as declared), and one per BookGroup when `book_group` is set. Otherwise fall back to the catalog's product name rather than the first collection. The fix belongs in `navigation.py` (R4's module). The engine side is complete.

### R7-05 · S3 · A `CodeLine` holding a cross-reference loses the link inside the fence, and the loss is not counted
- **Where:** `webworks.py:517-524` (`_coalesce_code` builds the `<pre>` from `markdown.text_of`, so the renderer never sees the `<a>` and `flattened_links` stays 0).
- **What:** Phase 8's rule is "a fence cannot hold a link, so count the ones it swallows". Here the swallowing happens before the counter can see it.
- **Failing scenario:** `activematrix_service_performance_manager/1.3.0_oct_2010/.../spm_install/install.3.20.htm`. A prose `CodeLine` ends "Refer `WWHClickedPopup('spm_install','install.3.8.htm#1820330')` Create New Administrator Server". The output fence reads "Refer Create New Administrator Server." with no link and no count.
- **Confirmed:** yes. **1,124** corpus code lines contain a popup or a relative href.
- **Suggested fix:** count the `<a href>` in a run before it is flattened and add the count to `renderer.flattened_links`. Optionally, emit a run whose lines are prose with links as paragraphs rather than a fence.

### R7-06 · S3 · `index_2.htm` / `index_3.htm` frameset stubs raise false `CONTENT_MISSING` warnings
- **Where:** `webworks.py:1125-1127` (`STUB_STEMS` matched on the first dot segment, so `index_2` is not `index`).
- **What:** WebWorks 2006 runtime stubs named `index_N.htm` are treated as topics. They convert to nothing and each one is reported as a warning.
- **Failing scenario:** `activematrix-adapter-service-engine-for-lotus-notes/6.0.0-november-2009`: `CONTENT_MISSING tib_adlnse_install/index_2.htm "converted to nothing"`, and five more like it.
- **Confirmed:** yes. **20** such files corpus-wide, all of them frameset launchers (`WWHHelpFrame_LaunchHelp`).
- **Suggested fix:** match `^(index|wwhsec)([_-]\d+)?$` on the stem, and count them under `runtime-stub`.

### R7-07 · S3 · Every book's cover page is filed under an "Unfiled" branch
- **Where:** `webworks.py:1288-1298`. `title.*` is deliberately converted (`webworks.py:41-46`).
- **What:** `title.htm` is in `files.js` but never in the TOC, so each book publishes an "Unfiled" node whose only child is the cover (product, guide name, version, date). §5.3.5 says front matter is "dropped, not filed".
- **Failing scenario:** the 13 TRA WebWorks versions publish **32 "Unfiled" branches**. 24 of their 38 children are `title.md`, and 18 branches hold nothing else.
- **Confirmed:** yes, but it is reported (`TOC_ORPHAN`, a note), so this is navigation noise rather than loss.
- **Suggested fix:** decide the policy (drop `title.*`, or make it the book's landing page), then align either the code or §5.3.5.

### R7-08 · S3 · `ListContinue` attaches to the deepest open item, whatever its class says
- **Where:** `webworks.py:595-597`.
- **What:** `ListContinue` (level-1 continuation) and `ListContinueIndent` (level-2) are treated alike. After a nested `StepInd`/`ListDash` item, a `ListContinue` is indented under the sub-item rather than the outer step.
- **Failing scenario:** Administrator 5.12.2 `admin_server.4.013.htm`: "On UNIX systems, kill the above processes." follows a nested item and is placed inside it.
- **Confirmed:** unconfirmed as wrong. **64** such paragraphs in the 38 family books (against 1,364 that follow a top-level item). Which level the author meant was not checked visually.
- **Suggested fix:** attach `ListContinue` to the innermost level of depth ≤ 0 (relative to the base) and `ListContinueIndent` to depth ≤ 1.

### R7-09 · S3 · Runtime-reader failures are silent or misattributed
- **Where:**
  - `webworks_toc.py:250-252`, `343-345` and `302-304`, with `webworks.py:1149-1154`: an unreadable `files.js`, `toc.js`, `title.js` or topic returns empty, and nothing is recorded.
  - `webworks.py:1083-1091`: the stripped-book line is filed as `NAV_NODE_DROPPED` and says "no wwhdata/js/toc.js", while the test is the absence of `files.js`.
- **What:** an unreadable `files.js` turns every TOC node into "no page and no children" and every topic into an orphan, and the cause is never named. `read_text`'s docstring says "every caller already reports [None] as CONTENT_MISSING", but only `_convert` does.
- **Failing scenario:** for example, a `files.js` locked or truncated on disk yields a `NAV_NODE_DROPPED` count and an "Unfiled" branch holding the whole book.
- **Confirmed:** n/a. The corpus has 0 unreadable runtime files (all 1,938 `files.js`/`toc.js`/`title.js` are valid UTF-8). The stripped-book message misnames the file for all 45 stripped books.
- **Suggested fix:** record a dedicated warning when a present runtime file yields nothing, and give the stripped-book case its own code or at least the right filename.

### R7-10 · S3 · Popup book names resolve first-wins across the version
- **Where:** `webworks.py:1061-1062` (`index.by_key.setdefault`). The popup's own book is not preferred (`webworks.py:402`, `1165`).
- **What:** when two books share a directory name or a `context.js` key, every popup naming that key, including same-book popups from the second copy, resolves into the first copy.
- **Failing scenario:** `loyalty/16.1.0`: popups in `html_v3/integration` link into `html/integration`.
- **Confirmed:** yes, but harmless today. **10** colliding aliases in 5 versions, all of them R4-01's duplicate copies (`loyalty/16.1.0` `html` vs `html_v3` are byte-identical). Once R4-01 drops duplicates, nothing collides.
- **Suggested fix:** resolve against the popup's own book first, then the version map, and report an ambiguous key.

### R7-11 · S4 · Cleanup
- `webworks.py:755-772`: `_runs(..., continues=)` is never passed `continues`. `_list_runs` replaced that use.
- `webworks.py:749-752`: `_is_heading` re-lists h1–h6 instead of reading `_REAL_HEADINGS`.
- `webworks.py:941-945`: `title_of` rebuilds its map on every call for a book with an empty file list.
- `webworks_toc.py:287`: `.lstrip("./")` strips a character set, not the `./` prefix. It is harmless for current hrefs, but `removeprefix` says what is meant.

## Edge notes (for X1)
- **`Document.anchors` is not the set of anchors in the body.** It is `renderer.emitted` (`webworks.py:1269`). It omits `<a name>` markers that the shared walk emits for `<a name href>`, which are the WebWorks footnotes: 580 `wwfootnote_inline_*` in 301 topics. It also omits anchors kept in passthrough tables. In the 30-version sample, 241 of 9,914 referenced anchors are in the body but not in the set. Same shape as R5-14. Any consumer that treats it as complete will report false misses.
- **`NavNode.anchor` never reaches the driver for WebWorks**, because of R7-01. `_retarget_fragments`' `toc.yml` branch has nothing WebWorks to work on (0 fragments in TRA's WebWorks `toc.yml`).
- **`Unit.metadata`:** only `collection_name` is consumed, first-wins (`navigation.py:497`). `collection`, `book_group`, `book_order` and `book_title` are produced and unread (R7-04).
- **Popup resolution depends on R4-01:** `by_key` is first-wins, so duplicate books must be removed before units are scanned (R7-10).
- **Support/legal:** every book reports its own pair (`_tail`). `navigation._tail` keeps the first unit's and drops the rest as `NAV_NODE_DROPPED`. This is documented at `navigation.py:26-34` and is consistent.
- **Coordinates:** the index is built in `units()` before the driver sets `subtrees`, and `_topic` completes the output path lazily. Verified on TRA output: links between named units and the root book are correct, so the Phase 17 contract holds.
- `units()` returns `[]` with `OUTPUT_ROOT_MISSING` (R4-06 covers the driver side).

## Test gaps (real-data paths only)
- No test where a child TOC entry carries an anchor into its parent's page (R7-01: 47.7% of corpus entries).
- No test for `Step` → `Bullet` → `Step` at the same depth, for a list whose first marker is not 1, or for `Unorderedlist2`/`ListDash2` kinds (R7-02).
- No test with two collections in one version, or one asserting the BookGroup level reaches `toc.yml`. `test_two_book_groups_are_carried_into_the_metadata` stops at the metadata (R7-04).
- No test for the `Heading_N` / `N2HeadingNoTOC` spellings (R7-03).
- No test for a `CodeLine` containing a `LiveLink` (R7-05), or for an `index_2.htm` stub (R7-06).
- No test for footnotes (`<a name href>`) and what `Document.anchors` reports for them (edge note).

## Docs drift
- `architecture.md` §5.3.3: "The engine emits a `toc.yml` level for a `BookGroup` only when a collection declares more than one". No level is ever emitted (R7-04). "The version's `toc.yml` is the collection's books": with two collections it is the first collection's name over all books.
- §5.3.5: "Front matter is dropped, not filed". The cover page is filed under "Unfiled" in every book (R7-07). The module docstring (`webworks.py:41-46`) says the opposite of §5.3.5 on purpose. One of them should change.
- §5.3.7: "`Italic` … and `Emphasis` … → `_`". The code emits `*` (`webworks.py:337`).
- §5.3.7's heading vocabulary lists only `N?Heading`, `MinorHead`, `Block-title`, `N3Syntax` and `Chapter_inner`. `Heading_1..4` and the `NoTOC` forms are absent from both the docs and the code (R7-03).
- `webworks.py:21-25` says "a trailing `_2` is level two". True, but the corpus also writes `Unorderedlist2`, `ListDash2` and `Orderedlist21`, which read as level 0 (R7-02).
- `webworks_toc.read_text` docstring: "every caller already reports [None] as `CONTENT_MISSING`". Only `_convert` does (R7-09).
- `reporting/findings.py:129-131` (`NAV_NODE_DROPPED`): "… Flare's childless headless node and its same-page child". The same-page child is never counted (R7-01).

## Checked and fine
- **Index files:** `toc.js` indexes `files.js`. No corpus book ships `toc.js` without `files.js`, so `files.htm` is never indexed into.
- **`books.xml`:** percent-decoding resolves **602 of 602** declared books. No declaration contains a `/`, so taking collection candidates only from book parents misses nothing. Declared order is preserved.
- **Encoding:** 33,190 topics declare their charset inside the 4 KB window, 0 beyond it, and 0 declare it wrongly. All 1,938 runtime JS files are UTF-8.
- **Content container:** `body > blockquote` was found in 1,584 of 1,584 family topics, with no parser-induced fallback.
- **Anchors:** on TRA, 3,506 of 3,509 referenced-and-present anchors appear in `Document.anchors`. The rest are emitted by the shared walk (edge note). Footnote and passthrough anchors are present in the body.
- **Popups and links:** TRA has 0 `TOPIC_LINK_DANGLING`. The sample's 16 are links into API trees that my harness gave no `api_urls`, not engine defects. Cross-unit links in TRA output are bare siblings and single climbs (Phase 17 holds).
- **Images:** TRA has 1,635 resolved, 0 dangling and 0 escaped. The sample has 3,133 resolved, 3 dangling, 0 escaped and 0 case mismatches. `tpl/` is skin.
- **Tables:** 20,716 corpus content tables, none misread as layout.
- **List markers:** the `dl` markers are only `Action:`/`Explanation:`/`Source:` (18,939). The `_CHAPTER_TEXT` rule has 0 false positives outside `Chapter`/`Appendix` kinds.
- **Callouts:** 13,978 of 14,047 corpus `IconTable`s have the one-row shape `_callout` reads, and 13,987 have two cells in the first row. **Not inspected:** 12 multi-row tables, whose rows after the first `_callout` would drop, and 57 with no direct row, which fall through to the content-table path. The scan that would have named them was stopped by the time limit.
- **Code fences:** coalescing works, including `<br>` inside a `CodeLine`.
- **Tests:** `tests/unit/test_webworks.py` passes, 77 tests.
