"""WebWorks' runtime metadata: `books.xml`, `toc.js`, `files.js`, `title.js`.

`architecture.md` §5.3.3 and §5.3.4. Split out of `webworks.py` for the reason
`flare_toc.py` was split out of `flare.py`: the readers answer "what did the
generator record about this book" and the engine answers "what Markdown does a
topic become", and the two have no vocabulary in common. It is also the half that
can be pinned by a test without a DOM.

Four facts shape this module, all measured on 2026-09-09 and re-measured on
2026-09-11 against the `html-to-md` cache:

- **The TOC's nesting lives in a JavaScript variable, not in brackets.**
  `X = Y.fN(title, l)` makes the new node a child of `Y`'s node. So the file is
  read by scanning for calls and tracking receivers -- and it is *parsed*, never
  executed, the same rule Flare's `define({…})` chunks get.
- **`l` indexes `wwhdata/common/files.js` and not `wwhdata/files.htm`.** Ground
  truth over 646 books and 68,915 anchored entries: `files.js` resolves
  **68,915 (100.0000%)**, every one of them to a file that exists, while
  `files.htm` resolves **60,939 (88.43%)**, leaves 98 books resolving nothing at
  all, and is **never** the better of the two. This is the predecessor's central
  bug (§5.3.10). `files.htm` is read only for the 45 stripped books, and those
  books ship no `toc.js` either -- so nothing ever indexes into it and it serves
  purely as their topic list.
- **`<Book directory>` and `files.js` hrefs are percent-encoded.** 22 declarations
  are `directory="TIBCO%20Product%20Documentation%20and%20Support%20Services"`;
  decoding takes declared-book resolution from 580 to **602 of 602** across 157
  collections, with nothing left unresolved. One rule, two places.
- **The declared book order is authored order.** It is not alphabetical in 112 of
  157 collections, so sorting would scramble nearly three quarters of the corpus's
  navigation.
"""

import html as html_entities
import posixpath
import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree

from bs4 import XMLParsedAsHTMLWarning

# `charset=iso-8859-1` in a `<meta>`, or `encoding="…"` in an XML declaration.
# Both are ASCII by construction and both sit in the first few hundred bytes, so
# they are matched against the raw bytes before any decode is attempted.
_META_CHARSET = re.compile(rb"""charset\s*=\s*["']?\s*([\w.:+-]+)""", re.IGNORECASE)
_XML_ENCODING = re.compile(rb"""<\?xml[^>]*\bencoding\s*=\s*["']([\w.:+-]+)""", re.IGNORECASE)
_DECLARATION_WINDOW = 4096

# The JavaScript escapes these files actually use, plus the ones a generator could
# emit. `\uXXXX` and `\xXX` are handled separately because they consume digits.
_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}

_IDENTIFIER_TAIL = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*$")

# A comparison or a compound assignment, so that `if (A == B.fN(…))` is not read as
# an assignment to `A`. Nothing in the corpus writes one; the guard costs a lookup.
_NOT_ASSIGNMENT = frozenset("=!<>+-*/%&|^")

# `return "…";` -- the whole of `title.js` and `context.js`.
_RETURN = re.compile(r"""\breturn\s*(["'])(?P<value>.*?)\1""", re.DOTALL)

# `wwhdata/files.htm` hrefs are written relative to `wwhdata/`, so they climb out
# of it: `../admin.5.15.htm`. Resolved against that directory rather than against
# the book, which is the difference between 45 books indexed and 45 books empty.
_FILES_HTM_BASE = "wwhdata"


