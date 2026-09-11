"""Reference classification, normalization and emission.

`design.md` §6.4 step 3, points 1-3, plus the emission rule from step 4. Split out
from `assets.py` because links to *topics* and links to *assets* share every rule
up to the point where one becomes a `.md` path and the other becomes a copy: a
second implementation of "strip the fragment, percent-decode, fix the slashes"
would be a second set of answers to the same question.

Two rules here are corpus-measured rather than conventional:

- **Normalize in order: strip `#fragment` and `?query`, percent-decode, `\\` to
  `/`.** Skipping it reports 1,872 WebWorks references as missing that are not --
  1,224 percent-encoded and 648 backslash-separated (`architecture.md` §5.5.6).
- **Percent-encode on emit with a literal `%` escaped first.** 6,587 of 792,607
  corpus assets sit at a path that breaks a bare Markdown URL, and 104 filenames
  already contain a `%`; encoding in the wrong order produces a different filename.
"""

import posixpath
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath
from urllib.parse import quote, unquote

# `.htm` dominates Flare and WebWorks, `.html` DITA; `.xhtml` appears in neither
# but is what an XSLT-published tree emits, and mapping it costs one entry.
TOPIC_SUFFIXES = (".htm", ".html", ".xhtml")

# Anything with a scheme is external and is emitted unchanged. Matched as a real
# scheme (`a-z`, then letters/digits/`+-.`, then `:`) rather than by looking for
# `://`, so `mailto:` and `data:` are caught and a Windows-ish `C:` is not: a bare
# drive letter is one character and the pattern needs two.
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]+:")


class ReferenceKind(StrEnum):
    """What a raw `href`/`src` turned out to be (§6.4 step 3.1)."""

    RELATIVE = "relative"
    # http, https, ftp, mailto, data, javascript -- emitted unchanged, never copied.
    ABSOLUTE = "absolute"
    # Same-page `#foo`. Not an asset and not a document link.
    FRAGMENT = "fragment"
    # Server-absolute `/foo/bar`. Cannot be resolved inside an output root, so it
    # is treated as external rather than silently rooted at the tree.
    ROOTED = "rooted"
    EMPTY = "empty"


@dataclass(frozen=True)
class Reference:
    """A raw reference, classified and normalized."""

    raw: str
    kind: ReferenceKind
    # Percent-decoded, forward-slashed, fragment and query removed. Empty unless
    # `kind is RELATIVE`.
    path: str = ""
    fragment: str = ""
    query: str = ""

    @property
    def resolvable(self) -> bool:
        return self.kind is ReferenceKind.RELATIVE and bool(self.path)


def classify(raw: str) -> Reference:
    """Classifies and normalizes one raw reference. Never raises."""
    text = (raw or "").strip()
    if not text:
        return Reference(raw, ReferenceKind.EMPTY)
    if _SCHEME.match(text):
        return Reference(raw, ReferenceKind.ABSOLUTE)
    if text.startswith("//"):
        # Protocol-relative. External by any reading, and resolving it against a
        # directory would produce a path nobody meant.
        return Reference(raw, ReferenceKind.ABSOLUTE)

    body, fragment = _split(text, "#")
    body, query = _split(body, "?")
    if not body:
        return Reference(raw, ReferenceKind.FRAGMENT, fragment=fragment, query=query)

    # Decode *after* the split, so a `%23` inside a filename is not mistaken for
    # the fragment separator, and before the slash fix, so `%5C` becomes a `/`.
    body = unquote(body).replace("\\", "/")
    kind = ReferenceKind.ROOTED if body.startswith("/") else ReferenceKind.RELATIVE
    return Reference(raw, kind, path=body, fragment=unquote(fragment), query=query)


def _split(text: str, separator: str) -> tuple[str, str]:
    head, found, tail = text.partition(separator)
    return head, tail if found else ""


def resolve(base_dir: PurePosixPath, path: str) -> PurePosixPath:
    """Resolves a relative reference against the source topic's own directory.

    `.` and `..` are normalized textually, never against the filesystem: a `..`
    that climbs out of the output root has to *survive* as a leading `..` so
    §6.4 step 3.5's escape check can see it. `Path.resolve()` would consult the
    disk and hand back an absolute path with the escape already erased.
    """
    joined = posixpath.normpath(posixpath.join(str(base_dir), path))
    return PurePosixPath("" if joined == "." else joined)


def escapes(path: PurePosixPath) -> bool:
    """Does this resolved path leave the output root? (§6.4 step 3.5.)"""
    return str(path).startswith("..")


def is_topic(path: str) -> bool:
    return PurePosixPath(path).suffix.lower() in TOPIC_SUFFIXES


def to_markdown(path: PurePosixPath | str) -> PurePosixPath:
    """`Getting_Started.htm` -> `Getting_Started.md`. The suffix, nothing else.

    Deliberately not a slug: Flare mirrors its source tree precisely so that link
    rewriting is a suffix substitution, and renaming here would put the rename in
    two places (`architecture.md` §5.1.2).
    """
    target = PurePosixPath(path)
    if target.suffix.lower() in TOPIC_SUFFIXES:
        return target.with_suffix(".md")
    return target


def relative_to(source: PurePosixPath, target: PurePosixPath) -> str:
    """The path from the emitted topic to the emitted target, as Markdown wants it.

    From the *file*, so the topic's own directory is the base. A same-directory
    sibling comes back bare (`sibling.md`), which is what every renderer expects
    and what `./sibling.md` would only obscure.
    """
    base = str(source.parent) or "."
    return posixpath.relpath(str(target), base).replace("\\", "/")


def encode(path: str) -> str:
    """Percent-encodes a path for emission into Markdown.

    One `quote()` call, and the ordering rule §6.4 step 4 insists on falls out of
    it: `quote` reads the string once, left to right, so a literal `%` becomes
    `%25` before anything else can be appended after it. Doing this as successive
    `str.replace` calls is what produces `%2520` from a filename containing `%20`.
    """
    return quote(path, safe="/")


def emit(target: PurePosixPath | str, fragment: str = "") -> str:
    """The final URL for a Markdown link: encoded path, plus an encoded fragment."""
    url = encode(str(target))
    if fragment:
        url += "#" + quote(fragment, safe="")
    return url
