"""Stage 6a: one version's navigation, synthesized from what the engines reported.

The four engines report a node list, a landing page and a support/legal pair per
unit and decide none of §10's three rules (`engines/base.py`). This is where those
rules run -- once, for all four -- and where the per-unit lists become the one
`toc.yml` a version publishes.

It runs **inside the conversion build, before the swap**, and that is a decision
rather than a convenience. The node list exists only while the engine's `Unit` is
in hand: nothing persists it, and the generated container pages below are Markdown
documents that have to land in the staging tree, which stops existing the moment
`swap()` runs. The alternative -- write the tree to `state.db` and synthesize from
a later command -- stores a derived artifact whose only consumer runs milliseconds
afterwards, and makes a re-run decide whether to trust it.

Three things the specification did not say, measured over the predecessor's cache
on 2026-09-12 and settled here:

- **A version is normally several units.** WebWorks ships more than one in 128 of
  142 versions (90.1%), median 3 and up to 9; Flare in 15 of 157 (9.6%), SuiteHelp
  in 5 of 108 (4.6%), DocBook in 0 of 2. So one unit contributes its nodes to the
  version's top level directly and several get a node each -- the same shape
  §5.3.3 already uses for `BookGroup`, where a level with one child is not
  navigation. Unit order is the engine's, never re-sorted: WebWorks returns books
  in `books.xml` declaration order, non-alphabetical in 71% of collections.
- **The support/legal tail is positional, not deduplicated by content.** §10's
  "one legal node, not two" was written for Flare, where a version is one output
  root. 105 of 400 multi-book versions carry a legal page in more than one book,
  and in 83 of them the copies are **not** byte-identical -- but the difference is
  FrameMaker anchor ids (`<a name="113179">` against `<a name="113190">`) and the
  prose is the same, so a hash would keep all nine copies of one notice. The first
  unit in unit order supplies the version's tail; the others' copies leave the
  navigation as `NAV_NODE_DROPPED` and stay on disk, because a CSH identifier or an
  inbound link may still reach one.
- **A unit label needs a chain.** `Unit.title` first (the engine's own answer), then
  the unit's landing-page title, then the directory stem with its separators opened
  out -- `doc/relnotes`, not `tib_adas400_concepts`.
"""

import posixpath
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from docushift.engines.base import ConversionContext, Document, NavNode, Unit
from docushift.utils.templating import template as _template

# Where a generated container page goes when its children share no directory, and
# what the version index is called. Both are Markdown documents like any other.
INDEX_NAME = "index"


@dataclass
class Synthesis:
    """The version's navigation, and the pages that had to be written to make it."""

    nodes: list[NavNode] = field(default_factory=list)
    # Container pages and the version index. Written by the driver into the
    # staging tree, before the swap, exactly like a converted topic.
    documents: list[Document] = field(default_factory=list)
    landing: PurePosixPath | None = None
    # Nodes that left the tree: a duplicate tail page, or a container whose last
    # child went with it. Counted rather than silent (invariant 10).
    dropped: int = 0

    @property
    def generated(self) -> int:
        return len(self.documents)


@dataclass
class _View:
    """One unit with its paths rebased onto the version root.

    The engine reports paths relative to its own unit, because that is the only
    frame it has; every rule below compares paths across units, so they are moved
    into the version's frame once, here, rather than at each comparison.
    """

    unit: Unit
    nodes: list[NavNode]
    landing: PurePosixPath | None = None
    support: PurePosixPath | None = None
    legal: PurePosixPath | None = None


# -- the stage ------------------------------------------------------------------


