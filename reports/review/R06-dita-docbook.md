# R6 — DITA & DocBook engines: findings

Base: review-base (7dda975) · Reviewed: `src/docushift/engines/dita.py`, `src/docushift/engines/docbook.py` (+ `tests/unit/test_dita.py`, `test_docbook.py`; 86 pass) · Date: 2026-10-02

| S1 | S2 | S3 | S4 |
|---:|---:|---:|---:|
| 2 | 3 | 9 | 2 |

**How it was measured.** DocBook: the engine was re-run from the frozen code on `families/en-us-tib-streaming/extracted/tibco-streaming/11.2.1` into `C:\tmp\review-R6\db1121`. The results were compared with `output/en-us-tib-streaming/…` and with the `findings` table of `cache/state.db` (opened read-only, convert runs 107–324). DITA: no `engine=dita` row exists in `config/versions.csv`, so nothing DITA has been converted. The engine was run on 4 SuiteHelp doc-sets from `html-to-md/cache/pub` (marketo 7.1.0; amx-bpm 4.3.0 `install`, `tutorials`, `soahelp`: 2,168 topics). The engine's own plan-pass functions were also run over **all 353 cache doc-sets (67,087 topics)**. The scripts are in `C:\tmp\review-R6\` (`scan.py`, `run_dita.py`, `run_docbook.py`, `dbscan.py`).

## Findings

### R6-01 · S1 · DocBook multi-column `simplelist` is read row-major, so its items come out in the wrong order
- **Where:** `engines/docbook.py:248-260` (`_simplelist`)
- **What:** DocBook XSL lays a `simplelist` (default `type="vert"`) out column-major across its table. `find_all(["td","th"])` reads it row-major, so an alphabetical list is interleaved with no warning.
- **Failing scenario:** `dochome/archive-lv-noteworthy.html` has `[[alerting_advanced, lv-sbd], [auth, lvweb], …]`. The output reads `alerting_advanced, lv-sbd, auth, lvweb, …` (`output/…/11.2.1/dochome/archive-lv-noteworthy.md:77-85`).
- **Confirmed:** yes. 11.2.1 has 129 top-level `table.simplelist`. **9 have more than one column and more than one row** (4 pages: `dochome/archive-lv-noteworthy`, `dochome/sb-1050`, `dochome/xarchive-sb-noteworthy`, `hocon/hocon-sb-adaptergroup`). The 23 nested inside another table go through as HTML and keep the right order. Impact is low (order only, nothing is lost).
- **Suggested fix:** read cells column by column when the table has more than one column. If a `horiz` list has to be told apart, keep it as an HTML table rather than guess.

### R6-02 · S1 · DITA `Document.title` gains stray spaces around inline markup
- **Where:** `engines/dita.py:1010-1013` (`_title`: `get_text(" ")`)
- **What:** joining text nodes with a space inserts one at every inline element boundary. The page's frontmatter title then differs from its own `#` heading and from `<title>`.
- **Failing scenario:** `Editing TIBCO Hawk<sup>®</sup> Rulebase Files` becomes `Editing TIBCO Hawk ® Rulebase Files`, and `(<span>CONFIG_HOME</span>)` becomes `( CONFIG_HOME)`.
- **Confirmed:** yes. **14 of 2,068** converted topics in the three amx-bpm doc-sets (0 in marketo) differ from `<title>` only by this. It is cosmetic, but it shows up in frontmatter and in the nav label of orphaned topics.
- **Suggested fix:** use `get_text()` (or `markdown.text_of`) and then collapse whitespace. DocBook's `_text` reads `<title>` and is unaffected.

