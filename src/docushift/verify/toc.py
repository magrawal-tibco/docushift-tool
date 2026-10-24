"""The TOC kept its shape: every entry, under the same parent, in the same order.

Two hops, one comparison each (`planning.md` Phase 55, A5 and B4):

- **old TOC -> `toc.yml`**, matched by *page*: an old entry and a new one are the
  same entry when they open the same published page (and anchor). A title may
  change on the way, so it is reported, not matched on.
- **`toc.yml` -> the staging menu**, matched by *title*: the menu's links are AEM
  URLs, which are not the repo's paths, but the titles are written by the same
  file. Matching there is also how `published.py` learns each page's URL, so no
  URL is ever derived by rule.

A presence check would pass a TOC that kept every entry under the wrong parent,
which is the failure this module exists for.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from docushift.verify.text import words


@dataclass
class Node:
    """One TOC row. `key` identifies the page it opens; None for a heading-only row."""

    title: str
    key: str | None = None
    children: list[Node] = field(default_factory=list)
    #: Anything the caller wants back on a match -- the staging URL, for B.
    ref: str = ""

    def walk(self, parent: Node | None = None):
        for child in self.children:
            yield child, self
            yield from child.walk(self)


def root(children: list[Node]) -> Node:
    return Node("", None, children)


def same_title(a: str, b: str) -> bool:
    return words(a) == words(b)


@dataclass
class Issue:
    kind: str          # missing | moved | order | title
    key: str           # the entry, as its page or title path
    detail: str = ""


@dataclass
class Comparison:
    issues: list[Issue] = field(default_factory=list)
    #: old/`toc.yml` node -> the node it matched on the other side.
    matched: dict[int, Node] = field(default_factory=dict)

    def of(self, kind: str) -> list[Issue]:
        return [i for i in self.issues if i.kind == kind]


def _identity(node: Node | None) -> str:
    """A parent as a comparable value: its page, or for a heading-only row its title."""
    if node is None or (node.key is None and not node.title):
        return "(top)"
    return node.key or f"title:{' '.join(words(node.title))}"


def by_page(old: Node, new: Node, skip: set[str] = frozenset()) -> Comparison:
    """A5: the old TOC against `toc.yml`, matching entries by the page they open.

    `skip` holds keys that are known drops and must not be reported missing. A row
    that repeats its parent's page adds nothing to the navigation (the converter
    folds it, `NAV_NODE_DROPPED`), so it is skipped too.
    """
    result = Comparison()
    placed: dict[str, tuple[Node, Node]] = {}
    for node, parent in new.walk():
        if node.key is not None:
            placed.setdefault(node.key, (node, parent))

    groups: dict[int, tuple[Node, list[str]]] = {}
    for node, parent in old.walk():
        if node.key is None or node.key in skip or (parent.key is not None and parent.key == node.key):
            continue
        hit = placed.get(node.key)
        if hit is None:
            result.issues.append(Issue("missing", node.key, node.title))
            continue
        twin, new_parent = hit
        result.matched[id(node)] = twin
        was, now = _identity(_parent(old, parent)), _identity(_parent(new, new_parent))
        # A heading-only row that the new tree gives a page of its own (Phase 63's
        # parent pages) is the same parent under its title, not a move (Phase 60).
        if was != now and not (parent.key is None and parent.title and
                               same_title(parent.title, new_parent.title)):
            # Reported once, as a move. Its siblings' order is judged without it.
            result.issues.append(Issue("moved", node.key, f"under {was} -> {now}"))
            continue
        if not same_title(node.title, twin.title):
            result.issues.append(Issue("title", node.key, f"{node.title!r} -> {twin.title!r}"))
        groups.setdefault(id(parent), (parent, []))[1].append(node.key)

    _order(result, groups, lambda key: placed[key])
    return result


def _parent(tree: Node, parent: Node) -> Node | None:
    """`parent` as a row, or None when it is the tree's own root (a top-level row)."""
    return None if parent is tree else parent


def _order(result: Comparison, groups, locate) -> None:
    """One `order` issue per parent whose matched children appear in another order."""
    for parent, keys in groups.values():
        positions: list[tuple[int, str]] = []
        for key in keys:
            twin, new_parent = locate(key)
            siblings = new_parent.children
            positions.append((next(i for i, s in enumerate(siblings) if s is twin), key))
        seen = [p for p, _ in positions]
        if seen != sorted(seen):
            result.issues.append(Issue("order", _identity(parent),
                                       f"{len(keys)} entries under it are in a different order"))


def by_title(local: Node, served: Node) -> Comparison:
    """B4: `toc.yml` against the menu staging serves, matching siblings by title.

    Walked in parallel from the top: a `toc.yml` row matches the first unused
    sibling with the same title. A row with no such sibling is looked for anywhere
    in the menu (`moved`); failing that, an unmatched sibling at the same position
    is taken as the same row retitled (`title`); failing that, it is `missing`.
    """
    result = Comparison()
    everywhere: dict[str, list[tuple[Node, Node]]] = {}
    for node, parent in served.walk():
        everywhere.setdefault(" ".join(words(node.title)), []).append((node, parent))
    _match(local, served, result, everywhere, ())
    return result


def _match(local: Node, served: Node, result: Comparison, everywhere, trail: tuple[str, ...]) -> None:
    used: set[int] = set()
    order: list[int] = []
    for index, row in enumerate(local.children):
        path = " > ".join((*trail, row.title))
        twin = next((s for s in served.children if id(s) not in used and same_title(s.title, row.title)), None)
        if twin is None:
            elsewhere = [n for n, _ in everywhere.get(" ".join(words(row.title)), []) if id(n) not in used]
            if elsewhere:
                twin = elsewhere[0]
                result.issues.append(Issue("moved", path, "found under another parent in the served menu"))
            elif index < len(served.children) and id(served.children[index]) not in used:
                twin = served.children[index]
                result.issues.append(Issue("title", path, f"{row.title!r} -> {twin.title!r}"))
            else:
                result.issues.append(Issue("missing", path))
                continue
        else:
            order.append(served.children.index(twin))
        used.add(id(twin))
        result.matched[id(row)] = twin
        _match(row, twin, result, everywhere, (*trail, row.title))
    if order != sorted(order):
        result.issues.append(Issue("order", " > ".join(trail) or "(top)",
                                   f"{len(order)} entries in a different order"))