def synthesize(context: ConversionContext, units: list[Unit], templates: Path) -> Synthesis:
    """Assembles one version's navigation and generates the pages it needs."""
    views = [_view(unit) for unit in units]
    documents = {
        _under(view.unit.name, document.relative): document
        for view in views
        for document in view.unit.documents
    }

    result = Synthesis()
    nodes = _assemble(views, documents)
    result.dropped += _tail(views, nodes)
    result.landing, wants_index = _landing(views, nodes, documents)

    taken = set(documents)
    nodes, dropped = _generate(nodes, taken, documents, result.documents, templates)
    result.dropped += dropped

    if wants_index and nodes:
        # No unit reported a landing page -- WebWorks has none by design (§5.3.5),
        # DITA's TOC is a forest in 23 of 23 sampled doc-sets (§5.2.3). The version
        # gets a generated index rather than opening on whichever book sorted
        # first, and it is built last so that it links the tree as published.
        label = _version_label(context, views)
        page = _page(label, nodes, "", taken, documents, templates, stem=INDEX_NAME)
        result.documents.append(page)
        nodes.insert(0, NavNode(label=label, document=page.relative))
        result.landing = page.relative

    result.nodes = nodes
    if result.dropped:
        context.record("NAV_NODE_DROPPED", count=result.dropped,
                       message=f"{result.dropped} node(s) dropped assembling the version")
    return result


def _view(unit: Unit) -> _View:
    name = unit.name
    return _View(
        unit=unit,
        nodes=[_rebase(node, name) for node in unit.nav],
        landing=_under(name, unit.landing),
        support=_under(name, unit.support),
        legal=_under(name, unit.legal),
    )


def _assemble(views: list[_View], documents: dict[PurePosixPath, Document]) -> list[NavNode]:
    """One unit's nodes become the version's; several units become one node each.

    A lone unit must not gain a wrapper naming the directory it happened to sit
    in, which is the same reason §5.3.3 flattens a single `BookGroup`.
    """
    if len(views) == 1:
        return list(views[0].nodes)

    nodes = []
    for view in views:
        children = list(view.nodes)
        if view.landing is not None:
            # The unit's own landing page becomes the wrapper's page, so the
            # wrapper needs no generated one -- and the node that pointed at it
            # from inside goes, the way a Flare container drops a child pointing
            # at its own page (§5.1.4). One page, one position.
            children = _without(children, view.landing)
        nodes.append(NavNode(
            label=_unit_label(view, documents),
            document=view.landing,
            children=children,
        ))
    return nodes


def _tail(views: list[_View], nodes: list[NavNode]) -> int:
    """Support then legal, last, once per version. Moved, never appended.

    Positional and not content-addressed: see the module docstring. The chosen
    pages come from the first unit that reports each, which is the first book in
    `books.xml` order -- not the first alphabetically, and not the largest.
    """
    support = next((view.support for view in views if view.support is not None), None)
    legal = next((view.legal for view in views if view.legal is not None), None)

    dropped = 0
    duplicates = [
        path
        for view in views
        for path in (view.support, view.legal)
        if path is not None and path not in (support, legal)
    ]
    for path in duplicates:
        node = _find(nodes, path)
        # A tail page with children is not a tail page; it is a section that
        # happens to be named like one, and dropping it would take its children
        # out of the navigation with it. Left where the engine filed it.
        if node is None or node.children:
            continue
        _extract(nodes, path)
        dropped += 1

    for path in (support, legal):
        if path is None:
            continue
        node = _extract(nodes, path)
        if node is None:
            # Reported by the engine but never a TOC entry -- WebWorks'
            # `copyrigh.htm` is in the TOC of almost no book (§5.3.5), so the node
            # is created here rather than lost.
            node = NavNode(label="", document=path)
        nodes.append(node)
    return dropped


def _landing(
    views: list[_View],
    nodes: list[NavNode],
    documents: dict[PurePosixPath, Document],
) -> tuple[PurePosixPath | None, bool]:
    """The landing page is the first node. Moved to first, or inserted as first.

    Never left to fall through to "Unfiled", which is where Flare's `DefaultUrl`
    lands in 55 of 60 sampled roots if nothing hoists it.
    """
    landing = next((view.landing for view in views if view.landing is not None), None)
    if landing is None:
        return None, True

    node = _extract(nodes, landing)
    if node is None:
        node = NavNode(label=_label_of(landing, documents), document=landing)
    nodes.insert(0, node)
    return landing, False


