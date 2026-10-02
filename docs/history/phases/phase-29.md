> Archived from `docs/planning.md` on 2026-10-02. Status: **Complete, 2026-09-30**. Kept verbatim; a heading that says *Planned* was built later in this same section.
> Index of every phase: [`docs/planning.md`](../../planning.md#finished-phases).

### Phase 29: The Filename Is the URL — **Planned, 2026-09-30**

From `docs/claude-code-naming-spec.md`. AEM generates the published URL itself, one
segment per node in the TOC chain, each segment the lowercased filename cut at 50
characters. **So a page's filename is not an implementation detail; it is the address a
reader sees and a colleague pastes.** Today's names are inherited from MadCap, which
truncates its own filenames at 20 characters, and Reframe names a merged page after its
first topic's *source stem* rather than its title.

**Measured, 2026-09-30.** Of 1,700 merged pages, **428 have a filename that disagrees with
their own title** — `schema` for "Schema Resource", `installation-2` for "Installation",
`attributes-panel-1` for "Attributes Panel". One is actively wrong: a page titled
*Upgrading to Release 5.13.0* publishes as `upgrading-to-release-5-12-4.md`. Separately,
**33 of 1,700 exceed the 50-character limit**, the longest at 74.

#### Answers taken, 2026-09-30 — these were open questions in the spec and are not assumptions

| question | answer | consequence |
|---|---|---|
| How does AEM build a URL? | **The TOC chain of filenames**, not the repo path | `architecture.md` §6.1 and `sync/redirects.published()` describe the wrong model and must be corrected |
| Where does the work live? | **Inside Reframe**, replacing `packer.assign`'s naming rule | No new stage. Reframe already renames, rewrites every link, retargets `csh.yml` and regenerates redirects in one pass |
| Separator | **`-`**, as a config key with that default | The spec's own example showed `_`; confirmed illustrative |
| Section stub | **No `_section_*.md`** — that was the old tool. Where a parent node has no page of its own, the stub takes the folder name | |
| Internal link form | **Relative `.md` paths**, unchanged — AEM resolves them to the generated URL | Confirmed, so the rewriter and `validate`'s on-disk resolution both stand |
| Served URL shape | **`{region}/{lang}/{product}/{doc-class}/{version}/{toc chain}.html`** — no tree segment, `en-us` split **region-first** to `us/en` | `sync/redirects.published()` is wrong in three ways at once, below |
| Heading anchors | **AEM ignores `<a id>` and generates its own** from heading text, lowercased and hyphenated, deduped GitHub-style (`location`, `location-1`, `location-2`) | The largest single piece of this phase — see below |
| Duplicate placements | **A copy per guide**, reported with topic name and usage | |
| Folder layout | **Mirror the merged TOC.** Every page-leading node with page-leading children becomes a folder named after its own file | Overrides the spec's "flat inside each section" |

**The folder answer makes the URL correction much smaller than it looked.** If folders mirror
the TOC, the repo path *becomes* the TOC chain, so the path half of the URL is right by
construction rather than by a new computation.

**The prefix half is wrong in three ways at once**, and `sync/redirects.published()`
(`redirects.py:73`) is the single place all three live:

```
today   {tree}/{locale}/{product}/{doc-class}/{version}/installation/requirements.md
served  {region}/{lang}/{product}/{doc-class}/{version}/installation/requirements.html
```

The tree segment does not appear in a URL; `en-us` splits **region-first** into `us/en`, not
language-first; and the suffix is `.html`. One function, one fix — but see the migration note
below, because that function is also what decides which rows in a published map the tool owns.

#### The anchors are the bigger half of this phase, not the filenames

**Measured, 2026-09-30.** Of 19,083 internal links in the merged tree, **17,937 (94%) carry a
`#fragment`** — 5,475 of them same-page. All 154 `csh.yml` entries carry one. Every published
redirect targets one.

Anchors today are `slugify(topic.source.stem)`, deduped per page. AEM computes them from the
**heading text**. The two agree for **7,153 of 18,657 markers (38%)** — so roughly 11,500
anchors currently name something AEM will never create, and every link and help ID pointing
at one lands at the top of the page instead of at the section.

**And the new rule collides where the old one could not.** 400 of 1,700 pages repeat a
heading: `installed-components.md` has three "Location", three "Syntax", three "Examples";
`view-menu.md` repeats "Add Resource". GitHub-style numbering resolves them and is
replicable exactly, at a cost worth naming — **the suffix is positional**, so inserting a
section above a repeated heading renumbers every later one and moves a published anchor.
No content change prevents that; it is a property of the rule AEM uses.

#### Decisions

| decision | what gets built | why not the obvious alternative |
|---|---|---|
| **A page is named from its title, not its source stem** | `utils/naming.py`: NFKC, decode `u0027`-style escapes, strip apostrophes without a separator, `&`→`and`, drop `®™©`, lowercase, one separator, 50 chars by dropping stopwords then cutting at a separator boundary | `utils/slug.py` stays as it is. It names *repositories and folders* from catalog values, where 50 characters and stopword-dropping would be wrong; two callers with different rules in one function is how both get broken. |
| **Uniqueness is global and case-insensitive, and the earlier page wins** | On collision the later page becomes `<parent-slug><sep><slug>`, re-cut to 50 by shortening the parent part first; `-2` only as a last resort. Every disambiguation reported | `packer.assign`'s current `-2/-3` loop is per-directory and silent. Under the new URL model two pages in different folders can still collide on a segment, so the scope has to widen to the doc set. |
| **A generic title takes its parent's prefix** | `overview`, `introduction`, `summary`, `services`, `requirements`, `before-you-begin` become `installation-overview` | These are the titles most likely to repeat, and a URL ending `/overview` tells a reader nothing. |
| **Folders mirror the merged TOC** | A node that leads a page *and* has children that lead pages becomes a folder named after its own file stem, with its page beside it | The spec asked for one flat folder per section. Nesting is what makes the repo path equal the URL, which is worth more than flatness. |
| **A topic in two guides becomes two pages** | `packer`'s first-occurrence `claimed` dedupe is replaced by per-placement packing; each copy is reported with its topic name and both usages | Sharing one page gives a topic two TOC parents and therefore two URLs for one file, which the new URL model cannot express. **Measured: 36 extra copies corpus-wide, 32 of them DataSynapse (out of scope) — so 4 pages in scope, all EMS 10.4.0/10.4.1.** |
| **Names are persisted and reused** | `rename-map.csv` beside `reframe.yml`: `old_path,new_path,title,toc_breadcrumb,expected_aem_url`. A mapped file is not renamed because its title changed unless `--renormalize` | A published URL that moves because somebody fixed a typo in a title is the failure this phase is meant to prevent, not cause. |
| **An anchor is the slug of the heading AEM will render** | `assign` takes a `heading_of(source)` callable beside `words_of`, slugs it the way AEM does, and dedupes per page with `-1`, `-2` | Computing it from the source filename is what put 62% of them wrong. The callable keeps the packer's rule that it never opens a topic body — the same seam `words_of` already uses, so layout stays testable against a dict. |
| **The `<a id>` markers stop being emitted** | `anchor_marker` and its insertion in `shift_headings` go; `added` drops to 0 for a topic with an H1 | An anchor that looks real and is inert is worse than none — it is precisely what let 11,500 fragments drift wrong without a single check firing. The heading text becomes the one source of truth, and `validate` resolves fragments against it. |

#### Scope

- `src/docushift/utils/naming.py` — new; the slug algorithm and the 50-char rule. Pure, unit-tested.
- `src/docushift/reframe/packer.py` — `assign` names from `Topic.title`; doc-set-wide uniqueness; parent-prefix disambiguation; per-placement packing for duplicates.
- `src/docushift/reframe/pages.py` — `shift_headings` stops emitting the marker; `added` becomes 0 with an H1 and `1 + word_count(title)` without. `rewrite_links` is otherwise unchanged, which is the payoff of relative `.md` links being confirmed.
- `src/docushift/validation/references.py` + `links.py` — a `#fragment` resolves against heading-derived anchors rather than `<a id>`/`name` attributes.
- `src/docushift/reframe/manifest.py` — `rename-map.csv`.
- `src/docushift/reframe/audit.py` — word conservation becomes a per-*placement* equality, not per-topic, or the 4 duplicated pages fail the stage; and its anchor check reads headings.
- `src/docushift/sync/redirects.py` + `docs/architecture.md` §6.1 — the corrected URL model (no tree segment, `us/en`, `.html`), the 50-char per-segment cut, and the old-prefix migration.
- `src/docushift/validation/artifacts.py` — `_check_redirects` resolves against the computed URL table, not the filesystem.
- `config/reframe.yaml` — `naming.separator`, `naming.max_segment`, `naming.generic_slugs`, `duplicates`.
- `policy.py` — the new keys join the currency digest; `_ALGORITHM` → 3.

#### Exit

Every merged page's filename equals `naming.slugify(its TOC title)`, is at most 50
characters, matches `^[a-z0-9]+(-[a-z0-9]+)*\.md$`, and is unique across the doc set
case-insensitively. **The 428 disagreements go to 0 and the 33 over-length names go to 0.**
No two TOC nodes compute the same AEM URL.

**And the anchor half, which is the one that can fail silently:** every `#fragment` in all
17,937 fragment-bearing links, and all 154 `csh.yml` values, resolves to a heading that
exists on the target page under AEM's own rule — measured by recomputing anchors from
heading text and matching, not by trusting the emitter. Today that figure is 38%. No `<a id>`
marker remains in the output. `audit` clean, `validate` 0 errors, and `reframe` run twice is
byte-identical.

#### The migration the URL fix drags with it

`redirects.prefix()` is `published()` with an empty path, and `owned_prefixes` uses it to
decide which rows in a doc-class map this tool is entitled to replace (`redirects.py:150-188`;
everything else is carried through verbatim, which is what protects a hand-added row).
**Change the prefix and the 17,252 rows already published stop being recognised as ours** —
they would be left in place as foreign rows while a full set of new ones is inserted beside
them, doubling every map and leaving the stale half pointing at URLs that never existed.

So the fix needs a one-time migration in the same change: recognise the *old* prefix shape as
also-owned for the purpose of deletion, emit only the new one. Written down here because it
is invisible until it has already happened, and because the map is the one artifact `sync`
merges rather than replaces.

`validation/artifacts.py:_check_redirects` resolves a row's `to` against files on disk. A
`.html` URL will not resolve that way, so the per-version check has to compare against the
computed URL table instead — or it reports `LINK_BROKEN` on every correct row.

#### Built so far — the anchors, 2026-09-30

`utils/anchors.py` (`slugify_heading`, `anchor_run`), `assign` taking a
`headings_of` callable, `shift_headings` losing its `anchor` parameter and the
markers with it, `references.anchors()` reading headings only, and
`csh._value` dropping the identifier's own fragment. `_ALGORITHM` → 3.
**1,625 tests pass**, lint clean.

| | before | after |
|---|---:|---:|
| ActiveSpaces fragments resolving under the platform's rule | — | **1,614 / 1,628 (99%)** |
| EMS fragments resolving | — | **13,821 / 14,178 (97%)** |
| Anchors agreeing with the platform, corpus-wide | 7,153 / 18,657 (38%) | — |
| `csh.yml` entries resolving | **0 / 154** | **154 / 154** |

**The `csh.yml` figure is the one that was not in the plan.** Checking it the
moment `references.anchors()` stopped counting `<a id>` showed **every Help
button in every published set landing nowhere** — each identifier kept its own
Flare alias fragment (`aa.advisory.helpurl`), backed by a marker the platform
ignores. `csh._value` now drops that fragment for the section anchor: less
precise than the help author asked for, and the whole of what the platform can
express. §9.6's rule is that a Help button may move and may never disappear, and
keeping an unreachable fragment was the disappearing case.

The ~370 fragments that still miss are *source* anchors — `#ID-000071DF`,
`#top`, `#Starting` — pointing into the middle of a topic with no heading behind
them. Nothing in the content can make those work; `validate` now reports them
honestly instead of passing them against the markers it used to emit itself.

#### Built so far — the filenames, 2026-09-30

`utils/naming.py` (`slugify`, `shorten`, `qualify`, `GENERIC`, `MAX_SEGMENT`),
`Topic.parent` threaded through the packer, and `_name_for` in `assign`.
**1,651 tests pass**, lint clean.

| | before | after |
|---|---:|---:|
| merged pages whose filename is unrelated to their title | **428 / 1,700** | **1 / 1,505** |
| filenames longer than 50 characters | **33** | **0** |

Measured over the three re-merged families (ActiveSpaces 359 pages, EMS 964,
TRA 182). DataSynapse's 235 pages still carry the old names and account for the
remaining over-length ones; it is out of scope and was not re-merged.

**The one remaining mismatch is the pin working, not a fault.** EMS 10.5.1 titles
a topic "Activation" and 10.4.0 titles the same topic "Product Activation"; the
projected version keeps the reference's `activation.md` so the URL does not move
between versions, which is what R1.4 exists for.

Both of the spec's golden long names now come in under the cut —
`configuring-ssl-existing-non-ssl-gridserver` at 43 and
`configuring-permissions-processor-utilization` at 45 — so the platform truncates
nothing and the filename *is* the URL leaf.

**One rule changed on measurement rather than on reading.** The anchor slug
stripped `_` as Markdown emphasis. Over the merged corpus **3,625 of 32,706
headings contain an underscore and none of them uses underscore-emphasis** --
they are environment variables (`TIBCO_HOME`) and error codes. Stripping it was
wrong for 11% of headings and right for none, so `_` now survives, as it does
under the platform's own rule.

#### Built so far — the folders, 2026-09-30

`packer.relocate` puts every navigated page in a folder chain mirroring the TOC:
a page with child pages becomes a folder named after its own file, its children
inside it, its own page beside the folder. So `installation.md` sits next to
`installation/`, and `/installation/requirements` is both the repo path and the
address. **1,655 tests pass**, lint clean.

Folder depth over the 1,505 re-merged pages: 2 levels 131, 3 levels 424, 4
levels 585, 5 levels 306, 6 levels 53, 7 levels 6.

**The folder decision retired a rule the spec asked for, and that is a
correction rather than a shortcut.** §3.6–3.7 wanted doc-set-wide unique names
and a parent prefix on every generic one, which was right when folders were
flat. With the chain restored, `/installing/overview` and `/upgrading/overview`
are already distinct and read correctly, and prefixing would publish
`/installing/installing-overview`. Uniqueness is now scoped to the TOC parent --
the same scope as the folder, and the only scope a clash can happen in.

**Three faults, each found by running it rather than by reading it.**

1. **Windows stopped at 260 characters.** Deep chains put a Runtime Agent page
   past the limit, and both the `mkdir` and the write failed with a bare
   `FileNotFoundError`. `long_path` on the page write and the asset copy.
2. **Then the *count* was wrong, not the write.** 118 pages written, 116
   counted, and the acceptance check correctly refusing a complete tree:
   `Path.rglob` reaches each directory through the unprefixed spelling and
   **omits an over-limit file silently**. `utils/longpath.walk_files` exists for
   exactly this and says so in its own docstring; `_measure_merged` was not
   using it.
3. **`tibco-runtime-agenttm`.** NFKC gives `™` a compatibility decomposition to
   the letters "TM", so dropping trademark glyphs *after* normalizing drops
   nothing. `utils/slug.py` has had the right order since it was written; this
   module lost it and got it back off a real folder name.

**One consequence to accept: 3 of 1,505 published paths exceed 260 characters**,
all Runtime Agent, the longest 280. `sync` already refuses those with
`PUBLISHED_PATH_TOO_LONG`, so they are named rather than silently truncated --
the fix is a shorter title, which is a writer's call.

#### Built so far — the served URL and its migration, 2026-09-30

`redirects.published` now emits `{region}/{lang}/{product}/{doc-class}/{version}/
path.html`: no repository segment, `en-us` split region-first to `us/en`, and
`.html`. `owned_prefixes` claims the old shape as well as the new one, purely so
the rows written under it can be deleted. `validation.artifacts` resolves a row
through `disk_candidates`, one per published tree, because the URL no longer
says which tree it lives in. **1,657 tests pass**, lint clean.

Re-synced and verified on the real maps: **1,957 + 8,639 rows, every one in the
served shape, zero legacy rows and zero duplicate keys.** Without the migration
every map would have doubled, half of it pointing at URLs that never existed.

Two faults found by running it. `shutil.copytree` into the `.part` staging
directory crossed 260 characters on seven ActiveSpaces versions -- the published
path is comfortably under, and five characters of staging suffix were taking the
whole doc set down -- so the copy is long-path spelled on both ends. And
`relative_path` keyed on the tree name being the URL's first segment; with that
segment gone it resolved **nothing**, so the check passed by doing no work
rather than by finding none.

#### What this uncovered, and it is bigger than the phase

With `anchors()` reading headings only, `validate` can finally say whether a
fragment resolves the way the platform resolves it. Over the whole published
target:

| tree | fragments resolving |
|---|---|
| ActiveSpaces (merged) | 1,614 / 1,736 (92%) |
| EMS (merged) | 13,821 / 14,178 (97%) |
| **Streaming (unmerged)** | **0 / 45,248** |
| **Runtime Agent (unmerged)** | **0 / 4,531** |

**Roughly 50,000 published cross-references in the unmerged trees cannot resolve
in AEM**, and none of them ever could. Stage 6a emits an `<a id>` for every
source anchor and rewrites every cross-reference to point at one; the platform
ignores markers. The merged trees are fine because Reframe now targets heading
anchors.

This is not Phase 29's to fix and must not be done quietly: the repair is for
Stage 6a to retarget a fragment onto the nearest heading's anchor, exactly as
`csh._value` now does, and it touches every unmerged product. **Raised as its
own phase rather than absorbed into this one.**

#### Built so far — `rename-map.csv`, 2026-09-30

`reframe/renames.py` and `packer.override`. One row per merged page, keyed on
the source topic that leads it: `old_path, new_path, title, toc_breadcrumb,
expected_aem_url, shortened`. **1,662 tests pass**, lint clean.

It is a record *and* an override. A `new_path` a human keeps is read back on the
next run and pins the page, so a published URL does not move because somebody
fixed a typo in a title -- the failure requirements §1 calls permanent and that
no amount of care at the naming end can prevent. `reframe --renormalize`
recomputes anyway, so the pinning is a decision rather than a trap. Register
**60 → 61** (`RENAME_MAP_APPLIED`, a note) so a reviewer can tell a tree that is
stable from one that happened to recompute the same answer.

`expected_aem_url` comes from `sync.redirects.published`, not a second formula
beside it: the point of printing the address is that a reviewer can compare it
against what the site serves, and two derivations would make that comparison
meaningless exactly when it mattered.

**The `shortened` column is the hook for model-assisted naming**, and it is why
the build stays free of a model. Written over the real corpus: **1,505 rows, 90
flagged** -- `creating-domain-that-integrates-ldap-directory` for "Creating a
Domain that Integrates with an LDAP Directory Server", where the cut took
"Server". A suggestion pass fills in `new_path`, a human approves, and the
deterministic build reads the approved map as fixed input. The tool asserts
byte-identical re-runs; a name that varied between runs would be a published
address that moved on its own.

#### Built — a copy per guide, 2026-09-30

`claimed` is now scoped to one top-level guide rather than to the version, so a
topic listed under two guides is packed once per guide; `Topic.node` carries the
TOC row that placed it and `toc.retarget` resolves each row to *its own* guide's
copy. Within a guide a second listing is still a cross-reference, not a second
placement. **1,663 tests pass**, lint clean.

**It changed nothing on the in-scope corpus, and that is the honest result.**
All 4 in-scope duplicates -- EMS 10.4.0 and 10.4.1 -- turn out to be listed
twice inside the *same* guide ("User Guide"), which the rule correctly still
shares. The rule fires where the duplicates really are cross-guide: GridServer
7.2.0 has 13, every one of them spanning two or three guides, with
`Typographical_Conventions.md` in all three. That product is out of scope and
was not re-merged, so the behaviour is pinned by tests rather than by output.

Worth stating plainly because the alternative reading is that the change was
unnecessary: it was necessary and is currently inert. Under the old rule those
13 GridServer rows would each resolve to an address sitting under whichever
guide reached the topic first.

## Phase 29 is complete.

#### Nothing is carried unverified

Every question the spec raised has been answered against a real AEM instance rather than
assumed, including the two that turned out to matter most — the URL is the TOC chain, and
anchors come from heading text. That is the difference between this phase and a rewrite that
would have shipped 11,500 broken fragments and looked clean doing it.

**One accepted fragility, recorded rather than discovered later.** GitHub-style anchor
numbering is positional: on the 400 pages with a repeated heading, inserting a section above
one of them renumbers every later duplicate and moves a published anchor. No content change
prevents it. The mitigation, if it ever bites, is editorial — make the repeated headings
distinct — which is a writer's call and belongs in the review queue, not in the packer.

---
