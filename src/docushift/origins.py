"""Where a converted topic is served today, and the 301 row that replaces it.

*Phase 33 addendum.* "Nothing is inferred" below is still the rule, but there is
now a second source of verified answers: the docsite's Coveo sitemap, which lists
every live page of a version (`discovery/sitemap.py`). `derive()` picks the one
mapping from source path to live URL that the list confirms, and `listed()` checks
every row against the list, so an undeclared product gets a map without anyone
guessing. A declaration in `origin-urls.yaml` still wins.

Every redirect artifact before this one is expressed in coordinates this tool
invented. `reframe/manifest.redirects` maps a converted path to the merged page
that absorbed it; `sync/redirects` prefixes both sides into published URLs. Both
are correct and neither is a cutover instruction, because the `from` side of a
cutover is an address on `docs.tibco.com` that this tool has never written.

This module supplies that side, and it is deliberately the smallest thing that
can: a template per product, read from `config/origin-urls.yaml`, applied to the
source path `state.db` already records for every converted topic.

**Nothing is inferred.** The shape that works for EMS --
`/pub/{folder_path}/doc/{path}` with the package wrapper dropped -- is one of
four in the converted catalog, and the other three differ in whether there is a
wrapper at all, whether the served root is `html` or `designerhelp`, and whether
`doc/` is already part of the recorded path. A rule that guessed would be right
for the pilot and wrong for Runtime Agent, and the wrongness is invisible until
a reader follows the link. So an undeclared product yields no rows and a finding,
which is the one failure mode here that a human can act on.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import unquote, urlsplit

from docushift.transforms import links

#: The per-version and per-doc-class file. One name at two levels, for the reason
#: `sync/redirects.REDIRECTS` carries one: it is one map, published at the level it
#: can be served from and recorded at the level it can be audited from.
ORIGINS = "301.yml"

VERSION_HEADER = (
    "# Origin 301 map -- the docs.tibco.com URL each page is served at today,\n"
    "# against where it lands in the new structure (planning.md Phase 22).\n"
    "# `to` is relative to this version folder; `sync` publishes the served form.\n"
)

PUBLISHED_HEADER = (
    "# Published origin 301 map -- assembled by `docushift sync` from the version\n"
    "# folders beneath this one (planning.md Phase 22). `from` is the live docsite\n"
    "# URL that stops working at cutover. Rows are regenerated per version segment;\n"
    "# anything else here is left exactly as it was found.\n"
)

#: Where a docsite package URL starts. A `zip_url` that is not under this is an
#: archive path the API returned verbatim (`docsite.yaml: archive_field`), whose
#: shape is not the active one and must not be read as though it were.
_PUB = "pub"


@dataclass(frozen=True)
class OriginTemplate:
    """One product's answer to "where is this served today?"."""

    #: `{folder_path}` and `{path}` substituted; everything else literal.
    template: str
    #: Leading segments of the recorded source path to discard -- the package
    #: wrapper, usually exactly one, and zero for a tree recorded from its root.
    drop_segments: int = 0


def template_for(declared: Mapping[str, Any], slug: str) -> OriginTemplate | None:
    """This product's template, or `None` if it has not been declared.

    `None` is a routine answer and not an error condition: one product is
    declared today. The caller turns it into a finding once per version, which is
    where the version is in hand and can be named.
    """
    entry = declared.get(slug)
    if not isinstance(entry, dict):
        return None
    template = str(entry.get("template") or "").strip()
    if not template or "{path}" not in template:
        # A template that cannot place the path would render one URL for every
        # topic in the product. Declining is the same answer as not declaring.
        return None
    try:
        drop = int(entry.get("drop_segments", 0))
    except (TypeError, ValueError):
        return None
    return OriginTemplate(template=template, drop_segments=max(0, drop))


