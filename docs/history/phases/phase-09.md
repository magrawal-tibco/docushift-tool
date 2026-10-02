> Archived from `docs/planning.md` on 2026-10-02. Status: **Complete**. Kept verbatim; a heading that says *Planned* was built later in this same section.
> Index of every phase: [`docs/planning.md`](../../planning.md#finished-phases).

### Phase 9: A Generated `toc.yml` Points at Pages, Not at Artifacts

Found on the first real `sync` of a family (`datasynapse`, 2026-09-17), by reading the shelf rather than by a check. `release-information/7-2-0/toc.yml` lists the release-notes PDF and the readme TXT as two navigation items; `user-guides/` and `reference-documents/` do the same, and `archives/` lists forty ZIPs. **None of those is a page.** AEM's `toc.yml` is the reader's navigation, so every item in it is a promise that there is somewhere to land, and a PDF is a download. Each of these folders has exactly one page — the `index.md` §6.2.2 already generates — and it already carries the file list as links.

This is a **spec change, not a bug fix**: `architecture.md` §6.2.2 currently says, in as many words, "`toc.yml` is flat … with one item per file carrying `title`, `path`, `type` and `bytes`." The code does what it was told. So the doc moves first and the template follows it.

**The rule, stated once for all four generated TOCs:** a generated `toc.yml` contains exactly one item, pointing at the `index.md` beside it, titled as that index titles itself. The per-artifact list does not disappear — it stays in `index.md`, which is where a list of downloads belongs.

| Doc-class | `toc.yml` before | `toc.yml` after |
| :--- | :--- | :--- |
| `user-guides` | one item per PDF | one item → `index.md` |
| `release-information` | one item per relnotes/readme | one item → `index.md` |
| `reference-documents` | one item per licence/VPAT/doc file | one item → `index.md` |
| `archives` | one item per catalog archived row | one item → `index.md` |
| `online-help` | **unchanged** — a real nav tree of real pages | unchanged |

**`archives/` is in scope, decided rather than assumed.** Its entries are the one case with an argument for staying: they are catalog rows, not files in the folder, and most have no local file at all — so unlike a PDF they were never implying a page-per-entry. It collapses anyway, on the ground that *one* rule for generated TOCs is worth more than a defensible exception. Its `index.md` keeps the complete version history and its ZIP links, which is the part §6.2.3 actually argues for.

**The entry carries `title` and `path` only.** `type` and `bytes` described the artifact; `index.md` is not one, and publishing `type: "md"` beside `bytes: 412` for a generated page is noise that invites something downstream to branch on it.

##### What changes

| File | Change |
| :--- | :--- |
| `docs/architecture.md` §6.2.2, §6.2.3 | Rewrite "Shape of the generated files" — the per-file `toc.yml` rule becomes the single-entry rule; state the page-vs-artifact reason so it is not re-litigated |
| `docs/design.md` §10.5 | The `toc.yml` step of the document-index algorithm |
| `config/aem_templates/documents_toc.yml.j2` | Loop over `entries` → one item; drop `type`/`bytes` |
| `config/aem_templates/archives_toc.yml.j2` | Same |
| `sync/documents.py:render_toc` | Takes the title, not the entries; the docstring's "flat — these doc-classes have no hierarchy" is now the wrong reason for the right shape |
| `sync/archives.py:render_toc` | Same |
| `tests/unit/test_documents.py:277`, `test_archives.py:145` | Assert one item at `index.md`, and assert the artifact list is still complete **in `index.md`** — the point is that it moved, not that it went |

##### What this is expected *not* to touch

- **`online-help/toc.yml`** — built by `converter/navigation.py`, a genuine tree of converted pages. Out of scope, and the rule above says why.
- **`validation/artifacts.py`** — it walks every `path` in a `toc.yml` and raises `LINK_BROKEN`. It needs no change: `index.md` is a sibling and resolves. The check gets *weaker*, though, because the artifact paths it used to verify are no longer in the TOC. Whether `validate` should follow `index.md`'s links instead is a real question and is **deliberately left open** rather than folded in here.
- **`sync/archives.py:151`'s currency check** compares the published file set against `expected | {"index.md", "toc.yml", "metadata.yml"}` — a set of filenames, not of TOC entries, so it is unaffected. Confirmed by reading, not assumed.

##### Acceptance

Re-sync `datasynapse` to a scratch shelf and read the four doc-classes: each `toc.yml` has exactly one item at `index.md`, each `index.md` still lists every artifact the old TOC did, and `validate` reports no new `LINK_BROKEN`. Then the full suite.

---
