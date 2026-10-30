# DocuShift findings -- convert run 1108

- **Command:** `docushift convert`
- **Started:** 2026-10-22T11:42:07+00:00
- **Finished:** 2026-10-22T11:50:33+00:00
- **Exit code:** 0
- **Findings:** 4 errors, 6 warnings, 7 notes

## convert

### REFERENCE_UNRESOLVED (error)

A reference producing neither link nor copy -- *design.md invariant 13*

| Product | Path | Message |
| :--- | :--- | :--- |
| tibco-activematrix-bpm@4.2.0 | `BPM_Developer` | 2 reference(s) resolved to nothing |
| tibco-activematrix-bpm@4.2.0 | `Modeling` | 2 reference(s) resolved to nothing |
| tibco-activematrix-bpm@4.2.0 | `os-localization` | 1 reference(s) resolved to nothing |
| tibco-activematrix-bpm@4.2.0 | `tutorials/PLUGINS_ROOT` | 1 reference(s) resolved to nothing |

### FRAGMENT_UNPLACEABLE (warning)

A cross-reference naming an anchor with no heading behind it; left as written and will not resolve -- *planning.md Phase 30*

| Product | Path | Message |
| :--- | :--- | :--- |
| tibco-activematrix-bpm@4.2.0 |  | 8 cross-reference(s) name no anchor marker with a heading behind it in their target; left as written and will not resolve |

### METADATA_MISMATCH (warning)

SuiteHelp release-version / release-date disagreeing with the catalog -- *planning.md Phase 6 contract*

| Product | Path | Message |
| :--- | :--- | :--- |
| tibco-activematrix-bpm@4.2.0 |  | homepage release-version 'Software Release 4.2' != catalog '4.2.0' |
| tibco-activematrix-bpm@4.2.0 | `soahelp` | homepage release-version 'Software Release 4.2' != catalog '4.2.0' |
| tibco-activematrix-bpm@4.2.0 | `tutorials` | homepage release-version 'Software Release 4.2' != catalog '4.2.0' |

### ORIGIN_SITEMAP_MISSING (warning)

No Coveo sitemap page list for this version and no declared template, so no 301.yml was written -- *planning.md Phase 33*

| Product | Path | Message |
| :--- | :--- | :--- |
| tibco-activematrix-bpm@4.2.0 |  | no Coveo sitemap page list for this version (cache/coveo/manifest.json lists no product file for tibco-activematrix-bpm) and no usable template in config/origin-urls.yaml (none is declared), so no 301.yml was written |

### OUTPUT_COUNT_MISMATCH (warning)

Fewer Markdown files on disk than documents converted; two writes resolved to one path -- *planning.md Phase 13*

| Product | Path | Message |
| :--- | :--- | :--- |
| tibco-activematrix-bpm@4.2.0 |  | 7311 document(s) converted but 7309 Markdown file(s) on disk; 2 write(s) landed on another |

### API_LINK_REWRITTEN (note)

Link into an api-reference tree pointed at its published -resources URL -- *design.md §10.7*

| Product | Path | Count | Message |
| :--- | :--- | ---: | :--- |
| tibco-activematrix-bpm@4.2.0 |  | 1289 | 1289 link(s) rewritten to the -resources tree across 3 API tree(s) |

### ASSET_ORPHANED (note)

Unreferenced asset -- 54.6% is normal for Flare -- *architecture.md §5.5.7*

| Product | Path | Count | Message |
| :--- | :--- | ---: | :--- |
| tibco-activematrix-bpm@4.2.0 |  | 44838 | 44795 unreferenced file(s), 446539036 bytes |

### CODE_LINK_FLATTENED (note)

Link inside a code block kept its words and lost its target; a GFM fence cannot hold a link -- *planning.md Phase 8*

| Product | Path | Count | Message |
| :--- | :--- | ---: | :--- |
| tibco-activematrix-bpm@4.2.0 |  | 49 | 49 link(s) inside a code block kept their words and lost their target |

### FRAGMENT_RETARGETED (note)

Cross-references pointed at a heading instead of an inert anchor marker the platform does not honour -- *planning.md Phase 30*

| Product | Path | Count | Message |
| :--- | :--- | ---: | :--- |
| tibco-activematrix-bpm@4.2.0 |  | 1438 | 1438 cross-reference(s) pointed at a heading instead of an inert anchor marker the platform does not honour |

### NAV_NODE_DROPPED (note)

A navigation node with no page and no children -- DITA's lof/lot/ix, Flare's childless headless node -- or a Flare/WebWorks child repeating its parent's page with no bookmark of its own -- *planning.md Phase 5*

| Product | Path | Count | Message |
| :--- | :--- | ---: | :--- |
| tibco-activematrix-bpm@4.2.0 |  | 58 | 58 node(s) dropped assembling the version |

### TOC_ORPHAN (note)

Converted topics in no TOC entry, kept out of toc.yml and unmerged under unfiled/ -- 5.9% for Flare; left in an Unfiled node only when the version has no other TOC entry -- *architecture.md §5.1.4, Phase 43*

| Product | Path | Count | Message |
| :--- | :--- | ---: | :--- |
| tibco-activematrix-bpm@4.2.0 |  | 40 | 38 converted topic(s) in no TOC entry |

### TOPIC_LINK_DANGLING (note)

A cross-reference to a topic this run did not produce; text kept, link dropped -- *architecture.md §5.1.3*

| Product | Path | Count | Message |
| :--- | :--- | ---: | :--- |
| tibco-activematrix-bpm@4.2.0 |  | 2294 | GUID-494A9582-CE21-4077-9E62-0B91709E2E2F.html -> #GUID-494A9582-CE21-4077-9E62-0B91709E2E2F__ID-187-0000002B (anchor absent; link kept, bookmark dropped) |
