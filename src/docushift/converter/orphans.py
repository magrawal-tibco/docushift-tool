"""Phase 43: orphan topics leave the navigation and move to `unfiled/`.

A topic in no source TOC entry may be one its authors meant to hide, so the tool
must not add it to the navigation or merge it into another page: both change the
content of the docset (the user's rule, 2026-10-06). The engines still collect
such topics under an "Unfiled" node, because that is where they count them
(`TOC_ORPHAN`). This pass then takes the node out of `toc.yml`, deletes its
generated `unfiled.md`, and moves each orphan to `unfiled/<its path>`.

**A pass over a written tree, not an engine change.** `convert` runs it on its
staging tree before the swap, and `convert --reshelve-orphans` runs it on output
already written. It needs no source file, so the ~160 versions that are no longer
unpacked are fixed without a re-download.

What follows each move:

- **Links.** Every page's references to a moved topic, and a moved topic's own
  relative references, are re-pathed, so the tree stays consistent. AEM does not
  publish `unfiled/`, so a link from a listed page into an orphan breaks there;
  the user judged all sampled ones linked by mistake and let them break.
- **`csh.yml`.** Retargeted, never dropped: an identifier may move and may never
  disappear (§9.6).
- **`301.yml`.** Rows into an orphan are dropped. A redirect to a page that is
  not published only trades one 404 for another.
- **A record of the links that break.** `write_inbound` lists every link from a
  listed page into `unfiled/` in `unfiled/inbound-links.csv`, so the authors can
  decide each one. `reframe` calls it again for the merged tree, whose linking
  pages differ, and `validate` reports the same links as `LINK_TO_UNFILED`.

Running it twice changes nothing: the second run finds no Unfiled node.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from docushift import origins
from docushift.transforms import csh as csh_transform
from docushift.transforms import fragments, links
from docushift.utils import textfile
from docushift.utils.csvio import write_rows
from docushift.utils.longpath import long_path, walk_files
from docushift.utils.naming import UNFILED, is_unfiled

#: The label the four engines give the orphan node (`engines/*.py`).
LABEL = "Unfiled"

#: The list of links into `unfiled/`, version-relative, inside the folder itself.
INBOUND = f"{UNFILED}/inbound-links.csv"
INBOUND_COLUMNS = ("page", "line", "link_text", "orphan", "orphan_title")

_TOC = "toc.yml"
_FRONTMATTER = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*\n", re.DOTALL)
_CSH = "csh.yml"
_NODE = re.compile(r'^(?P<indent> *)- title: "Unfiled"\s*$')
_GENERATED = re.compile(r"\A---[ \t]*\n(?:(?!---).*\n)*?generated:[ \t]*true[ \t]*\n")
#: A generated page's list item: `- [label](target)`, the shape `navigation` writes.
_ITEM = re.compile(r"^[ \t]*[-*][ \t]+\[(?:[^\]\\]|\\.)*\]\((?P<target>[^)\s]*)\)[ \t]*\n?", re.MULTILINE)


@dataclass
class Reshelved:
    """What one pass did to one version tree."""

    # Version-relative old path -> new path, one per orphan moved.
    moved: dict[str, str] = field(default_factory=dict)
    # References re-pathed in pages, and `csh.yml` values retargeted.
    links: int = 0
    csh: int = 0
    # `301.yml` rows dropped because their target is now unfiled.
    redirects: int = 0
    # Whether an Unfiled node was taken out of `toc.yml`.
    removed: bool = False
    # Set when Unfiled nodes were found and deliberately left alone.
    kept: str = ""
    # Links in `unfiled/` pages repaired after an earlier pass missed them.
    repaired: int = 0


def reshelve(root: Path) -> Reshelved:
    """Moves the orphans of the version tree at `root` into `unfiled/`, in place."""
    result = Reshelved()
    _shelve(root, result)
    result.repaired = _repair_unfiled(root)
    return result


def _shelve(root: Path, result: Reshelved) -> None:
    toc_path = root / _TOC
    if not long_path(toc_path).is_file():
        return
    text = long_path(toc_path).read_text(encoding="utf-8")
    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError:
        return
    nodes = loaded.get("docs") if isinstance(loaded, dict) else None
    if not isinstance(nodes, list):
        return

    listed: set[PurePosixPath] = set()
    pages: set[PurePosixPath] = set()
    orphans: list[PurePosixPath] = []
    _walk(root, nodes, listed, pages, orphans)
    if not pages:
        return
    if not any(not _generated(root, path) for path in listed):
        # Every topic is "unfiled" only when the TOC itself was lost
        # (`TOC_UNREADABLE`). Shelving them all would publish an empty version,
        # so the tree is left as converted and the caller reports it.
        result.kept = "no topic outside the Unfiled node, so the TOC was not read"
        return

    moves: dict[PurePosixPath, PurePosixPath] = {}
    for orphan in orphans:
        if orphan in listed or orphan in moves or is_unfiled(orphan):
            continue
        if long_path(root / orphan).is_file():
            moves[orphan] = PurePosixPath(UNFILED) / orphan

    long_path(toc_path).write_text(textfile.lf(_without_nodes(text, pages)),
                                   encoding="utf-8", newline="\n")
    result.removed = True
    for page in pages:
        target = long_path(root / page)
        if target.is_file():
            target.unlink()

    result.links = _repath_pages(root, moves, pages)
    result.csh = _retarget_csh(root, moves)
    result.redirects = _drop_redirects(root, moves)
    for old in moves:
        _prune(root, old.parent)
    result.moved = {str(old): str(new) for old, new in moves.items()}
    write_inbound(root)


def inbound(root: Path) -> list[dict[str, str]]:
    """Every link from a page outside `unfiled/` to one inside it, in page order."""
    rows: list[dict[str, str]] = []
    titles: dict[PurePosixPath, str] = {}
    for relative, absolute in sorted(walk_files(root)):
        page = PurePosixPath(relative.as_posix())
        if page.suffix.lower() != ".md" or is_unfiled(page):
            continue
        body = absolute.read_text(encoding="utf-8", errors="replace")
        for line, raw, text in fragments.labelled(body):
            target = _resolved(page.parent, raw)
            if target is None or not is_unfiled(target) or links.escapes(target):
                continue
            if target not in titles:
                titles[target] = _title(root / target)
            rows.append({"page": str(page), "line": str(line), "link_text": text,
                         "orphan": str(target), "orphan_title": titles[target]})
    return rows


def write_inbound(root: Path) -> int:
    """Writes `unfiled/inbound-links.csv`, or removes it when no link remains."""
    path = long_path(root / INBOUND)
    rows = inbound(root) if long_path(root / UNFILED).is_dir() else []
    if rows:
        write_rows(path, INBOUND_COLUMNS, rows)
    elif path.is_file():
        path.unlink()
    return len(rows)


def _title(path: Path) -> str:
    """A page's frontmatter `title`, or empty."""
    try:
        with long_path(path).open(encoding="utf-8", errors="replace") as handle:
            head = textfile.lf(handle.read(4096))
    except OSError:
        return ""
    matter = _FRONTMATTER.match(head)
    try:
        loaded = yaml.safe_load(matter.group(1)) if matter else None
    except yaml.YAMLError:
        return ""
    title = loaded.get("title") if isinstance(loaded, dict) else None
    return title.strip() if isinstance(title, str) else ""


