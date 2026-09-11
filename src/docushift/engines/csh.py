"""Reading context-sensitive-help maps out of an extracted tree.

`design.md` §9.2 splits CSH three ways: the schema, the resolver and the writer
are engine-neutral and belong to Phase 5's `transforms/csh.py`; an engine
contributes only a **reader**, yielding `(identifier, link, anchor)`. This module
is the three readers, plus the shape test that locates their sources. Stage 4
needs exactly this much -- what help a package ships and how many identifiers
have to resolve -- and Phase 5 puts the resolver on top of it rather than
parsing the same files a second time.

Three sources, all read (`architecture.md` §5.4.4):

| Format           | Where                              | Identifier                     |
| :--------------- | :--------------------------------- | :----------------------------- |
| `flare_alias`    | `<book>/Data/Alias.xml`            | the `Map`'s `Name`             |
| `dita_head_js`   | `<doc-set>/static/head.js`         | the `suitehelp.contexts` key   |
| `webworks_topics`| `<book>/wwhdata/common/topics.js`  | the `if(P=="…")` case label    |

Two nearby files are deliberately **not** sources. `<doc-set>/ctx/` holds
redirect stubs generated *from* the map rather than holding it, and
`<book>/wwhdata/xml/files.xml` is a lossy XML twin of `topics.js` -- where the
two disagree it is the XML that is missing entries, and one observed book ships
no `files.xml` at all.

**An empty map is the normal case**, not a failure: 476 of 863 Flare alias files
(55%), 492 of 647 WebWorks `topics.js` (76%), 38 of 418 DITA `head.js` (9%).
Empty, zero-byte and unparseable sources are counted and skipped, never raised.
"""

import json
import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from xml.etree import ElementTree

# Identifiers are byte-exact strings and are never case-folded (§9.1):
# `GatewayInstances` and `gatewayInstances` are two different live help targets
# in TIBCO BC 7.4/7.5, and with `ResolvedId` discarded case is the only thing
# keeping them apart.

_DITA_CONTEXTS = re.compile(r"suitehelp\s*\.\s*contexts\s*=\s*(\{)", re.IGNORECASE)
_WEBWORKS_CASE = re.compile(
    r"""if\s*\(\s*P\s*==\s*(["'])(?P<id>.*?)\1\s*\)\s*C\s*=\s*(["'])(?P<target>.*?)\3""",
    re.IGNORECASE | re.DOTALL,
)
# 300 KB covers every source in the corpus with room to spare; the cap is here so
# that a mis-detected binary cannot be read into memory whole.
_MAX_SOURCE_BYTES = 300_000


class CshFormat(StrEnum):
    """The format token recorded per source in `state.db`."""

    FLARE_ALIAS = "flare_alias"
    DITA_HEAD_JS = "dita_head_js"
    WEBWORKS_TOPICS = "webworks_topics"


class CshStatus(StrEnum):
    """What happened when the source was read.

    `EMPTY` is a measurement, not a defect -- it is the majority of the corpus.
    `UNPARSEABLE` and `UNREADABLE` are the two that earn a triage line, because
    "help we could not read" and "no help" are different facts and only one of
    them is acceptable to discover after publishing.
    """

    OK = "ok"
    EMPTY = "empty"
    UNPARSEABLE = "unparseable"
    UNREADABLE = "unreadable"


@dataclass
class CshEntry:
    """One help identifier and where it points, before any resolution."""

    identifier: str
    link: str
    anchor: str = ""


@dataclass
class CshSource:
    """One located help map: what it is, and what parsed out of it."""

    path: Path
    fmt: CshFormat
    status: CshStatus = CshStatus.EMPTY
    entries: list[CshEntry] = field(default_factory=list)
    # The output root that owns it, relative to the extracted tree. Filled in by
    # the caller, which is the only party holding the root list.
    doc_set: str = ""

    @property
    def count(self) -> int:
        return len(self.entries)


def csh_format_of(path: Path) -> CshFormat | None:
    """Is this file a CSH source, judged by its name *and* its parent directory?

    By shape rather than by position under an output root: 153 Flare alias files
    sit inside a nested root, and a doc-set is not always a top-level folder. The
    parent test is what keeps a stray `head.js` in a script directory out.
    """
    name = path.name.lower()
    parts = [part.lower() for part in path.parts]
    if name == "alias.xml" and len(parts) >= 2 and parts[-2] == "data":
        return CshFormat.FLARE_ALIAS
    if name == "head.js" and len(parts) >= 2 and parts[-2] == "static":
        return CshFormat.DITA_HEAD_JS
    if name == "topics.js" and len(parts) >= 3 and parts[-3:-1] == ["wwhdata", "common"]:
        return CshFormat.WEBWORKS_TOPICS
    return None