### R6-03 · S2 · DITA drops every bookmark whose target anchor carries `_unique_N` in a converted topic
- **Where:** `engines/dita.py:302-306` (`_fragment`), `:927` (`_fragment_values`), `:848`/`:854` (`_prune_anchors`)
- **What:** the code always strips `_unique_N` from the *reference*. It never strips it from the *target's* anchors. When the target is an original (converted) topic whose own ids carry `_unique_N` (conref-reused steps and tables), the stripped value matches nothing. The bookmark is dropped and the anchor is pruned out of the page.
- **Failing scenario:** `amx-bpm/4.3.0/soahelp/GUID-E0F4606E….html` defines `id`/`name="GUID-E0F4606E…__STEP_E06AA…_unique_78"`, and another page links exactly that string. The output link loses its `#…` and the anchor is deleted. The engine reports "anchor absent" (false).
- **Confirmed:** yes. The scan over all 353 doc-sets finds **196 links** where the raw fragment exists in the target and the de-uniqued one does not. The engine run on `soahelp` shows 2 of its 21 `TOPIC_LINK_DANGLING` are this case. The only report is `TOPIC_LINK_DANGLING`, a NOTE that is folded per version, so these cases are invisible inside the count.
- **Suggested fix:** in both `_fragment` and `_prune_anchors`, match the raw fragment first and fall back to the de-uniqued form only when the raw one is absent. The de-uniqued form is what links into a *duplicate* need.

### R6-04 · S2 · DITA never finds the legal page: SuiteHelp titles it "Important Information"
- **Where:** `engines/dita.py:773-790` (`_tail`), `engines/base.py:153` (`is_legal_label`)
- **What:** `_tail` can only match a TOC label, because the path is a GUID. Since Phase 36, `is_legal_label` matches neither "Important Information" nor the WebWorks `copyrigh` filename for DITA. The legal slot stays empty and the licence boilerplate page stays where it is in the nav.
- **Failing scenario:** in marketo 7.1.0, `important-information.md` is the TIBCO licence text. The engine sets `legal=None` and records `TAIL_PAGE_MISSING`.
- **Confirmed:** yes. Over 353 doc-sets, the legal page is found in **78**. In **273 (77%)** the TOC has an "Important Information" entry and no matching label, and in 2 neither exists. So the warning fires on ~4 of 5 DITA doc-sets and stops meaning anything.
- **Suggested fix:** give DITA an engine-local rule like DocBook's `FOOTER_SUPPORT_IDS`. For example, an exact (case-folded) TOC label "Important Information" at depth ≤1. Do not widen the shared predicate.

### R6-05 · S2 · DocBook footnote links are dropped and reported as dangling, though both targets are emitted
- **Where:** `engines/docbook.py:521` (`page.anchors` excludes any `<a>` with an `href`), `:289-292`
- **What:** a DocBook footnote's anchors are `<a name="d0e78149" href="#ftn.d0e78149">` and `<a id="ftn.d0e78149" href="#d0e78149">`. Both carry an `href`, so neither enters `page.anchors`. Both footnote links are then unlinked and recorded as `TOPIC_LINK_DANGLING`, even though `_anchor()` writes both markers into the body.
- **Failing scenario:** `adaptersguide/embeddedRTPP.html` reports `-> #ftn.d0e78149` and `-> #d0e78149`, and the footnote number renders as plain text.
- **Confirmed:** yes (engine re-run on 11.2.1). There are 3 footnote pairs in 11.2.1. Small.
- **Suggested fix:** collect `markdown.anchor_target(a)` for every `<a>`, with or without `href`, and exclude only `a.ix`.

### R6-06 · S3 · DocBook `ANCHOR_DROPPED` is a false positive on every row it has produced
- **Where:** `engines/docbook.py:166-170,269,596-601`. `emitted_anchors` is fed only by `inline_override`, but `markdown.py:299-303` (pipe-table hoist), `:324-331` (passthrough `rewrite`) and `:414` (`code_span` hoist) also write `<a id>` markers.
- **What:** an anchor written by any of those three paths counts as "kept but not emitted". It is reported as a warning and removed from `Document.anchors`.
- **Failing scenario:** for 11.1.3 the run reports `rtcmd/epadmin-globals.md: kept but not emitted: d0e3109, d0e3244`. The published file has `<td colspan="2"><a id="d0e3109"></a><code>discoveryhosts</code></td>` at line 102.
- **Confirmed:** yes. All 6 `ANCHOR_DROPPED` rows in run 324 (11.1.0 ×3, 11.1.2, 11.1.3 ×2) were checked. The anchor is present in the output every time.
- **Suggested fix:** derive the emitted set from the rendered body (`_MARKER.findall(body)`) rather than from one hook. That covers every path and also gives DITA the guard (R6-12).

