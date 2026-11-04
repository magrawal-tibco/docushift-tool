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

from pathlib import Path, PurePosixPath

import yaml

from docushift.transforms.csh import quote
from docushift.utils.naming import UNFILED

#: Literals rather than imports from `origins` / `reframe.csh`: `sync` imports
#: those lazily, and the names are a published contract that does not move.
ORIGINS = "301.yml"
CSH = "csh.yml"

ORIGINS_HEADER = (
    "# Origin 301 map -- \"old docs.tibco.com URL\": \"new location\" (planning.md Phase 72).\n"
    "# A page is its Markdown file's path from the repository root (Phase 68); a\n"
    "# document (PDF, txt, ...) is its AEM DAM path.\n"
)

CSH_NOTE = "# Paths are from the repository root (planning.md Phase 68).\n"

#: `published_maps`' answer for a map that must not be published at all.
NOT_PUBLISHED = ""


def in_unfiled(reference: str) -> bool:
    """Whether a version-relative page sits in an `unfiled/` folder, at any depth.

    Any depth, not only the top: since Phase 63 a doc set laid out on its own has
    its own `{doc-set}/unfiled/`, which `naming.is_unfiled` does not see.
    """
    return UNFILED in PurePosixPath(str(reference).partition("#")[0]).parts


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


def origins_text(text: str, prefix: str, assets: dict[str, str] | None = None) -> str | None:
    """A version's published `301.yml`: `"old": "new"`, one per line. `None` if the
    working tree's file does not parse.

    Phase 72 (the AEM team, 2026-11-04): the flat shape `csh.yml` already has, in
    place of the list of `from` / `to` / `status`. Pages are rooted (Phase 68);
    `assets` are the version's document rows, old URL -> DAM path, written in the
    same file. Sorted by old URL, so a re-sync is a reviewable diff. A page row and
    an asset row with the same old URL cannot both stand; the page row wins.
    """
    try:
        document = yaml.safe_load(text) if text else None
    except yaml.YAMLError:
        return None
    if document is None:
        document = {"redirects": []}
    if not isinstance(document, dict) or not isinstance(document.get("redirects") or [], list):
        return None
    published: dict[str, str] = dict(assets or {})
    for row in document.get("redirects") or []:
        if not isinstance(row, dict) or "to" not in row or not row.get("from"):
            return None
        published[str(row["from"])] = rooted(prefix, str(row["to"]))
    if not published:
        return NOT_PUBLISHED
    lines = [f"{quote(old)}: {quote(published[old])}" for old in sorted(published)]
    return ORIGINS_HEADER + "\n".join(lines) + "\n"


def csh_text(text: str, prefix: str) -> str | None:
    """A version's `csh.yml` with every value rooted. `None` if it does not parse.

    **Entries into `unfiled/` are dropped** (the user, 2026-10-29): a page left out
    of the TOC is not one a Help button should open -- the rule `301.yml` follows
    (Phase 43). A map with nothing left is `NOT_PUBLISHED`: no file, not an empty
    one, for `transforms/csh.write`'s reason.

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
    kept = {key: value for key, value in document.items() if not in_unfiled(str(value))}
    if not kept:
        return NOT_PUBLISHED
    header = _leading_comments(text)
    if CSH_NOTE not in header:
        header += CSH_NOTE
    lines = [f"{quote(str(key))}: {quote(rooted(prefix, str(value)))}"
             for key, value in kept.items()]
    return header + "\n".join(lines) + "\n"


_REWRITERS = {ORIGINS: origins_text, CSH: csh_text}


def published_maps(source: Path, prefix: str, assets: dict[str, str] | None = None) -> dict[str, str]:
    """`{file name: published text}` for the maps a converted version folder has.

    `NOT_PUBLISHED` for a map that exists in the source and must not be published.
    `assets` (Phase 72) are the version's document rows; a version whose tree has
    no `301.yml` but has asset rows still publishes one, holding only those.

    A map that will not parse is left out, so it is copied through verbatim and
    `validate` names it -- the rule every other artifact `sync` cannot read follows.
    """
    found: dict[str, str] = {}
    for name, rewrite in _REWRITERS.items():
        path = source / name
        if not path.is_file():
            if name == ORIGINS and assets:
                found[name] = origins_text("", prefix, assets) or NOT_PUBLISHED
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rewritten = origins_text(text, prefix, assets) if name == ORIGINS else rewrite(text, prefix)
        if rewritten is not None:
            found[name] = rewritten
    return found