def _generate(
    nodes: list[NavNode],
    taken: set[PurePosixPath],
    documents: dict[PurePosixPath, Document],
    pages: list[Document],
    templates: Path,
) -> tuple[list[NavNode], int]:
    """Gives every childed node a page, and drops the childless ones with none.

    Bottom-up, so a container's generated page links children that already have
    pages of their own. AEM treats a childed node with no page as a broken parent;
    Flare's `'___'` sentinel produces 165 of them per 60 output roots, 151 at top
    level with 1,357 children between them.
    """
    kept: list[NavNode] = []
    dropped = 0
    for node in nodes:
        node.children, child_dropped = _generate(node.children, taken, documents, pages, templates)
        dropped += child_dropped
        if node.document is None and not node.children:
            dropped += 1
            continue
        if node.document is None:
            page = _page(node.label, node.children, _home(node), taken, documents, templates)
            pages.append(page)
            node.document = page.relative
        kept.append(node)
    return kept, dropped


# -- the generated page ---------------------------------------------------------


def _page(
    label: str,
    children: list[NavNode],
    home: str,
    taken: set[PurePosixPath],
    documents: dict[PurePosixPath, Document],
    templates: Path,
    stem: str = "",
) -> Document:
    """One synthesized page: a title and its immediate children as links.

    `generated: true` in frontmatter, so a re-run replaces it instead of reading it
    back as something an author wrote. It has no `source`, because there is no
    source -- it never enters the §9.3 output map and no CSH identifier resolves
    to it.
    """
    relative = _free(home, stem or _slug(label), taken)
    taken.add(relative)
    parent = posixpath.dirname(str(relative)) or "."
    links = [
        {
            "label": child.label or _label_of(child.document, documents),
            "path": _link(parent, child),
        }
        for child in children
        if child.document is not None
    ]
    body = _template(templates, "index.md.j2").render(title=label, children=links).strip()
    return Document(
        source=Path(),
        relative=relative,
        title=label,
        body=body,
        frontmatter={"generated": True},
    )


def _free(home: str, stem: str, taken: set[PurePosixPath]) -> PurePosixPath:
    """A page path beside the children it indexes, never over one of them."""
    stem = stem or INDEX_NAME
    for attempt in range(1, 100):
        name = f"{stem}.md" if attempt == 1 else f"{stem}-{attempt}.md"
        relative = PurePosixPath(home) / name if home else PurePosixPath(name)
        if relative not in taken:
            return relative
    raise ValueError(f"no free path for {stem!r} under {home!r}")  # pragma: no cover


def _home(node: NavNode) -> str:
    """The deepest directory holding every page under this node.

    A container's index belongs with its children: for a unit wrapper that is the
    unit's own subtree, which falls out of this rather than being special-cased.
    """
    parts: list[list[str]] = [
        PurePosixPath(child.document).parent.parts
        for child in node.walk()
        if child.document is not None
    ]
    if not parts:
        return ""
    common = parts[0]
    for other in parts[1:]:
        limit = min(len(common), len(other))
        index = 0
        while index < limit and common[index] == other[index]:
            index += 1
        common = common[:index]
    return "/".join(common)


def _link(parent: str, node: NavNode) -> str:
    target = posixpath.relpath(str(node.document), parent or ".")
    return f"{target}#{node.anchor}" if node.anchor else target


# -- rendering ------------------------------------------------------------------


def render_toc(nodes: list[NavNode], templates: Path, title: str = "") -> str:
    """`toc.yml` for one version: the tree, flattened into indented rows.

    Flattened in Python rather than recursed in Jinja because the depth is the
    only part that is not a straight substitution, and a recursive template that
    gets its own indentation wrong produces YAML that parses into the wrong tree
    instead of failing. Every scalar goes through the same unconditional quote
    `csh.yml` uses -- a title carrying a colon is ordinary prose and must not
    become a mapping.
    """
    return _template(templates, "toc.yml.j2").render(title=title, rows=_rows(nodes, 0))