### R6-07 · S3 · DocBook's duplicate directories are never reported under the real extract layout
- **Where:** `engines/docbook.py:974-995` (`_duplicate_roots`), `:434-438`
- **What:** the function scans only the tree's depth-1 children and skips any child that contains a root. Real extracts add a wrapper (`11.2.1/tibco-streaming-11-2-1/{html,adaptersguide,…}`), so the wrapper is skipped and the 8 duplicates beneath it are never looked at.
- **Failing scenario:** for `str` 11.2.1, `adaptersguide`, `architect`, `dochome`, `install`, `lv-admin`, `lv-devel`, `rtadmin` and `welcome` are byte-identical to their `html/` twins (`diff -rq` gives 0 differences) and produce no `DOCSET_SKIPPED`.
- **Confirmed:** yes. There is **0 `DOCSET_SKIPPED`** for either streaming product in any convert run (107–324), against the 51 that §5.6 records. Output is correct (nothing is converted twice). Only the promised report line is missing.
- **Suggested fix:** search below the roots' common parent (`root.parent`'s siblings), or walk to the depth of the root.

### R6-08 · S3 · DITA files topics as orphans even when `toc_crawler.html` places them
- **Where:** `engines/dita.py:651-658` (`_toc`), `:94`
- **What:** the crawler is used only when the primary list is missing. Topics that only the crawler places go to "Unfiled" (reported as `TOC_ORPHAN`, a NOTE).
- **Failing scenario:** in marketo 7.1.0, 21 of 100 topics are unfiled, and **all 21** appear in `toc_crawler.html`.
- **Confirmed:** yes, but small corpus-wide: 195 orphans in 67,087 topics, of which **33 are in the crawler** (15 doc-sets ship both files). The behaviour follows §5.2.3 as written ("fallback, never a supplement"), so this is a design question.
- **Suggested fix:** attach crawler-only topics under their crawler parent where that parent is placed. Keep the primary's structure and labels everywhere else.

### R6-09 · S3 · A DITA slug can collide with another topic's tie-break suffix and silently overwrite it
- **Where:** `engines/dita.py:955-961` (`_assign_slugs`), `:564-568` (`documents[...] = document`)
- **What:** ties are suffixed `-2`, `-3` without checking that the result is free.
- **Failing scenario:** the titles `Fault Tab`, `Fault Tab` and `Fault Tab 2` produce `fault-tab.md`, `fault-tab-2.md`, `fault-tab-2.md`. One topic is lost from `documents`, and links to it land on the other (repro: `C:\tmp\review-R6\slugrepro.py`).
- **Confirmed:** n/a (S3). It occurs in **0 of 353** doc-sets today, and there are 0 case-only collisions.
- **Suggested fix:** assign slugs against a global taken-set, bumping the suffix until it is free.

### R6-10 · S3 · DITA CSH ids that target a republished duplicate cannot resolve
- **Where:** `engines/dita.py:644-649`, read with `converter/driver.py:427-435`. `output_map` gets one row per `Document.source`, so a duplicate's filename never appears in it.
- **What:** links reach duplicates through `plan.targets`, but CSH resolves through `output_map`. §5.2.2's claim that "CSH and links cannot disagree" therefore does not hold.
- **Confirmed:** n/a (S3). 2 of 1,134 head.js entries (`sfire-dsc/6.5.0` `WO_107`, in two copies of the doc-set).
- **Suggested fix:** let the engine expose duplicate-to-original source aliases so the driver writes an `output_map` row for each.

### R6-11 · S3 · DITA takes the first homepage, not the one whose GUID matches the TOC root
- **Where:** `engines/dita.py:603-606`, `:964-983` (`into.setdefault`)
- **What:** §5.2.7 says "take the one whose GUID matches the TOC root", but the code takes the first homepage in sort order. That feeds `METADATA_MISMATCH` and `unit.title`.
- **Confirmed:** n/a (S3). 5 of 353 doc-sets ship more than one homepage.
- **Suggested fix:** pick the homepage whose GUID matches the first TOC entry, or correct the doc.

