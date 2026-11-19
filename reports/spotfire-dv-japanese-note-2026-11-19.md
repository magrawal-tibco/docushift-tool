# Spotfire Data Virtualization: Japanese help added, 19 Nov 2026

[en-us-spotfire-data-virtualization-userdocs](https://github.com/tibco/en-us-spotfire-data-virtualization-userdocs), `main` at [`540ccdcf`](https://github.com/tibco/en-us-spotfire-data-virtualization-userdocs/commit/540ccdcf).

## What is new

- **Japanese online help for 8.8.0 and 8.8.1**, in the same repository as the English, under
  `ja-jp/tibco-data-virtualization/online-help/8-8-0/` and `8-8-1/` (beside `en-us/`). 8.9.0 has no
  Japanese edition.
- **Laid out like the English:** each Japanese page sits at the same path as its English page (e.g.
  `ja-jp/.../8-8-1/user-guides/whats-new-3.md` and `en-us/.../8-8-1/user-guides/whats-new-3.md`), and
  the menu is the English menu with Japanese titles. The adapter guides are English only, so they
  are not in the Japanese menu.
- 3,203 pages (8.8.0) and 3,705 (8.8.1); 52 and 576 of them have no English twin and sit under
  `unfiled/` (mostly Web UI pages that exist in Japanese only).
- Redirect files (`301.yml`) for every old `docs.tibco.com/pub/tdv/8.8.x/doc/html/ja-JP/...` page,
  3,003 per version.
- **English fix in the same push:** 31 pictures whose names had spaces (`guide images/`,
  `image 1.png`) renamed to `guide-images/`, `image-1.png`, and their links updated.

## Checked

No errors in the repository check. Every link and picture resolves to a file with exactly the same
letter case. No spaces or non-ASCII characters in file names, no heading jumps, no raw `<` in menu
titles. Content compared with the Japanese source: 1 sentence and the POSITION topic missing, as in
the English (POSITION is not in the package).

## To note

- In each Japanese version, the folders `BusinessDiirectory/`, `StudioHelp/` and `WebUI/` hold only
  pictures (they stay where the pages link to them); there are no pages in them.
- Please confirm how the Spotfire site serves the `ja-jp/` tree of this repository (language switch
  between `en-us` and `ja-jp` pages of the same path).