def folder_path(zip_url: str | None) -> str | None:
    """The docsite folder a version's package sits in -- `ems/10.5.1`.

    Read off `zip_url` rather than rebuilt from `(slug, version)`, for the reason
    `sync/redirects` gives about deriving two things separately: the URL the
    downloader actually fetched is the one the docsite serves from, and a second
    composition of the same segments is how the two come to disagree.

    `None` for anything not under `/pub/` -- an archived version's `zipPath`
    comes back from the API verbatim and its shape is not this one.
    """
    if not zip_url:
        return None
    parts = PurePosixPath(urlsplit(str(zip_url)).path.lstrip("/")).parts
    # `pub`, at least one folder segment, and the filename.
    if len(parts) < 3 or parts[0] != _PUB:
        return None
    return "/".join(parts[1:-1])


def origin_url(template: OriginTemplate, folder: str, source: str) -> str | None:
    """The live URL for one recorded source path, or `None` if it has no tail.

    Percent-encoded through `links.emit`, which is what every other URL this tool
    writes goes through, so a topic with a space in its filename is encoded the
    same way here as in the page that links to it.
    """
    parts = PurePosixPath(str(source)).parts
    if len(parts) <= template.drop_segments:
        return None
    tail = "/".join(parts[template.drop_segments:])
    return template.template.format(folder_path=folder, path=links.emit(tail))


