"""Context-sensitive help: the resolver, the flat `csh.yml`, and the frontmatter.

`design.md` §9.3-§9.5. The three *readers* landed in Phase 4b-2 (`engines/csh.py`)
because Stage 4 has to count identifiers; everything above them is engine-neutral
and lives here. An engine contributes `(identifier, link, anchor)` tuples and
nothing else -- there is one resolver, one writer and one quoting rule for all
three engines, or there are three subtly different answers to "did this Help
button survive".

**Resolution runs after the version's topics have been converted**, against the
source-HTML -> output-Markdown map the converter recorded in `state.db`. Not
against a recomputed one: the converter is the only party that knows what it
renamed, deduplicated or dropped, and a second derivation of that answer would
disagree with it silently -- which is the same defect invariant 13 forbids for
assets.

**`csh.yml` is a flat `"<identifier>": "<path>"` map** (AEM contract, 2026-09-10).
That single decision removes four fields, and each removal has to go somewhere:

- The anchor is **appended to the path** rather than carried beside it.
- `doc_set` is already the first segment of the relative path, so it is not lost.
- `also` has nowhere to go, so an identifier claimed by two doc-sets needs a
  **deterministic winner** instead of a list -- see `order_doc_sets`.
- `sources`, `counts` and `unresolved` move to the findings register. That is not
  polish: after this change the register is the *only* remaining record of a Help
  identifier that resolves to nothing, and invariant 10 says absence is reported.

Identifiers are byte-exact and never case-folded (§9.1), and they are always
emitted double-quoted -- 834 of 11,054 Flare names are digit-only, and an
unquoted `1234` comes back from a YAML 1.1 loader as an int.
"""

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from docushift.engines.csh import CshSource, CshStatus
from docushift.transforms import links


@dataclass(frozen=True)
class Resolved:
    """One identifier that landed on a topic the converter actually produced."""

    identifier: str
    doc_set: str
    # Output-root-relative POSIX path, anchor already appended. What goes in the file.
    target: str


@dataclass(frozen=True)
class Unresolved:
    """One identifier whose link matched no produced topic anywhere in the version.

    Kept, and reported as `CSH_UNRESOLVED`. Dropping it would turn a broken Help
    button into an absence no later check can find.
    """

    identifier: str
    doc_set: str
    link: str


@dataclass(frozen=True)
class Ambiguity:
    """One identifier that two doc-sets resolved differently. Reported, not merged."""

    identifier: str
    chosen: str
    dropped: tuple[str, ...]


@dataclass
class CshMap:
    """Everything resolution produced: the file's contents, and what the file cannot say."""

    entries: dict[str, str] = field(default_factory=dict)
    unresolved: list[Unresolved] = field(default_factory=list)
    ambiguous: list[Ambiguity] = field(default_factory=list)
    # doc-set -> (identifiers seen, identifiers resolved). §9.4's `sources` tally,
    # relocated to the report.
    tallies: dict[str, tuple[int, int]] = field(default_factory=dict)
    # Identifiers rescued by the version-wide fallback -- 22% of Flare links, and
    # the single measurement that justifies the per-version file over a per-doc-set
    # one. Counted so a regression in it is visible.
    rescued: int = 0
    # Sources located but not usable, by status. "Help we could not read" and "no
    # help" are different facts (§5.4.4).
    unusable: dict[str, int] = field(default_factory=dict)

    @property
    def empty(self) -> bool:
        """No resolved identifier. **No file is written** in this state (§9.4)."""
        return not self.entries


def order_doc_sets(sources: list[CshSource]) -> list[str]:
    """The version's doc-sets, **most resolved entries first, ties alphabetical**.

    One ordering serving two rules that were written separately and are the same
    rule: §9.3 step 5's "the primary is the doc-set with the most resolved entries"
    and the flat schema's "an ambiguous identifier resolves to the first doc-set in
    the version's ordered doc-set list". Deterministic, and it picks the main help
    output over a release-notes sidecar every time -- which is the outcome that
    matters, because the sidecar is exactly the file Flare copies wholesale into a
    sibling where none of its links exist.

    Counted on *entries*, not on resolution: the order is needed to decide the
    fallback scan, which happens before anything is resolved.
    """
    counts: dict[str, int] = {}
    for source in sources:
        counts[source.doc_set] = counts.get(source.doc_set, 0) + source.count
    return sorted(counts, key=lambda doc_set: (-counts[doc_set], doc_set))