def _walk(root: Path, nodes: list[Any], listed: set[PurePosixPath], pages: set[PurePosixPath],
          orphans: list[PurePosixPath]) -> None:
    """Sorts every `toc.yml` url into listed pages and Unfiled pages and orphans."""
    for node in nodes:
        if not isinstance(node, dict):
            continue
        path = _path(node.get("url"))
        children = node.get("subfolderlist")
        children = children if isinstance(children, list) else []
        if (node.get("title") == LABEL and path is not None and children
                and _generated(root, path)):
            pages.add(path)
            _collect(children, orphans)
            continue
        if path is not None:
            listed.add(path)
        _walk(root, children, listed, pages, orphans)


def _collect(nodes: list[Any], found: list[PurePosixPath]) -> None:
    for node in nodes:
        if not isinstance(node, dict):
            continue
        path = _path(node.get("url"))
        if path is not None:
            found.append(path)
        children = node.get("subfolderlist")
        if isinstance(children, list):
            _collect(children, found)


def _path(url: Any) -> PurePosixPath | None:
    """A `toc.yml` url as a version-relative path, fragment dropped."""
    if not isinstance(url, str) or not url:
        return None
    reference = links.classify(url)
    return PurePosixPath(reference.path) if reference.resolvable else None


def _generated(root: Path, path: PurePosixPath) -> bool:
    """Is this page one `navigation` generated, with `generated: true`?"""
    try:
        with long_path(root / path).open(encoding="utf-8", errors="replace") as handle:
            head = handle.read(2048)
    except OSError:
        return False
    return bool(_GENERATED.match(textfile.lf(head)))


def _without_nodes(text: str, pages: set[PurePosixPath]) -> str:
    """`toc.yml` with every Unfiled node block cut out, the rest byte-for-byte."""
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    index = 0
    while index < len(lines):
        match = _NODE.match(lines[index].rstrip("\n"))
        if match and index + 1 < len(lines) and _url_line(lines[index + 1]) in pages:
            depth = len(match["indent"])
            index += 1
            while index < len(lines) and _indent(lines[index]) > depth:
                index += 1
            # A parent left with no child would read `subfolderlist: null`.
            if out and out[-1].strip() == "subfolderlist:" and (
                    index >= len(lines) or _indent(lines[index]) <= _indent(out[-1])):
                out.pop()
            continue
        out.append(lines[index])
        index += 1
    return "".join(out)


def _url_line(line: str) -> PurePosixPath | None:
    stripped = line.strip()
    if not stripped.startswith("url:"):
        return None
    try:
        loaded = yaml.safe_load(stripped)
    except yaml.YAMLError:
        return None
    return _path(loaded.get("url")) if isinstance(loaded, dict) else None


