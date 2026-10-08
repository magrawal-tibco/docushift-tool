"""Phase 43: orphan topics leave the TOC and are kept, unmerged, under `unfiled/`.

The pass works on a written version tree, so these build one by hand in the
shape `navigation` writes: a `toc.yml` with an "Unfiled" node, its generated
`unfiled.md`, and the pages, `csh.yml` and `301.yml` that name the orphans.
"""

from pathlib import Path

import yaml

from docushift.converter.orphans import INBOUND, reshelve, write_inbound
from docushift.utils import textfile
from docushift.utils.csvio import read_rows

TOC = """\
# AEM table of contents
docs_list_title: "Online Help"
docs:
  - title: "Guide"
    url: "guide/index.md"
    subfolderlist:
      - title: "Start"
        url: "guide/start.md"
      - title: "Unfiled"
        url: "guide/unfiled.md"
        subfolderlist:
          - title: "Hidden"
            url: "guide/hidden.md"
  - title: "Legal"
    url: "legal.md"
"""

GENERATED_INDEX = """\
---
title: "Guide"
generated: true
---

# Guide

- [Start](start.md)
- [Unfiled](unfiled.md)
"""

UNFILED_PAGE = """\
---
title: "Unfiled"
generated: true
---

# Unfiled

- [Hidden](hidden.md)
"""

FILES = {
    "toc.yml": TOC,
    "guide/index.md": GENERATED_INDEX,
    "guide/unfiled.md": UNFILED_PAGE,
    "guide/start.md": "# Start\n\nSee [the hidden page](hidden.md#setup) and ![](images/a.png).\n"
                      "\n```\n[not a link](hidden.md)\n```\n",
    "guide/hidden.md": "# Hidden\n\n## Setup\n\n![](images/a.png) Back to [start](start.md).\n"
                       '<a href="hidden.md#setup">self</a>\n',
    "guide/images/a.png": "png",
    "legal.md": "# Legal\n",
    "csh.yml": '"start": "guide/start.md"\n"hidden": "guide/hidden.md#setup"\n',
    "301.yml": "# header\nredirects:\n"
               "- from: https://docs.example/pub/x/start.htm\n  to: guide/start.md\n  status: 301\n"
               "- from: https://docs.example/pub/x/hidden.htm\n  to: guide/hidden.md\n  status: 301\n",
}


def _tree(root: Path, files: dict[str, str] = FILES) -> Path:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        textfile.write_text(path, text)
    return root


def test_an_orphan_moves_to_unfiled_and_leaves_the_toc(tmp_path: Path) -> None:
    root = _tree(tmp_path)

    result = reshelve(root)

    assert result.moved == {"guide/hidden.md": "unfiled/guide/hidden.md"}
    assert not (root / "guide" / "hidden.md").exists()
    assert not (root / "guide" / "unfiled.md").exists()
    assert (root / "unfiled" / "guide" / "hidden.md").is_file()
    toc = (root / "toc.yml").read_text(encoding="utf-8")
    assert "Unfiled" not in toc and "hidden" not in toc
    assert yaml.safe_load(toc)["docs"][0]["subfolderlist"] == [
        {"title": "Start", "url": "guide/start.md"}]
    # The rest of the file is left byte for byte.
    assert toc == TOC.replace(TOC[TOC.index('      - title: "Unfiled"'):TOC.index('  - title: "Legal"')], "")


def test_links_into_and_out_of_a_moved_orphan_follow_it(tmp_path: Path) -> None:
    root = _tree(tmp_path)

    result = reshelve(root)

    start = (root / "guide" / "start.md").read_text(encoding="utf-8")
    assert "[the hidden page](../unfiled/guide/hidden.md#setup)" in start
    assert "![](images/a.png)" in start
    assert "[not a link](hidden.md)" in start  # code is prose
    hidden = (root / "unfiled" / "guide" / "hidden.md").read_text(encoding="utf-8")
    assert "![](../../guide/images/a.png)" in hidden
    assert "[start](../../guide/start.md)" in hidden
    assert '<a href="hidden.md#setup">' in hidden
    index = (root / "guide" / "index.md").read_text(encoding="utf-8")
    assert "unfiled.md" not in index and "- [Start](start.md)" in index
    assert result.links == 3


def test_csh_is_retargeted_and_the_redirect_dropped(tmp_path: Path) -> None:
    root = _tree(tmp_path)

    result = reshelve(root)

    csh = yaml.safe_load((root / "csh.yml").read_text(encoding="utf-8"))
    assert csh == {"start": "guide/start.md", "hidden": "unfiled/guide/hidden.md#setup"}
    rows = yaml.safe_load((root / "301.yml").read_text(encoding="utf-8"))["redirects"]
    assert [row["to"] for row in rows] == ["guide/start.md"]
    assert (result.csh, result.redirects) == (1, 1)


def test_reshelving_twice_changes_nothing(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    reshelve(root)
    before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}

    again = reshelve(root)

    assert (again.moved, again.removed) == ({}, False)
    assert {path: path.read_bytes() for path in root.rglob("*") if path.is_file()} == before


