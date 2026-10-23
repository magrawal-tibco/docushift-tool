"""`docushift verify`: one published version folder at a time, A then B then C.

Reads the catalog for the version's workspace, `state.db` for what each source
became (`output_map`) and what the conversion dropped on purpose, the merge's
`redirects.yml` where there is one, and the published folder itself. Writes
nothing but findings and the report rows the CLI turns into a CSV.

**Known drops are classified per topic only where the data proves it** (Phase 55,
as built). The conversion's drop findings are per-version counts with no path, so
they cannot excuse one topic. A page under `unfiled/` is a TOC orphan; a TOC row
that repeats its parent's page, or opens no page, adds nothing; anything else
missing is `VERIFY_TOPIC_MISSING`, with the version's recorded drop counts in the
message for the reviewer to reconcile.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

import yaml
from bs4 import BeautifulSoup

from docushift.engines import flare_toc
from docushift.engines.dita import CHROME_SELECTORS as DITA_CHROME
from docushift.engines.dita import CONTENT_SELECTOR as DITA_CONTENT
from docushift.engines.docbook import CONTENT_ID as DOCBOOK_CONTENT_ID
from docushift.engines.flare import CHROME_SELECTORS as FLARE_CHROME
from docushift.engines.flare import CONTENT_SELECTOR as FLARE_CONTENT
from docushift.engines.flare import LANDING_CHROME, PORTAL_BLOCKS
from docushift.models import SourceEngine
from docushift.reframe.toc import schema_for
from docushift.reporting.findings import FindingsRun
from docushift.utils.slug import version_segment
from docushift.validation.tree import VersionFolder, walk
from docushift.verify import images as pictures
from docushift.verify import live, published
from docushift.verify import text as texts
from docushift.verify.fetch import Fetcher
from docushift.verify.toc import Node, by_page, root

#: The doc-class `verify` reads. The others hold PDFs and generated index pages.
DOC_CLASS = "online-help"
DROP_CODES = ("NAV_NODE_DROPPED", "ROOT_COPY_DROPPED", "TOC_ORPHAN", "TOC_SUBPROJECT_UNPLACED")
UNFILED = "unfiled/"
_PORTAL = frozenset(" ".join(texts.words(label)) for label in PORTAL_BLOCKS)
_SELECTORS = {
    SourceEngine.FLARE: FLARE_CONTENT,
    SourceEngine.DITA: DITA_CONTENT,
    SourceEngine.DOCBOOK: f"#{DOCBOOK_CONTENT_ID}",
    SourceEngine.WEBWORKS: "body",
}
#: Chrome *inside* the container, removed exactly as the engine removes it -- a
#: Flare topic's feedback widget is in `#mc-main-content`, and left in it would
#: read as a sentence every converted page lost.
_CHROME: dict[SourceEngine, tuple[str, ...]] = {
    SourceEngine.FLARE: FLARE_CHROME,
    SourceEngine.DITA: DITA_CHROME,
}

COLUMNS = [
    "slug", "version", "old_url", "local_source", "new_path", "staging_url", "text_percent",
    "missing_sentences_count", "images_found", "images_expected", "toc_parent_matched",
    "toc_position_matched", "published_status", "skip_reason", "missing_sentences",
]


@dataclass
class VersionResult:
    folder: VersionFolder
    version: str = ""
    skipped: str = ""
    rows: list[dict[str, str]] = field(default_factory=list)
    errors: int = 0


class Verifier:
    def __init__(self, cfg, catalog, state, target: Path, findings: FindingsRun,
                 fetcher: Fetcher | None = None, base_url: str = "", live_sample: int = 0) -> None:
        self.cfg, self.catalog, self.state = cfg, catalog, state
        self.target, self.findings = target, findings
        self.fetcher, self.base_url, self.live_sample = fetcher, base_url, live_sample

    def selection(self, product: str | None, version: str | None) -> list[VersionFolder]:
        return [v for entry in walk(self.target, product, version, DOC_CLASS) for v in entry.versions]

    # -- one version ------------------------------------------------------------

    def version(self, folder: VersionFolder) -> VersionResult:
        result = VersionResult(folder)
        product = self.catalog.products.get(folder.slug)
        number = next((v for v in (product.versions if product else {})
                       if version_segment(v) == folder.segment), None)
        if product is None or number is None:
            result.skipped = "not in the catalog"
            return result
        result.version = number
        ver = product.versions[number]
        extracted = self.cfg.extracted_dir(product.bu, product.family) / folder.slug / number
        outmap = self.state.get_output_map(folder.slug, number) if self.state else {}
        if not outmap or not extracted.is_dir():
            result.skipped = "no converted output recorded" if not outmap else "extracted package not on disk"
            return result

        redirects = _redirects(self.cfg.reframed_path(product.bu, product.family, folder.slug, number))
        roots = sorted(p.parent.parent for p in extracted.rglob("Data/HelpSystem.xml"))
        engine = ver.engine if ver.engine in _SELECTORS else (SourceEngine.FLARE if roots else ver.engine)
        selector = _SELECTORS.get(engine, "body")
        chrome = _CHROME.get(engine, ())
        landings = _landings(roots, extracted)
        drops = self.state.latest_counts(folder.slug, number, DROP_CODES) if self.state else {}
        old_urls = {to: url for url, to in live.origins(folder.path / "301.yml")}

        def key_of(source: str) -> str:
            out = outmap[source]
            return redirects.get(out, out)

        # A1-A3: every converted topic against the page it became.
        rows: dict[str, dict[str, str]] = {}
        unfiled = 0
        for source in sorted(outmap):
            key = key_of(source)
            page = key.partition("#")[0]
            row = _row(folder, number, source, key, old_urls.get(page, old_urls.get(outmap[source], "")))
            rows[source] = row
            if page.startswith(UNFILED):
                unfiled += 1
                row["skip_reason"] = "TOC_ORPHAN: kept under unfiled/, in no menu"
                continue
            md_path = folder.path / PurePosixPath(page)
            if not md_path.is_file():
                self._record(result, "VERIFY_TOPIC_MISSING", folder, page,
                             f"{source} -> {key}: no published page{_counts(drops)}")
                row["published_status"] = "missing locally"
                continue
            self._compare(result, folder, extracted / PurePosixPath(source), md_path, page, selector,
                          chrome, landing=source in landings, row=row)
        if unfiled:
            self._record(result, "VERIFY_TOPIC_UNFILED", folder, "", f"{unfiled} topic(s) under unfiled/",
                         count=unfiled)

        # A1 for topics only the old TOC names, and A5.
        if engine is SourceEngine.FLARE and roots:
            old_tree, unconverted = _flare_tree(roots, extracted, outmap, key_of)
            for source, title in unconverted:
                self._record(result, "VERIFY_TOPIC_MISSING", folder, source,
                             f"old TOC entry {title!r} ({source}) was not converted{_counts(drops)}")
            new_tree = _toc_tree(folder.path / "toc.yml")
            if new_tree is not None:
                skip = {k for k in (key_of(s) for s in outmap) if k.startswith(UNFILED)}
                compared = by_page(old_tree, new_tree, skip)
                codes = {"missing": "VERIFY_TOC_ENTRY_MISSING", "moved": "VERIFY_TOC_MOVED",
                         "order": "VERIFY_TOC_ORDER", "title": "VERIFY_TOC_TITLE_CHANGED"}
                for issue in compared.issues:
                    self._record(result, codes[issue.kind], folder, issue.key, issue.detail)
                _mark_toc(rows.values(), compared)
        else:
            self._record(result, "VERIFY_TOC_UNCHECKED", folder, "",
                         f"engine {engine}: no old-TOC reader in verify yet")

        # B: staging.
        if self.fetcher is not None and self.base_url:
            self._published(result, folder, rows)

        # C: a sample of the live site.
        if self.fetcher is not None and self.live_sample > 0:
            self._live(result, folder, extracted, outmap, key_of, selector, chrome)

        result.rows = list(rows.values())
        return result

    def _compare(self, result, folder, source: Path, md_path: Path, page: str, selector: str,
                 chrome: tuple[str, ...], landing: bool, row: dict[str, str]) -> None:
        try:
            html = source.read_text(encoding="utf-8", errors="replace")
            markdown = md_path.read_text(encoding="utf-8")
        except OSError as exc:
            self._record(result, "VERIFY_TOPIC_MISSING", folder, page, f"could not read: {exc}")
            return
        soup = BeautifulSoup(html, "html.parser")
        container = soup.select_one(selector) or soup.body or soup
        for css in (*chrome, *(LANDING_CHROME if landing else ())):
            for tag in container.select(css):
                tag.decompose()
        found = pictures.html_images(container, source)
        old = texts.Text(texts.html_blocks(container))
        if landing:
            old = texts.cut_at(old, _PORTAL)
        cover = texts.coverage(old, texts.markdown_text(markdown))
        row["text_percent"] = f"{cover.percent}"
        row["missing_sentences_count"] = str(len(cover.missing))
        row["missing_sentences"] = " | ".join(cover.missing)
        if cover.missing:
            self._record(result, "VERIFY_TEXT_DROPPED", folder, page,
                         f"{len(cover.missing)} sentence(s) missing, e.g. {_quote(cover.missing)}")

        new = pictures.markdown_images(markdown, md_path)
        gone = pictures.missing(found, new)
        row["images_expected"] = str(len(found.pictures))
        row["images_found"] = str(len(found.pictures) - len(gone))
        for picture in gone:
            self._record(result, "VERIFY_IMAGE_MISSING", folder, page, f"{picture.src} not on the page")
        for picture in pictures.broken(new):
            self._record(result, "VERIFY_IMAGE_MISSING", folder, page, f"{picture.src} not in the tree")

    def _published(self, result: VersionResult, folder: VersionFolder, rows) -> None:
        toc = _toc_tree(folder.path / "toc.yml")
        if toc is None:
            return
        urls = published.entry_urls(self.base_url, folder.locale, folder.slug, folder.doc_class,
                                    folder.segment, toc)
        checked = published.check(self.fetcher, urls, toc, folder.path)
        if not checked.reachable:
            self._record(result, "VERIFY_PUBLISHED_PAGE_MISSING", folder, "",
                         f"no menu served at {' or '.join(urls)}")
            for row in rows.values():
                row["published_status"] = row["published_status"] or "version not served"
            return
        codes = {"missing": "VERIFY_PUBLISHED_TOC_ENTRY_MISSING", "moved": "VERIFY_PUBLISHED_TOC_MOVED",
                 "order": "VERIFY_PUBLISHED_TOC_ORDER", "title": "VERIFY_PUBLISHED_TOC_TITLE_CHANGED"}
        for issue in checked.menu.issues if checked.menu else []:
            self._record(result, codes[issue.kind], folder, issue.key, issue.detail)
        for page, check in checked.pages.items():
            if check.status == "missing":
                self._record(result, "VERIFY_PUBLISHED_PAGE_MISSING", folder, page, f"{check.url} is not served")
            if check.missing:
                self._record(result, "VERIFY_PUBLISHED_TEXT_DIFF", folder, page,
                             f"{len(check.missing)} sentence(s) not served, e.g. {_quote(check.missing)}")
            if check.callouts:
                self._record(result, "VERIFY_PUBLISHED_CALLOUT_UNRENDERED", folder, page,
                             f"{check.callouts} note(s) shown with no label", count=check.callouts)
            for detail in check.broken_images:
                self._record(result, "VERIFY_PUBLISHED_IMAGE_BROKEN", folder, page, detail)
            for rel in check.alt_dropped:
                self._record(result, "VERIFY_PUBLISHED_ALT_DROPPED", folder, page, f"{rel}: alt text not served")
        for row in rows.values():
            check = checked.pages.get(row["new_path"].partition("#")[0])
            if check is not None:
                row["staging_url"] = check.url
                row["published_status"] = check.status if check.status != "ok" else (
                    "ok" if not check.missing else f"text {check.text_percent}%")

    def _live(self, result, folder, extracted: Path, outmap, key_of, selector: str,
              chrome: tuple[str, ...]) -> None:
        by_page: dict[str, str] = {}
        for source in outmap:
            by_page.setdefault(key_of(source).partition("#")[0], source)
        uncheckable = 0
        for url, to in live.sample(live.origins(folder.path / "301.yml"), self.live_sample):
            source = by_page.get(to.partition("#")[0])
            local = None
            if source is not None:
                try:
                    local = texts.html_text((extracted / PurePosixPath(source)).read_text(
                        encoding="utf-8", errors="replace"), selector, chrome)
                except OSError:
                    local = None
            checked = live.check(self.fetcher, url, local, selector, chrome)
            if checked.status == "uncheckable":
                uncheckable += 1
            elif checked.status == "drift":
                self._record(result, "VERIFY_LIVE_DRIFT", folder, to,
                             f"{url}: {len(checked.missing)} sentence(s) not in the downloaded copy, "
                             f"e.g. {_quote(checked.missing)}")
        if uncheckable:
            self._record(result, "VERIFY_LIVE_UNCHECKABLE", folder, "",
                         f"{uncheckable} sampled page(s) answered with sign-in or an error", count=uncheckable)

    def _record(self, result: VersionResult, code: str, folder: VersionFolder, path: str,
                message: str, count: int = 1) -> None:
        finding = self.findings.record(code, folder.slug, result.version or folder.segment,
                                       (folder.relative / path).as_posix() if path else folder.relative.as_posix(),
                                       message, count)
        if finding.severity == "error":
            result.errors += 1


# -- helpers ----------------------------------------------------------------------


def _row(folder: VersionFolder, number: str, source: str, key: str, old_url: str) -> dict[str, str]:
    row = dict.fromkeys(COLUMNS, "")
    row.update(slug=folder.slug, version=number, old_url=old_url, local_source=source, new_path=key)
    return row


def _redirects(reframed: Path) -> dict[str, str]:
    """`output path -> page.md#anchor` from a merge's `redirects.yml`; empty if unmerged."""
    rows = live.origins(reframed / "redirects.yml")
    return {src: dst for src, dst in rows}