def resolve(sources: list[CshSource], output_map: dict[str, str]) -> CshMap:
    """Resolves every identifier in a version against what conversion produced.

    `output_map` is `state.db`'s `output_map` for this version: source path
    relative to the extracted tree -> output path relative to the version's output
    root, both POSIX. `sources` carry the tree-relative `doc_set` Stage 4 recorded.

    Never raises. Every identifier ends in exactly one of `entries` or
    `unresolved`, so the two always sum to the number read.
    """
    result = CshMap()
    order = order_doc_sets(sources)
    seen: dict[str, list[Resolved]] = {}
    counted: dict[str, list[int]] = {doc_set: [0, 0] for doc_set in order}

    for source in sources:
        if source.status is not CshStatus.OK:
            key = str(source.status)
            result.unusable[key] = result.unusable.get(key, 0) + 1
            continue
        tally = counted.setdefault(source.doc_set, [0, 0])
        for entry in source.entries:
            tally[0] += 1
            target, rescued = _target(entry.link, entry.anchor, source.doc_set, order, output_map)
            if target is None:
                result.unresolved.append(Unresolved(entry.identifier, source.doc_set, entry.link))
                continue
            tally[1] += 1
            result.rescued += int(rescued)
            seen.setdefault(entry.identifier, []).append(
                Resolved(entry.identifier, source.doc_set, target)
            )

    rank = {doc_set: index for index, doc_set in enumerate(order)}
    for identifier in sorted(seen):
        # Same target from several doc-sets is not a conflict, it is the same
        # answer arrived at twice -- the common case, and it collapses silently.
        candidates = sorted(
            {candidate.target: candidate for candidate in seen[identifier]}.values(),
            key=lambda candidate: (rank.get(candidate.doc_set, len(rank)), candidate.target),
        )
        winner = candidates[0]
        result.entries[identifier] = winner.target
        if len(candidates) > 1:
            result.ambiguous.append(
                Ambiguity(identifier, winner.target, tuple(c.target for c in candidates[1:]))
            )

    result.tallies = {doc_set: (values[0], values[1]) for doc_set, values in counted.items()}
    return result


def _target(
    link: str, anchor: str, doc_set: str, order: list[str], output_map: dict[str, str]
) -> tuple[str | None, bool]:
    """One link to an output path, or None. The bool is "the fallback rescued it".

    Step 3 resolves inside the link's own doc-set. Step 4 tries the identical
    relative path in every sibling, **in the version's doc-set order**, and takes
    the first hit -- a Flare remedy specifically: 1,609 of 7,220 links dangle in
    their own doc-set and 10 of the 11 affected files are a `relnotes` alias
    resolving at 0%. WebWorks links resolve inside their own book 100% of the time
    and never reach it.
    """
    reference = links.classify(link)
    if not reference.resolvable:
        return None, False
    fragment = anchor or reference.fragment

    inside = links.resolve(PurePosixPath(doc_set), reference.path)
    if not links.escapes(inside):
        output = output_map.get(str(inside))
        if output is not None:
            return _join(output, fragment), False

    relative = links.resolve(PurePosixPath(""), reference.path)
    if links.escapes(relative):
        return None, False
    for sibling in order:
        if sibling == doc_set:
            continue
        output = output_map.get(str(links.resolve(PurePosixPath(sibling), reference.path)))
        if output is not None:
            return _join(output, fragment), True
    return None, False


def _join(output: str, anchor: str) -> str:
    """Path plus anchor, as one string.

    The anchor is the **source's**, unmodified. Whatever slug the engine gave the
    heading is the engine's business; this module has no way to know it and
    guessing would produce a link that looks right and lands nowhere. Tracked as
    an Open in §9.4.
    """
    return f"{output}#{anchor}" if anchor else output


def identifiers_by_source(sources: list[CshSource]) -> dict[str, list[str]]:
    """Tree-relative source-HTML path -> the identifiers that topic owns (§9.5).

    Runs **before** conversion, not after: the identifiers are in the alias file
    and need no resolution, so frontmatter lands in the topic's first and only
    write rather than in a read-modify-write pass over the whole output tree.
    Sorted and deduplicated, so re-converting a version produces the same bytes.
    """
    owned: dict[str, set[str]] = {}
    for source in sources:
        if source.status is not CshStatus.OK:
            continue
        for entry in source.entries:
            reference = links.classify(entry.link)
            if not reference.resolvable:
                continue
            path = links.resolve(PurePosixPath(source.doc_set), reference.path)
            if links.escapes(path):
                continue
            owned.setdefault(str(path), set()).add(entry.identifier)
    return {path: sorted(identifiers) for path, identifiers in sorted(owned.items())}


def quote(text: str) -> str:
    """A YAML double-quoted scalar. **Unconditional** -- never "quote if needed".

    A conditional quote is a branch, and a branch can be wrong about `1234`,
    `6.2`, `yes`, `null` or an empty string. Escaping is the double-quoted style's
    own: backslash, then the quote, then the control characters a path could
    plausibly carry.
    """
    escaped = (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def render(mapping: dict[str, str]) -> str:
    """The flat `csh.yml`, keys sorted byte-exact.

    Sorted by the identifier's code points rather than case-insensitively, because
    `GatewayInstances` and `gatewayInstances` are two different live help targets
    in TIBCO BC 7.4/7.5 and a case-folded sort would put them in an order that
    depends on which was read first.
    """
    lines = [f"{quote(identifier)}: {quote(mapping[identifier])}" for identifier in sorted(mapping)]
    return "\n".join(lines) + "\n"


def write(path: Path, mapping: dict[str, str]) -> bool:
    """Writes `csh.yml`, or does not. Returns whether a file now exists there.

    **An empty map gets no file at all** (§9.4): an empty map file is
    indistinguishable from a failed run, so absence plus a report line is the
    honest signal. An existing file from a previous run is removed for the same
    reason -- a version that lost its help must not keep yesterday's answer.
    """
    if not mapping:
        if path.exists():
            path.unlink()
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(mapping), encoding="utf-8")
    return True


def frontmatter_value(identifiers: list[str]) -> str:
    """`csh: ["a", "b"]` -- the value half, flow style, always a list (§9.5).

    Always a list even at length one, because a page commonly owns several and a
    consumer that has to handle both a scalar and a sequence will eventually
    handle one of them wrongly.
    """
    return "[" + ", ".join(quote(identifier) for identifier in identifiers) + "]"
