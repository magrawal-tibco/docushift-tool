"""Links measured against what git holds, not against the disk (Phase 83, DOCOPS-374).

Every publish repo has `core.ignorecase=true`, so a path tracked as
`Resources/Images/x.png` keeps that spelling in the index when the disk now says
`resources/images/x.png`, and a new file under that folder takes the folder's index
spelling. `git status` stays clean, the disk resolves the link, `validate`'s
case-exact walk of the disk passes, and AEM -- which serves what was committed --
shows a placeholder. 21,458 links on 17 Nov, in 149 versions.

So the question here is asked of git's listing (`git ls-tree -r <ref>`, or the
index when no ref is given), never of the disk. The extraction is the measurement
script's (`C:/tmp/case_audit/audit.py`), so a census reads what the table in
planning.md Phase 83 counted: page links, `![]()`, `<img src>` and other local
files in page bodies, `toc.yml` `url:` rows and `301.yml` targets. A target found in
no case at all is someone else's finding (`LINK_BROKEN`, the 3,781 missing rows),
not this one's.

Shared by repair R004's census and apply and by `validate`'s
`LINK_CASE_UNCOMMITTED`, so the three cannot disagree on what a link is.
"""

from __future__ import annotations

import posixpath
import re
import subprocess
from collections import defaultdict
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

MD_LINK = re.compile(r"\]\(\s*<?([^)\s>]+)")
HTML_ATTR = re.compile(r"""\b(?:src|href)\s*=\s*["']([^"']+)["']""", re.I)
YML_URL = re.compile(r"""^\s*-?\s*url:\s*["']?([^"'\s]+)""")
R301 = re.compile(r"""^\s*"[^"]*"\s*:\s*"([^"]+)\"""")
SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:|^//|^#|^\{")
# What `git grep` pre-selects; `targets` then reads each line exactly.
GREP = r"\]\(|src=|href=|url:|^\""
SCANNED = ("*.md", "*toc.yml", "*301.yml")


def kind_of(path: str) -> str | None:
    """`md`, `toc` or `301` for a file whose links are read; `None` otherwise."""
    lower = path.lower()
    if lower.endswith(".md"):
        return "md"
    if lower.endswith("301.yml"):
        return "301"
    if lower.endswith("toc.yml"):
        return "toc"
    return None


@dataclass(frozen=True)
class Target:
    """One link target on one line: as written, and resolved from the repo root."""

    file: str
    line: int
    source: str  # md, html, toc, 301
    raw: str  # the path part as written: no fragment, no query, not unquoted
    resolved: str


def targets(file: str, line: int, text: str) -> list[Target]:
    """The local targets on one line of `file` (a repo-relative POSIX path)."""
    kind = kind_of(file)
    if kind == "md":
        found = [("md", m) for m in MD_LINK.findall(text)] + [("html", m) for m in HTML_ATTR.findall(text)]
    elif kind == "toc":
        found = [("toc", m) for m in YML_URL.findall(text)]
    elif kind == "301":
        found = [("301", m) for m in R301.findall(text)]
    else:
        return []
    out = []
    for source, written in found:
        if SCHEME.match(written):
            continue
        raw = written.split("#")[0].split("?")[0]
        path = unquote(raw)
        if not path:
            continue
        if path.startswith("/"):
            resolved = posixpath.normpath(path.lstrip("/"))
        else:
            resolved = posixpath.normpath(posixpath.join(posixpath.dirname(file), path))
        if resolved.startswith("..") or resolved in (".", ""):
            continue
        out.append(Target(file, line, source, raw, resolved))
    return out


class Committed:
    """A repo's committed paths: exact, and folded for the case-only lookup."""

    def __init__(self, files: Iterable[str]) -> None:
        self.exact = set(files)
        self.dirs: set[str] = set()
        for name in self.exact:
            parent = posixpath.dirname(name)
            while parent and parent not in self.dirs:
                self.dirs.add(parent)
                parent = posixpath.dirname(parent)
        self._files: dict[str, list[str]] = defaultdict(list)
        for name in self.exact:
            self._files[name.lower()].append(name)
        self._dirs: dict[str, list[str]] = defaultdict(list)
        for name in self.dirs:
            self._dirs[name.lower()].append(name)

    def respelled(self, path: str) -> bool:
        """Whether the file `path` is committed, but only in another case."""
        return path not in self.exact and path.lower() in self._files

    def case_only(self, resolved: str) -> str | None:
        """The committed spelling when `resolved` is held only in another case.

        `None` when it is held exactly, or in no case at all. A link to a folder
        counts too (the audit's `(dir)` rows), with the folder's committed spelling.
        """
        if resolved in self.exact or resolved in self.dirs:
            return None
        found = self._files.get(resolved.lower()) or self._dirs.get(resolved.lower())
        return sorted(found)[0] if found else None


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, timeout=600)