def _read(path: Path) -> str | None:
    try:
        with path.open("rb") as handle:
            raw = handle.read(_MAX_SOURCE_BYTES)
    except OSError:
        return None
    return raw.decode("utf-8", errors="replace")


def _split_fragment(link: str) -> tuple[str, str]:
    """`config/Getting_Started.htm#adb.palette` -> path and anchor.

    Applied to every format rather than special-cased: 3% of Flare links carry a
    fragment and 43% of WebWorks ones do, and the shape is identical.
    """
    path, _, anchor = link.partition("#")
    return path, anchor


def _read_flare(text: str) -> tuple[CshStatus, list[CshEntry]]:
    """`<Map Name="TOPIC_ID" Link="path.htm" ResolvedId="1000"/>`.

    `ResolvedId` is parsed and discarded (§9.1): it is not unique even inside one
    file -- 29 of 196 files reuse an id for a *different* topic -- so it cannot
    address a page. `Name` is, in 0 of 196 files, ambiguous.
    """
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        return CshStatus.UNPARSEABLE, []
    entries = []
    for element in root.iter("Map"):
        identifier = element.get("Name")
        if not identifier:
            continue
        link, anchor = _split_fragment(element.get("Link", ""))
        entries.append(CshEntry(identifier, link, anchor))
    return (CshStatus.OK if entries else CshStatus.EMPTY), entries


def _read_dita(text: str) -> tuple[CshStatus, list[CshEntry]]:
    """`suitehelp.contexts={"id":"GUID-….html", …}` -- one flat object.

    Located rather than executed, and the braces are matched by scanning so that
    the rest of a 200 KB `head.js` is never handed to the JSON parser.
    """
    match = _DITA_CONTEXTS.search(text)
    if match is None:
        return CshStatus.EMPTY, []
    body = _extract_object(text, match.start(1))
    if body is None:
        return CshStatus.UNPARSEABLE, []
    try:
        contexts = json.loads(body)
    except ValueError:
        return CshStatus.UNPARSEABLE, []
    if not isinstance(contexts, dict):
        return CshStatus.UNPARSEABLE, []
    entries = []
    for identifier, target in contexts.items():
        if not identifier or not isinstance(target, str):
            continue
        link, anchor = _split_fragment(target)
        entries.append(CshEntry(identifier, link, anchor))
    return (CshStatus.OK if entries else CshStatus.EMPTY), entries


def _extract_object(text: str, start: int) -> str | None:
    """The `{…}` beginning at `start`, brace-counted with string awareness."""
    depth = 0
    quote = ""
    index = start
    while index < len(text):
        char = text[index]
        if quote:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
        index += 1
    return None


def _read_webworks(text: str) -> tuple[CshStatus, list[CshEntry]]:
    """The generated `if(P=="<id>")C="<file>[#<anchor>]";` dispatch chain.

    492 of 647 files (76%) return `null` unconditionally and produce no cases at
    all -- the WebWorks equivalent of an empty `<CatapultAliasFile />`. A file
    that does not even name the function is a different matter and is
    unparseable rather than empty.
    """
    entries = [
        CshEntry(match.group("id"), *_split_fragment(match.group("target")))
        for match in _WEBWORKS_CASE.finditer(text)
        if match.group("id")
    ]
    if entries:
        return CshStatus.OK, entries
    if "WWHBookData_MatchTopic" in text:
        return CshStatus.EMPTY, []
    return CshStatus.UNPARSEABLE, []


_READERS = {
    CshFormat.FLARE_ALIAS: _read_flare,
    CshFormat.DITA_HEAD_JS: _read_dita,
    CshFormat.WEBWORKS_TOPICS: _read_webworks,
}


def read_csh_source(path: Path, fmt: CshFormat) -> CshSource:
    """Reads one located source. **Never raises** -- a bad file is a status."""
    source = CshSource(path=path, fmt=fmt)
    text = _read(path)
    if text is None:
        source.status = CshStatus.UNREADABLE
        return source
    if not text.strip():
        # Zero-byte alias files are 31 of 863 in the corpus and are ordinary.
        source.status = CshStatus.EMPTY
        return source
    source.status, source.entries = _READERS[fmt](text)
    return source