def read_text(path: Path, default: str = "utf-8") -> str | None:
    """Decodes one source file by its **declared** charset (§5.3.1).

    Of the 30,603 topics `files.js` lists corpus-wide, **every one declares a
    charset**: 30,307 `utf-8` and 294 `iso-8859-1`. 196 fail a strict UTF-8
    decode, and the declaration accounts for all of them. So the declaration is
    authoritative and it is never absent -- which is why there is no chardet-style
    guess here and no `errors="replace"` on the first attempt. The UTF-8 default
    covers only a file reached outside that index.

    Never raises: an unreadable file comes back as None, which every caller
    already reports as `CONTENT_MISSING`.
    """
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    head = raw[:_DECLARATION_WINDOW]
    match = _META_CHARSET.search(head) or _XML_ENCODING.search(head)
    declared = match.group(1).decode("ascii", "replace").lower() if match else default
    for encoding in (declared, default):
        try:
            return raw.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    # Declared wrong *and* not the default: the bytes are still the only copy of
    # the prose, so they are decoded lossily rather than dropped.
    return raw.decode(default, errors="replace")


# -- the JavaScript call scanner -----------------------------------------------


@dataclass(frozen=True)
class Call:
    """One `target = receiver.method(arguments…)`, with string arguments only."""

    receiver: str
    # The variable the result was assigned to, or `""` for a bare statement.
    target: str
    arguments: tuple[str, ...]


def calls(text: str, method: str) -> list[Call]:
    """Every `X.method("…", "…")` in `text`, in source order. Never executes.

    A scanner rather than a regular expression because the arguments are JS string
    literals with real escapes -- `\\u0027`, `\\"` -- and a pattern that reads them
    correctly is longer and less legible than the reader below. A call whose
    arguments are not all string literals is skipped rather than guessed at: these
    files ship with a runtime that could put an expression in one.
    """
    found: list[Call] = []
    marker = f".{method}"
    at = text.find(marker)
    while at >= 0:
        after = _space(text, at + len(marker))
        if text[after:after + 1] == "(":
            receiver, target = _receiver(text, at)
            arguments = _arguments(text, after + 1)
            if receiver and arguments is not None:
                found.append(Call(receiver=receiver, target=target, arguments=tuple(arguments)))
        at = text.find(marker, at + len(marker))
    return found


def _receiver(text: str, at: int) -> tuple[str, str]:
    """The identifier before the `.`, and the one assigned to, if any."""
    head = text[:at].rstrip()
    match = _IDENTIFIER_TAIL.search(head)
    if match is None:
        return "", ""
    receiver = match.group(0)
    head = head[: match.start()].rstrip()
    if not head.endswith("=") or head[-2:-1] in _NOT_ASSIGNMENT:
        return receiver, ""
    head = head[:-1].rstrip()
    match = _IDENTIFIER_TAIL.search(head)
    return receiver, match.group(0) if match is not None else ""


def _arguments(text: str, at: int) -> list[str] | None:
    """The comma-separated string literals up to `)`, or None if any is not one."""
    values: list[str] = []
    position = _space(text, at)
    if text[position:position + 1] == ")":
        return values
    while True:
        if text[position:position + 1] not in ("'", '"'):
            return None
        value, position = _string(text, position)
        if value is None:
            return None
        values.append(value)
        position = _space(text, position)
        char = text[position:position + 1]
        if char == ",":
            position = _space(text, position + 1)
            continue
        return values if char == ")" else None


def _string(text: str, at: int) -> tuple[str | None, int]:
    """One JS string literal starting at `at`. `(None, at)` if it is unterminated."""
    quote = text[at]
    out: list[str] = []
    position = at + 1
    while position < len(text):
        char = text[position]
        if char == quote:
            return "".join(out), position + 1
        if char == "\n":
            # A literal newline ends a JS string. A file truncated mid-literal is
            # the only way to reach this, and reading on would swallow the rest.
            return None, at
        if char != "\\":
            out.append(char)
            position += 1
            continue
        escape = text[position + 1: position + 2]
        if escape in ("u", "x"):
            width = 4 if escape == "u" else 2
            digits = text[position + 2: position + 2 + width]
            if len(digits) < width:
                return None, at
            try:
                out.append(chr(int(digits, 16)))
            except ValueError:
                out.append(digits)
            position += 2 + width
            continue
        if not escape:
            return None, at
        out.append(_ESCAPES.get(escape, escape))
        position += 2
    return None, at