def _rows(nodes: list[NavNode], depth: int) -> list[dict]:
    rows: list[dict] = []
    for node in nodes:
        rows.append({
            "indent": " " * (2 + 4 * depth),
            "title": node.label,
            "path": _target(node),
            "children": bool(node.children),
        })
        rows.extend(_rows(node.children, depth + 1))
    return rows


def _target(node: NavNode) -> str:
    if node.document is None:  # pragma: no cover - every kept node has a page
        return ""
    return f"{node.document}#{node.anchor}" if node.anchor else str(node.document)


def render_metadata(values: list[tuple[str, str]], templates: Path, level: str = "") -> str:
    """`metadata.yml`, at whichever level the caller is writing.

    Two keys and no more: AEM specified `csg-product` at product level and
    `csg-version` at version level, and the ~11 fields the Phase-1 placeholder
    invented are gone rather than kept alongside -- shipping a guess beside a
    contract is what makes the guess look load-bearing.
    """
    return _template(templates, "metadata.yml.j2").render(level=level, values=values)


# -- paths and labels -----------------------------------------------------------


def _under(name: str, path: PurePosixPath | None) -> PurePosixPath | None:
    if path is None:
        return None
    return PurePosixPath(name) / path if name else path


def _rebase(node: NavNode, name: str) -> NavNode:
    return NavNode(
        label=node.label,
        document=_under(name, node.document),
        anchor=node.anchor,
        children=[_rebase(child, name) for child in node.children],
    )


def _find(nodes: list[NavNode], path: PurePosixPath) -> NavNode | None:
    for node in nodes:
        if node.document == path:
            return node
        found = _find(node.children, path)
        if found is not None:
            return found
    return None


def _extract(nodes: list[NavNode], path: PurePosixPath) -> NavNode | None:
    """Removes and returns the node for `path`, wherever it sits. Depth-first."""
    for index, node in enumerate(nodes):
        if node.document == path:
            return nodes.pop(index)
        found = _extract(node.children, path)
        if found is not None:
            return found
    return None


def _without(nodes: list[NavNode], path: PurePosixPath) -> list[NavNode]:
    kept = []
    for node in nodes:
        if node.document == path and not node.children:
            continue
        node.children = _without(node.children, path)
        kept.append(node)
    return kept


def _unit_label(view: _View, documents: dict[PurePosixPath, Document]) -> str:
    """What to call a unit in a multi-unit version. First hit wins."""
    if view.unit.title:
        return view.unit.title
    if view.landing is not None:
        label = _label_of(view.landing, documents)
        if label:
            return label
    return _pretty(view.unit.name)


def _version_label(context: ConversionContext, views: list[_View]) -> str:
    """What to call the generated version index.

    WebWorks names the collection in `books.xml` and that is the better answer
    where it exists: it is what the collection called itself. The catalog's
    display name is the fallback, and the slug the last resort.
    """
    for view in views:
        name = view.unit.metadata.get("collection_name", "")
        if name:
            return name
    return context.product_name or _pretty(context.slug) or "Documentation"


def _label_of(path: PurePosixPath | None, documents: dict[PurePosixPath, Document]) -> str:
    document = documents.get(path) if path is not None else None
    if document is None:
        return _pretty(PurePosixPath(path).stem) if path is not None else ""
    return document.nav_label or document.title or _pretty(path.stem)


def _pretty(name: str) -> str:
    """A directory stem as a label: `html/tib_adas400_concepts` reads as nothing."""
    stem = PurePosixPath(name).name or name
    return re.sub(r"[_.\-]+", " ", stem).strip().title()


def _slug(label: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", label.lower())).strip("-")