def rows(
    output_map: Mapping[str, str],
    moved: Mapping[str, str],
    template: OriginTemplate,
    folder: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    """One version's map: live URL -> where the page ended up in this folder.

    `output_map` is `state.db`'s `source -> output` for this version. `moved` is
    Reframe's `output -> page.md#anchor`; a path absent from it did not move, and
    takes its own output path. That is the only correct default and it is also
    what makes this work for a product that never reframes at all.

    Returns the rows and the source paths that produced no URL, so the caller can
    assert the count rather than discover a short map later. Sorted by `from`,
    because a redirect map is looked up rather than read.
    """
    built: list[dict[str, Any]] = []
    dropped: list[str] = []
    for source, output in output_map.items():
        url = origin_url(template, folder, source)
        if url is None:
            dropped.append(source)
            continue
        built.append({"from": url, "to": moved.get(output, output), "status": 301})
    built.sort(key=lambda row: str(row["from"]))
    return built, dropped


def document(built: list[dict[str, Any]]) -> dict[str, Any]:
    """The file's shape. One key, so `redirects.parse` reads it unchanged."""
    return {"redirects": built}


# -- Phase 33: derived from the Coveo sitemap ----------------------------------

#: How many leading source segments `derive` will try to drop. The four layouts
#: Phase 22 found need 0 or 1; 3 leaves room without inviting a match on a bare
#: filename, which every subtree has.
MAX_DROP = 3

#: The winning mapping must cover this share of the version's `output_map`...
MIN_COVERAGE = 0.90
#: ...and no other mapping may come within this many points of it.
MIN_MARGIN = 0.10


@dataclass(frozen=True)
class Derivation:
    """`derive`'s answer: a template, or the numbers that explain why there is none."""

    template: OriginTemplate | None
    #: Sources the winning mapping placed on a listed page.
    hits: int
    #: The runner-up's count, from a mapping that produces a *different* URL set.
    rival: int
    sources: int


def page_path(url: str) -> str:
    """The comparison key for a live URL: its decoded path, no leading slash.

    Decoded because the sitemap publishes `API Activity/x.htm` with a raw space
    while `links.emit` writes `API%20Activity`; both are the same page.
    """
    return unquote(urlsplit(str(url)).path).lstrip("/")


def derive(sources: Iterable[str], page_urls: Iterable[str], folder: str | None = None) -> Derivation:
    """The one source-to-URL mapping a version's sitemap confirms, or none.

    A candidate is "drop k leading segments of the source path, put the rest
    under prefix P". For every source and every k, each listed page whose path
    ends with that tail proposes its P. Candidates are then **grouped by the set
    of URLs they produce**: in every EMS version "drop 1 under `…/doc`" and "drop
    2 under `…/doc/html`" tie exactly, because they are the same URLs, and two
    names for one answer are not a rival.

    The winner needs `MIN_COVERAGE` of the sources and a `MIN_MARGIN` lead over
    the next group. Coverage is measured against `output_map`, not against the
    sitemap: a leaf also lists API reference and PDFs this tool does not convert
    (680 of 2,117 for EMS 10.5.1), and a threshold on the leaf would reject every
    product that ships an API reference.

    `folder`, when known, must prefix the winning P (`pub/ems/10.5.1/...`). It is
    the guard against a tail that happens to match a page of another version.
    """
    sources = list(sources)
    urls = list(page_urls)
    base = ""
    by_tail: dict[str, set[str]] = {}
    for url in urls:
        if not base:
            parts = urlsplit(url)
            base = f"{parts.scheme}://{parts.netloc}"
        segs = page_path(url).split("/")
        for i in range(len(segs)):
            by_tail.setdefault("/".join(segs[i:]), set()).add("/".join(segs[:i]))

    pub = f"{_PUB}/{folder}".rstrip("/") if folder else ""
    produced: dict[tuple[int, str], set[str]] = {}
    for source in sources:
        parts = PurePosixPath(str(source)).parts
        for k in range(0, min(MAX_DROP + 1, len(parts))):
            tail = "/".join(parts[k:])
            for prefix in by_tail.get(tail, ()):
                if pub and prefix != pub and not prefix.startswith(pub + "/"):
                    continue
                produced.setdefault((k, prefix), set()).add(f"{prefix}/{tail}" if prefix else tail)

    # One representative per distinct URL set: the smallest drop, then the
    # shortest prefix, so the same input always names the same template.
    groups: dict[frozenset[str], tuple[int, str]] = {}
    for key in sorted(produced, key=lambda kp: (kp[0], len(kp[1]), kp[1])):
        groups.setdefault(frozenset(produced[key]), key)
    ranked = sorted(((len(found), key, found) for found, key in groups.items()), key=lambda r: (-r[0], r[1]))

    total = len(sources)
    if not ranked or not total:
        return Derivation(None, 0, 0, total)
    hits, (drop, prefix), winner = ranked[0]
    # A group whose URLs the winner already produces is the same answer seen
    # through a deeper drop (`c.htm` under `.../API Activity`), not a rival.
    rival = next((count for count, _, found in ranked[1:] if not found <= winner), 0)
    if hits < MIN_COVERAGE * total or (hits - rival) < MIN_MARGIN * total:
        return Derivation(None, hits, rival, total)
    stem = f"{base}/{prefix}" if prefix else base
    # Rendered through `str.format` like a declared template; a literal brace in
    # a published path must not be read as a placeholder.
    stem = stem.replace("{", "{{").replace("}", "}}")
    return Derivation(OriginTemplate(template=stem + "/{path}", drop_segments=drop), hits, rival, total)


def listed(built: list[dict[str, Any]], page_urls: Iterable[str]) -> tuple[list[dict[str, Any]], list[str]]:
    """Splits rows into those whose `from` the sitemap lists and those it does not.

    The per-row proof Phase 22 got from a hand check: a derived template right for
    99% of a version is still wrong for the 1%, and those are the rows a reader
    would follow to a dead page.
    """
    keys = {page_path(url) for url in page_urls}
    kept: list[dict[str, Any]] = []
    unlisted: list[str] = []
    for row in built:
        if page_path(row["from"]) in keys:
            kept.append(row)
        else:
            unlisted.append(str(row["from"]))
    return kept, unlisted


def unmapped(built: list[dict[str, Any]], page_urls: Iterable[str]) -> list[str]:
    """Listed live pages no row starts from -- each a 404 at cutover. Sorted."""
    covered = {page_path(row["from"]) for row in built}
    return sorted({url for url in page_urls if page_path(url) not in covered})