### R6-12 · S3 · DITA has no kept-versus-emitted anchor check (the Phase 19 bug class)
- **Where:** `engines/dita.py:680,695-696`. `_prune_anchors` inserts an `<a name>` as the *first child* of any id-bearing element. For `<pre>`, `<ol>`/`<ul>` and `<img>` the walk discards that marker (`markdown.py:263,277`), and `Document.anchors` still claims it.
- **Confirmed:** n/a (S3). In 4 converted doc-sets, 82 of 82 kept anchors are present in the body. The only downstream safety net is the driver's `FRAGMENT_UNPLACEABLE`.
- **Suggested fix:** reuse the body-derived check from R6-06 in DITA.

### R6-13 · S3 · DocBook labels its API trees as `not-docbook`/`foreign-generator`, never `api-reference`
- **Where:** `engines/docbook.py:419` (`skips_api_references = False`), `:482-487`
- **What:** the `api-reference` reason in §5.6.10 can never fire. The 1,466 Sandcastle pages that §5.6's as-built note says were moved out of `not-docbook` are back in it.
- **Confirmed:** yes, for 11.2.1. `not-docbook` holds 1,476 pages: `apidocs/dotnet` 1,428, `apidocs/lv-js` 24, `apidocs/lv-python-client` 13, plus `README.html` and `lv-config-ref` (XSD documentation). `foreign-generator` holds 844: javadoc 799, `mms` 45. Output is correct. Only the reason buckets are wrong.
- **Suggested fix:** keep the positive `is_docbook_page` test, but name the reason `api-reference` when `is_api_reference(path, context.api_roots)`. Also update §5.6.10 (see Docs drift).

### R6-14 · S3 · Misleading dangling message for `href="???"`
- **Where:** `engines/docbook.py:287-292`
- **What:** `href="???"` (an unresolved DocBook ulink) classifies as an empty FRAGMENT and is reported as `-> # (anchor absent; link kept, bookmark dropped)`. In fact the link is removed and there was no bookmark.
- **Confirmed:** yes. 6 cases in `adaptersguide/embeddedInputSyslog.html` (11.2.1).
- **Suggested fix:** route an empty-fragment FRAGMENT to `dangling_link` with the raw href.

### R6-15 · S4 · DocBook's `referenced` set is unit-wide, but DocBook ids are per page
- **Where:** `engines/docbook.py:527-528`, `:875`
- **What:** `d0eNNNN` ids repeat across pages. A fragment referenced on page A keeps a same-named anchor on every page B. Every R6-06 false positive was one of these: `d0e3109` is referenced only as `adapter-restrictions-enterprise.html#d0e3109`.
- **Suggested fix:** key `referenced` by `(resolved target page, fragment)`.

### R6-16 · S4 · DITA anchor regex is a superset
- **Where:** `engines/dita.py:149` (`_ANCHOR_ATTR`)
- **What:** `\b(?:id|name)=` also matches `data-id=` and `name=` on non-anchor tags. It also matches anchors inside chrome that `_strip_chrome` removes later. The result can be `_fragment` keeping a bookmark that no element backs. Not observed in the samples.
- **Suggested fix:** match `<a … name=` and ` id=` only, on the chrome-stripped slice.

