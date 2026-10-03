# R5 — Flare engine: findings
Base: review-base (7dda975) · Reviewed: `src/docushift/engines/flare.py`, `src/docushift/engines/flare_toc.py`, `tests/unit/test_flare.py` · Date: 2026-10-04

| S1 | S2 | S3 | S4 |
|---|---|---|---|
| 7 | 2 | 6 | 1 |

How things were measured: the frozen engine was run in memory with a harness built like the driver (`C:\tmp\review-R5\harness.py`, `render1.py`, `locroot.py`) on family trees and on cache versions. The frozen DOM passes were also run over topic samples (`domscan.py`, `mergescan.py`), and the TOC and manifest readers were run over **all 937 Flare roots** in `html-to-md\cache\pub` (`tocscan.py`). "Families" means the 21 Flare roots under `families\*\extracted` (13,609 topics). "Corpus sample" means 120 random cache roots with at most 80 topics each (6,833 topics). `pytest tests/unit/test_flare.py`: 93 passed.

## Findings

### R5-01 · S1 · Localized output roots are converted into the English tree
- **Where:** `flare.py:550-557` (`_rejection` only checks the *first path segment inside* a root), `flare.py:384-393` (every root is a unit)
- **What:** A Flare root that *is* a localized build (`ja-jp/`, `de-de/`, `fr-fr/`, `es-es/`, `ja/`) is converted like any other root, into subtree `ja-jp/` and so on, with no finding.
- **Failing scenario:** `wf-wf/9.3.5` has the units `doc/en`, `doc/html/{de-de,en-us,es-es,fr-fr,ja-jp}`. The `ja-jp` unit alone converts **2,779 Japanese topics**, and `LOCALIZED_TREE_SKIPPED` is never raised. In `sfire-dsc/7.1.0` the outer root `doc/html` skips `ja/` and *reports* `LOCALIZED_TREE_SKIPPED`, while the nested root `doc/html/ja` converts the same files. The report says the opposite of what happened.
- **Confirmed:** yes. `locroot.py` on `wf-wf/9.3.5` converted 2,779 documents with Japanese titles. Corpus count from `roots.txt`: **24 non-English roots** (10 ja-jp, 4 de-de, 4 fr-fr, 4 es-es, 2 ja) in 11 versions of `wf-wf`, `wf-as` and `sfire-dsc`.
- **Suggested fix:** Treat a root whose own last segment is a locale tag as localized. Skip it at `units()` with `LOCALIZED_TREE_SKIPPED`, unless the locale is the run's locale.

### R5-02 · S1 · Step numbers restart at 1 when anything except `<pre>` or `p.ListContinue` sits between two step tables
- **Where:** `flare.py:821-860` (`_fake_list_tables` throws away the autonum number), `flare.py:895-914` (`_merge_once` merges only across `pre` and `ListContinue`); `markdown.Renderer.list` ignores `start`
- **What:** Each `AutoNumber_p_Step` table becomes its own `<ol>`. If a `div`, a note or a plain `p` separates two of them, the second list starts at 1, even though `data-mc-autonum` says `3.`.
- **Failing scenario:** `output/en-us-tib-ems/.../10.5.1/users-guide/Deploying-the-FTL-Server-Cluster.md`: source step "3. Run the FTL server executable" is emitted as `1. Run the FTL server executable.`, after two `div`s of prose.
- **Confirmed:** yes, in the real output file above. Families: **110 of 1,285** numbered items carry the wrong number, in 47 lists that restart. Corpus sample: **178 of 803** items, 94 restarting lists. No item was numbered too high (0 over-merges).
- **Suggested fix:** Carry the first row's autonum number into `<ol start=N>` and make the list renderer honour `start` (an R8 hand-off).

