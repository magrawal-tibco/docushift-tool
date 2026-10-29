"""Phase 68: the published `301.yml` and `csh.yml` name the Markdown file from the repo root.

The AEM team's requirement (2026-10-29): every target in a published redirect or
help map is the page's path from the root of the docs repository, anchor kept --
`/en-us/ibi-focus/online-help/9-3-8/ibi-focus/before-you-begin/page.md#anchor`.
Forward slashes and a leading `/`, the user's choice: the `/` says "from the root"
where a bare `en-us/…` could be read as relative to the file.

**Rewritten at publish, never at conversion.** `convert` and `reframe` keep writing
version-relative paths, so their self-checks, orphan handling and `csh validate`
read the working trees unchanged, and a re-convert does not depend on where the
tree will be published. `sync` is the one stage that knows locale, slug,
doc-class and segment together, so it is the one that writes the prefix.

**The path is the file's, not a URL.** It is not percent-encoded: it names a file
in the repository, and an encoded space would name a file that does not exist.

Readers of a published repository (`validate`, `verify`) call `unroot` before
resolving, so the old version-relative form and the new one read alike while the
repositories are re-synced.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from docushift.transforms.csh import quote

#: Literals rather than imports from `origins` / `reframe.csh`: `sync` imports
#: those lazily, and the names are a published contract that does not move.
ORIGINS = "301.yml"
CSH = "csh.yml"

ORIGINS_HEADER = (
    "# Origin 301 map -- the docs.tibco.com URL each page is served at today,\n"
    "# against where it lands in the new structure (planning.md Phase 22).\n"
    "# `to` is the Markdown file's path from the repository root (Phase 68).\n"
)

CSH_NOTE = "# Paths are from the repository root (planning.md Phase 68).\n"


def folder_prefix(locale: str, slug: str, doc_class: str, segment: str) -> str:
    """`/en-us/ibi-focus/online-help/9-3-8/` -- a version folder from the repo root."""
    return f"/{locale}/{slug}/{doc_class}/{segment}/"


def rooted(prefix: str, reference: str) -> str:
    """A version-relative reference from the repo root. Idempotent.

    A reference that already starts at the root, or is a URL, is returned as it
    is: rewriting it twice would nest the prefix, and a URL is somebody else's.
    """
    text = str(reference)
    if text.startswith("/") or "://" in text:
        return text
    return prefix + text


def unroot(prefix: str, reference: str) -> str:
    """The reverse of `rooted`, for readers: version-relative again, or unchanged.

    A reference under another folder's prefix is left as it is, so a reader
    treats it as foreign rather than resolving it against the wrong folder.
    """
    text = str(reference)
    return text[len(prefix):] if text.startswith(prefix) else text


def _leading_comments(text: str) -> str:
    lines = []
    for line in text.splitlines(keepends=True):
        if not line.startswith("#"):
            break
        lines.append(line if line.endswith("\n") else line + "\n")
    return "".join(lines)


def origins_text(text: str, prefix: str) -> str | None:
    """A version's `301.yml` with every `to` rooted. `None` if it does not parse.

    The header is replaced rather than kept: the converted tree's says `to` is
    relative to the folder, which is the one thing the published copy is not.
    """
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError:
        return None
    if document is None:
        document = {"redirects": []}
    if not isinstance(document, dict) or not isinstance(document.get("redirects") or [], list):
        return None
    rows: list[dict[str, Any]] = []
    for row in document.get("redirects") or []:
        if not isinstance(row, dict) or "to" not in row:
            return None
        moved = dict(row)
        moved["to"] = rooted(prefix, str(row["to"]))
        rows.append(moved)
    body = yaml.safe_dump({**document, "redirects": rows}, sort_keys=False,
                          allow_unicode=True, width=10**6)
    return ORIGINS_HEADER + body


def csh_text(text: str, prefix: str) -> str | None:
    """A version's `csh.yml` with every value rooted. `None` if it does not parse.

    The source's order and comments are kept -- `reframe` writes its map in the
    source's order and `convert` sorts, and either is a reviewer's diff -- and every
    scalar is quoted as `transforms/csh.render` quotes it (7.5% of identifiers are
    all digits).
    """
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError:
        return None
    if document is None:
        return None
    if not isinstance(document, dict):
        return None
    header = _leading_comments(text)
    if CSH_NOTE not in header:
        header += CSH_NOTE
    lines = [f"{quote(str(key))}: {quote(rooted(prefix, str(value)))}"
             for key, value in document.items()]
    return header + "\n".join(lines) + "\n"


_REWRITERS = {ORIGINS: origins_text, CSH: csh_text}


def published_maps(source: Path, prefix: str) -> dict[str, str]:
    """`{file name: published text}` for the maps a converted version folder has.

    A map that will not parse is left out, so it is copied through verbatim and
    `validate` names it -- the rule every other artifact `sync` cannot read follows.
    """
    found: dict[str, str] = {}
    for name, rewrite in _REWRITERS.items():
        path = source / name
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rewritten = rewrite(text, prefix)
        if rewritten is not None:
            found[name] = rewritten
    return found
