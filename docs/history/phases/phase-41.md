> Archived from `docs/planning.md` on 2026-10-06. Status: **Complete, 2026-10-06**. Kept verbatim.
> Index of every phase: [`docs/planning.md`](../../planning.md#finished-phases).

### Phase 41: Flare Source Topics Shipped in the Output — **Complete, 2026-10-06**

**Why.** Validating `ibi-docs-aem` on 2026-10-06 (run 393) gave 45 `LINK_BROKEN` errors.
24 of them point at a page that is in the package but was never converted: a Flare
*source* topic (`.htm` as authored, not as built) that the build copied into the output
by mistake. It has no `#mc-main-content`, so §5.1.6 drops it as `CONTENT_MISSING`, and
every link to it breaks. The other 21 (ODH mainframe connectors, `inst_zos_new47`) point
at a page that is empty in the source too, and stay as they are.

Measured 2026-10-06 (`C:\tmp\an_fst_post.py`) over every extracted family in `families/`:

- **55 files** open with `<?xml …?>`, carry `xmlns:MadCap`, lack the container, and carry
  no `data-mc-runtime-file-type`. **All have real content** (every one ≥ 100 words).
  15 are under `ja-jp/`, 16 under Client 9.3.5's `de-de`/`es-es`/`fr-fr`. **24 are
  English**, in 11 versions: FOCUS 9.3.0–9.3.4 (`DisplayFormats114`, `dba100`, `fds83`),
  App Studio 9.3.3–9.3.4, and Client 9.3.2–9.3.5 (`Link_Tile_8207`). The same page is
  built normally in the neighbouring versions, e.g. Client 9.3.0, 9.3.1 and 9.3.6+.
- **Only ibi Flare projects so far.** The TIBCO families hold 1,700 XML-prologue files,
  and every one has the container. `html-to-md`'s cache was not surveyed (a full search
  ran over 10 minutes and was stopped). That is unmeasured, not shown to be clean.
- **A source topic is not finished output.** Across the 24: 1,023 `MadCap:variable`
  elements that are *empty* (the build fills them in, so converting from `<body>` drops
  every product name), 1,226 `MadCap:conditions` attributes (text for other products,
  e.g. `Product.webfocus` paragraphs in a FOCUS page), 1,775 `MadCap:keyword` index
  markers and 30 `MadCap:xref` links.
- **The built pages beside it give the answers.** In a built topic, a variable is
  `span.mc-variable.<name>` holding its value (`ibi-productNames.focus-3rd` → "FOCUS",
  5,978 times in FOCUS 9.3.0). A kept condition shows as `data-mc-conditions`. In FOCUS
  9.3.0, `Product.focus` appears on its own 1,194 times and `Product.webfocus` never.
  In Client 9.3.1, `Product.webfocus` appears on its own 2,121 times. Elements tagged with
  both appear in both builds, which is how Flare's include-any rule behaves.

#### Decisions

| decision | choice | why |
|---|---|---|
| **What counts as a source topic** | An HTML file that opens with an XML declaration, has `xmlns:MadCap` on `<html>`, no `data-mc-runtime-file-type` and no container | All 55 match, and none of 1,700 built XML-prologue files does. A Javadoc page has no MadCap namespace, so §5.1.6's "no fallback chain" still holds for everything else |
| **What gets converted** | Its `<body>`, through the same passes as every other topic | It is already in the planned set, so links to it are already written. Only the page itself is missing |
| **Variables** | Filled from the values the root's built topics show. A name no built topic shows becomes empty and is counted | Dropping 1,023 product names leaves sentences like "Use  to create a report" |
| **Conditions** | A tag is *kept* if a built topic in the root carries it alone. An element is removed when none of its tags is kept and at least one is known to the root. Tags the root never shows are left alone and counted | Matches the build's include-any behaviour in both FOCUS and Client. Removing on an unknown tag would delete text on a guess |
| **Index keywords** | Removed | No other converted topic carries index markers |
| **`MadCap:xref`** | Rendered like an `a href` | 30 links, all to sibling topics |
| **Reporting** | New note `CONTENT_SOURCE_TOPIC`, one row per root: how many topics, variables left unresolved, and condition tags left alone | One finding for the root, not one per page |
| **The parser warning** | Silenced for these files only | Parsing a source topic as HTML is now the intended behaviour |
| **Localized trees** | Same rule wherever the engine already reads | Not widened here. `ja-jp` handling is a separate question |

#### Steps

1. `engines/flare.py`: `_is_source_topic(soup)`. A per-root `_SourceContext` collects the
   variable values and kept condition tags from the built topics, lazily, only if a
   source topic turns up. `_convert` falls back to `<body>` for a source topic after
   resolving variables, removing excluded elements and stripping keywords.
   `FlareRenderer` treats `MadCap:xref` as a link.
2. Findings register (§7.5): `CONTENT_SOURCE_TOPIC`, a convert note.
3. Tests: a source topic converts; a variable resolves from a sibling's span, and one with
   no sibling is counted; a condition tag the root excludes is removed, one it keeps
   stays, an unknown one stays and is counted; `MadCap:keyword` is gone; `MadCap:xref`
   links; a Javadoc page with an XML prologue and no MadCap namespace is still
   `CONTENT_MISSING`.
4. Re-convert the 11 versions with `--force`, product by product (WebFOCUS ran out of
   memory family-wide on 2026-10-06). Re-sync FOCUS and WebFOCUS into `ibi-docs-aem`,
   then re-validate. Expected: 21 errors left, all ODH.

**Built.** Steps 1–3 done; 2,153 tests pass. Checked on FOCUS 9.3.0 into a scratch
folder: 3 source topics converted, 131 elements of excluded conditions removed, no
variable unresolved. FOCUS 9.3.0 also ships a built copy of `DisplayFormats114` under
`910-crlang/`, and the converted source copy matches it: the same 31 "WebFOCUS"
mentions, 15,617 words against 15,423.

**Step 4, 2026-10-06.** The 11 versions re-converted (runs 395–405): FOCUS 3 source
topics each, 131 elements removed; App Studio 9.3.3 4 and 28, 9.3.4 1 and 20; Client
1 each, none removed. No variable unresolved and no unknown condition tag anywhere.
Re-validated `ibi-docs-aem` (run 408): **21 errors, all ODH**, down from 45.
`ANCHOR_MISSING` rose by 123 (24,762 → 24,885). Those are the fragment links into the
newly published pages, now checked because the page exists.
