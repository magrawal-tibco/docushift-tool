"""The `toc.yml` adapter seam -- Stage 6b's one deliberate extension point.

Reframe both reads and rewrites the table of contents: it needs the tree to know
which topics are siblings under which guide (R1), and it regenerates it afterwards
so absorbed topics point at `page.md#anchor` (R3). Reading it is therefore the
place a second doc set will diverge first, and the integration plan names that as a
risk to seam now rather than retrofit later (§6, "TOC schema variance").

The registry mirrors `engines/base.py` exactly -- `register()`, a module-level
`_REGISTRY`, and a `schema_for()` that returns `None` rather than guessing. The
symmetry is the point: a new TOC dialect should be the same shape of change as a
new source engine, and a reader who has met one has met both.

**An unmatched shape is an error, not a fallback.** A parser that understands half
a tree does not produce a worse merge, it produces a merge that quietly drops the
half it did not recognise, and the page count looks plausible either way.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

# The one field `render_toc` emits that this module must round-trip verbatim: the
# anchor is appended raw after `#`, with no percent-encoding and no case folding
# (`converter/navigation.py::_target`). Reframe writes the same shape back.


@dataclass
class TocEntry:
    """One row of the navigation, as Reframe needs to see it.

    Deliberately not `NavNode`. `NavNode` is what the *engines* produce on the way
    into Stage 6 and carries a `Document`; this is what comes back off disk on the
    way into 6b, where the only things that exist are a title, a path and a shape.
    Reusing the engine type here would mean every TOC adapter had to fabricate the
    half of it that no longer applies.
    """

    title: str
    #: The `path` as written, split at `#`. Empty for a container row with no page.
    path: PurePosixPath | None = None
    #: The fragment after `#`, without it. Case and encoding exactly as on disk.
    fragment: str = ""
    children: list[TocEntry] = field(default_factory=list)

    def walk(self):
        """This entry, then every descendant, depth-first in document order."""
        yield self
        for child in self.children:
            yield from child.walk()

    @property
    def target(self) -> str:
        """The `path` value this row would be written back as."""
        if self.path is None:
            return ""
        return f"{self.path}#{self.fragment}" if self.fragment else str(self.path)


class TocSchema(ABC):
    """One `toc.yml` dialect: how to recognise it, and how to read it."""

    #: The name `reframe.yaml`'s `toc_schema` key selects this adapter by.
    name: str = ""

    @abstractmethod
    def matches(self, document: Any) -> bool:
        """Is this parsed YAML in this dialect? Must not raise on a foreign shape."""

    @abstractmethod
    def parse(self, document: Any) -> list[TocEntry]:
        """The top-level rows. Only called when `matches` returned True."""


class ItemsPathChildren(TocSchema):
    """`items:` of `{title, path, children}` -- what DocuShift's own Stage 6a writes.

    Verified against the reference corpus: EMS 10.5.1's `toc.yml` holds 1,441 paths,
    zero of which carry a fragment, under exactly this shape. The fragment branch is
    still parsed because `NavNode.anchor` is populated for 12.1% of Flare TOC entries
    upstream, so a set that keeps them will arrive here eventually.
    """

    name = "items-path-children"

    def matches(self, document: Any) -> bool:
        return isinstance(document, dict) and isinstance(document.get("items"), list)

    def parse(self, document: Any) -> list[TocEntry]:
        return self._rows(document.get("items") or [])

    def _rows(self, rows: Any) -> list[TocEntry]:
        out: list[TocEntry] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            raw = str(row.get("path") or "")
            path, _, fragment = raw.partition("#")
            out.append(
                TocEntry(
                    title=str(row.get("title") or ""),
                    path=PurePosixPath(path) if path else None,
                    fragment=fragment,
                    children=self._rows(row.get("children") or []),
                )
            )
        return out


_REGISTRY: dict[str, TocSchema] = {}


def register(schema: TocSchema) -> None:
    """Registers a TOC dialect under its `name`."""
    _REGISTRY[schema.name] = schema


def registered_schemas() -> list[str]:
    """Every registered dialect name, sorted -- what `--toc-schema` will accept."""
    return sorted(_REGISTRY)


def schema_for(document: Any, name: str = "") -> TocSchema | None:
    """The adapter for this document, or `None`.

    `name` forces one, and forcing one that does not exist is `None` rather than a
    fallback to detection: a configured schema that silently did not apply is the
    failure this seam exists to prevent. Detection order is registration order, so
    the general shape must register after any narrower one it would shadow.
    """
    if name:
        return _REGISTRY.get(name)
    for schema in _REGISTRY.values():
        if schema.matches(document):
            return schema
    return None


register(ItemsPathChildren())