def _space(text: str, at: int) -> int:
    while at < len(text) and text[at].isspace():
        at += 1
    return at


def _label(value: str) -> str:
    """A generator-written label as display text.

    A `files.js` title and its topic's `<title>` agree in 30,537 of 30,601 cases
    (§5.3.4). Unescaping and collapsing is what closes most of the other 64: they
    are `Prerequisites &amp; Dependencies` against `Prerequisites & Dependencies`,
    and `Chapter\\xa01 Introduction` against `Chapter\\xa01\\tIntroduction`.
    `str.split()` treats `\\xa0` as whitespace, so the `&nbsp;` padding these
    labels are written with goes with it.
    """
    return " ".join(html_entities.unescape(value).split())


# -- the file index (§5.3.4) ---------------------------------------------------


@dataclass(frozen=True)
class FileEntry:
    """One `P.fA("Title","href")`: a topic's authoritative title and its path."""

    title: str
    # Book-relative, percent-decoded, forward-slashed. The `l` index addresses
    # this list by position.
    href: str


def read_files(path: Path) -> list[FileEntry]:
    """`wwhdata/common/files.js` in declaration order -- the index `l` addresses.

    Percent-decoding is not optional; hrefs are written
    `fA("System Message Descriptions","error%20messages.4.001.htm")`. Decoded,
    all 30,603 entries name a file that exists and none still holds a `%`.

    No two entries share an href corpus-wide, so position is a sound identity and
    a later entry never quietly shadows an earlier one.
    """
    text = read_text(path)
    if text is None:
        return []
    entries: list[FileEntry] = []
    for call in calls(text, "fA"):
        if len(call.arguments) < 2:
            continue
        entries.append(FileEntry(title=_label(call.arguments[0]), href=_href(call.arguments[1])))
    return entries


def read_files_htm(path: Path) -> list[FileEntry]:
    """`wwhdata/files.htm` -- the topic list of the 45 books that ship nothing else.

    Those 45 have no `toc.js`, so this is not a substitute index that `l` points
    into; it is the only enumeration of their topics, and every one of them lands
    unfiled. Its hrefs are written relative to `wwhdata/` and climb out of it, so
    they are resolved against that directory and not the book root.

    Parsed with the shared walk's parser so the 45 books do not pull in a second
    one. Some of these files open with an XML declaration, which makes bs4 warn
    that an HTML parser is reading XML -- true and harmless here, since all that
    is wanted is the `<a href>` list, so the warning is kept off the console.
    """
    from docushift.transforms import markdown  # local: `markdown` imports no engine

    text = read_text(path)
    if text is None:
        return []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        soup = markdown.parse(text)
    entries: list[FileEntry] = []
    for anchor in soup.find_all("a", href=True):
        href = _href(str(anchor["href"]))
        if not href:
            continue
        resolved = posixpath.normpath(posixpath.join(_FILES_HTM_BASE, href)).lstrip("./")
        entries.append(FileEntry(title=_label(anchor.get_text(" ")), href=resolved))
    return entries


def _href(value: str) -> str:
    return unquote(value.strip()).replace("\\", "/").lstrip("/")


def read_return(path: Path) -> str:
    """The `return "…"` in `title.js` or `context.js`, or `""`.

    Both files are a one-line function around a single string, and both are read
    the same way -- the book's display name and the key its own popups name it by.
    """
    text = read_text(path)
    if text is None:
        return ""
    match = _RETURN.search(text)
    return _label(match.group("value")) if match is not None else ""


# -- the TOC (§5.3.4) ----------------------------------------------------------


@dataclass
class TocEntry:
    """One `fN` call: a label, an index into `files.js`, and an optional bookmark."""

    label: str
    # None where `l` is absent or not an integer -- 55 of 68,970 entries are
    # label-only. The node survives; only its page does not.
    index: int | None = None
    anchor: str = ""
    children: list["TocEntry"] = field(default_factory=list)

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()


