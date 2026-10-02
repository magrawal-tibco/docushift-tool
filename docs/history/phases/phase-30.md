> Archived from `docs/planning.md` on 2026-10-02. Status: **Complete, 2026-10-01**. Kept verbatim; a heading that says *Planned* was built later in this same section.
> Index of every phase: [`docs/planning.md`](../../planning.md#finished-phases).

### Phase 30: Fifty Thousand Cross-References That Never Worked — **Complete, 2026-10-01**

Found by Phase 29, not by a report. Once `references.anchors()` stopped counting
the `<a id>` markers the converter itself emits, `validate` could finally say
whether a fragment resolves the way the platform resolves it. It could not.

| published tree | fragments resolving |
|---|---:|
| ActiveSpaces, EMS (merged) | 92%, 97% |
| **TIBCO Streaming (unmerged)** | **0 of 45,248** |
| **Runtime Agent (unmerged)** | **0 of 4,531** |

**Roughly 50,000 published cross-references, and not one of them ever worked.**
The platform generates anchors from heading text and ignores markers; Stage 6a
emits a marker for every source anchor and points every cross-reference at one.
The merged trees were fine only because Phase 29 had just taught Reframe to
target headings.

Nothing had ever reported it, and the reason is the phase's lesson: the checker
resolved a fragment against the markers the emitter had written. **Six phases of
green anchor checks, confirming the tool agreed with itself.**

#### Decisions

| decision | what got built | why not the obvious alternative |
|---|---|---|
| **A marker is resolved to the nearest heading** | `transforms/fragments.marker_targets`: the *next* heading if only blank space separates them, otherwise the *previous* one | Those are the two shapes the corpus has -- a target hoisted above the heading it labels (which is where `markdown.anchor_marker` puts it, so the marker cannot pollute the heading's slug), or one part-way down a section. Guessing a synthetic anchor instead would replace a link that fails visibly with one that fails quietly somewhere else. |
| **A whole-tree pass, after every document and before the swap** | `converter.driver._retarget_fragments` | A fragment names a heading in *another* file and the converter emits one document at a time, so at render time the target may not exist yet. The same reason CSH resolution already runs there. |
| **What cannot be placed is left alone and counted** | `FRAGMENT_UNPLACEABLE`, a warning | The link still reaches the right *page*; the remedy is a heading the source does not have, which is an authoring decision this tool may name and must not make. |
| **This is a demotion and is documented as one** | A link that pointed at a sentence now points at the section containing it | Less precise than the author wrote, and the whole of what the platform can express -- the same trade `csh._value` took for Help buttons. The alternative on offer is not precision, it is a link that goes nowhere. |

#### Built, and what it measured

`transforms/fragments.py` (`marker_targets`, `retarget`) and one pass in the
converter. Register **61 → 63**. **1,665 tests pass**, lint clean.

Re-converted every eligible version: **52,930 cross-references retargeted across
34 versions.**

| tree | before | after |
|---|---:|---:|
| TIBCO Streaming | 0 / 45,248 | **45,248 / 45,248 (100%)** |
| Runtime Agent | 0 / 4,531 | **4,498 / 4,531 (99%)** |
| ActiveSpaces (unmerged) | — | 117 / 141 |
| EMS (unmerged) | — | 1,351 / 1,464 |
| **total** | | **51,220 / 52,015 (98%)** |

**The residue is not this phase's.** 170 of the remaining links name a marker
that is *absent from the target file altogether* -- a cross-reference to an
anchor the source never emitted, which is the `ANCHOR_MISSING` class Phase 7b
measured at 11.6% and which no retargeting can reach. The other 625 are
DataSynapse, out of scope and not re-converted.

**Most of them were in the navigation, not in the prose.** The first run of
this pass fixed the page bodies and `validate` still reported 18,112 missing
anchors -- **18,047 of them from `toc.yml` and 65 from `.md` files**. A TOC node
for a same-page section carries `path: "foo.md#anchor"`, and that anchor is a
marker like any other. The pass now rewrites the value in place rather than
re-emitting the YAML, so every other byte of the file is unchanged and a
re-convert stays diffable. Retargeted went 52,930 → **71,006**.

**Three more long-path traps, all the same shape.** `FolderIndex` and the
per-folder walk in `validation/links.py` used `rglob`, so the index did not hold
pages that are really there and every reference to one was reported broken --
263 `LINK_BROKEN`. `artifacts._check_redirects` tested `exists()` unprefixed --
60 more. Each one is `rglob` omitting an over-limit file *silently*, which
`utils/longpath.walk_files` exists to prevent and says so in its own docstring.
Phase 28 hit it once and Phase 29 twice; the deeper folders make it the default
failure of any new walk.

**And one defect this phase's own folders created.** `relocate` puts pages in
lower-cased slug folders while assets kept their source casing. ActiveSpaces has
a source directory `Concepts/` and a page folder `concepts/`: on Windows the
copy lands in whichever exists, so the tree looks right and every image link in
it reads `../Concepts/…` against a directory spelled `concepts`. On Linux those
are two directories and the image 404s -- **a defect that could not be seen on
the machine that produced it.** `packer.asset_destination` lower-cases the
directory (never the filename, §6.4's rule) and the copier and the link rewriter
both go through it, because the whole failure was the two disagreeing.

#### The published target, end to end

| | before Phase 29 | now |
|---|---:|---:|
| `validate` errors | 352 | **0** |
| `ANCHOR_MISSING` | 70,273 | **537** |
| `REDIRECT_SHADOWED` | 340 | 124 |

Fragments resolving in the published trees: Streaming **45,248 / 45,248**,
Runtime Agent 4,498 / 4,531, ActiveSpaces 1,730 / 1,736, EMS 14,171 / 14,178 --
**65,647 of 65,693 (99.9%)**. The 537 that remain name an anchor the source
never emitted at all, which no retargeting can reach.

**One import had to be inverted.** `transforms/fragments.py` needs
`validation.references.mask_code` -- the masker that stops a `# comment` in a
shell sample being read as a heading -- and `transforms` sits *below*
`validation`. At module scope the chain sync → converter → transforms →
validation → sync made `import docushift.sync` fail on a partially-initialised
package. Imported inside the function instead, with the reason written down:
reimplementing the masker would be worse, because two copies of it is how one of
them stops being fixed.

---
