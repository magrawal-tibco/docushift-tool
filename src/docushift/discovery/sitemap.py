"""The docsite's Coveo search-index sitemap, fetched once and read from disk.

Phase 22 had to declare each product's origin URL by hand because nothing on disk
said where a topic is served today. The public `/sitemap.xml` does not say either
-- it lists product landing pages and stops. The sitemap the docsite publishes for
its Coveo search index does (planning.md Phase 33):

    ftp_portal/coveo/sitemap.xml                      <sitemapindex>, one per product
      tibco-enterprise-message-service.xml            <sitemapindex>, one per version
        tibco-enterprise-message-service-10-5-1.xml   <urlset>, one <url> per page

A leaf's `<loc>` is the live URL; its `<coveo:metadata>` carries the title
(`d_name`), `productversion` and `access_level`.

**Child files are found by following `<loc>`, never by composing a name.** The
names happen to be `{slug}` and `{slug}-{version_dashed}`, which is what lets a
leaf be matched to a `versions.csv` row -- but the root also lists a duplicate, a
mojibake name and a placeholder, and a composed name would turn the first file
named otherwise into a silent "no pages".

**Fetched into `cache/coveo/`, read from there.** `reframe` and `validate` take no
network, and the 301 map should be a function of files on disk. A file whose
`lastmod` in its parent is unchanged since it was cached is not fetched again.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

from docushift.discovery.client import DocsiteClient, DocsiteError
from docushift.utils.swap import replace_file

# Elements are matched on their local name, not their namespace. The leaves
# declare their default namespace as `.../sitemap/0.9/sitemap.xsd` -- the schema
# file, not the namespace -- while the indexes use the correct URI. Both are the
# sitemap protocol; insisting on the URI would reject every leaf on the site.

#: What `fetch` writes beside the XML: every file's `lastmod` as last seen in its
#: parent, and which version files each product file listed. The second half is
#: what lets `pages()` find a version's leaf without composing its name.
MANIFEST = "manifest.json"


class SitemapError(Exception):
    """A sitemap file was not the XML shape its level promises."""


@dataclass(frozen=True)
class Entry:
    """One `<sitemap>` in an index: a child file and when it last changed."""

    loc: str
    lastmod: str

    @property
    def name(self) -> str:
        """The child's file name, decoded -- `tibco-enterprise-message-service.xml`."""
        return unquote(PurePosixPath(urlsplit(self.loc).path).name)

    @property
    def stem(self) -> str:
        name = self.name
        return name[:-4] if name.lower().endswith(".xml") else name


@dataclass(frozen=True)
class Page:
    """One `<url>` in a version's leaf."""

    loc: str
    title: str = ""
    version: str = ""
    access_level: str = ""


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _root(data: bytes, expected: str) -> ET.Element:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise SitemapError(f"not XML ({exc})") from exc
    if _local(root.tag) != expected:
        raise SitemapError(f"expected <{expected}>, found <{_local(root.tag)}>")
    return root


def _children(element: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in element if _local(child.tag) == name]


def _child_text(element: ET.Element | None, name: str) -> str:
    if element is None:
        return ""
    found = _children(element, name)
    return (found[0].text or "").strip() if found else ""


def parse_index(data: bytes) -> list[Entry]:
    """The entries of a `<sitemapindex>`, in file order. An entry with no `<loc>` is skipped."""
    root = _root(data, "sitemapindex")
    entries = []
    for node in _children(root, "sitemap"):
        loc = _child_text(node, "loc")
        if loc:
            entries.append(Entry(loc=loc, lastmod=_child_text(node, "lastmod")))
    return entries


def parse_urlset(data: bytes) -> list[Page]:
    """The pages of a version's `<urlset>`, in file order.

    `loc` is kept exactly as published. One leaf already carries an unencoded
    space, and deciding how to normalise that is the join's business, not the
    parser's -- a parser that normalised would hide the evidence.
    """
    root = _root(data, "urlset")
    pages = []
    for node in _children(root, "url"):
        loc = _child_text(node, "loc")
        if not loc:
            continue
        found = _children(node, "metadata")
        meta = found[0] if found else None
        pages.append(
            Page(
                loc=loc,
                title=_child_text(meta, "d_name"),
                version=_child_text(meta, "productversion"),
                access_level=_child_text(meta, "access_level"),
            )
        )
    return pages


def _is_html(data: bytes) -> bool:
    head = data.lstrip()[:64].lower()
    return head.startswith(b"<!doctype html") or head.startswith(b"<html")


def leaf_stem(slug: str, version: str) -> str:
    """The stem a version's leaf usually has -- `{slug}-{version_dashed}`."""
    return f"{slug}-{str(version).replace('.', '-')}"


def match_leaf(stems: Iterable[str], slug: str, version: str) -> str | None:
    """Which of a product file's leaves is this catalog version, or `None`.

    Matched on the **version suffix** among the leaves the product's own file
    listed, not on the full stem. A renamed product keeps its old name on old
    leaves: `tibco-streaming.xml` lists `spotfire-streaming-11-1-0`, and
    `spotfire-data-science-author.xml` lists `tibco-data-science-author-1-4-0`.
    The exact stem wins if present; otherwise exactly one suffix match is
    required, and two is `None` rather than a guess.

    The name left after the suffix must not end in a numeric segment, or `1.0`
    would claim `product-2-1-0` -- version 2.1.0 -- on its last two segments.
    """
    stems = list(stems)
    exact = leaf_stem(slug, version)
    if exact in stems:
        return exact
    suffix = "-" + str(version).replace(".", "-")
    found = [
        stem for stem in stems
        if stem.endswith(suffix) and not stem[: -len(suffix)].rsplit("-", 1)[-1].isdigit()
    ]
    return found[0] if len(found) == 1 else None