def read_toc(path: Path) -> list[TocEntry]:
    """`wwhdata/js/toc.js` as a forest. Nesting comes from the receiver variable.

    **A forest and not a tree**: of the 645 books that ship one, 583 have more than
    one top-level node -- 391 have six or more -- 61 have a single root and 1 is
    empty. So the book itself is the node with children and no page that §6.2
    generates a landing page for. The tree is shallow: 68,970 entries reach depth
    3 at the deepest, and only 258 get there.

    The function's own parameter -- `P` in every corpus file -- is never assigned,
    so a call on an unknown receiver is a root. That is why the root variable is
    recovered rather than constanted: a generator that renamed the parameter would
    otherwise produce an empty TOC and 100% orphans, silently.
    """
    text = read_text(path)
    if text is None:
        return []
    roots: list[TocEntry] = []
    scope: dict[str, TocEntry] = {}
    for call in calls(text, "fN"):
        if not call.arguments:
            continue
        location = call.arguments[1] if len(call.arguments) > 1 else ""
        index, _, anchor = location.partition("#")
        entry = TocEntry(
            label=_label(call.arguments[0]),
            index=int(index) if index.strip().isdigit() else None,
            anchor=anchor.strip(),
        )
        parent = scope.get(call.receiver)
        (parent.children if parent is not None else roots).append(entry)
        if call.target:
            scope[call.target] = entry
    return roots


# -- the collection (§5.3.3) ---------------------------------------------------


@dataclass(frozen=True)
class BookRef:
    """One `<Book directory="…"/>`, percent-decoded, with its group."""

    directory: str
    group: str = ""
    encoding: str = ""


@dataclass
class Collection:
    """One `wwhelp/books.xml` that declares books other than itself."""

    name: str = ""
    books: list[BookRef] = field(default_factory=list)

    @property
    def groups(self) -> list[str]:
        """Distinct `BookGroup` names, in declared order.

        Only 14 of 157 collections declare more than one; the rest have a single
        group named after the collection itself. So the level is worth emitting
        only when there are two or more -- a tree with one child at every level is
        not navigation.
        """
        seen: list[str] = []
        for book in self.books:
            if book.group and book.group not in seen:
                seen.append(book.group)
        return seen


def read_books(path: Path) -> Collection | None:
    """Reads `wwhelp/books.xml`, or None when it is absent or unparseable.

    **Declared order is preserved**, which is what `ElementTree`'s document order
    gives for free and what sorting would destroy in 112 of 157 collections.
    `<Book directory="."/>` is the self-declaration every *book* ships and is
    dropped here, so a collection is exactly a file this function returns books
    for -- the discriminator §5.3.3 needed and the one `wwhelp/` cannot give.
    """
    try:
        root = ElementTree.parse(path).getroot()
    except (OSError, ElementTree.ParseError):
        return None
    collection = Collection(name=(root.get("name") or "").strip())
    _read_group(root, "", collection)
    return collection


def _read_group(element: ElementTree.Element, group: str, into: Collection) -> None:
    """One level of `books.xml`. Recursive: 2 collections nest their groups."""
    for child in element:
        tag = child.tag.rpartition("}")[2].lower()
        if tag == "bookgroup":
            _read_group(child, (child.get("name") or "").strip() or group, into)
            continue
        if tag != "book":
            continue
        directory = _href(child.get("directory") or "")
        if not directory or directory == ".":
            continue
        into.books.append(BookRef(
            directory=directory,
            group=group,
            encoding=(child.get("encoding") or "").strip(),
        ))


__all__ = [
    "BookRef",
    "Call",
    "Collection",
    "FileEntry",
    "TocEntry",
    "calls",
    "read_books",
    "read_files",
    "read_files_htm",
    "read_return",
    "read_text",
    "read_toc",
]
