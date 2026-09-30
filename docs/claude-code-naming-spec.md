# Task: add a naming, folder-layout and link-rewrite stage to the conversion tool

Read this whole document first. Then explore the repo, write a short plan, and wait for my approval before changing code.

## 1. Context (why this matters)

The converted Markdown and its `toc.yml` are ingested by AEM, which generates the published URLs itself:

- Each URL segment is the **lowercased filename (without `.md`) of a node in the TOC chain**, from the top-level section down to the page. Each segment is **cut at 50 characters**. The last segment gets `.html`.
- The top-level segment comes from a section stub file (e.g. `_section_installation_guide.md`), not from the source folder.
- Source folders are ignored by AEM, and **YAML frontmatter is stripped**. The page title comes from the TOC.
- Verified example. TOC chain: `_section_installation_guide.md` > `Configuring_SSL.md` > `Manager_HTTPS_Configuration.md` > `Configuring_HTTPS_updated.md` > `Configuring_Manager.md` > `Configuring_SSL_on_Existing_Non-SSL_GridServer_Manager.md` becomes `/_section_installation_guide/configuring_ssl/manager_https_configuration/configuring_https_updated/configuring_manager/configuring_ssl_on_existing_non-ssl_gridserver_man.html`.

Therefore **the filename is the user-facing URL**. Today's Flare-derived names produce poor URLs (`Overview.md`, `1__Copy_Files_Before_Installation.md`, `Prior_to_Upgrade_.md`, `Configuring_HTTPS_updated.md`, `_section_developeru0027s_guide.md`). The new stage must fix names, folder layout and every link that refers to them.

## 2. First, explore and report (no edits yet)

- Find the pipeline stages (I know there is a `reframe` stage, "Stage 6b", that merges pages and writes `toc.yml`). Say where a new stage should go: **after** content is final and merged, and **before** the final `toc.yml` is written.
- Find the current `toc.yml` schema and keep it byte-for-byte compatible. Two schemas are in use. One uses `items / title / path / children`. The other uses `docs / title / url / subfolderlist` plus `docs_list_title`.
- List every place links are produced or parsed today.
- Show the plan, the config keys you propose, and the open questions in section 9.

## 3. Naming rules (deterministic slug algorithm)

Implement one function `slugify(title, fallback_stem)` with unit tests.

1. Input is the TOC title. If the title is empty, or looks like a filename (contains `_` and no spaces, e.g. `Know_the_Basics`), use `fallback_stem`.
2. Normalize: Unicode NFKC. Replace NBSP and other whitespace with a space. Decode literal escapes such as `u0027` and `\u0027`. Remove apostrophes and quotes without adding a separator ("Developer's" becomes "developers"). Remove `®™©`. `&` becomes `and`.
3. Lowercase. Replace every run of characters outside `[a-z0-9]` with **one separator**. Strip separators from both ends. The separator is config `naming.separator` (default `-`). Use it everywhere, never mix.
4. When the slug comes from a filename fallback, also strip edit-history tokens (`updated`, `new`, `old`, `copy`, a trailing `_1`/`_2`, a leading `1__`).
5. **Maximum 50 characters.** If longer: first drop stopwords (`a an the of for to and in on with`) except the first word. If still longer, cut at the last separator boundary at or below 50. Only hard-cut if a single word exceeds 50. Never end on a separator. Result: the URL leaf always equals the filename.
6. **Global uniqueness** across the whole doc set (case-insensitive). On a collision, the earlier page in TOC order keeps its slug. The later one becomes `<parent-slug><sep><slug>`, re-cut to 50 (shorten the parent part first). Only as a last resort append `-2`. Report every disambiguation.
7. Forbid generic-only slugs (`overview`, `introduction`, `summary`, `services`, `requirements`, `before-you-begin`) by prefixing the parent slug, so `installation-overview` and not `overview`.
8. **Stability.** Persist the mapping in `rename-map.csv` and reuse it on later runs. Never rename an already-mapped file because its title changed, unless `--renormalize` is passed (published URLs would change).

## 4. Folder layout

- One folder per top-level TOC section, named `slugify(section title)` (`installation-guide/`, not `install-guide/`).
- **Flat inside each section folder.** AEM builds hierarchy from the TOC, so nested source folders are unnecessary. `naming.max_folder_depth` may allow more, default 1.
- Section stub goes in `<section>/`. Make the stub filename configurable (`naming.section_stub`, e.g. `_section_{slug}.md` if AEM needs that literally). **Do not guess.** See section 9.
- Root-level content (`Whats-New.md`, `Typographical_Conventions.md`, `_templates/*`) moves into a named folder (e.g. `about/`) or a documented root exception list.
- Assets (images, PDFs, zips): move to `<section>/assets/`, normalize names with the same rules (lowercase, no spaces), keep extensions, and make them unique per section.
- Use `git mv` when the repo is a git repo so history is preserved. The default mode is **dry run**. `--apply` performs the moves.