## Edge notes (for the cross-stage pass X1)
- **`Document.anchors` has no consumer.** It is defined at `engines/base.py:66` and read nowhere outside the engines. Phase 19's "stop advertising" (docbook.py:601) therefore changes nothing. The real guard is the driver's `_retarget_fragments`, which counts `FRAGMENT_UNPLACEABLE`.
- **The platform ignores `<a id>`** (`transforms/fragments.py`). DocBook 11.2.1 emits **2,155 NavNodes with `anchor=`**, and they work only because the driver rewrites `toc.yml` afterwards. Engines should know their anchor values are intermediate.
- **`TOPIC_LINK_DANGLING` is a folded NOTE.** Only the first message per (code, slug, version) survives, so per-link detail is lost (R6-03, R6-05, R6-14).
- **`output_map` has no rows for DITA republished duplicates** (R6-10). Anything that maps by source path (CSH, origins) cannot find them.
- **`context.tree` is the extracted version directory, wrapper included.** Engine code that assumes `html/` sits at depth 1 breaks (R6-07). The driver's `_content_tree` knows the wrapper, but the engines do not get it.
- **`slugify` has no length cap.** DITA filenames come from full titles (for X2's 260-character check).
- **DITA `unit.title` is the homepage's `publication-title`**, or `""` in the 39 doc-sets without a homepage. The toc writer has to cope with blank unit titles.

## Test gaps (real-data paths only)
- DocBook duplicate directories under a **wrapper directory**: the test (`test_docbook.py:213`) puts `html/` at depth 1, which no real extract does (R6-07).
- `ANCHOR_DROPPED` with an anchor inside a passthrough table or a `<code>`: the real path, untested and wrong (R6-06).
- DITA `_unique_N` anchors inside an *original* topic (R6-03). Only the duplicate case is tested (`test_dita.py:578`).
- Multi-column `simplelist` ordering (R6-01). `test_docbook.py:455` uses one column.
- DITA legal page labelled "Important Information" (R6-04). `test_dita.py:720` uses a label the predicate matches.
- DocBook footnotes (R6-05).

## Docs drift
- **§5.6.7 and design.md:690** say 7 `a.indexterm` anchors in table cells are "lost on the table path — named, not yet fixed". They are emitted. The finding is a false positive (R6-06).
- **§5.6 as-built bullet 2 and §5.6.10** say `skips_api_references` stays `True` and `api-reference` covers about 2,400 files. The code sets it to `False` (bex 1.3.5/1.3.6), and the bucket is always 0 (R6-13).
- **§5.6 opening** says "10 versions in 2 products". `docbook.py:412-416` documents `bex` 1.3.5/1.3.6 as DocBook too, and versions.csv carries 8 streaming rows.
- **§5.6 opening** gives `DOCSET_SKIPPED 51` as a measured result, and §5.6.3 says duplicates are "reported once each". Today the number is 0 (R6-07).
- **§5.6.8** says "no fragment in the corpus resolves to an element `id`". Footnote back-links do (`#ftn.…` names an `id`) (R6-05).
- **§5.2.5** says `remember`, `attention` and `restriction` map to `[!NOTE]`. `callouts._ALIASES` maps `attention` and `restriction` to `IMPORTANT`, and the code comment at `dita.py:219-221` agrees with the code.
- **§5.2.2** says "CSH and links cannot disagree" (R6-10). **§5.2.7** says "take the one whose GUID matches the TOC root" (R6-11).
- **§5.2.3 and §5.2.4** give a "2-3% orphan rate". It measures **0.3%** (195 of 67,087) on the current code.

## Checked and fine
- **DocBook navigation on 11.2.1:** 1,177 of 1,178 documents are in the nav (`index.md` is hoisted to `landing`). There are 25 top-level nodes, the 13 menu labels come in menu order, and the rest are alphabetical. Support and legal resolve from `#footer`. `TOC_ORPHAN` is 28, and no `NAV_NODE_DROPPED`.
- **DocBook heading promotion:** 89 pages open below `h1`: 81 `refentry`, 6 `index`, 2 `glossary`. None has its first heading inside a consumed box. Every admonition has a direct `h3.title`. The `_HEADINGS`/`_consumed_heading` interplay is correct. Nav labels and titles have no stray spaces (only `.NET` matches the pattern).
- **DocBook chrome:** container-only selection, the `a.ix` drop, the mediaobject unwrap, the `span.bold`/`command` unwrap, and the `cgi-bin` olink handling all behave as §5.6 says. No `ANCHOR_DROPPED` is a real loss.
- **DITA identity, all 353 doc-sets:** 0 slug overwrites, 0 case-only collisions, 0 non-republished identifier collisions. Republished duplicates collapse correctly (15, 75 and 1 in the amx-bpm samples). Ties break by GUID deterministically.
- **DITA vocabulary:** all 24,858 callouts are `<div>`, with 0 on other tags. `note tip` resolves through the label span, the labels are removed, and GFM alerts render. `familylinks`, copyright and `noscript` are stripped. No duplicate `#` title is prepended (0 of 2,168 bodies start with a marker).
- **DITA TOC reader:** `_own_anchor`/`_own_label` handle section nodes. TOC labels equal topic titles except where the TOC uses a short label by design.
- **Tests:** 86 of 86 pass on the frozen code.
