"""The two sidecars a merged tree carries, per planning §20.3.

The proof-of-concept wrote three CSVs into a `manifest/` directory beside the
script -- `pages.csv`, `topic-mapping.csv`, `redirects.csv` -- shared across every
version it ever ran on, so the second run overwrote the first. Here they become
two YAML files at the root of the version's own tree, which is the only place that
survives the `.part` swap and the only place Stage 7 can find them without being
told where to look:

- **`reframe.yml`** folds `pages.csv` and `topic-mapping.csv` into one document.
  They were always the same data at two grains -- a page and its sections -- and a
  nested mapping says so, where two flat files leave the join to the reader.
- **`redirects.yml`** is R5's 301 map, and is separate because it has a different
  consumer: Stage 7 publishes it, and 20d adds the check that every entry still
  resolves once the tree is in its repository.

YAML rather than CSV for both because the shapes are nested and because every
other machine-readable artifact DocuShift writes into an output tree is YAML
(`toc.yml`, `metadata.yml`, `version.yml`). The review queue stays CSV in 20c: it
is a flat worklist meant to be opened in a spreadsheet by a writer, which is a
different audience and a different shape.

Both are sorted -- pages in reading order, redirects by source path -- so C5's
byte-identical requirement does not depend on dictionary iteration order.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from docushift.reframe.packer import Page
from docushift.reframe.pages import LinkCounts
from docushift.reframe.policy import ReframePolicy
from docushift.reframe.review import Flag

PAGES_HEADER = (
    "# Written by `docushift reframe` (Stage 6b). Do not hand-edit: this file is\n"
    "# regenerated in full on every merge, and it is the record of which source\n"
    "# topic became which section of which page.\n"
)

REDIRECTS_HEADER = (
    "# Written by `docushift reframe` (Stage 6b). One 301 per source topic, so a\n"
    "# published URL from before the merge lands on the section that replaced it.\n"
)

TOC_HEADER = (
    "# Merged by `docushift reframe` (Stage 6b). A url carrying `#` is a section of\n"
    "# a merged page and must not generate an HTML page of its own.\n"
)


def summary(
    pages: Sequence[Page],
    policy: ReframePolicy,
    counts: LinkCounts,
    schema: str,
    flagged: dict[PurePosixPath, list[Flag]] | None = None,
) -> dict[str, Any]:
    """`reframe.yml`'s document: the policy that shaped the tree, then every page."""
    flagged = flagged or {}
    return {
        "generated_by": "docushift reframe",
        "toc_schema": schema,
        "max_words": policy.max_words,
        "policy_key": policy.key,
        "topics": sum(len(page.topics) for page in pages),
        "pages": len(pages),
        "links": {
            "checked": counts.checked,
            "rewritten": counts.rewritten,
            "same_page": counts.intra,
            "cross_page": counts.inter,
            "assets": counts.asset,
            # Named separately because §6 fails on one and tolerates the other.
            "unresolved": counts.unresolved,
            "orphaned": counts.orphaned,
        },
        "merged": [_page(page, flagged.get(page.path, [])) for page in pages],
    }


def _page(page: Page, flags: list[Flag]) -> dict[str, Any]:
    return {
        "path": str(page.path),
        "title": page.topics[0].title,
        "guide": page.guide,
        "topics": len(page.topics),
        "words": page.words,
        # Every R6 flag, not just the queueing ones. `review-queue.csv` is a view
        # over this, so narrowing the queue never loses a measurement -- widening
        # it later is a filter change rather than a re-run (planning §20c).
        "flags": [flag.name for flag in flags],
        "sections": [
            {
                "anchor": page.anchors[topic.source],
                "title": topic.title,
                "source": str(topic.source),
                "words": topic.words,
            }
            for topic in page.topics
        ],
    }


def redirects(located: dict[PurePosixPath, tuple[Page, str]]) -> dict[str, Any]:
    """R5's map, sorted by source path.

    Every entry carries the anchor, including a page's own first topic whose TOC
    node is the bare `page.md`. The POC did the same and it is right: a redirect is
    followed by a reader who had the old URL, and landing them at the top of a
    twelve-section page when their link named the ninth section is a worse answer
    than one extra fragment.
    """
    return {
        "redirects": [
            {"from": str(source), "to": f"{page.path}#{anchor}", "status": 301}
            for source, (page, anchor) in sorted(located.items())
        ]
    }


def write(path: Path, header: str, document: dict[str, Any]) -> None:
    """One sidecar, header comment first. `sort_keys=False` keeps the order above."""
    body = yaml.safe_dump(document, sort_keys=False, allow_unicode=True, width=10**6)
    path.write_text(header + body, encoding="utf-8", newline="\n")
