"""Which generator produced an extracted tree -- `docs/design.md` §7.

Three passes, cheapest first: a directory listing, then a bounded read of the
HTML, then the `<meta name="generator">` tag. The rules and every figure quoted
in the comments below were measured against the whole `html-to-md` cache on
2026-09-08/09 -- 1,822 versions, of which 539 carry no HTML at all.

Runs at extract time rather than at conversion time, which is why it lives in
Phase 4b: §6.2's CSH inventory and §6.4's asset destinations are both
engine-specific, and they walk the tree the moment it is unpacked.

Two rules govern the answer (§7.3). **Never guess** -- a tree matching nothing
stays `auto`, because a wrong engine does not fail, it produces plausible-looking
and silently wrong Markdown. And **name what cannot be converted** -- `auto` is a
detector bug, while a named engine with no handler is a scoping decision for a
human, so they are different values rather than one.
"""

import re
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from docushift.models import SourceEngine

# Pass 2 and 3 read content, so they are bounded rather than exhaustive: the
# first 8 KB of at most 200 HTML files, breadth-first. `<head>`, the generator
# comment and the `MadCap:`/`DC.*` markers all live in the first few hundred
# bytes of a file, and breadth-first reaches one file from each guide folder
# before it reaches the second file of any. The bound is stated so that
# exhausting it can be a report line instead of a silent `auto`.
_MAX_CONTENT_FILES = 200
_CONTENT_BYTES = 8192

_HTML_SUFFIXES = frozenset({".html", ".htm"})

# `GUID-*.html`, the SDL SuiteHelp filename. 316 of the 371 DITA versions.
GUID_HTML_NAME = re.compile(r"^guid-.+\.html?$")

_META_TAG = re.compile(r"<meta\b[^>]*>", re.IGNORECASE)
_META_NAME = re.compile(r"""\bname\s*=\s*["']?([^"'\s>]+)""", re.IGNORECASE)
_META_CONTENT = re.compile(r"""\bcontent\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""", re.IGNORECASE)


@dataclass
class Detection:
    """One tree's answer, and enough of the evidence to argue with it."""

    engine: SourceEngine = SourceEngine.AUTO
    # 1, 2 or 3 -- which pass decided. 0 means nothing did.
    decided_by: int = 0
    # The raw `<meta name="generator">` string, kept whenever pass 3 saw one.
    # `other` alone is unactionable; the string is what a human triages from.
    generator_raw: str = ""
    # True when the content passes hit `_MAX_CONTENT_FILES` without deciding, so
    # "we looked at everything and found nothing" and "we stopped looking" stay
    # distinguishable in a report.
    sample_exhausted: bool = False
    html_files: int = 0
    # Immediate child directory -> its own engine. §7.3 step 4: one version's ZIP
    # commonly bundles nine sibling guide folders of a single Flare output, and
    # should a bundle ever genuinely mix generators the map makes it visible
    # rather than flattening it into one CSV cell.
    folders: dict[str, SourceEngine] = field(default_factory=dict)


@dataclass
class _Survey:
    """What one breadth-first pass over the tree saw."""

    markers: set[SourceEngine] = field(default_factory=set)
    html: list[Path] = field(default_factory=list)
    html_seen: int = 0


def _survey(tree: Path) -> _Survey:
    """Walks `tree` once, collecting pass-1 markers and a bounded HTML sample.

    Breadth-first and hand-rolled rather than `os.walk`, because the HTML sample
    has to be breadth-first to be representative of a multi-guide bundle, and
    doing both in one traversal means the tree is read from disk once.
    """
    found = _Survey()
    queue: deque[Path] = deque([tree])
    while queue:
        current = queue.popleft()
        try:
            entries = sorted(current.iterdir())
        except OSError:
            # An unreadable directory is not a detection failure. Skip it and
            # decide on what the rest of the tree says.
            continue
        names = {entry.name.lower() for entry in entries}
        for entry in entries:
            name = entry.name.lower()
            if entry.is_dir():
                queue.append(entry)
                # `wwhdata/` is the WebWorks rule: 195 of 195 versions, zero
                # false positives and zero false negatives (§7.1). `wwhelp/`
                # reaches only 178 -- it stays for corroboration, not recall.
                if name in ("microcontent", "_globalpages"):
                    found.markers.add(SourceEngine.FLARE)
                elif name in ("wwhelp", "wwhdata"):
                    found.markers.add(SourceEngine.WEBWORKS)
                elif name == "static":
                    try:
                        inner = {child.name.lower() for child in entry.iterdir()}
                    except OSError:
                        inner = set()
                    if {"head.js", "body.js"} <= inner:
                        found.markers.add(SourceEngine.DITA)
                # `Skins/` and `Data/` are deliberately absent. Over 1,822
                # versions they are 91.4% and 88.0% precise and account for all
                # 94 of the seven-marker list's false positives, while removing
                # them costs no recall at all: `*.mcwebhelp` alone finds all 595
                # Flare versions and `csh.js` alone finds all 595 (§7.1).
                continue
            suffix = entry.suffix.lower()
            if suffix in (".mcwebhelp", ".mclog") or name == "csh.js":
                found.markers.add(SourceEngine.FLARE)
            elif name in ("snext.css", "snextchm.css"):
                found.markers.add(SourceEngine.R_HELP)
            elif suffix in _HTML_SUFFIXES:
                if GUID_HTML_NAME.match(name):
                    found.markers.add(SourceEngine.DITA)
                found.html_seen += 1
                if len(found.html) < _MAX_CONTENT_FILES:
                    found.html.append(entry)
        # `static/head.js` + `static/body.js` can also sit beside their siblings
        # when the tree *is* the static folder.
        if current.name.lower() == "static" and {"head.js", "body.js"} <= names:
            found.markers.add(SourceEngine.DITA)
    return found