def _indent(line: str) -> int:
    if not line.strip():
        return 10**6  # a blank line belongs to whatever block it sits in
    return len(line) - len(line.lstrip(" "))


def _repath_pages(root: Path, moves: dict[PurePosixPath, PurePosixPath],
                  removed: set[PurePosixPath]) -> int:
    """Re-paths references in every page; moves each orphan's file. Returns the count."""
    total = 0
    for relative, absolute in list(walk_files(root)):
        if relative.suffix.lower() != ".md":
            continue
        old = PurePosixPath(relative.as_posix())
        if old in removed:
            continue
        new = moves.get(old, old)
        body = absolute.read_text(encoding="utf-8")
        updated = body
        if _GENERATED.match(textfile.lf(body[:2048])):
            updated = _ITEM.sub(
                lambda item, base=old.parent: "" if _resolved(base, item["target"]) in removed
                else item[0],
                updated,
            )

        def destination_for(raw: str, old: PurePosixPath = old,
                            new: PurePosixPath = new) -> str | None:
            reference = links.classify(raw)
            if not reference.resolvable:
                return None
            target = links.resolve(old.parent, reference.path)
            landed = moves.get(target, target)
            if landed == target and new == old:
                return None
            emitted = links.emit(links.relative_to(new, landed), reference.fragment)
            return f"{emitted}?{reference.query}" if reference.query else emitted

        updated, count = fragments.repath(updated, destination_for)
        total += count
        if new == old:
            if updated != body:
                textfile.write_text(absolute, updated)
            continue
        destination = long_path(root / new)
        destination.parent.mkdir(parents=True, exist_ok=True)
        textfile.write_text(destination, updated)
        absolute.unlink()
    return total


def _repair_unfiled(root: Path) -> int:
    """Re-paths what an earlier pass left pointing from a moved page's old path.

    Phase 44: the pass before it never saw the outer link of a linked image, so
    in a tree it reshelved that link still resolves from where the page was.
    Such a link is re-pathed to its target, or to the target's own `unfiled/`
    path when the target moved too. A link that resolves already, or from
    neither place, is left as written. Returns the count.
    """
    total = 0
    for relative, absolute in list(walk_files(root)):
        page = PurePosixPath(relative.as_posix())
        if page.suffix.lower() != ".md" or not is_unfiled(page):
            continue
        before = page.relative_to(UNFILED)

        def destination_for(raw: str, page: PurePosixPath = page,
                            before: PurePosixPath = before) -> str | None:
            reference = links.classify(raw)
            if not reference.resolvable or _exists(root, links.resolve(page.parent, reference.path)):
                return None
            target = links.resolve(before.parent, reference.path)
            for landed in (target, PurePosixPath(UNFILED) / target):
                if _exists(root, landed):
                    emitted = links.emit(links.relative_to(page, landed), reference.fragment)
                    return f"{emitted}?{reference.query}" if reference.query else emitted
            return None

        body = absolute.read_text(encoding="utf-8")
        updated, count = fragments.repath(body, destination_for)
        if count:
            textfile.write_text(absolute, updated)
            total += count
    return total


def _exists(root: Path, path: PurePosixPath) -> bool:
    return bool(path.parts) and path.parts[0] != ".." and long_path(root / path).is_file()


def _resolved(base: PurePosixPath, raw: str) -> PurePosixPath | None:
    reference = links.classify(raw)
    return links.resolve(base, reference.path) if reference.resolvable else None


def _moved_value(value: str, moves: dict[PurePosixPath, PurePosixPath]) -> str:
    path, separator, anchor = value.partition("#")
    landed = moves.get(PurePosixPath(path))
    return f"{landed}{separator}{anchor}" if landed is not None else value


def _retarget_csh(root: Path, moves: dict[PurePosixPath, PurePosixPath]) -> int:
    path = long_path(root / _CSH)
    if not moves or not path.is_file():
        return 0
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        return 0
    mapping = {str(key): str(value) for key, value in loaded.items()}
    retargeted = {key: _moved_value(value, moves) for key, value in mapping.items()}
    count = sum(1 for key in mapping if mapping[key] != retargeted[key])
    if count:
        csh_transform.write(path, retargeted)
    return count


def _drop_redirects(root: Path, moves: dict[PurePosixPath, PurePosixPath]) -> int:
    path = long_path(root / origins.ORIGINS)
    if not moves or not path.is_file():
        return 0
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    rows = loaded.get("redirects") if isinstance(loaded, dict) else None
    if not isinstance(rows, list):
        return 0
    kept = [row for row in rows
            if not (isinstance(row, dict)
                    and PurePosixPath(str(row.get("to") or "").partition("#")[0]) in moves)]
    if len(kept) != len(rows):
        origins.write(path, kept)
    return len(rows) - len(kept)


def _prune(root: Path, folder: PurePosixPath) -> None:
    """Removes `folder` and its parents while they are empty, never `root`."""
    while folder.parts:
        target = long_path(root / folder)
        try:
            if not target.is_dir() or any(os.scandir(target)):
                return
            target.rmdir()
        except OSError:
            return
        folder = folder.parent