def _landings(roots: list[Path], extracted: Path) -> set[str]:
    """Each Flare root's `DefaultUrl` page, as an `output_map` source path."""
    found: set[str] = set()
    for root_dir in roots:
        manifest = flare_toc.read_manifest(root_dir)
        if manifest is not None and manifest.default_url:
            found.add((root_dir.relative_to(extracted) / manifest.default_url).as_posix())
    return found


def _flare_tree(roots: list[Path], extracted: Path, outmap: dict[str, str], key_of):
    """The old TOC of every Flare root as one tree keyed by published page.

    Returns the tree and the `(source, title)` rows whose page was never converted.
    A `.flprj` insertion point is a merge marker, not a page (Phase 51), and is left out.
    """
    unconverted: list[tuple[str, str]] = []

    def build(nodes, base: str) -> list[Node]:
        out: list[Node] = []
        for node in nodes:
            if node.entry.project:
                continue
            key = None
            if node.entry.path:
                source = f"{base}/{node.entry.path}" if base else node.entry.path
                if source in outmap:
                    key = key_of(source)
                    # A bookmark row opens the page at its anchor, as `toc.yml`
                    # writes it -- unless the merge already placed the topic at
                    # an anchor of its own, which then is the row's target.
                    if node.entry.anchor and "#" not in key:
                        key = f"{key}#{node.entry.anchor}"
                else:
                    unconverted.append((source, node.entry.label))
            out.append(Node(node.entry.label, key, build(node.children, base)))
        return out

    top: list[Node] = []
    for root_dir in roots:
        manifest = flare_toc.read_manifest(root_dir)
        name = manifest.toc if manifest and manifest.toc else ""
        files = [root_dir / name] if name else flare_toc.tree_files(root_dir)[:1]
        for file in files:
            toc = flare_toc.read_toc(file)
            top.extend(build(toc.nodes, root_dir.relative_to(extracted).as_posix()))
    return root(top), unconverted


def _toc_tree(path: Path) -> Node | None:
    """A published `toc.yml` as a tree keyed by `page.md` or `page.md#anchor`."""
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    schema = schema_for(document)
    if schema is None:
        return None

    def convert(entries) -> list[Node]:
        return [Node(e.title, (f"{e.path.as_posix()}#{e.fragment}" if e.fragment else e.path.as_posix())
                     if e.path is not None else None, convert(e.children)) for e in entries]

    return root(convert(schema.parse(document)))


def _mark_toc(rows, compared) -> None:
    moved = {i.key for i in compared.of("moved")} | {i.key for i in compared.of("missing")}
    for row in rows:
        if row["skip_reason"]:
            continue
        row["toc_parent_matched"] = "no" if row["new_path"] in moved else "yes"
        row["toc_position_matched"] = row["toc_parent_matched"]


def _counts(drops: dict[str, int]) -> str:
    return "" if not drops else "; the conversion recorded " + ", ".join(f"{c} {n}" for c, n in drops.items())


def _quote(sentences: list[str]) -> str:
    shown = " | ".join(f'"{s[:140]}"' for s in sentences[:3])
    return shown + (f" and {len(sentences) - 3} more" if len(sentences) > 3 else "")