# Pass 1's precedence. Only the first pair is measured: 19 versions carry Flare
# *and* WebWorks markers -- a Flare output with a WebWorks tree left beside it --
# and Flare wins. The rest are ordered for determinism; no corpus version
# collides across them.
_MARKER_PRECEDENCE = (
    SourceEngine.FLARE,
    SourceEngine.WEBWORKS,
    SourceEngine.DITA,
    SourceEngine.R_HELP,
)


def _pass_one(survey: _Survey) -> SourceEngine:
    for engine in _MARKER_PRECEDENCE:
        if engine in survey.markers:
            return engine
    return SourceEngine.AUTO


def _read_head(path: Path) -> str:
    """The first `_CONTENT_BYTES` of a file, lowercased, or "" if unreadable."""
    try:
        with path.open("rb") as handle:
            raw = handle.read(_CONTENT_BYTES)
    except OSError:
        return ""
    return raw.decode("utf-8", errors="replace").lower()


def _pass_two(text: str) -> SourceEngine | None:
    """Content signatures. The only means of identifying DocBook, whose flat HTML
    output has no distinctive layout at all.
    """
    if "madcap:" in text or "xmlns:madcap" in text:
        return SourceEngine.FLARE
    if "docbook xsl stylesheets" in text:
        return SourceEngine.DOCBOOK
    if "dita open toolkit" in text or "dita-ot" in text:
        return SourceEngine.DITA
    # Matched case-insensitively, and that is not incidental: SuiteHelp writes
    # `DC.Type` and the file-named flavour writes `DC.type`. A case-sensitive
    # match silently drops all 66 of the latter's versions -- it did exactly that
    # once during the survey and produced a confident, wrong correction of 371
    # down to 316 before the casing was spotted (§7.2).
    if any(marker in text for marker in ("dc.type", "dc.identifier", "dc.title")):
        return SourceEngine.DITA
    if 'class="rdname"' in text or 'class="rdtitle"' in text:
        return SourceEngine.R_HELP
    return None


def _generator(text: str) -> str:
    """The `<meta name="generator">` content, or "".

    Read from the already-lowercased head, so the returned string is lowercase
    too -- it is matched against, and stored for a human to read, never echoed
    back into a file.
    """
    for tag in _META_TAG.findall(text):
        name = _META_NAME.search(tag)
        if not name or name.group(1).strip("\"'") != "generator":
            continue
        content = _META_CONTENT.search(tag)
        if content:
            return (content.group(1) or content.group(2) or content.group(3) or "").strip()
    return ""


# Pass 3's long tail: 19 versions and ~7,200 files. None has a Stage 5 handler;
# they are recorded anyway, because "identified and unconvertible" is a scoping
# decision and `auto` is a bug (§7.3 step 2).
_GENERATOR_NAMES = (
    ("robohelp", SourceEngine.ROBOHELP),
    ("frontpage", SourceEngine.FRONTPAGE),
    ("help & manual", SourceEngine.HELP_AND_MANUAL),
    ("help and manual", SourceEngine.HELP_AND_MANUAL),
    ("mkdocs", SourceEngine.MKDOCS),
    ("docusaurus", SourceEngine.DOCUSAURUS),
    ("doxia", SourceEngine.DOXIA),
    # Corroboration only, and never evidence of absence: the WebWorks generator
    # tag names WebWorks or ePublisher in 3 of the 195 WebWorks versions -- 1.5%
    # recall (§7.1). Pass 1's `wwhdata/` is the WebWorks rule.
    ("webworks", SourceEngine.WEBWORKS),
    ("epublisher", SourceEngine.WEBWORKS),
    ("madcap", SourceEngine.FLARE),
)


def _pass_three(generator: str) -> SourceEngine:
    for needle, engine in _GENERATOR_NAMES:
        if needle in generator:
            return engine
    # A string we cannot map to a known name. `other` rather than `auto`: we know
    # it was generated, we just have no handler, and the raw value is kept.
    return SourceEngine.OTHER


def detect_tree(tree: Path) -> Detection:
    """Detects the engine of one directory, without descending into a folder map.

    The unit of detection: `detect_version` calls it once for the version and
    once per guide folder.
    """
    survey = _survey(tree)
    result = Detection(html_files=survey.html_seen)

    engine = _pass_one(survey)
    if engine is not SourceEngine.AUTO:
        result.engine = engine
        result.decided_by = 1
        # Pass 3 still runs below when pass 1 is silent; here we stop, because a
        # layout marker is the least ambiguous evidence there is and reading
        # 200 files to confirm it buys nothing.
        return result

    for path in survey.html:
        text = _read_head(path)
        if not text:
            continue
        signature = _pass_two(text)
        if signature is not None:
            result.engine = signature
            result.decided_by = 2
            return result
        generator = _generator(text)
        if generator:
            result.generator_raw = generator
            result.engine = _pass_three(generator)
            result.decided_by = 3
            return result

    result.sample_exhausted = survey.html_seen > len(survey.html)
    return result


def detect_version(tree: Path) -> Detection:
    """The version's engine, plus the per-guide-folder map (§7.3 step 4).

    The version-level answer is detected over the whole tree rather than voted
    for out of the folder answers, so a bundle whose markers sit at the top level
    -- and one whose markers sit inside nine sibling guide folders -- give the
    same answer. The map is recorded regardless of whether it is unanimous;
    finding out that it was not is the reason it exists.
    """
    result = detect_tree(tree)
    try:
        children = sorted(child for child in tree.iterdir() if child.is_dir())
    except OSError:
        children = []
    for child in children:
        folder = detect_tree(child)
        if folder.engine is not SourceEngine.AUTO:
            result.folders[child.name] = folder.engine
    return result
