"""Stage 9: verify -- nothing was lost between the old site and the new one (Phase 55).

Three comparisons, each over what the reader sees rather than what the tool wrote:

- **A, local**: every old page against the page it became in the published tree --
  topic, text, images and the TOC's structure (`driver.py`).
- **B, staging**: every published page against what stg-docs.ibi.com serves
  (`published.py`).
- **C, live sample**: a sample of docs.tibco.com pages against the downloaded copy
  (`live.py`).

Text is compared as sentences and 8-word shingles of normalised text (`text.py`),
images by content hash (`images.py`), and TOCs as trees (`toc.py`).
"""
