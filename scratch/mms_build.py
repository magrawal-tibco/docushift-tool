"""Phase 84 (DOCOPS-381): Streaming's Model Management Server guide from its Markdown.

Per version, from the writers' release tag in `cache/downloads/ep-streaming-web/ep-streaming-web`:
export the guide, render the six Velocity templates, fit the pages to the help's
house style, place them as `mms/` in the version's output, add one top-level menu
entry (from `site.xml`) and one `301.yml` row per page. The OpenAPI page goes to
the resources repo beside the other API references.

Idempotent: re-run after any `convert` of Streaming 11.2.0 / 11.2.1 (convert rewrites
`toc.yml` and `301.yml` and does not know this guide).

    python scratch/mms_build.py [--version 11.2.1] [--resources <repo>] [--dry-run]
"""

import argparse
import html
import io
import re
import shutil
import subprocess
import sys
import tarfile
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from docushift.transforms import callouts, escapes  # noqa: E402
from docushift.validation import references  # noqa: E402

REPO = ROOT / "cache/downloads/ep-streaming-web/ep-streaming-web"
SITE = "documentation/public-documentation/src/site"
OUTPUT = ROOT / "output/en-us-tib-streaming/tibco-streaming"
OLD_SITE = ROOT.parent / "html-to-md/cache/pub/str"
RESOURCES = Path("C:/github/tibco-docs-aem/en-us-tib-streaming-userdocs-resources")
RES_PREFIX = "en-us-tib-streaming-userdocs-resources/en-us/tibco-streaming/api-references"
API_NAME = "mms-artifact-manager"
OPENAPI_REL = "reference/openapi/artifact-manager"
VERSIONS = ("11.2.0", "11.2.1")
MENU_TITLE = "Model Management Server"
MENU_AFTER = "Studio Reference"
MARK = "# Phase 84: Model Management Server guide (scratch/mms_build.py)"


def git(*args: str) -> bytes:
    return subprocess.run(["git", "-C", str(REPO), *args], check=True,
                          capture_output=True).stdout


def export(version: str) -> dict[str, bytes]:
    """Every file under the tag's `src/site`, keyed by its path below `src/site`."""
    data = git("archive", "--format=tar", f"sb/releases/{version}", SITE)
    files = {}
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        for m in tar.getmembers():
            if m.isfile():
                files[m.name[len(SITE) + 1:]] = tar.extractfile(m).read()
    return files


def pom_values(version: str) -> dict[str, str]:
    # The tag is the release, so the project version is the tag's; the installer's
    # comes from the root pom (`installer.version`).
    installer = re.findall(r"<installer\.version>([^<]+)<", git(
        "show", f"sb/releases/{version}:pom.xml").decode())
    return {"project.version": version, "installerVersion": installer[0]}


