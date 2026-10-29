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

import filecmp
import re
import subprocess
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

import yaml
from bs4 import BeautifulSoup

from docushift import origins
from docushift.engines import flare_toc
from docushift.engines.dita import CHROME_SELECTORS as DITA_CHROME
from docushift.engines.dita import CONTENT_SELECTOR as DITA_CONTENT
from docushift.engines.docbook import CONTENT_ID as DOCBOOK_CONTENT_ID
from docushift.engines.flare import CHROME_SELECTORS as FLARE_CHROME
from docushift.engines.flare import CONTENT_SELECTOR as FLARE_CONTENT
from docushift.engines.flare import LANDING_CHROME, PORTAL_BLOCKS
from docushift.engines.roots import by_language
from docushift.extractor import content_root
from docushift.models import SourceEngine
from docushift.reframe.toc import schema_for
from docushift.reporting.findings import FindingsRun, Severity
from docushift.state import READ_BACK_CODES
from docushift.sync import distributor, rooted, router
from docushift.sync import documents as document_index
from docushift.utils.csvio import natural_version_key
from docushift.utils.slug import is_primary_locale, version_segment
from docushift.validation import references
from docushift.validation.tree import VersionFolder, walk
from docushift.verify import images as pictures
from docushift.verify import live, published, triage
from docushift.verify import redirects as redirect_maps
from docushift.verify import text as texts
from docushift.verify.fetch import Fetcher
from docushift.verify.toc import Node, by_page, root

#: The doc-class `verify` reads. The others hold PDFs and generated index pages,
#: read only for a version with no online help (Phase 66).
DOC_CLASS = "online-help"
#: `index.md` links its documents as `- [title](link)`.
_INDEX_LINK = re.compile(r"\]\(([^)\s]+)\)")
DROP_CODES = READ_BACK_CODES
UNFILED = "unfiled/"
PRIMARY_LOCALE = "en-us"
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
    "toc_position_matched", "published_status", "skip_reason", "findings", "triage", "missing_sentences",
]


@dataclass
class VersionResult:
    folder: VersionFolder
    version: str = ""
    skipped: str = ""
    rows: list[dict[str, str]] = field(default_factory=list)
    #: Unexplained errors and warnings; `explained` counts the triaged ones of both.
    errors: int = 0
    warnings: int = 0
    explained: int = 0
    codes: Counter = field(default_factory=Counter)
    scope: str = "local"
    commit: str = ""
    #: page -> [(code, triage label)], for the report's per-page columns.
    on_page: dict[str, list[tuple[str, str]]] = field(default_factory=dict)

    @property
    def outcome(self) -> str:
        """`lost` > `issues` > `explained` > `clean` (Phase 58; notes never count)."""
        if self.errors:
            return "lost"
        if self.warnings:
            return "issues"
        return "explained" if self.explained else "clean"