def listing(repo: Path, ref: str | None = None) -> list[str]:
    """Every committed path in `repo` at `ref`, or in its index when `ref` is None."""
    args = ["ls-tree", "-r", "--name-only", "-z", ref] if ref else ["ls-files", "-z"]
    done = _git(repo, *args)
    if done.returncode != 0:
        return []
    return [p for p in done.stdout.decode("utf-8", "replace").split("\0") if p]


def committed(repo: Path, ref: str | None = None) -> Committed:
    """`repo`'s paths, with its `-resources` sibling's, as the audit counted them."""
    files = listing(repo, ref)
    sibling = repo.with_name(repo.name + "-resources")
    if not repo.name.endswith("-resources") and (sibling / ".git").exists():
        files += listing(sibling, ref)
    return Committed(files)


def grep(repo: Path, ref: str | None = None, paths: Sequence[str] = ()) -> Iterator[tuple[str, int, str]]:
    """`(file, line, text)` for every candidate line, read from git, not the disk."""
    specs = [f"{p.rstrip('/')}/{glob}" for p in paths for glob in SCANNED] if paths else list(SCANNED)
    # `--cached` is an option, so it goes before the pattern; a ref after it.
    options, refs = ([], [ref]) if ref else (["--cached"], [])
    done = _git(repo, "grep", "-z", "-n", "-I", *options, "-E", GREP, *refs, "--", *specs)
    if done.returncode not in (0, 1):
        return
    prefix = len(ref) + 1 if ref else 0
    for raw in done.stdout.decode("utf-8", "replace").splitlines():
        try:
            path, number, text = raw.split("\0", 2)
        except ValueError:
            continue
        if number.isdigit():
            yield path[prefix:], int(number), text.rstrip("\r")


@dataclass(frozen=True)
class CaseRow:
    """A target git holds only in another case."""

    target: Target
    real: str


def case_rows(repo: Path, ref: str | None = None, paths: Sequence[str] = (),
              held: Committed | None = None) -> list[CaseRow]:
    """Every target in `repo` (or under `paths`) that resolves only case-insensitively."""
    held = held if held is not None else committed(repo, ref)
    rows = []
    for file, number, text in grep(repo, ref, paths):
        for target in targets(file, number, text):
            real = held.case_only(target.resolved)
            if real is not None:
                rows.append(CaseRow(target, real))
    return rows


def key_of(path: str) -> tuple[str, str]:
    """`(product folder, segment)` from `{locale}/{folder}/{doc-class}/{segment}/...`."""
    parts = path.split("/")
    return (parts[1], parts[3]) if len(parts) > 4 else (parts[1] if len(parts) > 1 else "", "")


def respelled(row: CaseRow) -> str:
    """`row`'s target as written, each segment respelled as git holds it.

    Segment by segment rather than `relpath`, so the link keeps its form: `./`,
    `../` and a leading `/` stay where the writer put them. A segment carrying a
    `%`-escape is left as written; its unescaped form is compared, never rebuilt.
    """
    raw, real = row.target.raw, row.real.split("/")
    stack = [] if raw.startswith("/") else [p for p in posixpath.dirname(row.target.file).split("/") if p]
    out = []
    for segment in raw.split("/"):
        if segment in ("", "."):
            out.append(segment)
            continue
        if segment == "..":
            if stack:
                stack.pop()
            out.append(segment)
            continue
        stack.append(segment)
        index = len(stack) - 1
        wanted = real[index] if index < len(real) else segment
        same = unquote(segment).lower() == wanted.lower()
        out.append(wanted if same and "%" not in segment else segment)
    return "/".join(out)