def render_velocity(text: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        text = text.replace("${" + key + "}", value)
    # `#[[ ... ]]#` is Velocity's unparsed-content block: its text, as written.
    return re.sub(r"#\[\[(.*?)\]\]#", r"\1", text, flags=re.S)


_PRE = re.compile(r"<pre>\s*<code(?:\s[^>]*)?>(.*?)</code>\s*</pre>", re.S)
_IMG = re.compile(r"<img\s+([^>]*?)/?>", re.S)
_FONT = re.compile(r"</?font\b[^>]*>", re.I)
_LINK = re.compile(r"(\]\()([^)\s]+)(\))")


def _fence(match: re.Match, indent: str) -> str:
    body = html.unescape(match.group(1)).strip("\n")
    fence = "````" if "```" in body else "```"
    lines = [fence, *body.split("\n"), fence]
    return "\n".join(indent + line if line else line for line in lines)


def pre_to_fences(text: str) -> str:
    out, pos = [], 0
    for m in _PRE.finditer(text):
        start = text.rfind("\n", 0, m.start()) + 1
        prefix = text[start:m.start()]
        indent = prefix if prefix.strip() == "" else ""
        lead = "" if indent or not prefix else "\n\n"
        out.append(text[pos:m.start()] + lead + _fence(m, indent if not lead else ""))
        pos = m.end()
    out.append(text[pos:])
    return "".join(out)


def img_to_markdown(text: str) -> str:
    def repl(m: re.Match) -> str:
        attrs = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
        return f"![{attrs.get('alt', '')}]({attrs['src']})" if "src" in attrs else m.group(0)
    return _IMG.sub(repl, text)


def fix_links(text: str, page: PurePosixPath, pages: set[str], version: str) -> str:
    dashed = version.replace(".", "-")

    def repl(m: re.Match) -> str:
        target = m.group(2)
        if re.match(r"[a-z]+:", target) or target.startswith("#"):
            return m.group(0)
        path, _, frag = target.partition("#")
        resolved = PurePosixPath(*_norm(page.parent / path))
        if str(resolved).startswith(OPENAPI_REL):
            return f"{m.group(1)}{RES_PREFIX}/{dashed}/{API_NAME}/index.html{m.group(3)}"
        if path.endswith(".html"):
            md = str(resolved)[:-5] + ".md"
            if md in pages:
                path = path[:-5] + ".md"
        return m.group(1) + path + ("#" + frag if frag else "") + m.group(3)
    return _LINK.sub(repl, text)


_FULL_LINK = re.compile(r"(!?)\[([^\]]*)\]\(([^)\s]+)\)")
DEAD: list[str] = []


def drop_dead_links(text: str, page: PurePosixPath, pages: set[str]) -> str:
    """A link to a page the guide never published becomes its text; a picture
    that was never published is dropped. Both are dead on the old site too."""
    def repl(m: re.Match) -> str:
        bang, label, target = m.groups()
        path = target.partition("#")[0]
        if not path or re.match(r"[a-z]+:", path) or path.startswith(RES_PREFIX):
            return m.group(0)
        resolved = "/".join(_norm(page.parent / path))
        if bang:
            if resolved.startswith("images/") and resolved not in IMAGES:
                DEAD.append(f"{page} picture {resolved}")
                return ""
            return m.group(0)
        if path.endswith(".md") and resolved not in pages:
            DEAD.append(f"{page} -> {resolved}")
            return label
        return m.group(0)
    return _FULL_LINK.sub(repl, text)


IMAGES: set[str] = set()


def _norm(p: PurePosixPath) -> list[str]:
    parts: list[str] = []
    for part in p.parts:
        if part == "..":
            parts.pop()
        elif part != ".":
            parts.append(part)
    return parts


def title_of(text: str) -> str:
    m = re.search(r"^#\s+(.+?)\s*#*\s*$", text, re.M)
    return html.unescape(m.group(1)).strip() if m else ""


_FENCE = re.compile(r"^\s*(```|~~~)")
_UNDERLINE = re.compile(r"^(=+|-+)\s*$")


def setext_to_atx(text: str) -> str:
    """`Title` over `=====` / `-----` becomes `# Title` / `## Title` (outside code).

    The heading rule the platform and `validate` read is ATX only, and the
    converter writes ATX. A `---` after a blank line stays a rule.
    """
    lines = text.split("\n")
    out: list[str] = []
    fenced = False
    for line in lines:
        if _FENCE.match(line):
            fenced = not fenced
        prev = out[-1] if out else ""
        if (not fenced and _UNDERLINE.match(line) and prev.strip()
                and not prev.lstrip().startswith(("#", "-", "*", "|", ">", "<", "`"))
                and not re.match(r"^\s*\d+\.", prev) and not prev.startswith("    ")):
            out[-1] = ("# " if line.startswith("=") else "## ") + prev.strip()
            continue
        out.append(line)
    return "\n".join(out)


def drop_comments(text: str) -> str:
    """Writers' `<!-- ... -->` notes, outside code: never shown, but links inside
    them are read by `validate` (and a dropped section's links are dead)."""
    parts = re.split(r"(?ms)(^\s*(?:```|~~~).*?^\s*(?:```|~~~)[^\n]*$|<pre>.*?</pre>)", text)
    return "".join(p if i % 2 else re.sub(r"(?s)<!--.*?-->\n?", "", p)
                   for i, p in enumerate(parts))


_ID = re.compile(r'<a\s+id="([^"]+)"\s*>\s*</a>')


def retarget_anchors(texts: dict[str, str]) -> tuple[dict[str, str], int, list[str]]:
    """Point every `#fragment` at a heading anchor, the only kind AEM serves.

    Doxia's pages link to `<a name>` markers; the platform builds anchors from heading
    text alone (`validation/references.py` `anchors`). A marker's fragment becomes the
    anchor of the first heading after it; a fragment that differs from a heading
    anchor only in case takes the heading's spelling. Returns the texts, the number
    of links changed, and the fragments still unresolved.
    """
    heads = {p: set(references.headings(t)) for p, t in texts.items()}
    ids: dict[str, dict[str, str]] = {}
    for p, t in texts.items():
        by_line = sorted((line, a) for a, (line, _) in references.headings(t).items())
        marks = {}
        for m in _ID.finditer(t):
            line = t.count("\n", 0, m.start()) + 1
            nxt = next((a for ln, a in by_line if ln >= line), None)
            if nxt is not None and next(ln for ln, a in by_line if a == nxt) - line <= 3:
                marks[m.group(1)] = nxt
        ids[p] = marks
    changed, unresolved = 0, []

    def resolve(target: str, frag: str) -> str | None:
        if frag in heads.get(target, set()):
            return frag
        if frag in ids.get(target, {}):
            return ids[target][frag]
        folded = {a.lower(): a for a in heads.get(target, set())}
        return folded.get(frag.lower())

    out = {}
    for p, t in texts.items():
        page = PurePosixPath(p)

        def repl(m: re.Match) -> str:
            nonlocal changed
            path, _, frag = m.group(2).partition("#")
            if not frag or re.match(r"[a-z]+:", path) or not (path == "" or path.endswith(".md")):
                return m.group(0)
            target = p if path == "" else "/".join(_norm(page.parent / path))
            new = resolve(target, frag)
            if new is None:
                unresolved.append(f"{p} -> {path}#{frag}")
                return m.group(0)
            if new == frag:
                return m.group(0)
            changed += 1
            return f"{m.group(1)}{path}#{new}{m.group(3)}"
        out[p] = _LINK.sub(repl, t)
    return out, changed, unresolved


def page_text(raw: str, page: PurePosixPath, pages: set[str], version: str) -> str:
    text = raw.replace("\r\n", "\n")
    text = _FONT.sub("", text)
    text = drop_comments(text)
    text = setext_to_atx(text)
    # House style for a link target: `<a id>`, as the converter writes (`name` is
    # obsolete HTML that the anchor check and AEM do not read).
    text = re.sub(r'<a\s+name="([^"]+)"', r'<a id="\1"', text)
    text = pre_to_fences(text)
    text = img_to_markdown(text)
    text = fix_links(text, page, pages, version)
    text = drop_dead_links(text, page, pages)
    text = callouts.fix_markdown(text).text
    title = title_of(text).replace('"', '\\"')
    text = f'---\ntitle: "{title}"\n---\n\n' + text.lstrip("\n")
    return escapes.fix_markdown(text).text


def menu_rows(site_xml: bytes, md: dict[str, str]) -> tuple[list[str], list[str]]:
    """`toc.yml` rows for the guide (indent 2), and the pages `site.xml` leaves out.

    The menu follows `site.xml`. A page it leaves out (Doxia publishes it, reached
    only by links) is listed last under its folder's `index.md` entry, titled by its
    first heading, so no page is an orphan.
    """
    pages = set(md)
    root = ET.fromstring(site_xml)
    ns = {"": root.tag[1:].split("}")[0]} if root.tag.startswith("{") else {}
    body = root.find("body", ns)
    # A node: [title, url, children]
    tree: list = []
    by_url: dict[str, list] = {}

    def node(item: ET.Element) -> list | None:
        href = item.get("href", "")
        target = href[:-5] + ".md" if href.endswith(".html") else href
        if target not in pages:
            return None
        n = [item.get("name"), target, []]
        by_url[target] = n
        for kid in item.findall("item", ns):
            k = node(kid)
            if k:
                n[2].append(k)
        return n

    for menu in body.findall("menu", ns):
        for item in menu.findall("item", ns):
            if item.get("href") == "index.html":
                continue
            n = node(item)
            if n:
                tree.append(n)
    missing = sorted(pages - set(by_url) - {"index.md"})
    for page in missing:
        parent = by_url.get(str(PurePosixPath(page).parent / "index.md"))
        n = [title_of(setext_to_atx(md[page])) or PurePosixPath(page).stem, page, []]
        (parent[2] if parent else tree).append(n)

    rows = [f'  - title: "{MENU_TITLE}"', '    url: "mms/index.md"', "    subfolderlist:"]

    def render(n: list, depth: int) -> None:
        pad = "  " * depth
        rows.append(f'{pad}- title: "{n[0].replace(chr(34), chr(92) + chr(34))}"')
        rows.append(f'{pad}  url: "mms/{n[1]}"')
        if n[2]:
            rows.append(f"{pad}  subfolderlist:")
            for k in n[2]:
                render(k, depth + 2)

    for n in tree:
        render(n, 3)
    return rows, missing


def insert_menu(toc: str, rows: list[str]) -> str:
    toc = strip_marked(toc)
    lines = toc.rstrip("\n").split("\n")
    top = [i for i, line in enumerate(lines) if line.startswith("  - title: ")]
    after = next(i for i, n in enumerate(top) if lines[n] == f'  - title: "{MENU_AFTER}"')
    at = top[after + 1] if after + 1 < len(top) else len(lines)
    block = [MARK, *rows, MARK.replace("# ", "# end ", 1)]
    return "\n".join(lines[:at] + block + lines[at:]) + "\n"


def strip_marked(text: str) -> str:
    end = MARK.replace("# ", "# end ", 1)
    return re.sub(rf"(?m)^{re.escape(MARK)}\n.*?^{re.escape(end)}\n", "", text, flags=re.S)


def redirects(version: str, pages: list[str]) -> str:
    rows = [MARK]
    for page in pages:
        old = page[:-3] + ".html"
        rows += [f"- from: https://docs.tibco.com/pub/str/{version}/doc/html/mms/{old}",
                 f"  to: mms/{page}", "  status: 301"]
    rows.append(MARK.replace("# ", "# end ", 1))
    return "\n".join(rows) + "\n"


def build(version: str, resources: Path, dry: bool) -> None:
    files = export(version)
    values = pom_values(version)
    sources = {k[len("markdown/"):]: v for k, v in files.items() if k.startswith("markdown/")}
    md = {}
    for name, data in sources.items():
        if name.endswith(".md.vm"):
            md[name[:-3]] = render_velocity(data.decode("utf-8"), values)
        elif name.endswith(".md"):
            md[name] = data.decode("utf-8")
    pages = set(md)
    left = sorted(n for n, t in md.items() if re.search(r"\$\{(project\.|installer)", t))
    rows, missing = menu_rows(files["site.xml"], md)
    old = OLD_SITE / version / "html/mms"
    published = {str(p.relative_to(old).as_posix())[:-5] + ".md"
                 for p in old.rglob("*.html")} if old.is_dir() else set()
    print(f"== {version}: {len(md)} pages, {values}; templates unrendered: {left or 'none'}")
    print(f"   not in site.xml menu (listed under their folder): {missing or 'none'}")
    print(f"   published but no source: {sorted(published - pages) or 'none'}")
    print(f"   source but not published: {sorted(pages - published) or 'none'}")
    if dry:
        return
    dest = OUTPUT / version / "mms"
    if dest.exists():
        shutil.rmtree(dest)
    IMAGES.clear()
    IMAGES.update(n for n in sources if n.startswith("images/"))
    DEAD.clear()
    texts = {n: page_text(t, PurePosixPath(n), pages, version) for n, t in md.items()}
    print(f"   dead links made text / missing pictures dropped: {len(DEAD)}")
    for row in DEAD:
        print(f"     {row}")
    texts, retargeted, unresolved = retarget_anchors(texts)
    print(f"   links pointed at heading anchors: {retargeted}; unresolved: {len(unresolved)}")
    for row in unresolved:
        print(f"     {row}")
    for name, text in texts.items():
        out = dest / name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8", newline="\n")
    images = 0
    for name, data in sources.items():
        if name.startswith("images/") and not name.endswith(".plantuml"):
            out = dest / name
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
            images += 1
    toc = OUTPUT / version / "toc.yml"
    toc.write_text(insert_menu(toc.read_text(encoding="utf-8"), rows), encoding="utf-8", newline="\n")
    red = OUTPUT / version / "301.yml"
    red.write_text(strip_marked(red.read_text(encoding="utf-8")).rstrip("\n") + "\n"
                   + redirects(version, sorted(pages)), encoding="utf-8", newline="\n")
    api = resources / "en-us/tibco-streaming/api-references" / version.replace(".", "-") / API_NAME
    src = old / OPENAPI_REL
    if api.exists():
        shutil.rmtree(api)
    shutil.copytree(src, api)
    print(f"   wrote {len(md)} pages, {images} pictures, menu entry, {len(pages)} redirects; "
          f"OpenAPI page -> {api}")


USERDOCS = Path("C:/github/tibco-docs-aem/en-us-tib-streaming-userdocs")


def publish(version: str, repo: Path) -> None:
    """Place the built guide in the published repo without a full `sync`.

    A full sync of Streaming would re-copy every page from output/ and undo the
    repairs applied in the repo only (R002, 05f0c9f). This copies `mms/`, puts the
    marked menu block into the repo's `toc.yml` (identical to output's otherwise),
    and adds the redirects in the repo's served form (Phase 72).
    """
    dashed = version.replace(".", "-")
    built = OUTPUT / version
    dest = repo / "en-us/tibco-streaming/online-help" / dashed
    if (dest / "mms").exists():
        shutil.rmtree(dest / "mms")
    shutil.copytree(built / "mms", dest / "mms")
    block = re.search(rf"(?ms)^{re.escape(MARK)}\n.*?^{re.escape(MARK.replace('# ', '# end ', 1))}\n",
                      (built / "toc.yml").read_text(encoding="utf-8")).group(0)
    rows = [line for line in block.split("\n")[1:-2]]
    toc = dest / "toc.yml"
    toc.write_text(insert_menu(toc.read_text(encoding="utf-8"), rows), encoding="utf-8", newline="\n")
    pages = sorted(p.relative_to(dest / "mms").as_posix() for p in (dest / "mms").rglob("*.md"))
    served = [MARK] + [
        f'"https://docs.tibco.com/pub/str/{version}/doc/html/mms/{p[:-3]}.html": '
        f'"/en-us/tibco-streaming/online-help/{dashed}/mms/{p}"' for p in pages
    ] + [MARK.replace("# ", "# end ", 1)]
    red = dest / "301.yml"
    red.write_text(strip_marked(red.read_text(encoding="utf-8")).rstrip("\n") + "\n"
                   + "\n".join(served) + "\n", encoding="utf-8", newline="\n")
    print(f"   published {version}: {len(pages)} pages, menu entry, {len(pages)} redirects -> {dest}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", choices=VERSIONS, action="append")
    ap.add_argument("--resources", type=Path, default=RESOURCES)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--publish", action="store_true",
                    help="after building, place the guide in the userdocs repo (no commit)")
    a = ap.parse_args()
    for v in a.version or VERSIONS:
        build(v, a.resources, a.dry_run)
        if a.publish and not a.dry_run:
            publish(v, USERDOCS)


if __name__ == "__main__":
    main()
