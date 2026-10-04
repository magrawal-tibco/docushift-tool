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
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote, urlsplit

import yaml

from docushift.transforms import links
from docushift.utils import textfile

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
    return declaration(declared, slug)[0]


def declaration(declared: Mapping[str, Any], slug: str) -> tuple[OriginTemplate | None, str]:
    """`template_for`, plus why a declaration that exists was refused.

    The reason is empty when the product is simply not declared, and non-empty
    when a human wrote an entry that failed validation (Phase 34, R1-07). The
    two used to be one answer, so a declaration with `drop_segments: "one"` was
    discarded without a word and the run reported "none is declared".
    """
    if slug not in declared:
        return None, ""
    entry = declared.get(slug)
    if not isinstance(entry, dict):
        return None, "the entry is not a mapping with `template` and `drop_segments`"
    template = str(entry.get("template") or "").strip()
    if not template:
        return None, "the entry has no `template`"
    if "{path}" not in template:
        # A template that cannot place the path would render one URL for every
        # topic in the product. Declining is the same answer as not declaring.
        return None, f"template '{template}' has no {{path}}"
    try:
        # Rendered once here so a stray `{version}` or a lone brace is a refused
        # declaration, not a `KeyError` from `str.format` halfway through a run.
        template.format(folder_path="", path="")
    except (KeyError, IndexError, ValueError) as error:
        return None, (f"template '{template}' does not render with only {{folder_path}} "
                      f"and {{path}} ({type(error).__name__}: {error})")
    try:
        drop = int(entry.get("drop_segments", 0))
    except (TypeError, ValueError):
        return None, f"drop_segments {entry.get('drop_segments')!r} is not a whole number"
    return OriginTemplate(template=template, drop_segments=max(0, drop)), ""


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


# -- Phase 35: one builder for every stage that writes the map --------------------


@dataclass
class Built:
    """`build`'s answer: rows to write (or `None` for no file), and what to report.

    Findings are `(code, message, count)` and the caller records them, so this
    module stays free of any stage's findings plumbing.
    """

    rows: list[dict[str, Any]] | None
    findings: list[tuple[str, str, int]]


def page_list(cache_dir: Path, slug: str, version: str) -> list[str]:
    """A version's listed live URLs from the `catalog sitemap` cache, or `[]`.

    Never fetches: the stages that write `301.yml` take no network. An unreadable
    cached file is the same as no list -- it is reported as a missing sitemap,
    and `catalog sitemap` replaces it on the next walk.
    """
    from docushift.discovery.sitemap import SitemapCache, SitemapError

    try:
        pages = SitemapCache(Path(cache_dir) / "coveo").pages(slug, version)
    except SitemapError:
        return []
    return [page.loc for page in pages] if pages else []


def build(
    declared: Mapping[str, Any],
    slug: str,
    zip_url: str | None,
    output_map: Mapping[str, str],
    moved: Mapping[str, str],
    page_urls: list[str],
) -> Built:
    """One version's `301.yml` rows, by Phase 22's and Phase 33's rules.

    A declaration wins and writes every row; the sitemap only counts where they
    disagree. Without one, the sitemap's derived mapping is used and only listed
    rows are written. Shared by `convert` (the tree `sync` publishes for most
    products) and `reframe` (the merged tree), so the two cannot disagree.
    """
    found: list[tuple[str, str, int]] = []
    folder = folder_path(zip_url)
    template, refused = declaration(declared, slug)
    derived = template is None
    if refused:
        # Then derived exactly as if undeclared: the sitemap's rows are each
        # confirmed against the live list, so falling back guesses nothing. What
        # it must not do is pass for "no declaration" -- the person who wrote
        # one is the person who needs to hear it was thrown away.
        found.append(("ORIGIN_TEMPLATE_REJECTED", (
            f"config/origin-urls.yaml declares this product but the entry was "
            f"ignored: {refused}"), 1))
    # Says which of the two it was, so neither message below claims "none".
    absent = "the declared one was rejected" if refused else "none is declared"
    if derived:
        if not page_urls:
            found.append(("ORIGIN_SITEMAP_MISSING", (
                f"no Coveo sitemap page list for this version and no usable template "
                f"in config/origin-urls.yaml ({absent}), so no {ORIGINS} was written"), 1))
            return Built(None, found)
        answer = derive(output_map, page_urls, folder)
        if answer.template is None:
            found.append(("ORIGIN_TEMPLATE_UNDECLARED", (
                f"the sitemap confirms no single URL mapping ({answer.hits} of "
                f"{answer.sources} topics placed, runner-up {answer.rival}), and "
                f"{absent} in config/origin-urls.yaml, so no {ORIGINS} was written"), 1))
            return Built(None, found)
        template = answer.template
    elif folder is None:
        found.append(("ORIGIN_TEMPLATE_UNDECLARED", (
            f"zip_url '{zip_url}' is not a /pub/ docsite package path, so the "
            f"origin folder cannot be read off it and no {ORIGINS} was written"), 1))
        return Built(None, found)

    built, dropped = rows(output_map, moved, template, folder or "")
    # The join has three inputs and a silent drop in any of them produces a short
    # map that looks entirely plausible. Asserting the count against the map it
    # was built from is the one check that catches it, and it is free.
    # Its own code, counted per source (R1-07): it used to ride on
    # `ORIGIN_TEMPLATE_UNDECLARED` with a count of 1, which named the wrong
    # condition and reported one whatever the number was.
    if dropped:
        found.append(("ORIGIN_PATH_TOO_SHORT", (
            f"{len(dropped)} source path(s) are shorter than the template's "
            f"drop_segments and produced no URL, e.g. '{dropped[0]}'"), len(dropped)))

    if page_urls:
        # A derived row must be on the list to be written; a declared one was
        # checked by a human and is written regardless, the list only counting
        # where the two disagree.
        kept, unlisted = listed(built, page_urls)
        if derived:
            built = kept
        if unlisted:
            found.append(("ORIGIN_URL_UNLISTED", (
                f"{len(unlisted)} origin URL(s) not in the docsite sitemap"
                f"{', withheld' if derived else ' (declared template, written anyway)'}"
                f", e.g. {unlisted[0]}"), len(unlisted)))
        missed = unmapped(built, page_urls)
        if missed:
            found.append(("ORIGIN_PAGE_UNMAPPED",
                          f"{len(missed)} live page(s) with no {ORIGINS} row, e.g. {missed[0]}",
                          len(missed)))
    return Built(built, found)


def write(path: Path, built: list[dict[str, Any]]) -> None:
    """A version's `301.yml`, written the way `reframe/manifest.write` writes every
    sidecar -- same dump options -- so the two stages' files are byte-comparable."""
    body = yaml.safe_dump(document(built), sort_keys=False, allow_unicode=True, width=10**6)
    textfile.write_text(path, VERSION_HEADER + body)