## 5. Link and reference rewriting (the critical part)

Build the full `old_path -> new_path` map first. Then rewrite **every** reference, in one pass, from the map:

- Markdown inline links and images: `[t](path#anchor "title")` and `![a](img)`.
- Reference-style definitions: `[id]: path`.
- HTML inside Markdown: `<a href>`, `<img src>`, `<source>`, `<object>`.
- TOC entries (`path` or `url`).
- Any include or snippet paths, if the tool emits them.

Rules:

- Resolve each link against the **original location of the file that contains it**. Write it relative to the **new location** of that file.
- Match case-insensitively (Flare content comes from Windows). URL-decode (`%20`) before matching and re-encode when writing.
- Preserve `#anchors`, query strings, and link titles. Leave external URLs (`http(s):`, `mailto:`) untouched.
- If a target is not in the map, **do not invent a path**. Leave the link unchanged and report it as broken, with source file, line and link text.
- Verify that every `#anchor` exists in the target file. The heading-to-anchor algorithm must match what AEM uses (see section 9). Report the misses.
- Never rewrite text inside fenced or inline code.
- Links to pages that were merged into another page (a `#section` path) should point at the merged file plus the anchor.
- Same-file `#anchor` links stay as they are.
- The operation must be **idempotent**. Running twice changes nothing the second time.

## 6. TOC output

- Emit the new `toc.yml` with the same schema as today, **UTF-8, LF line endings, no BOM**, and updated paths.
- Keep TOC order and titles unchanged. Only paths change. Clean encoding artifacts in titles (NBSP, `u0027`, double spaces).
- **Duplicates** (one file listed under several parents, common when guides reuse topics). Config `duplicates: report | keep | error`. Default `report`: keep the entries, but list each file with all its placements and the resulting URLs.
- Depth above 4 is a warning.

## 7. Deliverables and commands

Add these to the CLI (names may follow the existing style):

- `normalize` runs the stage. It is dry-run by default and takes `--apply` and `--renormalize`.
- `lint` is read-only and exits non-zero on errors.
- `whereis <aem-url | leaf | filename>` prints the source file, TOC breadcrumb and expected URL.

Generated artifacts:

- `rename-map.csv`: `old_path,new_path,title,toc_breadcrumb,expected_aem_url`.
- `redirects.csv`: `old_aem_url,new_aem_url`, only if a previous site exists (config `previous_site: true`).
- `normalize-report.md`: counts, disambiguations, truncations, broken links, missing anchors, duplicates, orphans.

`lint` must check:

1. Every TOC path exists, and every file is in the TOC (orphans reported).
2. Filenames match `^[a-z0-9]+(<sep>[a-z0-9]+)*\.md$`, are at most 50 characters, and are globally unique (case-insensitive).
3. **Simulated AEM URL**: the URL computed from the TOC chain with the rule in section 1. No two nodes may produce the same URL. Report the longest URLs.
4. No broken links or anchors.
5. Each file's H1 equals its TOC title. Config `ensure_h1: report | fix`, default `report`. Frontmatter is stripped by AEM, so the title must not depend on it.
6. No NBSP, `uXXXX` residue or double spaces in titles or filenames.

## 8. Tests (write them before the implementation)

- **Golden URL tests** using the three real examples: the two long names must truncate to exactly 50 characters (`configuring_ssl_on_existing_non-ssl_gridserver_man`, `configuring_permissions_for_processor_utilization_`), and `Cache_Loader_Write_through_and_Bulk_Operations` (46) is unchanged. The new stage must also make the leaf equal the filename.
- **Slug tests**: `Developer's Guide` becomes `developers-guide`; a title with NBSP; `Know_the_Basics` uses the fallback; a 63-character title cuts at a word boundary; `Overview` under two parents disambiguates with the parent slug.
- **Link tests**: relative link across sections; `%20` in a path; case mismatch; `#anchor` preserved; a broken link is reported and left alone; idempotency on a second run; code fences untouched.
- A small fixture repo with 2 sections, about 15 pages and images, run end to end in CI.

## 9. Ask me before implementing (do not assume)

1. Separator: `-` or `_`? (Default `-`.)
2. Does AEM require a section stub file per section (like `_section_*.md`) or does it build the first URL segment from the section title? What exact filename?
3. How does AEM expect internal links: relative `.md` paths, relative `.html`, or absolute URLs?
4. Which heading-anchor slug algorithm does AEM use (GitHub-style, or other)?
5. Duplicate topics: keep one page listed twice, or generate per-guide copies?

## 10. Working style

- Small, reviewable commits, one concern each: slug function, mapping, mover, link rewriter, TOC writer, lint, CLI.
- Run the full test suite and `lint` on a real converted sample before saying it is done.
- Do not modify content prose. Only names, paths, links, encoding artifacts in titles, and (if enabled) H1 insertion.
- Never delete a file. If something must be dropped, list it in the report and stop for my decision.
