"""Flare's runtime manifest and its TOC, which is JavaScript.

`architecture.md` §5.1.4. Three facts shape this module, all measured:

- **The TOC is declared, not discovered.** `Data/HelpSystem.xml` names it in its
  `Toc=` attribute. Globbing `Data/Tocs/*.js` and taking the first is wrong in all
  three corpus roots that ship two trees, because alphabetical order picks the
  smaller one every time.
- **It is an AMD module, and it is parsed rather than executed.** `define({...})`
  around a JavaScript object literal: single-quoted keys, `\\u0027` escapes,
  unquoted identifiers. The parser below reads that literal and nothing else -- no
  expressions, no calls, no `eval`, no JS engine. A file that is not a literal
  raises and the caller reports it.
- **The tree carries no titles.** `tree` is nested `{i,c,n}` integer ids; the
  `<Name>_Chunk<N>.js` payload maps *path* to `{i:[ids], t:[labels], b:[anchors]}`
  as **parallel arrays**. So a titled tree is an index inversion followed by a
  depth-first walk, and the `k`th id is labelled by the `k`th title -- reading
  `t[0]` for every id relabels 60 corpus nodes that legitimately carry a different
  label at each of their positions. 0 of 37,598 sampled entries are ragged, so a
  ragged one is news and is counted.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from docushift.transforms.links import is_topic

# Flare's sentinel for a node that has a label and no page. 36 of 37,598 sampled
# entries; they carry 172 node ids between them.
HEADLESS_KEY = "___"

_CHUNK_FILE = re.compile(r"_Chunk\d+\.js$", re.IGNORECASE)
_DEFINE = re.compile(r"\bdefine\s*\(")


@dataclass(frozen=True)
class Manifest:
    """What `Data/HelpSystem.xml` declares. Attributes only -- the skin is chrome."""

    toc: str = ""
    default_url: str = ""
    alias: str = ""

    @property
    def complete(self) -> bool:
        return bool(self.toc)


def read_manifest(root: Path) -> Manifest | None:
    """Reads `Data/HelpSystem.xml`, or None when it is absent or unparseable."""
    path = root / "Data" / "HelpSystem.xml"
    try:
        element = ElementTree.parse(path).getroot()
    except (OSError, ElementTree.ParseError):
        return None
    return Manifest(
        toc=_slashed(element.get("Toc", "")),
        default_url=_slashed(element.get("DefaultUrl", "")),
        alias=_slashed(element.get("Alias", "")),
    )


def _slashed(value: str) -> str:
    return value.replace("\\", "/").lstrip("/")


@dataclass(frozen=True)
class Entry:
    """One TOC position: a page, a label, and an optional bookmark.

    `path` is empty for a headless node -- the `'___'` sentinel, or the one stray
    `.flprj` key in the sample. `label` is kept either way, because a headless node
    is exactly the case where the label is all there is.
    """

    path: str = ""
    label: str = ""
    anchor: str = ""


@dataclass
class TocNode:
    entry: Entry
    children: list["TocNode"] = field(default_factory=list)


@dataclass
class Toc:
    """One parsed tree file, with the counts that make its failures visible."""

    name: str
    nodes: list[TocNode] = field(default_factory=list)
    # Tree ids with no payload record. 0 across 39,488 sampled nodes.
    unmatched: int = 0
    # Entries whose `i`/`t`/`b` arrays disagree in length. 0 in 37,598 sampled.
    ragged: int = 0

    def walk(self):
        stack = list(reversed(self.nodes))
        while stack:
            node = stack.pop()
            yield node
            stack.extend(reversed(node.children))


def tree_files(root: Path) -> list[Path]:
    """Every TOC *tree* file in `Data/Tocs`, chunk payloads excluded."""
    directory = root / "Data" / "Tocs"
    try:
        found = [
            child for child in directory.iterdir()
            if child.is_file()
            and child.suffix.lower() == ".js"
            and not _CHUNK_FILE.search(child.name)
        ]
    except OSError:
        return []
    return sorted(found)


def read_toc(path: Path) -> Toc:
    """Reads one tree file and its chunks into a titled tree.

    Raises nothing the caller cannot act on: a missing or malformed file comes
    back as an empty `Toc`, which the engine reports and then treats as "every
    topic is an orphan" rather than as a crash.
    """
    toc = Toc(name=path.stem)
    document = _read_define(path)
    if not isinstance(document, dict):
        return toc

    index, toc.ragged = _index(path, document)
    tree = document.get("tree")
    roots = _children(tree)
    toc.nodes = [node for node in (_node(child, index, toc) for child in roots) if node]
    return toc


def _index(path: Path, document: dict[str, Any]) -> tuple[dict[int, Entry], int]:
    """Inverts the chunk payloads into `id -> Entry`."""
    prefix = str(document.get("prefix") or f"{path.stem}_Chunk")
    try:
        chunks = max(1, int(document.get("numchunks", 1)))
    except (TypeError, ValueError):
        chunks = 1

    index: dict[int, Entry] = {}
    ragged = 0
    for number in range(chunks):
        payload = _read_define(path.parent / f"{prefix}{number}.js")
        if not isinstance(payload, dict):
            continue
        for key, record in payload.items():
            if not isinstance(record, dict):
                continue
            ids = [value for value in _listed(record.get("i")) if isinstance(value, int)]
            labels = _listed(record.get("t"))
            anchors = _listed(record.get("b"))
            if len(labels) < len(ids) or len(anchors) < len(ids):
                ragged += 1
            target = _target(key)
            for position, identifier in enumerate(ids):
                index[identifier] = Entry(
                    path=target,
                    label=str(labels[position]) if position < len(labels) else "",
                    anchor=str(anchors[position]).lstrip("#") if position < len(anchors) else "",
                )
    return index, ragged


def _target(key: str) -> str:
    """The key as a root-relative topic path, or `""` when it names no page."""
    path = str(key).replace("\\", "/").lstrip("/")
    if not path or path == HEADLESS_KEY or not is_topic(path):
        return ""
    return path


def _listed(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return [] if value is None else [value]


def _children(tree: Any) -> list[Any]:
    """The top-level nodes of `tree`, which the corpus writes two ways.

    Every sampled root wraps them in a childed, id-less node (`tree:{n:[...]}`),
    but a bare array is the same structure with the wrapper omitted, and reading
    only one of the two shapes would silently produce an empty navigation.
    """
    if isinstance(tree, list):
        return tree
    if isinstance(tree, dict):
        return _listed(tree.get("n")) if "i" not in tree else [tree]
    return []


def _node(raw: Any, index: dict[int, Entry], toc: Toc) -> TocNode | None:
    if not isinstance(raw, dict):
        return None
    identifier = raw.get("i")
    entry = index.get(identifier) if isinstance(identifier, int) else None
    if entry is None:
        toc.unmatched += 1
        entry = Entry()
    children = [node for node in (_node(child, index, toc) for child in _listed(raw.get("n"))) if node]
    return TocNode(entry=entry, children=children)


# -- the literal reader --------------------------------------------------------


def _read_define(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None
    return parse_define(text)


def parse_define(text: str) -> Any:
    """The object literal inside `define(...)`, or None if there is not one.

    Deliberately a parser and not a regular expression: the payload holds
    `'\\u0027'`-escaped apostrophes and paths containing braces, and it is
    deliberately not an evaluator -- these files ship with a runtime that could
    put anything in them.
    """
    match = _DEFINE.search(text)
    if match is None:
        return None
    try:
        return _Literal(text, match.end()).value()
    except (ValueError, RecursionError):
        # A truncated or hand-edited file, or a tree nested past the interpreter's
        # limit. Either way the caller's answer is the same -- an empty TOC and
        # every topic reported as an orphan -- and it must not be an exception:
        # one malformed `.js` would otherwise abort a 200-version batch.
        return None


_WORD = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
_NUMBER = re.compile(r"-?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?")
_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}


class _Literal:
    """A recursive-descent reader for the JavaScript subset these files use."""

    def __init__(self, text: str, position: int):
        self.text = text
        self.at = position

    def value(self) -> Any:
        self._space()
        char = self._peek()
        if char == "{":
            return self._object()
        if char == "[":
            return self._array()
        if char in "'\"":
            return self._string()
        word = _WORD.match(self.text, self.at)
        if word:
            self.at = word.end()
            return {"true": True, "false": False, "null": None, "undefined": None}.get(
                word.group(), word.group()
            )
        number = _NUMBER.match(self.text, self.at)
        if number:
            self.at = number.end()
            raw = number.group()
            return float(raw) if "." in raw or "e" in raw.lower() else int(raw)
        raise ValueError(f"not a literal at {self.at}")

    def _object(self) -> dict[str, Any]:
        self.at += 1
        result: dict[str, Any] = {}
        while True:
            self._space()
            if self._peek() == "}":
                self.at += 1
                return result
            key = self._key()
            self._space()
            self._expect(":")
            result[key] = self.value()
            self._space()
            if self._peek() == ",":
                self.at += 1
                continue
            self._expect("}")
            return result

    def _array(self) -> list[Any]:
        self.at += 1
        result: list[Any] = []
        while True:
            self._space()
            if self._peek() == "]":
                self.at += 1
                return result
            result.append(self.value())
            self._space()
            if self._peek() == ",":
                self.at += 1
                continue
            self._expect("]")
            return result

    def _key(self) -> str:
        char = self._peek()
        if char in "'\"":
            return self._string()
        word = _WORD.match(self.text, self.at)
        if word:
            self.at = word.end()
            return word.group()
        number = _NUMBER.match(self.text, self.at)
        if number:
            self.at = number.end()
            return number.group()
        raise ValueError(f"not a key at {self.at}")

    def _string(self) -> str:
        quote = self._take()
        out: list[str] = []
        while True:
            char = self._take()
            if char == quote:
                return "".join(out)
            if char != "\\":
                out.append(char)
                continue
            escape = self._take()
            if escape == "u":
                out.append(chr(int(self._slice(4), 16)))
            elif escape == "x":
                out.append(chr(int(self._slice(2), 16)))
            else:
                out.append(_ESCAPES.get(escape, escape))

    def _space(self) -> None:
        while self.at < len(self.text) and self.text[self.at].isspace():
            self.at += 1

    def _peek(self) -> str:
        return self.text[self.at] if self.at < len(self.text) else ""

    def _take(self) -> str:
        char = self._peek()
        if not char:
            raise ValueError("unterminated literal")
        self.at += 1
        return char

    def _slice(self, length: int) -> str:
        """`length` characters, or a `ValueError` -- never a short read.

        A `\\u` at the end of a truncated file would otherwise hand `int()` an
        empty string, and every read here has to fail the same way so that
        `parse_define` has one exception type to catch.
        """
        chunk = self.text[self.at:self.at + length]
        if len(chunk) < length:
            raise ValueError("truncated escape")
        self.at += length
        return chunk

    def _expect(self, char: str) -> None:
        if self._peek() != char:
            raise ValueError(f"expected {char!r} at {self.at}")
        self.at += 1
