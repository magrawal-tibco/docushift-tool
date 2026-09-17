"""Where a unit's output goes, which is a property of the *set* of roots.

`architecture.md` §5.1.3, rewritten by Phase 10. Every case here is a row from the
measurement that forced the rewrite, taken over the `html-to-md` cache on
2026-09-17: of 611 Flare version trees, **491 ship a single output root and 0 of
those have it at the version root** -- 257 sit at `html/`, 203 at `doc/html/`. The
old rule named the subtree after the root's relative path, so 80.4% of Flare
versions published one or two directories below where the contract says they live.

The refusals are measured too, and they are the reason this returns a lookup for
the whole version rather than a name for one root.
"""

from pathlib import Path

from docushift.engines.roots import subtree_names


def tree(base: Path, *relatives: str) -> list[Path]:
    """Roots created on disk, because the clash test reads the primary's entries."""
    made = []
    for relative in relatives:
        path = base / relative
        path.mkdir(parents=True, exist_ok=True)
        made.append(path)
    return made


def test_a_lone_root_publishes_at_the_version_root(tmp_path: Path) -> None:
    """The 491, and `datasynapse` among them. Nothing else is in the tree, so
    there is nothing the collapse can collide with."""
    roots = tree(tmp_path, "doc/html")

    assert subtree_names(tmp_path, roots) == {roots[0]: ""}


def test_a_lone_root_already_at_the_version_root_is_unchanged(tmp_path: Path) -> None:
    """0 of 491 in the corpus, but the rule must not special-case its way into
    naming the version root after itself."""
    assert subtree_names(tmp_path, [tmp_path]) == {tmp_path: ""}


def test_the_shallowest_of_several_takes_the_root_and_the_rest_keep_their_last_segment(
    tmp_path: Path,
) -> None:
    """BusinessWorks 6.10.0's shape: `doc/html` + `doc/relnotes`. 93 versions.

    The `doc/` segment goes and so does `html`, which is what makes this the same
    rule as the single-root case rather than a prefix-strip wearing its clothes.
    """
    primary, secondary = tree(tmp_path, "doc/html", "doc/relnotes")

    assert subtree_names(tmp_path, [secondary, primary]) == {primary: "", secondary: "relnotes"}


def test_a_nested_pair_keeps_every_full_relative_name(tmp_path: Path) -> None:
    """32 versions, and the one case the rule cannot help.

    The inner root's files are already inside the outer one, so naming the inner
    root as a sibling folder does not separate them -- it renames the collision
    and then writes both into it.
    """
    outer, inner = tree(tmp_path, "doc/html", "doc/html/sub")

    assert subtree_names(tmp_path, [outer, inner]) == {
        outer: "doc/html", inner: "doc/html/sub",
    }


def test_two_secondaries_with_the_same_last_segment_keep_their_full_names(
    tmp_path: Path,
) -> None:
    """`stat` 14.4.0 -- the single measured clash in 93 eligible versions.

    It takes *three* roots to make one: with two, the primary takes the version
    root and the other is the only folder there is, whatever it is called. The
    clash is between secondaries, which is why the check counts those and not the
    whole set.
    """
    primary, first, second = tree(tmp_path, "doc/main", "doc/a/html", "doc/b/html")

    assert subtree_names(tmp_path, [primary, first, second]) == {
        primary: "doc/main", first: "doc/a/html", second: "doc/b/html",
    }


def test_two_roots_sharing_a_last_segment_do_not_clash_because_one_takes_the_root(
    tmp_path: Path,
) -> None:
    """The near-miss the test above is careful not to be: `doc/a/html` publishes
    at the version root, so the only folder written is the other one's."""
    first, second = tree(tmp_path, "doc/a/html", "doc/b/html")

    assert subtree_names(tmp_path, [first, second]) == {first: "", second: "html"}


def test_a_secondary_named_after_something_the_primary_already_holds_is_refused(
    tmp_path: Path,
) -> None:
    """The collapse lifts the primary's own entries to the version root, so a
    secondary root's folder name has to be free of them -- and the test folds
    case, because the shelf does not (Phase 8's lesson, applied one level up)."""
    primary, secondary = tree(tmp_path, "doc/html", "doc/RelNotes")
    (primary / "relnotes").mkdir()

    assert subtree_names(tmp_path, [primary, secondary]) == {
        primary: "doc/html", secondary: "doc/RelNotes",
    }


def test_no_roots_is_an_empty_lookup_and_not_an_error(tmp_path: Path) -> None:
    """`find_output_roots` returns `[]` for "no rule applies", which callers read
    as "the version tree is the single unit" -- a different fact, handled by the
    caller, and not this function's to invent a name for."""
    assert subtree_names(tmp_path, []) == {}