class Verifier:
    def __init__(self, cfg, catalog, state, target: Path, findings: FindingsRun,
                 fetcher: Fetcher | None = None, base_url: str = "", live_sample: int = 0,
                 triaged: list[triage.Entry] | None = None, base_urls: dict[str, str] | None = None,
                 repair_states: dict[tuple[str, str, str], str] | None = None,
                 redirect_sample: int = 0, seed: int = 0) -> None:
        self.cfg, self.catalog, self.state = cfg, catalog, state
        self.target, self.findings = target, findings
        self.fetcher, self.base_url, self.live_sample = fetcher, base_url, live_sample
        self.triaged = triaged or []
        #: Staging host per business unit (Phase 58); `base_url` overrides all of them.
        self.base_urls = base_urls or {}
        #: `(slug, version, repair) -> state` (Phase 59), for triage entries naming a repair.
        self.repair_states = repair_states or {}
        #: Phase 60: `301.yml` rows followed per version, and the seed that picks them.
        self.redirect_sample, self.seed = redirect_sample, seed

    def selection(self, product: str | None, version: str | None, *, bu: str | None = None,
                  family: str | None = None, latest_only: bool = False,
                  statuses: dict[tuple[str, str], str] | None = None, wanted: tuple[str, ...] = (),
                  limit: int = 0, locale: str | None = None) -> list[VersionFolder]:
        """The published version folders a wave covers (Phase 58).

        Read from the target, then narrowed through the catalog: `bu`, `family`,
        the newest published version of each product only, and `wanted`
        `_verify_status` values (`not-verified`, `stale`...), from `statuses`.
        `limit` caps the wave. A folder the catalog does not know is kept, so
        `version` can say why it is skipped. `locale` keeps one language's folders
        (Phase 64): an English-only change need not re-read the `loc-` trees.

        A version with no online-help folder but documents (a PDF-only version,
        Phase 66) is selected once, by its first document folder; `version` reads
        all of them.
        """
        folders = _version_folders(walk(self.target, product, version))
        if locale:
            folders = [f for f in folders if f.locale.lower() == locale.lower()]
        picked: list[VersionFolder] = []
        for folder in folders:
            prod = self.catalog.products.get(folder.slug)
            if prod is not None and ((bu and prod.bu != bu) or (family and prod.family != family)):
                continue
            if wanted and statuses is not None:
                number = _number(prod, folder.segment)
                if (statuses.get((folder.slug, number or ""), "not-verified") or "not-verified") not in wanted:
                    continue
            picked.append(folder)
        if latest_only:
            newest: dict[str, VersionFolder] = {}
            for folder in picked:
                prod = self.catalog.products.get(folder.slug)
                held = newest.get(folder.slug)
                if held is None or natural_version_key(_number(prod, folder.segment) or folder.segment) > \
                        natural_version_key(_number(prod, held.segment) or held.segment):
                    newest[folder.slug] = folder
            picked = [f for f in picked if newest.get(f.slug) is f]
        return picked[:limit] if limit > 0 else picked

    # -- one version ------------------------------------------------------------

    def version(self, folder: VersionFolder) -> VersionResult:
        if folder.doc_class != DOC_CLASS:
            return self.documents(folder)
        result = VersionResult(folder)
        product = self.catalog.products.get(folder.slug)
        number = _number(product, folder.segment)
        if product is None or number is None:
            result.skipped = "not in the catalog"
            return result
        result.version = number
        ver = product.versions[number]
        # Phase 66: `extract_path`, not `extracted_dir`, so a `--locale ja-jp` run falls
        # back to the English package its translated help ships inside.
        extracted = self.cfg.extract_path(product.bu, product.family, folder.slug, number)
        outmap = self.state.get_output_map(folder.slug, number) if self.state else {}
        if not outmap or not extracted.is_dir():
            result.skipped = "no converted output recorded" if not outmap else "extracted package not on disk"
            return result

        redirects = _redirects(self.cfg.reframed_path(product.bu, product.family, folder.slug, number))
        found = sorted(p.parent.parent for p in extracted.rglob("Data/HelpSystem.xml"))
        engine = ver.engine if ver.engine in _SELECTORS else (SourceEngine.FLARE if found else ver.engine)
        # Phase 64. A package can ship one Flare root per language
        # (`html/{de-de,en-us,ja-jp}`); this folder is one of them, so only its
        # own language's roots, and the unlabelled ones, are its old TOC.
        roots = by_language(found, folder.locale, is_primary_locale(folder.locale, PRIMARY_LOCALE))[0]
        selector = _SELECTORS.get(engine, "body")
        chrome = _CHROME.get(engine, ())
        landings = _landings(roots, extracted)
        drops = self.state.latest_counts(folder.slug, number, DROP_CODES) if self.state else {}
        old_urls = {to: url for url, to in live.origins(folder.path / "301.yml", _rooted_prefix(folder))}

        tops: dict[str, str] = {}

        def key_of(source: str) -> str:
            out = outmap[source]
            key = redirects.get(out, out)
            # Phase 60. A topic that opens its page is mapped to the page's own top
            # heading (`introduction.md#introduction`), and `toc.yml` lists the page
            # bare -- so every unmerged reframed page read as missing from the TOC.
            page, _, fragment = key.partition("#")
            if fragment and fragment == _top_anchor(folder.path / PurePosixPath(page), tops):
                return page
            return key

        # A1-A3: every converted topic against the page it became.
        rows: dict[str, dict[str, str]] = {}
        unfiled = 0
        for source in sorted(outmap):
            key = key_of(source)
            page = key.partition("#")[0]
            old_url = next((old_urls[k] for k in (key, page, redirects.get(outmap[source], ""), outmap[source])
                            if k in old_urls), "")
            row = _row(folder, number, source, key, old_url)
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

        # Phase 60: both 301 maps, every run; a sample of their rows followed.
        host = self.base_url or self.base_urls.get(product.bu, "")
        self._redirect_maps(result, folder, number, outmap, key_of, extracted, selector, chrome, host)

        # B: staging, against the product's own business unit's site.
        if self.fetcher is not None and host:
            self._published(result, folder, rows, host)
            result.scope += "+staging"

        # C: a sample of the live site.
        if self.fetcher is not None and self.live_sample > 0:
            self._live(result, folder, extracted, outmap, key_of, selector, chrome)
            result.scope += "+live"

        for row in rows.values():
            hits = result.on_page.get(row["new_path"].partition("#")[0], [])
            row["findings"] = " ".join(sorted({code for code, _ in hits}))
            row["triage"] = " ".join(sorted({label for _, label in hits if label}))
        result.rows = list(rows.values())
        # Phase 66: the documents beside the help, which `sync` publishes for the
        # primary language only.
        if is_primary_locale(folder.locale, PRIMARY_LOCALE):
            result.rows += self._documents(result, folder, product, number)
        result.commit = _commit(folder.path)
        return result

    def documents(self, folder: VersionFolder) -> VersionResult:
        """A PDF-only version (Phase 66): only its documents to check."""
        result = VersionResult(folder)
        product = self.catalog.products.get(folder.slug)
        number = _number(product, folder.segment)
        if product is None or number is None:
            result.skipped = "not in the catalog"
            return result
        result.version = number
        if not self.cfg.extract_path(product.bu, product.family, folder.slug, number).is_dir():
            result.skipped = "extracted package not on disk"
            return result
        result.rows = self._documents(result, folder, product, number)
        result.commit = _commit(folder.path)
        return result

    def _documents(self, result: VersionResult, folder: VersionFolder, product, number: str) -> list[dict[str, str]]:
        """The package's documents, published as shipped (Phase 66); one row per file.

        The expected set is what `sync` would place, from its own router and
        de-duplication, so the two cannot disagree on a name. Each document must be
        in its doc-class folder with the package's bytes and linked from `index.md`;
        nothing else may be there but the files `sync` renders. `folder` is any of
        the version's published folders: the doc-class folders are its siblings.
        """
        tree = self.cfg.extract_path(product.bu, product.family, folder.slug, number)
        metadata = self.state.get_version_metadata(folder.slug, number) if self.state else {}
        content = content_root.of(tree, metadata.get(content_root.METADATA_KEY))
        grouped = document_index.group(router.route_version(content, product.versions[number].engine))

        rows: list[dict[str, str]] = []
        for doc_class in router.DOCUMENT_DOC_CLASSES:
            place = VersionFolder(folder.path.parent.parent / doc_class / folder.segment, folder.tree,
                                  folder.locale, folder.slug, doc_class, folder.segment)
            expected = grouped.get(doc_class, [])
            if not expected and not place.path.is_dir():
                continue
            listed = _index_links(place.path / "index.md")
            names = {item.path.name for item in expected}
            here: list[dict[str, str]] = []
            for item in expected:
                name = item.path.name
                row = _row(place, number, item.path.relative_to(tree).as_posix(), f"{doc_class}/{name}", "")
                published = place.path / name
                if not published.is_file():
                    self._record(result, "VERIFY_DOCUMENT_MISSING", place, name,
                                 f"{name}: shipped in the package, not in the published folder")
                    row["published_status"] = "missing locally"
                elif not filecmp.cmp(item.path, published, shallow=False):
                    self._record(result, "VERIFY_DOCUMENT_CHANGED", place, name,
                                 f"{name}: published bytes differ from the package's")
                    row["published_status"] = "changed"
                else:
                    row["published_status"] = "ok"
                    if name not in listed:
                        self._record(result, "VERIFY_DOCUMENT_UNLISTED", place, name,
                                     f"{name}: not linked from index.md")
                here.append(row)
            extra = sorted(p.name for p in place.path.iterdir()
                           if p.is_file() and p.name not in names and p.name not in distributor.RENDERED) \
                if place.path.is_dir() else []
            for name in extra:
                self._record(result, "VERIFY_DOCUMENT_EXTRA", place, name,
                             f"{name}: in the published folder, but sync would not place it here")
                here.append(_row(place, number, "", f"{doc_class}/{name}", "") | {"published_status": "extra"})
            # `on_page` is keyed by filename, and one name can be in two doc-classes
            # (a release note moved between them), so each class takes its own now.
            for row in here:
                hits = result.on_page.pop(row["new_path"].partition("/")[2], [])
                row["findings"] = " ".join(sorted({code for code, _ in hits}))
                row["triage"] = " ".join(sorted({label for _, label in hits if label}))
            rows += here
        return rows

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

    def _published(self, result: VersionResult, folder: VersionFolder, rows, host: str) -> None:
        toc = _toc_tree(folder.path / "toc.yml")
        if toc is None:
            return
        urls = published.entry_urls(host, folder.locale, folder.slug, folder.doc_class,
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

    def _redirect_maps(self, result, folder, number: str, outmap, key_of, extracted: Path, selector: str,
                       chrome: tuple[str, ...], host: str) -> None:
        pages = origins.page_list(self.cfg.cache_dir, folder.slug, number)
        pages = origins.for_locale(pages, folder.locale, is_primary_locale(folder.locale, PRIMARY_LOCALE))
        ctx = redirect_maps.Context(
            folder=folder.path, locale=folder.locale, slug=folder.slug, doc_class=folder.doc_class,
            segment=folder.segment, base=self.cfg.publish_base_url(), pages=pages,
            sources={source: key_of(source) for source in outmap}, extracted=extracted,
            selector=selector, chrome=chrome)
        checked = redirect_maps.check(ctx, self.redirect_sample, self.seed, self.fetcher, host)
        for issue in checked.issues:
            self._record(result, issue.code, folder, issue.path, issue.message, count=issue.count)

    def _live(self, result, folder, extracted: Path, outmap, key_of, selector: str,
              chrome: tuple[str, ...]) -> None:
        by_page: dict[str, str] = {}
        for source in outmap:
            by_page.setdefault(key_of(source).partition("#")[0], source)
        uncheckable = 0
        for url, to in live.sample(live.origins(folder.path / "301.yml", _rooted_prefix(folder)), self.live_sample):
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
        version = result.version or folder.segment
        decided = triage.match(self.triaged, code, folder.slug, version, path)
        needed = decided is not None and decided.repair and \
            self.repair_states.get((folder.slug, version, decided.repair)) == "needed"
        if needed:
            # The repair that explains it has not reached this version yet.
            message = f"{message} [repair {decided.repair} still needed here]"
            decided = None
        if decided is not None:
            message = f"{message} [triage: {decided.label}]"
        finding = self.findings.record(code, folder.slug, version,
                                       (folder.relative / path).as_posix() if path else folder.relative.as_posix(),
                                       message, count)
        result.codes[code] += count
        result.on_page.setdefault(path.partition("#")[0], []).append((code, decided.label if decided else ""))
        if finding.severity is Severity.NOTE:
            return
        if decided is not None:
            result.explained += 1
        elif finding.severity is Severity.ERROR:
            result.errors += 1
        else:
            result.warnings += 1


# -- helpers ----------------------------------------------------------------------


def _version_folders(products) -> list[VersionFolder]:
    """Each product's online-help version folders, and one per PDF-only version (Phase 66).

    A version is PDF-only here when it has a document folder and no online-help
    folder for the same segment. Only the primary locale: `sync` publishes no
    documents to a `loc-` tree.
    """
    picked: list[VersionFolder] = []
    for entry in products:
        helps = {v.segment for v in entry.versions if v.doc_class == DOC_CLASS}
        picked += [v for v in entry.versions if v.doc_class == DOC_CLASS]
        if not is_primary_locale(entry.locale, PRIMARY_LOCALE):
            continue
        seen: set[str] = set()
        for v in entry.versions:
            if v.doc_class in router.DOCUMENT_DOC_CLASSES and v.segment not in helps | seen:
                seen.add(v.segment)
                picked.append(v)
    return picked


def _index_links(index: Path) -> set[str]:
    """The filenames `index.md` links, unquoted; empty when there is no index."""
    try:
        text = index.read_text(encoding="utf-8")
    except OSError:
        return set()
    return {unquote(link) for link in _INDEX_LINK.findall(text)}


def _number(product, segment: str) -> str | None:
    """The catalog's version for a published segment (`9-3-8` -> `9.3.8`), or None."""
    return next((v for v in (product.versions if product else {}) if version_segment(v) == segment), None)


def _commit(path: Path) -> str:
    """The last commit touching the published folder, or "" outside git (Phase 58)."""
    try:
        done = subprocess.run(["git", "-C", str(path), "log", "-1", "--format=%h", "--", "."],
                              capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


def _row(folder: VersionFolder, number: str, source: str, key: str, old_url: str) -> dict[str, str]:
    row = dict.fromkeys(COLUMNS, "")
    row.update(slug=folder.slug, version=number, old_url=old_url, local_source=source, new_path=key)
    return row


def _top_anchor(md_path: Path, cache: dict[str, str]) -> str:
    """The anchor AEM gives the first heading of a published page, or ""."""
    key = md_path.as_posix()
    if key not in cache:
        try:
            text = md_path.read_text(encoding="utf-8")
        except OSError:
            text = ""
        cache[key] = next(iter(references.headings(text)), "")
    return cache[key]


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


def _rooted_prefix(folder) -> str:
    """The version folder from the repo root -- how a published `301.yml` names pages (Phase 68)."""
    return rooted.folder_prefix(folder.locale, folder.slug, folder.doc_class, folder.segment)
