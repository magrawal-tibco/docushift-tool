# Layout test: do the menu moves come from the old layout? (17 Nov 2026, DOCOPS-375)

**Answer: no.** The new rule leaves the move count **exactly the same** on all four test versions. The new rule is Phase 78 (pages by menu depth) plus Phase 81 (drafted `depth:` entries). The count stays the same:
- with a deep draft;
- with a shallow "whole chapters" draft;
- for three of the four, even with no merging at all (one page per converted topic).

The moves come from how `verify` reads the old docs.tibco.com menu, and from the extra parent levels the converter adds. They do not come from how `reframe` packs pages.

**Recommendation:** re-laying out Control Plane, iProcess, BusinessWorks, BPM or WebFOCUS would not remove these findings. Fix the old-menu reader in `verify` instead, which needs no republish.

## How it was measured
- **Moves now:** the latest verify run per version in `cache/state.db` (`VERIFY_TOC_MOVED`). The kinds are:
  - A: `(top)` → page;
  - B: heading group (`title:`) → page;
  - C: other parent;
  - D: same page, other heading;
  - E: raised to top.
- **Harness** (`C:/tmp/layout-test/measure.py`): verify's A5 step (old menu → `toc.yml` via `toc.by_page`), copied from `Verifier.version`. Against the published folders it reproduces the recorded counts exactly.
- **New layout:** `Reframer.reframe_one(..., output=C:/tmp/layout-test/out/...)` in standalone mode, which records nothing. The depth entries (and `merge: true` for WebFOCUS) were set in memory. `config/reframe.yaml`, `reframed/` and the docs repos were not written. State and catalog were copies.
- **Drafts** (`C:/tmp/layout-test/draft.py`, Phase 81 criteria applied mechanically):
  - a guide of 5,000 words or less is one page;
  - otherwise each chapter gets the shallowest depth at which its largest page is 5,000 words or less, capped at depth 2 (depth 3 above 30,000 words);
  - a second variant sets every chapter to depth 1.

## Results
Moves are given as the total, then A/B/C/D/E.

| Version | Moves now | Depth draft | Whole chapters | Unmerged | Pages now | Pages, depth draft | Pages, whole chapters |
|---|---|---|---|---|---|---|---|
| Control Plane 1.20.0 | 50 (50/0/0/0/0) | 50 | 50 | 50 | 195 | 221 | 148 |
| iProcess 11.9.2 | 78 (73/1/1/3/0) | 78 | 78 | n/a | 164 | 287 | 32 |
| BusinessWorks 6.12.0 | 77 (37/0/40/0/0) | 77 | 77 | 77 | 544 | 1,148 | 164 |
| WebFOCUS 9.3.8 | 88 (38/0/50/0/0) | 88 | 88 | 88 | 2,962 (unmerged today) | 2,107 | 300 |

## What moves, and why
- **Control Plane (50 A).** `old_toc.flare` drops each Flare sub-project's merge node and lists the sub-project menus at the top level: Flogo, BW5/BW6, EMS, Developer Hub, Control Tower. Flare and the converter nest them under Managing Capabilities.
- **iProcess (73 A).** The DB2, Oracle and SQL Server admin sub-projects are read at the top level, as in Control Plane. There are also 3 real anchor mix-ups, caused by a duplicate `#tibco-product-overview-1`.
- **BusinessWorks (37 A + 40 C).**
  - The package has three Flare roots. The reader lists them flat, while the converter wraps each in a guide page.
  - Each of the 40 C moves is a topic the old menu lists 2–9 times; each extra listing counts as a move.
- **WebFOCUS (36 A + 50 C).**
  - The package has several roots, listed flat by the reader and wrapped by the converter.
  - The 50 C moves are topics listed twice in the old menu: shared Windows/UNIX installation topics, and support and legal pages.

## What would remove them (verify only, no republish; needs approval)
1. Splice each Flare sub-project at its merge node in `old_toc.flare`, as Flare and the converter do. Give each of several Flare roots its own heading, as `_wrap` already does for DITA.
2. In `by_page`, treat a converter wrapper page (titled like the merge node or the root guide) as the same parent, as Phase 60 does for heading-only rows.
3. Report a topic listed N times in the old menu once, not as N−1 moves.
4. That leaves about 5 real iProcess anchor and key collisions.

## Drafted depth entries
185 lines of YAML, scoped to one version each, with 0 unmatched:
- Control Plane: 88 entries;
- iProcess: 14;
- BusinessWorks: 37;
- WebFOCUS: 38.

They are in `C:/tmp/layout-test/entries.yaml`, and the whole-chapter variants are in `C:/tmp/layout-test/whole-*.json`. Example (iProcess):
```yaml
- {guide: "Architecture Guide", depth: 1, versions: ["11.9.2"]}
- {guide: "TIBCO iProcess Engine Administrator's Guide", chapter: "Administrator's Guide", depth: 2, versions: ["11.9.2"]}
- {guide: "TIBCO iProcess Engine Database Administration Guide", chapter: "Administration Guide (DB2)", depth: 2, versions: ["11.9.2"]}
```

All test files are in `C:/tmp/layout-test`. The copies of state and catalog there (886 MB) can be deleted.