### R5-03 · S1 · Icon-table callouts lose their label and their admonition
- **Where:** `flare.py:265-269` (`span.autonumber` → `""`). There is no `icon_tables` pass, although §5.1.10 lists it in the inherited order.
- **What:** `TableStyle-IconTable` puts `p.IconNote data-mc-autonum="Note"` in cell 1 and the text in cell 2. Pipe-table cells are rendered inline, so `_labelled` never runs. The label span is dropped, and the note becomes a two-column pipe table with an empty header.
- **Failing scenario:** `datasynapse gridserver-manager 7.1.1 admin-guide/About_Grid_Libraries` renders as `|  |  |` / `| --- | --- |` / `|  | If the substitution is not found… |`. The word "Note" and the alert are gone.
- **Confirmed:** yes, rendered with the frozen engine (`render1.py`). Families: **79 autonum labels inside GFM-safe tables** (29 more in passthrough tables keep the text). Corpus: **6 of 120 sampled roots, 496 files** use icon tables.
- **Suggested fix:** Port the predecessor's `icon_tables` pass (a one-row icon/label table becomes a callout div before rendering), or have pipe cells re-emit `data-mc-autonum` labels.

### R5-04 · S1 · Colspan section-heading cells are flattened to bold text, losing links, code and paragraphs
- **Where:** `flare.py:958-975` (`_heading_paragraph`, the `len(text) <= 60` branch)
- **What:** A full-width row whose text is 60 characters or fewer is rebuilt from `get_text`. Only anchor targets are carried over. Links, `<code>`, images and the paragraph break are discarded.
- **Failing scenario:** EMS `c-and-cobol-reference/tibemsmsg.htm` has the cell `<b>Headers and Properties</b><p>For details, see <code><a href="headers.htm">Headers</a></code>.</p>`. It becomes `**Headers and Properties For details, see Headers .**` (`output/.../10.5.1/c-and-cobol-reference/tibemsmsg.md:55`), and the link is gone.
- **Confirmed:** yes, in real output. Families: 6 links lost (one per EMS version) and 30 code-formatted labels flattened. Corpus sample: 7 labels flattened, 1 image lost.
- **Suggested fix:** Take the short-label path only when the cell is pure inline text with no `a[href]`, `img` or block children. Otherwise move the children across as the long-label branch already does.