def test_a_version_whose_whole_toc_is_unfiled_is_left_alone(tmp_path: Path) -> None:
    """Every topic is an orphan only when the TOC was lost; shelving them all
    would publish an empty version."""
    toc = ('docs_list_title: "Online Help"\ndocs:\n  - title: "Unfiled"\n    url: "unfiled.md"\n'
           '    subfolderlist:\n      - title: "Hidden"\n        url: "hidden.md"\n')
    root = _tree(tmp_path, {"toc.yml": toc, "unfiled.md": UNFILED_PAGE, "hidden.md": "# Hidden\n"})

    result = reshelve(root)

    assert result.kept and not result.moved and not result.removed
    assert (root / "toc.yml").read_text(encoding="utf-8") == toc


def test_a_tree_with_no_unfiled_node_is_untouched(tmp_path: Path) -> None:
    files = {name: text for name, text in FILES.items() if name not in ("guide/unfiled.md",)}
    files["toc.yml"] = TOC[:TOC.index('      - title: "Unfiled"')] + TOC[TOC.index('  - title: "Legal"'):]
    root = _tree(tmp_path, files)

    result = reshelve(root)

    assert (result.moved, result.removed, result.links) == ({}, False, 0)


def test_links_from_listed_pages_into_unfiled_are_listed_in_unfiled(tmp_path: Path) -> None:
    """The links that break on AEM, on record beside the orphans themselves."""
    root = _tree(tmp_path)

    reshelve(root)

    # The orphan's own links and the fenced sample are not inbound links.
    assert read_rows(root / INBOUND) == [{
        "page": "guide/start.md", "line": "3", "link_text": "the hidden page",
        "orphan": "unfiled/guide/hidden.md", "orphan_title": ""}]


def test_the_inbound_list_takes_the_orphan_title_and_html_link_text(tmp_path: Path) -> None:
    root = _tree(tmp_path, {
        "a.md": '<p>See <a href="unfiled/x.md#y">the <b>X</b> page</a>.</p>\n',
        "unfiled/x.md": '---\ntitle: "X Topic"\n---\n\n# X\n',
    })

    assert write_inbound(root) == 1

    assert read_rows(root / INBOUND) == [{
        "page": "a.md", "line": "1", "link_text": "the X page",
        "orphan": "unfiled/x.md", "orphan_title": "X Topic"}]


def test_the_inbound_list_is_removed_when_no_link_remains(tmp_path: Path) -> None:
    root = _tree(tmp_path, {"a.md": "# A\n", "unfiled/x.md": "# X\n", INBOUND: "stale\n"})

    assert write_inbound(root) == 0

    assert not (root / INBOUND).exists()



def test_a_linked_image_in_a_moved_orphan_follows_it(tmp_path: Path) -> None:
    """Phase 44: the thumbnail and the full picture it opens are both re-pathed."""
    root = _tree(tmp_path, {**FILES,
                            "guide/hidden.md": "# Hidden\n\n[![t](images/a_thumb.png)](images/a.png)\n",
                            "guide/images/a_thumb.png": "png"})

    reshelve(root)

    hidden = (root / "unfiled" / "guide" / "hidden.md").read_text(encoding="utf-8")
    assert "[![t](../../guide/images/a_thumb.png)](../../guide/images/a.png)" in hidden


def test_a_linked_image_into_unfiled_is_listed_by_its_alt_text(tmp_path: Path) -> None:
    root = _tree(tmp_path, {
        "a.md": "# A\n\n[![The X shot](x_thumb.png)](unfiled/x.md)\n",
        "x_thumb.png": "png",
        "unfiled/x.md": "# X\n",
    })

    assert write_inbound(root) == 1

    assert read_rows(root / INBOUND) == [{
        "page": "a.md", "line": "3", "link_text": "The X shot",
        "orphan": "unfiled/x.md", "orphan_title": ""}]


def test_a_link_an_earlier_pass_left_behind_is_repaired_once(tmp_path: Path) -> None:
    """A tree the Phase 43 pass wrote: the thumbnail moved with the page, its link did not."""
    root = _tree(tmp_path, {
        "toc.yml": 'docs:\n  - title: "Start"\n    url: "guide/start.md"\n',
        "guide/start.md": "# Start\n",
        "guide/images/a.png": "png",
        "guide/images/a_thumb.png": "png",
        "guide/other.md": "# Other\n",
        "unfiled/guide/peer.md": "# Peer\n",
        "unfiled/guide/hidden.md": "# Hidden\n\n[![t](../../guide/images/a_thumb.png)](images/a.png)\n"
                                   "[peer](peer.md) [other](other.md) [gone](nowhere.md)\n",
    })

    result = reshelve(root)

    hidden = (root / "unfiled" / "guide" / "hidden.md").read_text(encoding="utf-8")
    assert "[![t](../../guide/images/a_thumb.png)](../../guide/images/a.png)" in hidden
    # Resolves already; moved from beside it; missing from both places.
    assert "[peer](peer.md) [other](../../guide/other.md) [gone](nowhere.md)" in hidden
    assert (result.removed, result.repaired) == (False, 2)
    assert reshelve(root).repaired == 0
