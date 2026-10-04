# R8 — Transforms: findings
Base: review-base-b3 (a976513) · Reviewed: `transforms/markdown.py`, `tables.py`, `links.py`, `fragments.py`, `assets.py`, `callouts.py`, `code.py`, `csh.py`, `deflists.py`, `headings.py`, `tests/unit/test_transforms.py` (plus the call sites in `converter/driver.py:_retarget_fragments` and the csh write) · Date: 2026-10-04

| S1 | S2 | S3 | S4 |
|---|---|---|---|
| 7 | 1 | 6 | 2 |

How things were measured (scripts in `C:\tmp\review-R8\`):
- **Output scans.** All 22,755 `.md` files in `output\` (ActiveSpaces, EMS, Streaming, TRA) were rendered with `markdown-it-py` (CommonMark + GFM tables), and the token stream was searched for the failure (`scan2.py`–`scan8.py`). The defects also appear in `reframed\` (`reframed_scan.py`).
- **Frozen-engine harness.** `harness.py` runs the frozen engines in memory over family trees, with the shared walk instrumented. Trees: all EMS and ActiveSpaces versions, TRA Runtime Agent and Administrator, 10 Streaming versions, and DataSynapse (DS) as a fourth Flare family that has no `output\`.
- **Synthetic repros.** `repro.py` runs each shape through the frozen `Renderer`.
- `pytest tests/unit/test_transforms.py`: 108 passed.

## Findings

### R8-01 · S1 · Anything inside a `<ul>`/`<ol>` that is not an `<li>` is silently dropped
- **Where:** `transforms/markdown.py:277` (`tag.find_all("li", recursive=False)`, and nothing else among the list's children is read)
- **What:** A `<p>`, `<pre>`, `<div>`, `<table>`, a nested `<ul>`, or bare text placed directly inside a list is never rendered, and nothing is counted.
- **Failing scenario:** ActiveSpaces 5.2.0 `Concepts/Registering-the-ActiveSpaces-JDBC-Driver-with-the-Driver-Manager.htm` has `<ol class="steps"><p>Use the following code snippet…</p><pre>// Register the ActiveSpaces JDBC Driver…</pre></ol>`. The output has `**Procedure**` followed by nothing: the sentence and the code are gone. EMS 10.5.1 `installation/optional-post-instal2.htm` loses the note "This script only works when your EMS_HOME path ends with ems/10.5." (`<p><div class="note">` between steps 2 and 3). TRA 5.13.0 `Upgrade_Security_Vendor` loses both FIPS branches ("Use the default Java security vendor. Set: TIBCO_SECURITY_VENDOR = j2se" and the bcfips line, in a `<ul>` that is a direct child of a `<ul>`).
- **Confirmed:** yes. The three pages above were checked in `output\` (the text is absent). Harness counts of non-`li` children that hold text (Flare `span.autonumber` labels excluded, since the engine re-emits those): **ActiveSpaces 33 (636 words, 12 holding code), DS 19 (1,248 words, including 2 whole `<table>`s in GridServer LogViewer), EMS 6 (72 words), TRA 4 (32 words)**. 62 elements in all.
- **Suggested fix:** In `list()`, attach a non-`li` child's blocks to the preceding item (or to a new item when there is none), the way a browser displays it. Count anything that still cannot be placed.

### R8-02 · S1 · Pipe-table cells holding a list or a `<pre>` are flattened into one run of text
- **Where:** `transforms/tables.py:110-122` (`_block_count` counts top-level children only, so a lone `<ul>`, `<pre>` or `div > ul` counts as 1 block). The cell is then rendered by `markdown.py:304` through `inline_children`, where `ul`/`ol`/`pre` fall to the generic branch (`markdown.py:376`).
- **What:** The table is judged GFM-safe. List items run together with no separator, and code loses its formatting and line breaks and is Markdown-escaped as prose.
- **Failing scenario:** Streaming 11.2.1 `adaptersguide/ClusterPubSubAdapter.md:324` gives `` `Error`—A human readable error message. `Topic`—The current topic. `` for a two-bullet list. ActiveSpaces 5.2.0 `SQL-INSERT-Statement.md:26` has the `<pre>` syntax as escaped prose: `INSERT INTO \<table_name> \[(column1 \[, …`. In the synthetic repro, `<td><ul><li>one</li><li>two</li></ul></td>` gives `| x | onetwo |`.
- **Confirmed:** yes, in the output files above. Harness counts of GFM-safe cells holding a block: **Streaming 1,220 (lists), DS 605 (601 `<pre>`), EMS 288 (252 `<pre>`, 36 lists), ActiveSpaces 69 (`<pre>`), TRA 1**. 2,183 cells in all. Streaming also has 860 cells with more than one `<p>` under one wrapper, whose paragraph breaks collapse.
- **Suggested fix:** Have `_block_count` (or `unsafe_reason`) treat any descendant `ul`/`ol`/`pre`/`dl`/`blockquote`/`table`, or more than one `p`, as multi-block, so the table takes the passthrough branch.

### R8-03 · S1 · Passthrough tables keep the source's blank lines and tab indents, so their tags render as code blocks
- **Where:** `transforms/tables.py:286-302` (`passthrough` returns `str(table)` with every whitespace text node intact)
- **What:** A GFM HTML block ends at the first blank line. The next line, if it is indented four or more columns (Flare's `\t\t\t\t  </td>`), becomes an indented code block. The reader sees a grey box with a literal `</td>` or `</p>`, and the cell is never closed. Text after a blank line becomes Markdown and is re-parsed.
- **Failing scenario:** EMS 10.4.0 `users-guide/ems-message-properti.md` (table at line 13). Its source cell is `…TIBCO Rendezvous.\n\n\n\t\t\t  </td>`, and it renders as a code block containing `</td>`. Streaming `adaptersguide/LVInputQuery.md`, `LVOutputAlert.md` and others behave the same, and `authoring/nulls.md` shows a whole `<p>` paragraph as code.
- **Confirmed:** yes. With markdown-it, **154 passthrough tables in 140 files** (Streaming 106, EMS 24, TRA 24) have their own lines rendered as an indented code block. 78 more tables have cell text re-parsed as Markdown paragraphs. 4,348 of 4,862 passthrough tables contain a blank line. The EMS reframed tree still carries about 48 such lines (`reframed_scan.py`).
- **Suggested fix:** Before serializing, collapse whitespace-only text nodes and runs of whitespace in text nodes, except inside `<pre>`, so the block has no blank or deeply indented lines. A test should assert that `passthrough()` output contains no `\n\s*\n`.

### R8-04 · S1 · `csh.yml` anchors are never retargeted onto headings, so Help buttons in unmerged trees land at the top of the page
- **Where:** `transforms/csh.py:203-211` (`_join` appends the source anchor unmodified), `converter/driver.py:330-334` (`csh.yml` is written before `_retarget_fragments` at `:571`, which rewrites `.md` bodies and `toc.yml` but not `csh.yml`)
- **What:** `fragments.py` exists because the platform ignores `<a id>` markers. Every body link and TOC link is moved onto a heading slug, but `csh.yml` keeps the marker name. The check in §5.4.6 passes, because the marker exists in the file.
- **Failing scenario:** TRA Runtime Agent 5.12.4 has `"aa.adapter.services.folder.helpurl": "palette.4.27.md#1684753"`. Marker 1684753 sits on `## Adapter Services Folder`, the second section of "Folder Reference". The Help button opens the page top. The reframed 5.13.0 file carries `…#adapter-services-folder` for the same identifier, because reframe retargets it there.
- **Confirmed:** yes (`cshcheck.py`, run over every `csh.yml` in `output\`). TRA is `publish: false`, so these files are what gets published. **345 entries in all 7 TRA versions** name a marker whose heading is not the page's first: Runtime Agent 5.12.2/3/4 88 each and 5.13.0 27; Administrator 5.12.2 and 5.12.4 24 each and 5.13.0 6. A further 124 land at the page top, which happens to be correct. 3 cannot be placed.
- **Suggested fix:** Write `csh.yml` after `_retarget_fragments`, and pass each value through the same `targets[path].get(anchor.lower())` lookup. Count the misses into `FRAGMENT_UNPLACEABLE`. Related to R4-05, a different defect in the same file.

### R8-05 · S1 · A `<br>` becomes a literal backslash at the end of a block and inside a pipe cell
- **Where:** `transforms/markdown.py:71` (`_BREAK = "\\\n"`), `:202-206` (`flush` strips the trailing newline and leaves the `\`), `:500-511` (`wrap` strips it inside `**…**`, which then reads `\**`), `transforms/tables.py:129-136` (`escape` turns the newline into a space, leaving `\ `)
- **What:** A hard break is valid only between two lines. At the end of a paragraph, alone in a block, at the end of a bold run, or in a table row, it prints a visible `\`. In bold it also escapes the closing `*`.
- **Failing scenario:** DocBook's `<br class="figure-break">` and `table-break` give a paragraph that is just `\`. Streaming 11.1.0 `admin/sec-ldap.md` has six of them. EMS 10.4.0 `tibemsOAuth2TokenFetchCallbackEx.md:32` has `…supplied in the call to\ [tibemsOAuth2Params_SetTokenFetchCallback](…)`. `<b>Warning<br/></b>text` gives `**Warning\** text`.
- **Confirmed:** yes, by markdown-it over `output\`: **2,064 lone-backslash paragraphs, 81 trailing backslashes, 71 mid-text `\ `** (42 of them in pipe rows), **520 files** (Streaming 390). ActiveSpaces' reframed tree still has 90 lone `\` lines.
- **Suggested fix:** Drop a break that ends or starts a block or an emphasis run. In `tables.escape`, map `_BREAK` to `<br>`, which is what its docstring already claims. Move a break out of `wrap` before stripping.

### R8-06 · S1 · The pipe-table branch drops `<caption>`, and demotes a `<thead>` row of `<td>` cells to a data row
- **Where:** `transforms/markdown.py:290-306` and `transforms/tables.py:68-89` (`read` reads only `tr`, and takes a header only when every cell of row 0 is `<th>`)
- **What:** A GFM-safe table loses its caption text without a word. A header row written as `<thead><tr><td>…` is emitted under an empty `|  |  |` header, as if it were data. WebWorks handles its own captions (`webworks.py:309-316`); Flare, DocBook and DITA do not.
- **Failing scenario:** TRA 5.13.0 `palette-reference/Advanced_Panel_1.md:209` has no "Processing Instruction" title, though the source has `<caption><p class="TableTitle">Processing Instruction</p></caption>`. TRA 5.13.0 `tramodify_Utility` shows "Parameter | Description" as a body row under a blank header.
- **Confirmed:** yes, in `output\` for the caption. Harness counts of captions lost on the pipe path: **TRA 113, EMS 66, DS 58**. This is separate from R5-05's split-table path, and R5's edge note handed it here. Header demotion: **65 tables** in 4 sampled versions (`theadscan.py`, raw-source estimate).
- **Suggested fix:** Emit the caption as an italic paragraph ahead of the pipe table, as WebWorks does, ideally by moving WebWorks' code into the shared `table()`. In `read`, treat a `<thead>`'s first row as the header whatever its cell tag.

### R8-07 · S1 · Two adjacent bold, italic or code runs merge into literal asterisks and backticks
- **Where:** `transforms/markdown.py:500-511` (`wrap`), `transforms/code.py:333-345` (`inline`). Nothing joins or separates two adjacent runs that use the same delimiter.
- **What:** `<b>ssl</b><b>.</b>` gives `**ssl****.**`. `<b>Default value:</b><i>none</i>` gives `**Default value:***none*`. `<code>a</code><code>b</code>` gives `` `a``b` ``. CommonMark reads each of these as literal delimiters, or as one code span that contains two backticks.
- **Failing scenario:** EMS `users-guide/rest-proxy-ems-server-certificate-authority-options.md` shows "\*\*Default value:\*\*\*none\*" literally. ActiveSpaces `Starting-Data-Grid-Processes-With-Authentication.md` renders `` -user <user_name>``-password <pwd_option> `` as one code span.
- **Confirmed:** yes, by markdown-it: **353 literal `**` in 83 files** (152 are the bold/italic `***` shape), and **849 merged code spans in 385 files**. Both survive into `reframed\`.
- **Suggested fix:** Merge adjacent runs of the same kind before emitting, or put a zero-width separator (`<!-- -->`) between them. Move a closing delimiter that sits after punctuation and before a word character outside the word, or emit `<strong>` instead.

### R8-08 · S2 · Percent-encoded fragments are never retargeted, and are reported as having "no heading behind" them
- **Where:** `transforms/links.py:161` (the fragment is emitted `quote()`d), `transforms/fragments.py:430-433` (passes the raw, encoded fragment to `anchor_for`), `converter/driver.py:607,637` (`found.get(fragment.lower())` against marker names that are not encoded)
- **What:** A target whose name contains a space or other reserved character, such as `<a name="tibdg proxy shed">`, is linked as `#tibdg%20proxy%20shed`. The lookup misses it, the link keeps pointing at an inert marker, and `FRAGMENT_UNPLACEABLE` counts it with a message that does not fit ("name an anchor with no heading behind it").
- **Failing scenario:** ActiveSpaces (all versions) `Methods-of-Selecting-a-Proxy-for-a-Client.md` → `tibdg-proxy-shed.md#tibdg%20proxy%20shed`.
- **Confirmed:** yes. Of 201 encoded fragments in `output\`, **53 name a marker that the decoded form would have found**. 142 point outside `output\`; 6 match nothing.
- **Suggested fix:** Have `retarget` (or `anchor_for`) `unquote` the fragment before the lookup. Re-encode the replacement only if it needs it.

### R8-09 · S3 · Narrow escaping lets `_word_` become emphasis and `&lt;` text become an entity
- **Where:** `transforms/markdown.py:74,110-112` (`_` and `&` are not escaped)
- **What:** The decision not to escape `_` is right inside words, but `_store_` and `__init__` at word boundaries render as italic and bold. Source text that displays as a literal `&lt;` comes out as `&lt;`, which GFM renders as `<`.
- **Failing scenario:** SFAS 1.2.0 `sfas_users_guide.4.2.md` (`*_store_*`). Streaming 11.1.1 `authoring/witsmloperator.md` (`list&lt;tuple&lt;uid string&gt;&gt;&gt;` renders as `list<tuple<…`).
- **Confirmed:** yes, small: underscore emphasis in **16 files**, entity text **24 times in 6 files**.
- **Suggested fix:** Escape `_` only where it is left- or right-flanking at a word boundary. Escape `&` when it is followed by `name;` or `#digits;`.

### R8-10 · S3 · `rewrite()` resolves only `<a>` and `<img>`; other `href`/`src` carriers in passthrough tables keep source paths
- **Where:** `transforms/markdown.py:318-337`, `transforms/tables.py:224-231` (`href` and `src` are kept on every element)
- **What:** `<code href="license.htm">` and `<madcap:xref href="FTL_Server_Cluster_Security.htm">` reach the output still pointing at `.htm` source files. They are not resolved, not counted, and not reported.
- **Failing scenario:** EMS 10.5.1 `users-guide/Sections_in_the_FTL_Server_Cluster_Configuration.md:228` and `tibemsd-options.md:38`.
- **Confirmed:** yes, **16 references in EMS** (the only non-`.md` relative references in `output\` other than cross-tree resource links: 20,258 asset references checked, no missing image).
- **Suggested fix:** Drop `href`/`src` from elements other than `a`/`img`/`area`/`source`. Route `madcap:xref` through `link()`, or unwrap it.

### R8-11 · S3 · Heading slugs are wrong for headings that contain an escaped `<` or an image
- **Where:** `transforms/fragments.py:364-367` → `utils/anchors.py:59-63` (`_TAG` deletes `<Project>` out of `\<Project> Window`, and a link or image keeps its URL text)
- **What:** `## \<Project> Window` slugs to `-window`. The platform slugs the rendered text, `project-window`. Retargeted fragments and validation both use the wrong anchor.
- **Failing scenario:** TRA 5.13.0 `user-guide/Window_Menu.md:22`. The WebWorks heading `## <a id="2051068"></a>![](images/palettes-menu.gif)` in `designer.4.06.md` gets a slug made from the image path.
- **Confirmed:** yes, rare: 4 headings with `\<`, 2 with an image (TRA only).
- **Suggested fix:** Unescape `\<` and strip `![…](…)` and `[…](url)` down to their text before `_TAG`. The code is R1's (`utils/anchors.py`); fragments is the consumer.

### R8-12 · S3 · A code span emitted as HTML relies on Markdown not parsing its contents
- **Where:** `transforms/markdown.py:429-448` (`_code_fragment`)
- **What:** The docstring says backslashes would be literal inside `<code>`. In CommonMark, text between inline HTML tags is still parsed as Markdown. `*`, `_`, `` ` `` and `[` inside the span are live, and are HTML-escaped, not Markdown-escaped. A `<br>` inside is also dropped, and the words on either side join.
- **Failing scenario:** `<code>a *b <a href=x>c</a> d* e</code>` would italicize part of the code.
- **Confirmed:** n/a today. 285 HTML code spans in `output\`, none mis-parsed.
- **Suggested fix:** Markdown-escape the text fragments as well, and map `<br>` to `<br>`.

### R8-13 · S3 · Elements outside the walk's vocabulary are reduced to their text, or vanish
- **Where:** `transforms/markdown.py:376` (generic inline fallback), `:55-62` (`_BLOCKS`)
- **What:** `<iframe>`, `<video>`, `<object>`, `<embed>` and `<svg>` emit nothing or their raw text. A `<br>` inside a heading splits it (`## Part one\` followed by a paragraph). Nothing is counted.
- **Failing scenario:** `<iframe src="https://www.youtube.com/embed/x">` gives no output (repro).
- **Confirmed:** unconfirmed: the harness reached none of these across the five families (0 media elements, 0 headings with `<br>`). Not measured over the corpus.
- **Suggested fix:** Count unknown elements per tag (one note per version), and emit media as a link to the source URL.

### R8-14 · S3 · `<ol type="a">` and `<ol type="i">` render as `1. 2. 3.`
- **Where:** `transforms/markdown.py:274-288`
- **What:** The numbering style is lost. GitHub's stylesheet restyles nested lists by depth, not by type, so a sub-step "b" becomes "2".
- **Failing scenario:** DocBook `orderedlist numeration="loweralpha"` in Streaming.
- **Confirmed:** yes, **980 lists** (956 `a`, 24 `i`) in 10 Streaming versions (harness). Cosmetic unless the prose says "step b".
- **Suggested fix:** Accept as a GFM limit and record it in the docs, or emit such a list as HTML `<ol type>` when its items are single-paragraph. (`start` is R5-02's hand-off and is not re-reported here. Its fix also covers 40 Streaming lists with `start≠1`.)

### R8-15 · S4 · Duplicated constants and dead branches
- **Where:** `markdown._HEADINGS` = `headings._LEVELS`; two different `_MARKER` regexes (`markdown.py:84`, `fragments.py:344`); two different `_BLOCKS` sets (`markdown.py:60`, `tables.py:29`); `Renderer.inline` is an alias of `_inline_node`; `_code_span_body` computes `body` twice (`:420,422`); the `p`/`dd`/`li`/`dl` branches of `_block` do what `_TRANSPARENT` does; `isinstance(tag, Tag)` after `find_all` in `headings.py:269` and `deflists.py:332,336,348`.
- **Confirmed:** n/a.
- **Suggested fix:** Consolidate in the end-of-phase cleanup commit.

### R8-16 · S4 · WebWorks carries a near-copy of `Renderer.table`
- **Where:** `engines/webworks.py:300-323` (`_content_table`) against `transforms/markdown.py:290-306`
- **What:** The copy adds caption handling and `header_row`. It lacks the pipe-branch anchor hoist (`markdown.py:299-303`), so Phase 16's table-level-target fix does not apply to WebWorks pipe tables (R7 to measure).
- **Confirmed:** n/a.
- **Suggested fix:** Give the shared `table()` a `header_row` hook and caption handling (which R8-06 needs anyway), and delete the copy.

## Edge notes (for X1)
- **`csh.yml` vs `_retarget_fragments`:** the converter writes `csh.yml` before fragments are retargeted and never revisits it. Reframe retargets it for merged trees (`reframe/csh.py`), so only `publish: false` products are hit (R8-04). X1 should confirm that no other consumer reads `csh.yml` anchors as heading slugs.
- **`fragments.retarget` → `anchor_for`:** the resolver receives the fragment as it appears in the Markdown, which is percent-encoded. The driver compares it against decoded marker names (R8-08).
- **`image()` returning None:** the walk emits nothing, alt text included (`markdown.py:469-472`). design §6.4 step 4 promises "the alt text or link label is emitted as plain text".
- **`link()` and `image()` must return already-encoded URLs:** `_anchor`/`_image` emit them verbatim. `AssetCopier.resolve` returns external URLs raw (`assets.py:143`). No broken link resulted (0 unparsed links in `output\`).
- **Pipe cells are rendered through `inline_children`:** `block_override` never runs inside a GFM-safe cell. That is R5-03's mechanism, and R8-02's.
- **`rewrite()` ignores `inline_override`/`block_override`:** engine vocabulary inside passthrough tables (Flare autonum labels, popups, DocBook callouts) is emitted as scrubbed HTML, not as the engine's construct.
- **`headings.is_empty` vs the walk:** an `<img>` whose `image()` returns None counts as heading content but emits nothing. The heading keeps its rung and the levels shift. Not measured.
- **`flattened_links`** is an instance attribute created on first `+=`, read by the engine after the walk. Engines that override `_block` for `pre` must count themselves.
- **WebWorks inline heading markers:** WebWorks headings keep `<a id>` inside the heading line (R7's own path). `slugify_heading` strips tags, so slugs survive, but image-only headings slug badly (R8-11).

## Test gaps (real-data paths only)
- `Renderer.list` has no test at all: non-`li` children (R8-01), nested `ul`-in-`ul`, `type`, `start`.
- No test of `<br>` at a block end, inside bold, or in a pipe cell. `test_a_pipe_and_a_newline_survive_a_cell` pins newline → space, which is the R8-05 behaviour (the docstring says `<br>`).
- No test that `passthrough()` output is free of blank or deeply indented lines (R8-03).
- `is_gfm_safe` is untested for a lone `<ul>`, a lone `<pre>`, and `div > ul` cells (R8-02).
- No captioned pipe table and no `<thead>`-of-`<td>` table (R8-06).
- No adjacent `<b>`/`<b>`, `<b>`/`<i>` or `<code>`/`<code>` case (R8-07).
- `escape_leading` has no direct test.
- No test of `fragments.retarget` with a percent-encoded fragment (R8-08), and no driver-level test that `csh.yml` anchors are retargeted (R8-04).

## Docs drift
- `tables.escape` docstring: "A newline ends the row, so it becomes `<br>`". The code makes it a space (and a test pins the space).
- design §6.4 step 4: "The alt text or link label is emitted as plain text so the prose still reads". For a dangling image, `_image` emits nothing.
- `tables._block_count` docstring: "a `<ul>` inside the cell's single `<p>` is one block". lxml never nests a list in a `<p>`. The real shapes are a bare `<ul>` and `div > ul`, and both are flattened (R8-02).
- `csh._join` docstring: "Tracked as an Open in §9.4". §9.4 has no such Open, and `fragments.marker_targets` now provides the mapping the docstring says is unknowable (R8-04).
- architecture §5.4.6 / design §9.6: "where it carries a `#anchor`, that anchor is present in the file". It is checked against markers, which `fragments.py` itself says the platform ignores.
- `_code_fragment` docstring: "inside a `<code>` the backslashes would be literal". CommonMark parses Markdown inside inline HTML (R8-12).

## Checked and fine
- **Link emission:** 0 unparsed `[..](..)` across 22,755 files. `encode` escapes `%` first (`quote` in a single pass). `classify` decodes the fragment on both paths.
- **Asset relinking:** 20,258 relative asset references in `output\`, no missing image or file. The 836 misses are 820 cross-tree resource links (synthesized, not transforms') plus R8-10's 16. Skin before existence, escape check, and the copy-failure recount all match design §6.4. Server-absolute references (24) are all inside code samples.
- **Code fences:** fence length grows past the longest backtick run. No block-level element reached the inline path in prose position (0 across five families).
- **`escape_leading`:** no accidental setext heading or list in `output\`.
- **`headings.compact`/`normalize`:** the stack rule matches design §14. `deflists`: `class="dl"` appears only on `<div>` (170 in sampled trees), so the retag never hits a table.
- **CSH:** resolve, `order_doc_sets`, quoting (digit-only identifiers), the byte-exact sort, and empty-map file deletion behave as §9.3–9.5 say (frontmatter is R4-05).
- **Callouts:** the vocabulary is closed and unmapped labels fall back, as documented.
- **Anchor-target rules (§5.7):** hoisting in headings, code spans and pipe tables works. Passthrough `name=` becomes `id=`.
