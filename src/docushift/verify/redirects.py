"""Phase 60: the 301 maps -- present, complete, and a sample of rows that work.

The AEM side reads `301.yml` (confirmed 2026-10-24), so every `verify` run checks
that a version has one and that its product's assembled map carries its rows.
Those checks read two files and compare dictionaries, so they cover every row.
What costs is following a row -- reading the target page, comparing the old text,
asking staging -- so that is done for a **random sample** per version, picked by a
seed the report records so a run can be repeated (the user, 2026-10-24).

A row's old page is found from its `from` URL by source path, never through the
map itself, so a row that sends readers to the wrong page cannot vouch for itself.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from docushift import origins
from docushift.sync import redirects as served
from docushift.validation import references
from docushift.verify import live, published
from docushift.verify import text as texts
from docushift.verify.fetch import Fetcher

FILE = "301.yml"
#: Below this share of the old page's words, a target is another page, not this one.
SAME_TOPIC_PERCENT = 50.0


@dataclass
class Issue:
    code: str
    path: str
    message: str
    count: int = 1


@dataclass
class Check:
    issues: list[Issue] = field(default_factory=list)

    def add(self, code: str, path: str, message: str, count: int = 1) -> None:
        self.issues.append(Issue(code, path, message, count))


@dataclass
class Context:
    """What one version's checks read; built by the driver."""

    folder: Path
    locale: str
    slug: str
    doc_class: str
    segment: str
    base: str
    #: The docsite sitemap's live URLs for this version; empty when not cached.
    pages: list[str]
    #: `output_map` source -> published page key (`page.md` or `page.md#anchor`).
    sources: dict[str, str]
    extracted: Path
    selector: str
    chrome: tuple[str, ...] = ()


def check(ctx: Context, sample: int, seed: int, fetcher: Fetcher | None = None, host: str = "") -> Check:
    result = Check()
    rows = _maps(ctx, result)
    if rows is None:
        return result
    find = _source_finder(ctx.sources)
    _coverage(ctx, rows, find, result)
    picked = _pick(rows, sample, seed, ctx)
    if not picked:
        return result
    listed = {origins.page_path(url) for url in ctx.pages}
    asked: list[tuple[str, str, bool]] = []
    for frm, to in picked:
        if listed and origins.page_path(frm) not in listed:
            result.add("VERIFY_REDIRECT_FROM_UNLISTED", "", f"{frm} is not in the docsite sitemap")
        page, _, fragment = to.partition("#")
        md_path = ctx.folder / PurePosixPath(page)
        try:
            markdown = md_path.read_text(encoding="utf-8")
        except OSError:
            result.add("VERIFY_REDIRECT_TARGET_MISSING", page, f"{frm} -> {to}: no such page")
            continue
        if fragment and fragment not in references.anchors(markdown):
            result.add("VERIFY_REDIRECT_TARGET_MISSING", page, f"{frm} -> {to}: no #{fragment} on the page")
        _same_topic(ctx, frm, to, page, markdown, find, result)
        if fetcher is not None and host:
            url = f"{host.rstrip('/')}/{_served(ctx, to).partition('#')[0]}"
            fetched = fetcher.get(url)
            asked.append((page, url, fetched.ok and published.is_page(fetched.text, url)))
    _staging(asked, result)
    result.add("VERIFY_REDIRECT_SAMPLED", "",
               f"{len(picked)} of {len(rows)} row(s) checked (seed {seed})"
               + ("" if ctx.pages else "; no cached sitemap, so coverage and `from` were not checked"))
    return result


# -- 0: both files present, the product's carrying the version's rows ------------


