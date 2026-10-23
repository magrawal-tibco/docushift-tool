"""B: what stg-docs.ibi.com serves, against the published repo (Phase 55).

The probe (2026-10-22) settled the shape this module reads:

- The version's own page is `{base}/{country}/{lang}/{slug}/{doc-class}/{segment}.html`
  (`en-us` -> `us/en`), and every page carries the **whole menu** in its HTML,
  fully expanded: `nav.cmp-navigation` -> `ul.cmp-navigation__group` ->
  `li.cmp-navigation__item` -> `a.cmp-navigation__item-link`. So the menu is read
  once, matched to `toc.yml` by title (`toc.by_title`), and each page's URL comes
  from the menu. No URL is derived by rule: below the version, AEM paths follow the
  menu, not the repo (`installation/overview.md` is `installation_guide/overview.html`).
- **An unknown path is served the docs home page with HTTP 200.** A page counts as
  found only when its `main[data-page-path]` names the path that was asked for.
- The article is `main#section-topic div.topic-renderer__content`; everything else
  on the page is chrome.
- Images are served from `/content/dam/.../{slug}/{doc-class}/{segment}/<repo path>`
  with the repo's own bytes, so they are compared by hash.
- A GitHub alert renders as `<a ... data-attr-keyref="!NOTE">` with no label
  (Phase 56); each one left is counted.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

from docushift.verify import images as pictures
from docushift.verify import text as texts
from docushift.verify.fetch import Fetcher
from docushift.verify.toc import Comparison, Node, by_title

MENU = "nav.cmp-navigation"
ARTICLE = "main#section-topic div.topic-renderer__content"
PAGE_PATH = "main[data-page-path]"
TITLE = "main#section-topic h1#topic-title"


def version_url(base: str, locale: str, slug: str, doc_class: str, segment: str) -> str:
    """`https://host/us/en/{slug}/{doc-class}/{segment}.html` for `en-us`."""
    lang, _, country = locale.lower().partition("-")
    region = f"{country}/{lang}" if country else lang
    return f"{base.rstrip('/')}/{region}/{slug}/{doc_class}/{segment}.html"


def entry_urls(base: str, locale: str, slug: str, doc_class: str, segment: str, toc: Node) -> list[str]:
    """Where to read the version's menu from, best first.

    The version's own URL (`.../9-3-8.html`) is a landing stub with no menu and no
    article (2026-10-23). A **top-level** `toc.yml` row is served as its page stem,
    lowercased, under the version (`_templates/Home.md` -> `.../9-3-8/home.html`,
    the probe), so the first row's page is where the menu is read. The stub is the
    fallback.
    """
    version = version_url(base, locale, slug, doc_class, segment)
    first = next((row.key for row in toc.children if row.key), None)
    urls = []
    if first:
        stem = PurePosixPath(first.partition("#")[0]).stem.lower()
        urls.append(f"{version[: -len('.html')]}/{stem}.html")
    return [*urls, version]


def read_menu(html: str, page_url: str) -> Node | None:
    """The served menu as a tree of `Node(title, ref=absolute URL)`, or None."""
    soup = BeautifulSoup(html, "html.parser")
    nav = soup.select_one(MENU)
    if nav is None:
        return None
    group = nav.find("ul", class_="cmp-navigation__group")
    return Node("", None, _items(group, page_url)) if isinstance(group, Tag) else Node("")


def _items(group: Tag, page_url: str) -> list[Node]:
    out: list[Node] = []
    for li in group.find_all("li", class_="cmp-navigation__item", recursive=False):
        link = li.find("a", class_="cmp-navigation__item-link")
        title = " ".join(link.get_text(" ").split()) if isinstance(link, Tag) else ""
        if not title:
            span = li.find("span")
            title = " ".join(span.get_text(" ").split()) if isinstance(span, Tag) else ""
        href = urljoin(page_url, str(link.get("href"))) if isinstance(link, Tag) and link.get("href") else ""
        child = li.find("ul", class_="cmp-navigation__group")
        out.append(Node(title, None, _items(child, page_url) if isinstance(child, Tag) else [], ref=href))
    return out


def _served_path(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one(PAGE_PATH)
    return str(main.get("data-page-path") or "") if main is not None else ""


def is_page(fetched_html: str, url: str) -> bool:
    """Did the server send *this* page, not its home-page fallback?"""
    wanted = unquote(urlsplit(url).path)
    wanted = wanted[: -len(".html")] if wanted.endswith(".html") else wanted
    served = _served_path(fetched_html)
    return bool(served) and served.endswith(wanted)


@dataclass
class PageCheck:
    """What one published page looks like on staging."""

    key: str
    url: str
    status: str = "ok"            # ok | missing | unmatched
    text_percent: float = 100.0
    missing: list[str] = field(default_factory=list)
    callouts: int = 0
    broken_images: list[str] = field(default_factory=list)
    alt_dropped: list[str] = field(default_factory=list)


@dataclass
class VersionCheck:
    url: str
    reachable: bool = False
    menu: Comparison | None = None
    pages: dict[str, PageCheck] = field(default_factory=dict)


def check(fetcher: Fetcher, urls: list[str] | str, toc: Node, folder: Path) -> VersionCheck:
    """B1-B4 for one published version folder. `toc` is its `toc.yml`, keyed by repo path.

    `urls` are the entry points to try for the menu (`entry_urls`); the first one
    that is really served and carries a menu is used.
    """
    candidates = [urls] if isinstance(urls, str) else list(urls)
    result = VersionCheck(candidates[0] if candidates else "")
    menu = None
    for url in candidates:
        landing = fetcher.get(url)
        if landing.ok and is_page(landing.text, url):
            menu = read_menu(landing.text, url)
            if menu is not None and menu.children:
                result.url = url
                break
            menu = None
    if menu is None:
        return result
    result.reachable = True
    result.menu = by_title(toc, menu)

    for row, _ in toc.walk():
        if row.key is None:
            continue
        page = row.key.partition("#")[0]
        if page in result.pages:
            continue
        twin = result.menu.matched.get(id(row))
        href = twin.ref.partition("#")[0] if twin is not None else ""
        if not href:
            result.pages[page] = PageCheck(page, "", status="unmatched")
            continue
        result.pages[page] = _page(fetcher, page, href, folder)
    return result


def _page(fetcher: Fetcher, page: str, url: str, folder: Path) -> PageCheck:
    out = PageCheck(page, url)
    fetched = fetcher.get(url)
    if not fetched.ok or not is_page(fetched.text, url):
        out.status = "missing"
        return out
    soup = BeautifulSoup(fetched.text, "html.parser")
    article = soup.select_one(ARTICLE)
    local_path = folder / PurePosixPath(page)
    try:
        local_md = local_path.read_text(encoding="utf-8")
    except OSError:
        local_md = ""
    if article is None:
        out.status = "missing"
        return out

    out.callouts = len(article.select('[data-attr-keyref^="!"]'))
    # The page title is rendered above the article, outside it; the Markdown's
    # `# Title` is page text all the same.
    title = soup.select_one(TITLE)
    heading = [" ".join(title.get_text(" ").split())] if title is not None else []
    served = texts.Text([*heading, *texts.html_blocks(BeautifulSoup(str(article), "html.parser"))])
    cover = texts.coverage(texts.markdown_text(local_md), served)
    out.text_percent, out.missing = cover.percent, cover.missing

    local = pictures.markdown_images(local_md, local_path)
    marker = f"/{folder.parent.name}/{folder.name}/"  # .../{doc-class}/{segment}/
    served_by_rel: dict[str, Tag] = {}
    for img in article.find_all("img"):
        path = unquote(urlsplit(str(img.get("src") or "")).path)
        if marker in path:
            served_by_rel[path.split(marker, 1)[1]] = img
    for picture in local.pictures:
        if picture.path is None:
            continue
        try:
            rel = picture.path.relative_to(folder.resolve()).as_posix()
        except ValueError:
            continue
        img = served_by_rel.get(rel)
        if img is None:
            out.broken_images.append(f"{rel}: not on the served page")
            continue
        got = fetcher.get(urljoin(url, str(img.get("src"))))
        if not got.ok:
            out.broken_images.append(f"{rel}: HTTP {got.status}")
        elif picture.sha and hashlib.sha256(got.body).hexdigest() != picture.sha:
            out.broken_images.append(f"{rel}: served bytes differ from the repo")
        if picture.alt.strip() and not str(img.get("alt") or "").strip():
            out.alt_dropped.append(rel)
    return out
