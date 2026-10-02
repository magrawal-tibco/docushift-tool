> Archived from `docs/planning.md` on 2026-10-02. Status: **Complete**. Kept verbatim; a heading that says *Planned* was built later in this same section.
> Index of every phase: [`docs/planning.md`](../../planning.md#finished-phases).

### Phase 10: A Version With One Output Root Publishes At Its Version Root

Two items, raised together, that turn out to be one measurement and one correction.

#### 10a. The `doc/html/` prefix is the corpus's normal case, not a staging accident

`online-help/7-2-0/` contains `doc/`, `metadata.yml`, `toc.yml` — every converted page sits under `doc/html/`, and every one of the 1,196 `toc.yml` paths is prefixed with it. This was previously written off as an artifact of staging `datasynapse` from the crawl cache's website-mirror root. **It is not.** Measured over the cache on 2026-09-17, by walking for `Data/HelpSystem.xml`:

| | |
|---|---|
| Flare output roots | 888 |
| version trees carrying them | 611 |
| **single-root version trees** | **491** |
| of those, root sitting *at* the version root | **0** |
| where it sits instead | `html/` (257), `doc/html/` (203), 31 others (`doc/adswift/html`, `doc/mi/html`, `users-guide`, …) |

So the rule in `architecture.md` §5.1.3 — a unit converts into a subtree "named from the root's path relative to the version" — puts **80.4% of Flare versions one or two directories below where the published contract says their content lives**. `datasynapse` is not the exception; it is the ordinary case, and it is only visible now because it is the first family read end-to-end since `validate` landed.

**The rule, in three cases.**

1. **One unit of work** → its subtree name is empty; output goes at the version root. 491 Flare versions.
2. **Several units, none nested inside another** → the **shallowest** root (ties broken by path, which is `find_output_roots`' existing order) takes the version root, and every other root becomes a folder named by its **last segment only**. `doc/html` + `doc/relnotes` publishes as the version root plus `relnotes/`. 93 versions.
3. **Several units with a nested pair, or a name clash in case 2** → today's full relative name, unchanged. 32 + 1 versions.

Case 3 is not a hedge, it is a measurement. Flattening every root onto the version root — the naive reading of "remove the `html` segment" — was tried against the cache and collides in **125 of 125 multi-root versions, 155,647 colliding paths**; BusinessWorks 6.10.0 alone collides 7,101, because separate Flare builds reuse the same `_templates/` chrome and overlapping topic filenames. Case 2 avoids that by giving each non-primary root a folder of its own; it is safe because the only thing that can collide is the folder name against the primary's own top-level entries, which was measured across all 93 and clashes **once** (`stat` 14.4.0, which ships two roots with the same last segment). Nested roots cannot use case 2 at all: the inner root's files are already inside the outer one, so naming the inner root as a sibling folder does not separate them.

The single-root case cannot collide with itself — there is one subtree, so there is nothing to collide with.

The combined `toc.yml` needs no new merging logic: a version folder already has exactly one `toc.yml` covering every unit, so `doc/html/install.md` and `doc/relnotes/notes.md` already sit in the same file. Only their prefixes change.

**The one real conflict, and why it resolves itself.** Collapsing lifts the root's own top-level files up beside the generated `csh.yml`/`toc.yml`/`metadata.yml`. Measured across the 495 single-root roots: no root ships a `toc.yml`, `metadata.yml`, `csh.yml` or `version.yml`, and **38 ship an `index.htm`/`index.html` that converts to `index.md`**. That last one is not a collision to prevent — it is the landing page `architecture.md` §6.1 wants at the version root, arriving on its own. `navigation._free` already tests case-insensitively against the converted set (Phase 8's lesson), so a synthesized container labelled "Index" is given another name rather than written over it. Confirmed by reading `navigation.py:291`, not assumed.

##### What changes

| File | Change |
|---|---|
| `converter/driver.py:261` | `unit_name = _relative(tree, root)` → the shared helper; `handler.units(context)` is materialized to a list first, because the name of the *first* unit now depends on how many there are |
| `engines/roots.py` | new `subtree_names(tree, roots) -> dict[Path, str]` — the three cases above, decided once for the whole version and returned as a lookup. A per-root function could not see the clash in case 2 |
| `engines/base.py` | `unit_name(context, root)` reads that lookup. One definition, because the driver's asset path and the engine's `Unit.name` must agree or assets and pages land in different subtrees |
| `engines/flare.py:388`, `dita.py:556`, `docbook.py:411`, `webworks.py:993` | all four already call `_relative(context.tree, root)`; each becomes the shared helper |
| `converter/base.py` (`ConversionContext`) | carries the unit count the helper reads |
| `architecture.md` §5.1.3, `design.md` | the rule, the 0-of-491 measurement, and the multi-root refusal |

Everything downstream is derived from `unit.name` and follows without edit: the output map, `csh.yml`'s paths, the synthesized `toc.yml`, cross-reference resolution. That is the argument for changing the name in one place rather than rewriting paths at the end.

##### What this is expected *not* to touch

- **Nested-root versions** — 32 Flare version trees, plus the 1 name clash, keep today's full relative names.
- **`online-help`'s missing `index.md` in the general case.** Collapsing hands 38 versions a real one and puts `datasynapse`'s landing page (`_templates/Home.md`) at the version root, but it does not *synthesize* an index where the source has none. Still open, still separate.
- **The `_templates/` directory** appearing in published output. Noted here as an open chrome question; **closed 2026-09-17 as correct behaviour, not a leak** — see Phase 11's note below.

#### 10b. `validate` already follows `index.md`'s links — the recorded gap is wrong

Phase 9 recorded that dropping artifact paths from `toc.yml` weakened `validate`, because `validation/artifacts.py` now sees only `index.md`. **Tested rather than reasoned about:** renaming `TIB_dsp_gridserver_7.2.0_relnotes.pdf` in the scratch shelf and re-running `validate` produced exactly `LINK_BROKEN 1 row(s), 1 occurrence(s)`, `1 error`. `index.md` is a Markdown page, the reference checker walks every Markdown page, and it therefore checks the artifact list wherever that list lives. Nothing was lost. The claim is corrected in `CONTEXT.md` §3 and `architecture.md` §6.2.2.

What is genuinely absent is the **opposite** direction — a file sitting in a published doc-class folder that `index.md` links to nowhere. There is no published-tree orphan check at all (`ASSET_ORPHANED` is a Stage 4 note about the extracted tree, not this), so this is a new check and not a restored one: one function in `validation/artifacts.py` taking the files present, minus the generated four, minus what `index.md` links to.

**It is expected to find nothing, and that is the point.** `render_index` is given the same routed list that decides what gets copied, so every published artifact is linked by construction. The requirement "all files should be linked in `index.md`" is therefore already met; what is missing is anything that would *notice* if a future change stopped meeting it. Hence `INDEX_UNLINKED`, at note severity — a gate that fires on correct output teaches people to skip it (§8.4's rule), and a silent invariant is one refactor away from being false.

##### Acceptance

Re-convert and re-sync `datasynapse` to a clean shelf: `online-help/7-2-0/` lists the converted pages directly, no `doc/` segment anywhere in it, and its `toc.yml` paths carry no prefix. `validate` on that shelf reports no `LINK_BROKEN` — which is the real test of the change, because every one of 1,196 TOC paths and every cross-reference moved at once — and no `INDEX_UNLINKED`. A multi-root version is converted and read: the primary at the version root, the secondary in its own folder, both in one `toc.yml`. A nested-root version is confirmed unchanged. Then the full suite.

---
