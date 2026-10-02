> Archived from `docs/planning.md` on 2026-10-02. Status: **Built, 2026-09-22**. Kept verbatim; a heading that says *Planned* was built later in this same section.
> Index of every phase: [`docs/planning.md`](../../planning.md#finished-phases).

### Phase 17: WebWorks Rewrites Its Links in the Coordinate System It Does Not Publish In — **Built, 2026-09-22**

The `tra` family is the second to go end to end and the **first non-Flare family to reach `validate`**. `download` 15/15, `extract` 15/15, `convert` 15/15 with 0 failures, `sync` 62 rows and 0 failed, idempotent on a third run. Then `validate --target-dir` over the published tree reports **3,862 `LINK_BROKEN`** and exits 1.

The split is exactly the engine line, which is the whole finding:

| product | versions | engine | `LINK_BROKEN` | `ANCHOR_MISSING` |
|---|---|---|---|---|
| `tibco-runtime-agent` | 5.12.2 / 5.12.3 / 5.12.4 | WebWorks | 2,398 | 267 |
| `tibco-administrator-enterprise-edition` | 5.12.2 / 5.12.4 | WebWorks | 996 | 49 |
| `tibco-designer-add-in-for-tibco-business-studio` | 1.0.0 – 1.5.0 (8) | WebWorks | 468 | 0 |
| both `5.13.0` | 2 | **Flare** | **0** | **0** |

**All 13 WebWorks versions fail. Both Flare versions are clean.** Phases 8, 14, 15 and 16 all measured on `ems`, which is Flare, and Phase 5d proved WebWorks against the *converted* tree — where the links are internally consistent and nothing was wrong. No WebWorks version had ever been walked by `validate` in its published form.

#### 17a. Two coordinate systems meet in one `relpath` call

`engines/webworks.py` builds a topic index once in `_scan`, and resolves every link through it in `_topic`:

```python
# _scan, line 1025 -- value is the TREE-relative source path, suffix-swapped
index.topics[source.lower()] = links.to_markdown(PurePosixPath(source))

# _render, line 1194-1201 -- self.output is the UNIT-relative OUTPUT path
output = PurePosixPath(_join(unit.name, relative))

# _topic, line 411
return links.emit(links.relative_to(self.output, target), fragment)
```

`relative_to` is handed a **source in output coordinates and a target in source coordinates**. The key is right — tree-relative is the correct lookup coordinate, and the docstring defends it. Only the *value* is in the wrong space.

For Flare the two spaces coincide: `architecture.md` §5.1.2 keeps the output tree mirroring the source precisely *so that* link rewriting is a suffix substitution. WebWorks publishes per unit, and `subtree_name` drops the book root — so the spaces differ by exactly the segment between the version root and the book, which is what appears in every broken link. The two published layouts both show it:

| book | `unit.name` | emitted | on disk |
|---|---|---|---|
| `…-5-12-2/designerhelp/tib_Designer_palettes` | `""` | `tibco-runtime-agent-5-12-2/designerhelp/tib_Designer_palettes/palette.4.03.md` | `palette.4.03.md` |
| `…-5-12-4/trahelp/tib_TRA_upgrade` | `tib_TRA_upgrade` | `../tibco-runtime-agent-5-12-4/trahelp/tib_TRA_upgrade/migrate.2.5.md` | `tib_TRA_upgrade/migrate.2.5.md` |

The second is the arithmetic proof: the leading `../` is `relpath` climbing out of a one-segment output directory before descending the source path. A flat book gets no `../` because its output parent is already `.`.

`subtree_name`'s own docstring named this failure mode before it happened — *"Two of them would be two answers, and two answers here put a topic's pages and that topic's images in different subtrees — every image on the version 404s and nothing reports it, because each half is internally consistent."* That is this defect, one field over: pages and *links to* pages rather than pages and images.

**The target identity was never wrong.** Every broken link names the right file and the right `#fragment`; only the prefix is in the wrong space. Re-resolving all 3,862 through `output_map` and testing the published tree on disk:

| | |
|---|---|
| `LINK_BROKEN` reported | **3,862** |
| parsed back out of the report | 3,859 (3 lost to console line-wrapping, see 17c) |
| target found in `output_map` and **present on disk** | **3,856 (99.9%)** |
| no `output_map` row — genuinely dangling | 3 |

So this is a rebase, not a repair: the fix is expected to take 3,862 to **3**, and those 3 should be re-checked upstream rather than assumed.

#### 17b. The fix puts the index in output coordinates

One line, at the one place the value is written. `_scan` already takes `context`, and `subtree_name` is a pure function of the book root, so the unit name is available there:

```python
for relative in book.topics:
    source = _join(book.name, relative)
    index.topics[source.lower()] = links.to_markdown(
        PurePosixPath(_join(context.subtree_name(book.root), relative))
    )
```

The key stays tree-relative — `_topic`'s docstring is right that a cross-book popup and a `../other_book/x.htm` must arrive at the same table through the same coordinate. `index.topics` is read at **exactly one site** (line 401), so the value's space is not load-bearing anywhere else; `index.anchors` and `index.referenced` are keyed on the same tree-relative string and are untouched.

**The other three engines need checking, not assuming.** Flare is proven correct by `ems` and by both `5.13.0` versions here. DITA and DocBook also publish flat or per-unit and have never been through `validate` either; each builds its own map and may or may not have the same mismatch. That check is part of this phase — a `validate` run over one published DITA version and one DocBook version — and whatever it finds is reported before any second fix is written.

#### 17c. A finding rewrites itself on the way to the terminal

`validate` **crashed** on this run with `UnicodeEncodeError: 'charmap' codec can't encode character '\U0001f4af'` — after the whole validation had completed, in the reporting loop at `cli.py:1649`. There is no 💯 anywhere in the corpus. The finding was:

```
palette.4.24.md:100: tibco-runtime-agent-5-12-2/designerhelp/…
```

`console.print` is given an **f-string with the path and message interpolated into rich markup**, and rich's emoji substitution is on by default: `:100:` is the shortcode for 💯. The finding is on line 100, so `.md:100:` became `.md💯`.

The crash is the lesser half. On a UTF-8 terminal there is **no error at all** — the line number is silently replaced by an emoji and the finding still prints, looking fine. The cp1252 console is the only reason anyone found out. The same interpolation also passes `[` through as markup, so a path containing brackets is eaten rather than printed.

Three sites share the pattern — `cli.py:1649` (`validate`), `cli.py:1980` (`report`) and `cli.py:2252` (`csh`) — and no site in the tool currently sets `emoji=False`, `markup=False` or `highlight=False`. The fix is to render untrusted text as data rather than as markup at all three: keep the colour on the literal parts, pass the path and message through `rich.markup.escape` with emoji off. A finding is machine output and must survive the terminal byte for byte.

This is filed here rather than as its own phase because 17a is the reason it was discovered, but it is independent of the link fix and lands first — otherwise the acceptance run for 17b cannot be read.

#### Acceptance

1. `convert --family tra --force`, `sync --family tra --force`, `validate --target-dir` over all 15 versions.
2. `LINK_BROKEN` **3,862 → 3**, and each of the 3 named with the upstream file it wants.
3. Both Flare versions stay at **0** — the fix must not move a coordinate that was already correct.
4. Output file count unchanged at **4,685**: this phase rewrites link text inside files, it does not add or remove any.
5. `ems` re-validated unchanged at `LINK_BROKEN` 0 — Flare's path goes through the same `relative_to`.
6. The 316 `ANCHOR_MISSING` are re-resolved through `output_map` the way Phase 16a did, and classified present-upstream vs absent-upstream **before** any decision to fix them. WebWorks' `_anchor` already emits `<a id=>` for wanted targets (line 335), so the Phase 16 remedy may or may not apply here; the count is not assumed to be the same defect.
7. A finding on line 100 prints as `:100:`, and one whose path contains `[` prints its brackets — tested through a cp1252-backed stream so the regression cannot pass only on a UTF-8 terminal.

Unit tests: a WebWorks link between two topics in the same flattened book emits a bare sibling; one from a nested unit to a topic in that same unit emits a bare sibling; one across two units emits `../other/x.md`; a cross-book `WWHClickedPopup` resolves through the same table and lands in output coordinates; the index key stays tree-relative so a `../other_book/x.htm` and a popup naming that book resolve to one entry.

#### Result

| | before | after |
|---|---|---|
| `LINK_BROKEN`, 13 WebWorks versions | 3,862 | **0** |
| `ANCHOR_MISSING`, 13 WebWorks versions | 316 | **0** |
| `LINK_BROKEN` / `ANCHOR_MISSING`, both Flare `5.13.0` | 0 / 1 | 0 / 1 |
| `ems` (6 Flare versions) `LINK_BROKEN` / `ANCHOR_MISSING` | 0 / 84 | 0 / 84 |
| output tree, `tra` | 4,685 files | **4,685 files**, unchanged |
| `validate --target-dir` over all 93 folders | exit 1 | **exit 0**, 85 warnings, 0 errors |
| suite | 1,327 pass | **1,334 pass** (+7), lint clean |

`LINK_BROKEN` went to **0**, not the predicted 3: the three that had no `output_map` row were the three the console wrapped mid-path in 17c's report, so they were never dangling — they were unreadable. The measurement was right about 3,856 and wrong about why the other 3 were missing, which is the reporting bug proving itself a second time.

`ANCHOR_MISSING` 316 → 0 was **not predicted**. Acceptance criterion 6 assumed a separate defect; it was the same one. The 85 warnings that remain are all Flare — 84 on `ems` (unchanged for five phases) and 1 on `tibco-administrator-enterprise-edition` 5.13.0 — and none of them are WebWorks.

**17b shipped differently than planned.** Putting `subtree_name` inside `_scan` does not work: `_scan` runs inside `units()`, *before* the driver calls `subtree_names`, so `context.subtrees` is still empty and `subtree_name` falls back to the full tree-relative path — the original bug, restored. The transform had to move to lookup time instead. `_Index.topics` now stores `(book.root, relative)` — deliberately not a finished path — and `_topic` completes it with `context.subtree_name(root)` once the driver has populated `context.subtrees`. A unit test caught this; nothing about it was visible from reading the code.

**A second instance of the same confusion was hiding one field over.** `renderer.key` was built in output coordinates while `index.anchors` and `index.referenced` are keyed tree-relative, so `wanted` came back empty for every book that did not take the version root and `<a id=>` was silently never written for any of them. That is the 316 `ANCHOR_MISSING`. `_convert` now derives `within = _join(book.name, relative)` and uses it for both `key` and `base`, keeping them in the index's coordinate while `output` stays in the publishing one. The `WebWorksRenderer.__init__` comments had the two spaces written the wrong way round, and `Unit`'s docstring in `engines/base.py` said `name` is "the unit's path relative to the extracted tree" — which is the misconception itself, in the definition. Both corrected.

**The test harness was the reason this survived Phase 5d.** `run()` in `test_webworks.py` named each unit by its full tree-relative path instead of going through `subtree_names`, so `unit.name == book.name` in every test and the two coordinate systems were identical in the fixture. The harness now calls `subtree_names` exactly as the driver does; three tests that asserted book identity through `unit.name` were retargeted at a new `Run.roots()`, and one test expecting `../reference/ref.md#p9` was updated — that expectation *was* the bug, written down and locked in.

**DITA and DocBook were checked statically, not measured.** No DITA or DocBook version is converted yet, so there is no published tree for `validate` to walk and that half of the plan is blocked rather than done. Reading the code: `dita.py:286` and `docbook.py:287` both pass `self.output` and `target.output`, two fields written in the same unit-relative space (`dita.py:957`, `docbook.py:475`), and `flare.py:314` does the same. WebWorks was the only engine whose index spans several books under one unit, which is the only place the two spaces can diverge. This stays open until a DITA and a DocBook family reach `validate`.

---