### R5-05 · S1 · Splitting a colspan table discards its `<caption>`
- **Where:** `flare.py:944-955` (only rows and orphan targets survive `table.decompose()`)
- **What:** The caption, such as "Status Codes", is silently dropped.
- **Failing scenario:** `output/.../10.5.1/c-and-cobol-reference/tibems-status.md` has no "Status Codes", which the source `<caption>` carries.
- **Confirmed:** yes. Families: **35 of 175** split tables have a caption that is lost. Corpus sample: **89 of 705**. Over all 22 captioned topics in EMS 10.5.1, 11 lose the caption: the split path plus the pipe path (the pipe path is R8's, see Edge notes).
- **Suggested fix:** Emit the caption as a paragraph ahead of the first replacement table.

### R5-06 · S1 · Topic links keep the href's letter case, not the file's, so they break on case-sensitive hosts
- **Where:** `flare.py:309-314`: membership is tested case-folded (`str(resolved).lower() in self.topics`), but the emitted path is `links.to_markdown(resolved)` in the href's case
- **What:** If the source link's case differs from the directory or file on disk, the link resolves on Windows and 404s on GitHub or AEM. Nothing is recorded.
- **Failing scenario:** `dsc-stat/14.1.0` UserGuide: `[…](../10-working-with-Statistica-query/file-new.md)`, but the written directory is `10-working-with-statistica-query/`.
- **Confirmed:** yes. 12 such links in `dsc-stat/14.1.0` (harness, full conversion). Rare elsewhere: 0 in 9,724 links over the 120-root sample. A full count over the other Statistica roots timed out.
- **Suggested fix:** Keep a case-folded map of planned path to real path, and emit the real path.

### R5-07 · S1 · List merging moves code and lists across the prose between them, and swallows a `<pre>` after an authored list
- **Where:** `flare.py:895-914` (`_merge_once` looks only at Tag siblings, so text nodes between them are invisible; it also applies to every `ul`/`ol`, not only fake lists)
- **What:** `<ul>…</ul> If the pattern needs… <pre>example</pre>` becomes a bullet that contains the example, followed by the sentence that introduced it.
- **Failing scenario:** `output/en-us-tib-activespaces/.../5.2.0/Concepts/LIKE-Operator.md`: `completed LIKE '100\%' ESCAPE '\'` is nested under the "_ (underscore)" bullet and comes before its explanation.
- **Confirmed:** yes, in real output (the same page in all 6 ActiveSpaces versions). It is rare: 1 topic in the 6,934-topic corpus sample. Families have 43 authored lists followed by a `<pre>`.
- **Suggested fix:** Stop absorbing when non-whitespace text lies between the siblings, and limit the absorptions to lists `_fake_list_tables` produced (mark them).

### R5-08 · S2 · Links into another output root of the same version become plain text, reported as "dangling"
- **Where:** `flare.py:309-312` (`escapes()` or "not in this root's planned set" → `dangling_link`)
- **What:** A link from one root to a topic converted by a sibling or nested root is flattened to text. The `TOPIC_LINK_DANGLING` note, which §5.1.8 calls a *source defect*, hides that the target exists in the output. Because the link never reaches `AssetCopier.escaped`, design §10.7 class 2 cannot route it later either.
- **Failing scenario:** `tp/1.1.0`: 109 dangling notes, **92 of them target topics converted by `Subsystems/*` nested roots** (for example `new-features.htm -> ../Subsystems/platform-ct/gateway-api-controller-resource.htm`).
- **Confirmed:** yes. `crossscan.py` over all 132 multi-root versions (at most 150 topics per root): **1,332 links to a topic of another root, in 18 versions** (`platform-cp` ×14, `tp`, `tibco-platform-cli`). 179 more are true misses.
- **Suggested fix:** Pass the version-wide planned map (root → subtree, topics) so that a cross-root target is emitted as a relative path across subtrees. Keep `TOPIC_LINK_DANGLING` for real misses.

### R5-09 · S2 · A whole root built without `#mc-main-content` is dropped one topic at a time
- **Where:** `flare.py:587-596` (the body fallback applies to the landing page only)
- **What:** The Statistica LTS roots use a skin whose topics put content straight in `<body>` (`data-mc-runtime-file-type="Topic"`). Every topic gets `CONTENT_MISSING` and is not converted.
- **Failing scenario:** `dsc-stat/14.1.0/StatLTSReleases`: the harness reports `CONTENT_MISSING` 288. Only the landing page converts.
- **Confirmed:** yes. 10 roots: 292 of 293 topics have no container in each 14.1.0 root and 5 of 7 in each 14.2.0 root, across `dsc-stat`, `stat`, `stat-ext`, `stat-sts` and `stat-all-servers`. That is about 1,485 topics. §5.1.6's 99.9% invariant is per topic and misses this per-root shape.
- **Suggested fix:** When *no* topic in a root has the container but they are MadCap `Topic` files, fall back to `<body>` minus known chrome for that root, and record it once per root instead of once per file.

### R5-10 · S3 · Runtime stubs named after the project raise 278 false `CONTENT_MISSING` warnings
- **Where:** `flare.py:106-107` (`STUB_FILENAMES` is a fixed `default*` list)
- **What:** Flare names the frameset stubs after the target (`<stem>.htm`, `<stem>_CSH.htm`, matching `<stem>.mcwebhelp`). They are planned as topics, fail the container check, and are warned about. A link to one would also emit a `.md` that is never written.
- **Confirmed:** n/a (S3). Counted anyway: **278 stubs in 139 roots**, none with a container. Seen in `tp/1.1.0` (10 warnings).
- **Suggested fix:** Add `<mcwebhelp stem>.htm` and `<stem>_CSH.htm` to the stub set for each root.

### R5-11 · S3 · Merged-project TOC nodes (`*.flprj` keys) are dropped as "no page and no children"
- **Where:** `flare_toc.py:175-180`, `flare.py:708-712`
- **What:** In a merged-project TOC, `/../../../x.flprj` marks where a sub-project's TOC is inserted. It is dropped, so the sub-guides (converted as separate units) lose their place in the navigation, and the finding text misdescribes the cause.
- **Confirmed:** n/a. **121 `.flprj` keys** across the 937 roots (`tp/1.1.0`: 6). §5.1.4 knows only "one stray".
- **Suggested fix:** Resolve a `.flprj` node to the nested or sibling unit it names, or at least give it its own finding code and label.

### R5-12 · S3 · TOC and manifest failures are silent, and `tree_files` takes any non-chunk `.js` as a tree
- **Where:** `flare.py:432,496-513`, `flare_toc.py:109-140`
- **What:** An unparseable `HelpSystem.xml` or tree file yields an empty `Manifest` or `Toc` with no finding (only `TOC_ORPHAN` later shows the effect). The docstrings say the opposite.
- **Confirmed:** n/a. The corpus does not trigger the real case today: 0 manifest failures and 0 missing declared TOCs over 937 roots. 11 helper scripts (`apply_fr.js`, …) fail to parse and 6 localized chunk files (`*_Chunk0_ja.js`) are read as empty trees. Both are harmless only by luck.
- **Suggested fix:** Record a finding when the declared TOC or the manifest does not parse. Read only `Toc=` plus the files `HelpSystem.xml` references, or require a `tree` key.

### R5-13 · S3 · Text popups are inlined with no delimiter
- **Where:** no `text_popups` pass (§5.1.10 lists one); the `a.MCTextPopup` → `link()` path returns `None` for `javascript:`
- **What:** `Operators<sup>1</sup><popup body>` renders as `Operators1See the Model Validation Operators section… to get further`.
- **Confirmed:** n/a. 2 topics in the corpus sample (`sfire-dsc/7.1.0`). The text is kept.
- **Suggested fix:** Render the popup body as a parenthetical or a footnote.

### R5-14 · S3 · `Document.anchors` is taken from the source before chrome is stripped
- **Where:** `flare.py:599`, `flare.py:1026-1029`
- **What:** It includes ids from `#feedback-survey`, the mini-TOC and the breadcrumbs, and ids on non-`<a>` elements the renderer never emits. The DITA, DocBook and WebWorks engines hand over the *emitted* set. No current consumer reads it for Flare (see X1).
- **Confirmed:** n/a.
- **Suggested fix:** Return the markers the renderer actually emitted, as the other engines do.

### R5-15 · S3 · `convert_unit` has no per-topic guard behind the base class's "never raises" contract
- **Where:** `flare.py:397-421`, `base.py:395-396`
- **What:** One topic that makes bs4 or the recursive renderer raise (for example `RecursionError` on deep nesting) aborts every root of the version.
- **Confirmed:** unconfirmed. No crash over about 49,000 converted documents (13 cache versions and 3 family versions via the harness).
- **Suggested fix:** Catch per topic, `unit.skip("render-error")`, and record it.

### R5-16 · S4 · Dead code
- **Where:** `flare.py:1098` `_relative` (unused), `flare_toc.py:47-49` `Manifest.complete` and `Manifest.alias` (unused), `_Plan.manifest` (stored, never read).
- **Confirmed:** n/a.
- **Suggested fix:** Remove.

## Edge notes (for the cross-stage pass X1)
- `markdown.Renderer.list` (R8) ignores `<ol start>`. R5-02's fix needs it.
- The pipe-table path (`tables_transform`, R8) drops `<caption>` everywhere. Together with R5-05, 11 of 22 EMS 10.5.1 captions are lost.
- The renderer drops `span.autonumber` on the assumption that `block_override` re-emits the label. That holds only in block position, not in pipe cells or other inline paths (R5-03).
- Escaped *topic* links never reach `AssetCopier.escaped`, so design §10.7 class 2 (Stage 7) can route only escaped assets. Cross-root topic links are lost at conversion (R5-08).
- `Document.anchors` means different things in different engines (R5-14). `NavNode.anchor` is not checked against emitted markers. It held in the sample (`runtime_agent 5.13.0`: 637 of 637 present).
- Flare never sets `Unit.title`. For multi-root versions the synthesizer falls back to the raw subtree name (`relnotes`, `ja-jp`, …).
- A localized root (R5-01) reaches the synthesizer and CSH as an ordinary unit, so its `Alias.xml` identifiers enter `csh.yml` too (not measured).

## Test gaps (real-data paths only)
- No test where step tables are separated by anything other than `pre` or `ListContinue` (R5-02, reached by 22% of numbered items in the sample).
- No icon-table fixture (R5-03).
- No colspan heading cell holding a link, `<code>` or a `<p>` (R5-04), and no captioned table (R5-05).
- No test of a link between two roots (R5-08), and no test of a localized root (R5-01).
- No test of prose between a list and a following `<pre>` (R5-07).
- No test that a link's case is normalized to the file's (R5-06).

## Docs drift
- §5.1.9 says "The `ja` localized subtree … the only localized subtree in the corpus". In fact there are 24 localized *output roots* (de-de, fr-fr, es-es, ja-jp, ja), and the code converts them (R5-01).
- §5.1.10 says "What is worth taking: the 13-pass ordering", and the module docstring says the ordering is inherited. The engine implements 4 of the passes (strip_chrome, fake_list_tables, merge_list_continuations, split_colspan_tables) plus shared deflists. `icon_tables`, `text_popups` and `extract_table_captions` are absent, and each absence is measurable (R5-03, R5-13, R5-05).
- §5.1.8 says "The 1.7% that dangle are source defects". `TOPIC_LINK_DANGLING` also counts 1,332+ links to topics that are in the output (R5-08).
- §5.1.4 says "one is a stray `/../../../ipe.flprj` project file". There are 121 `.flprj` keys, and they are merged-project insertion points (R5-11).
- §5.1.6 calls the selector "a 99.9% invariant". Ten whole roots break it (R5-09).
- The `flare_toc.py` module docstring says "A file that is not a literal raises and the caller reports it", and the `read_toc` docstring says "which the engine reports". Neither raises nor reports (R5-12).
- §5.1.3 says a root-level `index.htm` "converts to an `index.md` landing". The code skips `index.htm` as a stub, and correctly: 54 root-level index files, 0 of them MadCap topics. The doc is what is wrong.

## Checked and fine
- TOC reader over all 937 roots and 953 trees (456,388 keys): 0 ragged, 0 unmatched ids, 0 multi-chunk, 0 percent-encoded or escaping keys, 0 keys into nested roots, 0 manifest failures, 0 missing declared TOCs. The k-th id takes the k-th label, and the declared tree comes first.
- Nested-root ownership: `tp/1.1.0` outer root skips 308 nested files, and the inner units convert them once.
- Chrome order (`#feedback-survey` first), `div.topic-frame` unwrap, comments and CDATA stripped. No autonum label is doubled in the EMS or ActiveSpaces output.
- Callout mapping via autonum and the `note*` prefix. API-tree links (89 in EMS 10.5.1) go through `api_url` when a map is supplied.
- Landing page, What's New placeholder, and support/legal picked from the TOC: behave as §5.1.5 says on EMS, ActiveSpaces, TRA and `tp`.
- The fragments that dangle in the sample (ActiveSpaces, EMS, `focus 9.3.4`: 1,273) are source defects: the anchor is absent from the target source.
- `data-mc-conditions` content (478 topics in the sample) is build-filtered already. Keeping it is correct.
