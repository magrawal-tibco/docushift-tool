> Archived from `docs/planning.md` on 2026-10-02. Status: **Complete**. Kept verbatim; a heading that says *Planned* was built later in this same section.
> Index of every phase: [`docs/planning.md`](../../planning.md#finished-phases).

### Phase 11: The Landing Page Keeps Its Product, Loses Its Portal

`online-help` is navigated by `toc.yml` and needs no `index.md` — Phase 10b's `INDEX_UNLINKED` already excludes it, and Phase 10's note that `online-help`'s missing index is "still open" is hereby **closed as not-a-gap** rather than left pending.

Two changes to what that navigation and its landing page contain, both of them subtractive in spirit: the What's New topic becomes the first topic in `toc.yml` when it says something, and `_templates/Home.md` stops carrying the doc-portal blocks that only make sense on `docs.tibco.com`.

#### 11a. What's New first, unless it is still the template

**Measured over 903 Flare roots.** 797 carry `_templates/`; 648 carry a What's New file. The filename is not stable — `Whats-New.htm` dominates, with `Whats-New.html` (12), `What_s-New.htm` (9), `Whats_New.htm` (6), `What's-New.htm` (5) and per-component variants (`-client`, `-server`, `-old`) behind it — so the file is found by a normalized-name match inside `_templates/`, not by one literal.

**481 of the 648 are real; 167 are not.** The 167 are the authoring template shipped unfilled, and its main content is verbatim:

> What's New \[Provide list of update made to the product documentation. You can either provide list or categorize in sections of different features and components. You can also provide links to the topics which are updated.] \[Feature Name] \[Use sections with h2 styles to further categorize new features.]

**The detection rule needs no threshold, and that is why it is trustworthy.** Take the main content's text, drop every `[...]` span, drop the "open topic with navigation" chrome, drop the leading "What's New" heading, strip all non-alphanumerics, and count what is left. Across 654 files the residue is **0 for 167 files, 60+ for 467, 20–59 for 20 — and never between 1 and 19.** The twenty in the middle are genuine short releases ("No new features have been added in this release."). A gap that wide is not a tuned cutoff; `residue == 0` *is* the rule, and the 167 split as 5 empty main content and 162 unfilled stub.

| | versions | what changes |
|---|---|---|
| Real, already in the source TOC | 407 | entry **moves** to the front |
| Real, not in the source TOC | 74 | newly injected; today `_rejection()` discards these as `unreferenced-template` |
| Placeholder, in the source TOC | 4 | entry **removed** from nav |
| Placeholder, not in the source TOC | 163 | unchanged — already discarded today |

The 4 in row three are the only versions that lose an existing navigation entry, and they lose a page whose entire body is bracketed instructions to the writer.

**Position: second, after `_templates/Home.md`.** Home is the landing page and stays the entry point.

```
before                        after
- Home                        - Home
- Installation Guide          - What's New
  - What's New                - Installation Guide
- Administration Guide        - Administration Guide
```

The 74 injections also mean `_rejection()` can no longer treat an unreferenced What's New as chrome: the TOC builder decides it is referenced, so the rejection rule has to be asked *after* that decision rather than before it.

#### 11b. `Home.md` keeps the product, drops the portal

The converted landing page today ends with blocks that belong to the documentation website, not to a published version folder — and because their links were external or dropped, most of them render as bare text lists:

```
## Release Documents            ## Downloadable PDF Guides
- Readme                        - Installation Guide
- Release Notes                 - Introducing Grid Server
- License Agreement             - Administration Guide
...                             ...
```

Keep the overview and Key New Features; cut from the first portal block onward. The blocks are a **closed, measured set** — `Release Documents` (545), `Related Product Documentation` (537), `Most Visited Topics` (482), `Downloadable PDF Guides` (457), `Videos` (49), `Key Guides` (27), `Recommended Topics` (18), plus the `Related Products Documentation` and `Downloadable PDF Guide` spelling variants — so truncation is at the first of those labels rather than at "the section after Key New Features".

**Why the label list and not the Key-New-Features anchor.** 421 of 778 Homes have a Key New Features section and 351 do not; anchoring on it would leave a third of the corpus untrimmed. More importantly, 10 versions carry *genuine* feature subsections after it (`Server Improvements`, `Security`, `Governance & Security`, …), and anchoring would delete them. Truncating at the first portal label keeps those.

Run over all 778 Home files: **688 trimmed, 90 untouched** (no portal block present), and **0 in which a Key New Features section would be cut**. The headings kept before the cut are 2 for 446 files, 1 for 193, 3 for 31.

The h1/h2 lens is not enough on its own — `datasynapse`'s Home has exactly one `h1` and no `h2`, yet converts to a page with `## Key New Features`, because Flare styles these labels with classes rather than heading tags. The detector therefore reads the *converted Markdown* headings, which is the form the rule is actually stated about.

#### 11c. `_templates/` in the published tree is content, and stays

Phase 10 left open whether the `_templates/` segment surviving into `online-help/<version>/` was chrome leaking out of the Flare build. **It is not.** The directory is where a Flare project keeps the pages that are common to the whole product rather than to one guide, and the corpus's own TOCs treat them as topics: **1,737 `_templates/` paths are TOC entries across 660 of 676 roots** — legal 657, support 649, what's new 381, home 32, other 18. A rule that stripped the directory would be stripping a reader's landing page, legal notice and support page.

So the exclusions stand exactly as already defined, and no new one is added:

- a `_templates/` file no TOC entry reaches and that is not the `DefaultUrl` is not converted (`unreferenced-template`, §5.1.5);
- a What's New page still holding the authoring template is not converted even where a TOC entry *does* reach it (`placeholder-template`, 11a above).

Everything else under `_templates/` publishes where the source put it. The directory name is a Flare convention showing through into the output tree, and that is the same trade every other source directory name gets: the path is the source's, the content is the product's.

##### Acceptance

Re-convert and re-sync `datasynapse`. `logviewer 1.0.0`, `manager 7.1.1`, `manager 7.2.0` and `hpc-cloud-adapter 2.2.0` each show What's New as the second `toc.yml` entry; `hpc-cloud-adapter 2.0.0` and `2.1.0` show none, and no `Whats-New.md` is published for them. Every `Home.md` on the shelf ends at Key New Features with no `Release Documents` or `Downloadable PDF Guides` block. `validate` reports no new `LINK_BROKEN` — the trim removes links, so the risk is an anchor elsewhere pointing into a cut section. Then the full suite.

---