def _maps(ctx: Context, result: Check) -> list[tuple[str, str]] | None:
    mine = ctx.folder / FILE
    rows = live.origins(mine)
    if not rows:
        why = "no" if not mine.is_file() else "an unreadable or empty"
        result.add("VERIFY_REDIRECT_MAP_MISSING", FILE, f"the version has {why} {FILE}")
        return None
    product = ctx.folder.parent / FILE
    assembled = dict(live.origins(product))
    if not assembled:
        why = "no" if not product.is_file() else "an unreadable or empty"
        result.add("VERIFY_REDIRECT_MAP_MISSING", "",
                   f"{ctx.doc_class} has {why} product-level {FILE} beside version.yml")
        return rows
    absent = [frm for frm, _ in rows if frm not in assembled]
    moved = [frm for frm, to in rows if frm in assembled and assembled[frm] != _served(ctx, to)]
    if absent:
        result.add("VERIFY_REDIRECT_MAP_INCOMPLETE", "",
                   f"{len(absent)} of {len(rows)} row(s) missing from the product {FILE}, e.g. {absent[0]}",
                   len(absent))
    if moved:
        result.add("VERIFY_REDIRECT_MAP_INCOMPLETE", "",
                   f"{len(moved)} row(s) sent elsewhere by the product {FILE}, e.g. {moved[0]} -> "
                   f"{assembled[moved[0]]}", len(moved))
    return rows


def _served(ctx: Context, to: str) -> str:
    """A version-root `to` as the product map writes it -- `sync`'s own rule."""
    return served.published(ctx.base, "", ctx.locale, ctx.slug, ctx.doc_class, ctx.segment, to)


# -- 1: every live page of a published topic has a row ---------------------------


def _coverage(ctx: Context, rows, find, result: Check) -> None:
    if not ctx.pages:
        return
    orphans = unconverted = 0
    for url in origins.unmapped([{"from": frm} for frm, _ in rows], ctx.pages):
        source = find(url)
        if source is None:
            unconverted += 1
        elif ctx.sources[source].startswith("unfiled/"):
            orphans += 1  # left unpublished by rule (Phase 43), so no row
        else:
            result.add("VERIFY_REDIRECT_UNMAPPED", ctx.sources[source].partition("#")[0],
                       f"{url} has no row; its topic {source} is published")
    if unconverted:
        result.add("VERIFY_REDIRECT_UNCONVERTED", "",
                   f"{unconverted} live page(s) with no row and no converted topic"
                   + (f"; {orphans} more are unpublished orphans" if orphans else ""), unconverted)


def _source_finder(sources: dict[str, str]):
    """`live URL -> output_map source`, by the longest source path its path ends with.

    Sources keep their package root (`wfce-9-3-7/html/…`) and live paths drop it
    (`/pub/wfce/9.3.7/doc/html/…`), so both a source and the source less its first
    segment are indexed.
    """
    index: dict[str, str] = {}
    for source in sources:
        index.setdefault(source.lower(), source)
        _, _, rest = source.partition("/")
        if rest:
            index.setdefault(rest.lower(), source)

    def find(url: str) -> str | None:
        parts = origins.page_path(url).strip("/").lower().split("/")
        for i in range(len(parts)):
            hit = index.get("/".join(parts[i:]))
            if hit is not None:
                return hit
        return None

    return find


# -- 2-5: a sample of rows, followed ---------------------------------------------


def _pick(rows: list[tuple[str, str]], size: int, seed: int, ctx: Context) -> list[tuple[str, str]]:
    if size <= 0:
        return []
    chooser = random.Random(f"{seed}:{ctx.slug}:{ctx.segment}")
    return sorted(chooser.sample(rows, min(size, len(rows))))


def _same_topic(ctx: Context, frm: str, to: str, page: str, markdown: str, find, result: Check) -> None:
    source = find(frm)
    if source is None:
        return
    try:
        html = (ctx.extracted / PurePosixPath(source)).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    old = texts.html_text(html, ctx.selector, ctx.chrome) or texts.html_text(html, "body", ctx.chrome)
    if old is None or not old.word_count:
        return
    cover = texts.coverage(old, texts.markdown_text(markdown))
    if cover.percent < SAME_TOPIC_PERCENT:
        result.add("VERIFY_REDIRECT_WRONG_PAGE", page,
                   f"{frm} -> {to}: the target holds {cover.percent}% of the old page's text")


def _staging(asked: list[tuple[str, str, bool]], result: Check) -> None:
    if not asked:
        return
    if not any(ok for _, _, ok in asked):
        result.add("VERIFY_REDIRECT_NOT_ON_STAGING", "",
                   f"none of {len(asked)} sampled target(s) is served, e.g. {asked[0][1]}; "
                   "the layout has not reached staging yet")
        return
    for page, url, ok in asked:
        if not ok:
            result.add("VERIFY_REDIRECT_UNSERVED", page, f"{url} is not served")
