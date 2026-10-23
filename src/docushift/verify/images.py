"""Every picture on the old page is on the new one, matched by content.

Matched by SHA-256 of the file, never by name: the converter renames an image
whose published path would pass 260 characters (Phase 49) and AEM serves the
repo's own bytes (Phase 55's probe), so a name is the one thing that may change
and the bytes are the one thing that may not.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

from bs4 import Tag

SKIN_DIRECTORIES = frozenset({"skins"})

_MD_IMAGE = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<src><[^>]*>|[^)\s]+)(?:\s+\"[^\"]*\")?\)")
_HTML_IMG = re.compile(r"<img\b[^>]*\bsrc\s*=\s*[\"'](?P<src>[^\"']+)[\"'][^>]*>", re.IGNORECASE)
_HTML_ALT = re.compile(r"\balt\s*=\s*[\"'](?P<alt>[^\"']*)[\"']", re.IGNORECASE)


def digest(path: Path) -> str | None:
    """The file's SHA-256, or None when it cannot be read."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _local(src: str, page: Path) -> Path | None:
    """A relative `src` resolved against `page`; None for a URL or a data URI."""
    parts = urlsplit(src)
    if parts.scheme or parts.netloc or not parts.path:
        return None
    return (page.parent / unquote(parts.path)).resolve()


@dataclass
class Picture:
    src: str
    path: Path | None
    sha: str | None
    alt: str = ""


@dataclass
class PageImages:
    pictures: list[Picture] = field(default_factory=list)

    @property
    def hashes(self) -> set[str]:
        return {p.sha for p in self.pictures if p.sha}


def html_images(container: Tag, page: Path) -> PageImages:
    """The `<img>` inside a source page's content container, resolved and hashed.

    A reference to a file that is not in the package is not counted: there is no
    picture to have lost, and the converter reports the broken reference itself.
    """
    out = PageImages()
    seen: set[str] = set()
    for img in container.find_all("img"):
        src = str(img.get("src") or "")
        path = _local(src, page)
        # The help skin's own pictures -- a dropdown's transparent spacer, an
        # expand arrow -- are the old site's chrome, never content (Flare's
        # `Skins/`, a generated directory, `engines/flare.py`).
        if path is None or any(part.lower() in SKIN_DIRECTORIES for part in path.parts):
            continue
        sha = digest(path)
        if sha and sha not in seen:
            seen.add(sha)
            out.pictures.append(Picture(src, path, sha, str(img.get("alt") or "")))
    return out


def markdown_images(text: str, page: Path) -> PageImages:
    """The images a Markdown page references -- `![alt](src)` and raw `<img>`."""
    out = PageImages()
    found = [(m.group("src").strip("<>"), m.group("alt")) for m in _MD_IMAGE.finditer(text)]
    for m in _HTML_IMG.finditer(text):
        alt = _HTML_ALT.search(m.group(0))
        found.append((m.group("src"), alt.group("alt") if alt else ""))
    for src, alt in found:
        path = _local(src, page)
        out.pictures.append(Picture(src, path, digest(path) if path is not None else None, alt))
    return out


def missing(source: PageImages, target: PageImages) -> list[Picture]:
    """Source pictures whose bytes the target page does not reference."""
    held = target.hashes
    return [p for p in source.pictures if p.sha not in held]


def broken(target: PageImages) -> list[Picture]:
    """Target references whose file is not in the published tree."""
    return [p for p in target.pictures if p.path is not None and p.sha is None]


def published_path(src: str, base: str) -> PurePosixPath | None:
    """A staging image URL's path below `base` (the version's DAM folder), or None."""
    path = unquote(urlsplit(src).path)
    return PurePosixPath(path[len(base):].lstrip("/")) if path.startswith(base) else None