@dataclass
class FetchResult:
    fetched: int = 0
    reused: int = 0
    #: Product stems the root listed more than once; the first entry is used.
    duplicates: list[str] = field(default_factory=list)
    #: Requested slugs the root has no product file for.
    missing: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    #: Files the docsite answered with an HTML page -- its portal login page --
    #: instead of XML. HTTP 200 either way; this is how a file it does not have looks.
    not_served: list[str] = field(default_factory=list)
    #: product stem -> version leaf stems it listed.
    products: dict[str, list[str]] = field(default_factory=dict)


class SitemapCache:
    """`cache/coveo/`: the raw XML of every level, plus `manifest.json`."""

    def __init__(self, directory: Path):
        self.directory = Path(directory)

    def _manifest_path(self) -> Path:
        return self.directory / MANIFEST

    def manifest(self) -> dict:
        path = self._manifest_path()
        if not path.exists():
            return {"files": {}, "products": {}}
        loaded = json.loads(path.read_text(encoding="utf-8"))
        loaded.setdefault("files", {})
        loaded.setdefault("products", {})
        return loaded

    def save_manifest(self, manifest: dict) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        tmp = self._manifest_path().with_suffix(".json.part")
        tmp.write_text(json.dumps(manifest, indent=1, sort_keys=True), encoding="utf-8")
        replace_file(tmp, self._manifest_path())

    def path(self, name: str) -> Path:
        # A name comes from a <loc> on a site this tool does not own; keep only
        # the final component so no entry can write outside the cache.
        return self.directory / PurePosixPath(name.replace("\\", "/")).name

    def read(self, name: str) -> bytes | None:
        path = self.path(name)
        return path.read_bytes() if path.exists() else None

    def write(self, name: str, data: bytes) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.path(name)
        tmp = path.with_name(path.name + ".part")
        tmp.write_bytes(data)
        replace_file(tmp, path)

    def drop(self, name: str) -> None:
        self.path(name).unlink(missing_ok=True)

    def pages(self, slug: str, version: str) -> list[Page] | None:
        """A cached version's pages, or `None` if its product file listed no leaf for it (`match_leaf`)."""
        stem = match_leaf(self.manifest()["products"].get(slug, []), slug, version)
        if stem is None:
            return None
        data = self.read(f"{stem}.xml")
        return parse_urlset(data) if data is not None else None


def fetch(
    client: DocsiteClient,
    cache: SitemapCache,
    root_path: str,
    slugs: Iterable[str] | None = None,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> FetchResult:
    """Walks root -> product -> version for `slugs` (all products if `None`).

    The root is always fetched -- it is the only record of every child's
    `lastmod`. Below it, a file whose `lastmod` matches the manifest and which is
    on disk is reused rather than fetched. A failure on one file is recorded and
    the walk continues: one broken product file must not cost the other 499.
    """
    result = FetchResult()
    manifest = cache.manifest()
    files: dict[str, str] = manifest["files"]

    def get(entry: Entry, parse: Callable[[bytes], list]) -> list | None:
        # Parsed before it is cached, and again when reused: the docsite answers a
        # file it does not have with its login page and HTTP 200, and a cached
        # login page would read as a page list on every later run.
        cached = cache.read(entry.name)
        if cached is not None and entry.lastmod and files.get(entry.name) == entry.lastmod:
            try:
                parsed = parse(cached)
            except SitemapError:
                pass
            else:
                result.reused += 1
                return parsed
        try:
            data = client.get_bytes(entry.loc.replace(" ", "%20"))
        except DocsiteError as exc:
            result.errors.append(str(exc))
            return None
        try:
            parsed = parse(data)
        except SitemapError as exc:
            if _is_html(data):
                result.not_served.append(entry.name)
            else:
                result.errors.append(f"{entry.name}: {exc}")
            cache.drop(entry.name)
            files.pop(entry.name, None)
            return None
        cache.write(entry.name, data)
        files[entry.name] = entry.lastmod
        result.fetched += 1
        return parsed

    root = parse_index(client.get_bytes(root_path))
    result.fetched += 1

    by_stem: dict[str, Entry] = {}
    for entry in root:
        if entry.stem in by_stem:
            if entry.stem not in result.duplicates:
                result.duplicates.append(entry.stem)
            continue
        by_stem[entry.stem] = entry

    wanted = sorted(by_stem) if slugs is None else sorted(set(slugs))
    for index, slug in enumerate(wanted, 1):
        if on_progress:
            on_progress(index, len(wanted), slug)
        entry = by_stem.get(slug)
        if entry is None:
            result.missing.append(slug)
            continue
        versions = get(entry, parse_index)
        if versions is None:
            manifest["products"].pop(slug, None)
            continue
        stems: list[str] = []
        for leaf in versions:
            if get(leaf, parse_urlset) is not None:
                stems.append(leaf.stem)
        result.products[slug] = sorted(set(stems))
        manifest["products"][slug] = result.products[slug]
        # Saved per product, so an interrupted walk keeps what it fetched.
        cache.save_manifest(manifest)

    cache.save_manifest(manifest)
    return result
