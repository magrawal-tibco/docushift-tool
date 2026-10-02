> Archived from `docs/planning.md` on 2026-10-02. Status: **Built, 2026-09-19**. Kept verbatim; a heading that says *Planned* was built later in this same section.
> Index of every phase: [`docs/planning.md`](../../planning.md#finished-phases).

### Phase 15: The Package Wrapper Is Not the Version Root — **Built, 2026-09-19**

Phase 14 got the `ems` family through download, extract and convert. `sync --family ems --target-dir C:\github\tibco-docs-aem` is the first Stage 7 run against a package this tool actually fetched, and it publishes **one doc-class of four**:

| doc-class | result |
|---|---|
| `online-help` | **6 of 6**, 8,849 files |
| `archives` | index written, 28 archived versions |
| `api-references` | **0 of 6**, every version failed |
| `user-guides`, `release-information`, `reference-documents` | **0 files**, over 30 shipped PDFs |

One cause under all three failures. A downloaded EMS package unpacks to a **single child directory** — `tibco-enterprise-message-service-10-4-0/`, the name the ZIP carries — with `doc/ html/ javadoc/ pdf/` inside *it*. Every hand-copied tree in this repo came from the predecessor's cache, which has no such level, so every step written against those trees assumes content sits at the version root.

#### 15a. Two Stage 7 steps read the version root directly

`sync/router.py:source_folders` returns `tree/pdf`, `tree/doc/pdf`, `tree/doc` and `tree/doc/doc`. Against a wrapped tree all four are absent, `route()` returns nothing, and the three document doc-classes publish an empty set without reporting anything — the run says `-` in the Documents column, which reads as "this version ships no PDFs" rather than "this version's PDFs were not found". 10.4.0 ships five.

`sync/apirefs.py:display_name` names a published API folder from the tree's path relative to the version root, dropping known container segments (`doc`, `html`, `api`, …). The wrapper is not a container, so it survives into the name:

```
tibco-enterprise-message-service-10-4-0/html/api/dotnetdoc/html
  -> tibco-enterprise-message-service-10-4-0-dotnetdoc      (48 chars)
  -> dotnetdoc, once the wrapper is the root                 (9 chars)
```

Those 39 characters are pure repetition — the slug and the version are already two segments up the published path. They are also what pushes the longest published file past the ceiling:

| | |
|---|---|
| longest published path, as named today | **267** |
| the same path while staged as `10-4-0.part` | **272** |
| Windows ceiling, `LongPathsEnabled = 0x0` | 260 |
| the same path with the wrapper as root | **228** |

**This is not §4.4's transient overflow, and must not be fixed with `\\?\`.** 267 is the *final* path — a published tree no reader outside this tool could open. Architecture §4.4 draws that line deliberately, and this is the first case to land on the far side of it. The fix is the name, which is wrong on its own terms; the length is the symptom that made it visible.

#### 15b. A content root, resolved once at extract time

**Not a strip during extraction.** Unpacking the child's contents into the version directory would make the tree match what every step assumes, with no consumer changes — but it rewrites the layout on disk, invalidates every recorded `extract_path`, and means the extracted tree no longer matches the package it came from. When an upstream ZIP and our copy of it disagree about structure, the next defect of this kind is unfalsifiable.

**Not a patch to the two callers**, either. The assumption is "content is at the version root", and it is written in more than two places; fixing the two that failed leaves the rest waiting for a package that reaches them.

So: `extract` resolves a **content root** per version and records it in `state.db`, and Stage 5/6/7 derive from it instead of from the version directory. The rule has to survive the corpus, and the corpus already contains the counter-example:

| shape | versions on disk | single child | the child |
|---|---|---|---|
| `ems` packages | 6 | yes | `tibco-enterprise-message-service-10-4-0` |
| `datasynapse` packages | 5 | yes | `doc` |
| `gridserver-manager/7.1.1` | 1 | no (5 children) | — |

**"One child" is therefore not the rule.** `doc/` is a single child too, and it is *content* — `source_folders` looks for `doc/pdf` and `doc/doc` by name. A rule that descended into it would break the five versions that work today. The rule is: descend through a single child **only when that child is not itself a known content segment**.

##### Measured, 2026-09-19: 60 versions across 24 families, read over HTTP Range

A ZIP's central directory is a few kilobytes at the end of the file, so the shape of a package can be read without downloading it. 60 eligible versions, one per product, spread across every family that had one; three requests and roughly 40 KB apiece instead of ~200 MB.

| | |
|---|---|
| endpoints that returned a ZIP | **50** |
| one wrapper directory, named exactly `{slug}-{version_dashed}` | **46** |
| flat — `doc/`, `html/`, `pdf/` at the root | 4 |
| a single child that *is* content | **0** |
| endpoints that returned no ZIP | 10 |

**The wrapper is the dominant shape, at 46 of 50**, and its name was the package stem in every one of the 46 — `tibco-iprocess-workspace-windows-11-10-0`, `spotfire-data-science-for-life-science-operations-2-2-0`. The 4 flat packages are the shape every step in this tool was written against.

The 10 failures are all the known `ZIP_URL_UNRESOLVED` class and **not a third shape**: 3 return a gzipped HTML error page of about 7 KB and 7 return the empty HTTP 200 of §2.2, with no `Content-Length` at all. Nothing in the sample is a package this tool cannot describe.

**The `doc/`-only counter-example does not come from a ZIP.** No package in the sample unpacks to a lone content directory; the five DataSynapse trees that do were hand-copied from the predecessor's cache, which stores `doc/` as the top level. They are still trees `extract`'s consumers read, so the content-segment exclusion stays — it is just not defending against a package shape, it is defending against the cache's.

**The name match is corroboration, not the rule.** Matching `{slug}-{version_dashed}` would be exact on all 46 and would refuse anything else, but the sample reached no archived package and none of the 10 products whose endpoint is unknown, so the shapes it has not seen are precisely the ones a stem test would reject. "A single child directory that is not a known content segment" accepts those and costs nothing when it is wrong: descending into a mis-identified directory finds no `doc/` or `pdf/`, which is what happens today anyway.

#### 15c. A failed publish leaves its staging tree behind, and says so illegibly

`_place` and `_place_api_references` call `remove(staging)` on the way *in*, not on the way out, so six `10-4-x.part/` trees with 6,146 files in them were left sitting in the published workspace. A `.part` directory is this tool's private vocabulary; in a target directory it does not own, it is litter that the next reader has no way to interpret.

The failure also arrives as `shutil.Error`'s full list — every failed `(src, dst, why)` triple, several kilobytes of it, printed raw — and the run **exits 0**, because the per-version catch turns it into a `FAILED` row and `sync`'s exit rule is about findings, not rows.

Three changes: stage cleanup in a `finally`, a one-line message with the count and the first offender, and a new register code.

#### 15d. `PUBLISHED_PATH_TOO_LONG`

The register's 43rd row, and `sync`'s first `error`. `sync` measures the destination path before it copies, skips the root that would overflow, and names it with the length and the path. A published path over the ceiling is not a warning: unlike `ZIP_URL_UNRESOLVED`, whose remedy is a hand-supplied file, there is nothing a user can do at run time and nothing downstream can read what was written.

The code stays after 15b removes its only known occurrence. The ceiling is a property of the target filesystem and the publishing root the user chooses — `C:\github\tibco-docs-aem` is 24 characters, and a deeper one puts other products over the line with no wrapper involved.

#### 15e. The ceiling is on the **read** side, and `rglob` hides it

15a–15d built and run, `sync --family ems --target-dir C:\github\tibco-docs-aem`:

| | before 15 | after 15a–15d |
|---|---|---|
| document doc-classes | 0 files | **8,886 files, 128.2 MB**, all four classes |
| `api-references` | 0 of 6, kilobytes of raw `shutil.Error` | 0 of 6, **one line apiece** |
| `.part` trees left behind | 6, 6,146 files | **none** |
| Stage 5 counts | 8,613 topics / 8,847 files | **unchanged** |

The wrapper diagnosis was right and the documents prove it. But `api-references` still fails 6 of 6, and the remaining cause is the mirror image of what 15a assumed:

```
C:\github\docushift-tool\families\en-us-tib-ems\extracted\...
  \tibco-enterprise-message-service-10-5-1\html\api\dotnetdoc\html
  \class_t_i_b_c_o_1_1_..._consumer_message-members.html      265 chars, the SOURCE
C:\github\tibco-docs-aem\...\api-references\10-5-1\dotnetdoc\html\...
  \class_t_i_b_c_o_1_1_..._consumer_message.html              190 chars, the DESTINATION
```

**`PUBLISHED_PATH_TOO_LONG` is silent because the published path is fine.** 190 of 260. What cannot be opened is the file this tool extracted: `safe_extract` wrote it through `long_path` (§4.4), and nothing on the read side lifts the prefix back. `copytree` gets the name from `scandir` and fails to open it — `[WinError 3] The system cannot find the path specified`, 3 files per version, 12 files over 260 across the six ems trees.

This is **not** the far side of §4.4's line. That line separates paths this tool *publishes* from paths it *owns*; 267 in 15a was a published path and a defect, 265 here is inside our own extracted workspace, and what it publishes to is 190. The prefix is the right instrument for exactly this.

**And `Path.rglob` omits the offending files without saying so.** For 10.5.1's `dotnetdoc`: 798 entries plain, **801 prefixed**. Three consequences, all measured:

- `over_limit` walks with `rglob`, so the check written in 15d cannot see the three files that then break the copy. It is not wrong about the ceiling; it is blind to the paths that reach it.
- `apirefs.measure` walks with `rglob`, so every root's `files`/`bytes` are 3 low.
- `apirefs.current` compares `measure(destination)` — short paths, full count — against that low source total, so a successfully published API tree would compare unequal and be re-copied on **every** run.

Second defect, independent of the ceiling. `sync` **exited 0** with six `FAILED` rows on screen. `validate` raises `Exit(1)` when it records an error; `sync` calls `findings.finish()` with no exit code and never raises. A batch driver reading the exit status of that run is told six failures were a success.

Two changes:

1. **Read the extracted tree through `long_path`** at the three places Stage 7 touches it: `_place_api_references`'s `copytree` source, `over_limit`'s walk, and `apirefs.measure`. The destination stays unprefixed — it is short by construction, and 15d's check is what keeps it so.
2. **`sync` exits 1** when any version failed or any error finding was recorded, the same rule `validate` uses.

##### Acceptance

##### Measured, 2026-09-19 — `sync --family ems --target-dir C:\github\tibco-docs-aem`

| criterion | result |
|---|---|
| all four doc-classes publish | **6 of 6** `api-references` (6,218 files, 115.6 MB), 6 of 6 each of `online-help`, `user-guides`, `release-information`, `reference-documents` |
| the 30 shipped PDFs routed, an index apiece | **30** — 18 `user-guides`, 6 `release-information`, 6 `reference-documents`; 6 `index.md` in each class |
| API folders named for the tree, not the wrapper | `dotnetdoc`, `javadoc` |
| no `.part` survives any run | none, after the successful runs **and** after the forced failure |
| a second `sync` re-copies nothing | **31 already current, 0 copied** — `measure` now counts the same files on both sides |
| a forced over-limit destination | a 70-character target root: **6 `PUBLISHED_PATH_TOO_LONG`**, one line apiece naming the file and **278**, 0 files written, exit **1** |
| Stage 5's counts unchanged | **8,613 topics in 8,847 files** |

The forced run is also 15e proving 15d: the file it names, at 278, is the 265-character source `rglob` could not see. The check and the copy now walk the same tree.

**`validate --target-dir` is not clean, and not because of Phase 15.** 8,658 files and 17,214 references walked: **1 `LINK_BROKEN`** and **1,763 `ANCHOR_MISSING`**, all of them in `online-help`, which Stage 7 published unchanged by this phase. The broken link is `users-guide/%s:%d`, a printf format string in the source text. Both are left for their own phase rather than folded in here; naming them is the point of the register. (Phase 16 measured both: the anchors are Stage 5's, and the broken link turned out to be the *validator's* — see 16c.)
- No `.part` directory survives any run, successful or failed.
- `validate --target-dir` reads the published tree clean.
- The API folders are named `dotnetdoc`, `javadoc` — not slug-and-version-prefixed.
- A forced over-limit destination produces one `PUBLISHED_PATH_TOO_LONG` line, a skipped root, a non-zero exit, and no residue.
- Stage 5's counts are unchanged: 8,613 topics in 8,847 files, which is the check that the content root resolved to the same tree the converter was already finding.

---
