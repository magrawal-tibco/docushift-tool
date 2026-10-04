"""Unit tests for the engine-neutral transforms (design.md §6.4, §9.3-§9.5).

Everything here is a pure function or a per-unit object over a directory: no
catalog, no engine, no `state.db`. That is the point of the seam -- the rules
these tests pin are the ones all four engines share, and each one of them is a
corpus measurement rather than a convention.
"""

import re
from pathlib import Path, PurePosixPath

import pytest
from bs4 import BeautifulSoup

from docushift.engines.csh import CshEntry, CshFormat, CshSource, CshStatus
from docushift.models import SourceEngine
from docushift.transforms import (
    callouts,
    code,
    csh,
    deflists,
    fragments,
    headings,
    links,
    markdown,
    tables,
)
from docushift.transforms.assets import AssetCopier, AssetOutcome
from docushift.validation import references
from tests.unit.test_extractor import build_tree, page

# -- links (§6.4 step 3, points 1-3) ------------------------------------------


@pytest.mark.parametrize(
    ("raw", "kind"),
    [
        ("images/a.png", links.ReferenceKind.RELATIVE),
        ("https://docs.example/a", links.ReferenceKind.ABSOLUTE),
        ("mailto:support@example.com", links.ReferenceKind.ABSOLUTE),
        ("data:image/png;base64,AAA", links.ReferenceKind.ABSOLUTE),
        ("//cdn.example/a.js", links.ReferenceKind.ABSOLUTE),
        ("/shared/a.png", links.ReferenceKind.ROOTED),
        ("#section", links.ReferenceKind.FRAGMENT),
        ("   ", links.ReferenceKind.EMPTY),
    ],
)
def test_every_reference_lands_in_exactly_one_kind(raw: str, kind) -> None:
    assert links.classify(raw).kind is kind


def test_normalization_strips_the_fragment_decodes_and_fixes_slashes() -> None:
    """1,872 WebWorks references are 'missing' without this: 1,224 encoded, 648 `\\`."""
    reference = links.classify(r"..\Images\My%20Image.png?v=2#top")

    assert reference.path == "../Images/My Image.png"
    assert reference.fragment == "top"
    assert reference.query == "v=2"


def test_a_same_page_fragment_is_decoded_like_every_other_one() -> None:
    """The one branch that left it raw compared `%0A` against a real newline.

    A Flare anchor name can contain whitespace -- the corpus has one holding a
    pasted table -- and the link to it is written encoded, so the two sides never
    met. 6 of the `ems` tree's missing anchors were that, all of them present.
    """
    assert links.classify("#Event_Reason%0A%20Values").fragment == "Event_Reason\n Values"


def test_a_percent_encoded_hash_in_a_filename_is_not_the_fragment_separator() -> None:
    """The split happens before the decode, which is the whole reason for the order."""
    assert links.classify("a%23b.png").path == "a#b.png"


def test_a_climbing_reference_survives_as_a_leading_dotdot() -> None:
    """`Path.resolve()` would consult the disk and erase the escape (§6.4 step 3.5)."""
    resolved = links.resolve(PurePosixPath("Content"), "../../pdf/guide.pdf")

    assert str(resolved) == "../pdf/guide.pdf"
    assert links.escapes(resolved)


def test_a_literal_percent_is_escaped_before_anything_else() -> None:
    """104 corpus filenames already contain a `%`; the wrong order gives `%2520`."""
    assert links.encode("img/100%20done.png") == "img/100%2520done.png"
    assert links.encode("img/a b.png") == "img/a%20b.png"


def test_a_same_directory_sibling_is_emitted_bare() -> None:
    source = PurePosixPath("Content/topics/install.md")

    assert links.relative_to(source, PurePosixPath("Content/topics/config.md")) == "config.md"
    assert links.relative_to(source, PurePosixPath("Content/img/a.png")) == "../img/a.png"


def test_only_topic_suffixes_become_markdown() -> None:
    assert str(links.to_markdown("a/b.HTM")) == "a/b.md"
    assert str(links.to_markdown("a/b.png")) == "a/b.png"


# -- callouts -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "alert"),
    [
        ("Note", callouts.Alert.NOTE),
        ("tip", callouts.Alert.TIP),
        ("Danger", callouts.Alert.CAUTION),
        ("attention", callouts.Alert.IMPORTANT),
        ("Warning:", callouts.Alert.WARNING),
    ],
)
def test_source_labels_map_to_the_five_github_alerts(label: str, alert) -> None:
    assert callouts.alert_for(label) is alert


def test_an_unmapped_label_is_not_silently_a_note() -> None:
    """The caller reports it; the vocabulary never grows a guess."""
    assert callouts.alert_for("Editorial Comment") is None


def test_every_body_line_including_blanks_is_quoted() -> None:
    rendered = callouts.render(callouts.Alert.WARNING, "first\n\nsecond")

    assert rendered == "> [!WARNING]\n> first\n>\n> second"


# -- code fences --------------------------------------------------------------


def test_a_fence_outgrows_the_longest_backtick_run_it_contains() -> None:
    """API documentation quotes Markdown at itself; a 3-backtick fence ends early."""
    assert code.fence("a ``` b").startswith("````\n")
    assert code.fence("plain").startswith("```\n")


def test_a_fence_is_emitted_bare_unless_a_language_was_declared() -> None:
    assert code.fence("x") == "```\nx\n```"
    assert code.fence("x", "xml") == "```xml\nx\n```"


def test_inline_code_pads_when_the_body_touches_a_backtick() -> None:
    assert code.inline("`") == "`` ` ``"
    assert code.inline("a  b") == "`a b`"


# -- tables -------------------------------------------------------------------


def soup(html: str):
    return BeautifulSoup(html, "html.parser").find("table")


def test_a_spanned_table_is_not_gfm_safe() -> None:
    """GFM has no rowspan; converting anyway reads as a plausible, wrong table."""
    model = tables.read(soup("<table><tr><td colspan='2'>a</td></tr></table>"))

    assert tables.unsafe_reason(model) is tables.Unsafe.SPAN


def test_a_nested_tables_rows_belong_to_the_nested_table() -> None:
    """Counting them here would make every parent look ragged."""
    model = tables.read(soup(
        "<table><tr><td><table><tr><td>x</td><td>y</td></tr></table></td></tr></table>"
    ))

    assert len(model.rows) == 1
    assert tables.unsafe_reason(model) is tables.Unsafe.NESTED


def test_a_cell_wrapped_in_one_paragraph_is_safe_and_two_are_not() -> None:
    single = tables.read(soup("<table><tr><td><p>a</p></td><td><p>b</p></td></tr></table>"))
    double = tables.read(soup("<table><tr><td><p>a</p><p>b</p></td><td>c</td></tr></table>"))

    assert tables.is_gfm_safe(single)
    assert tables.unsafe_reason(double) is tables.Unsafe.MULTI_BLOCK


def test_a_passthrough_table_loses_the_generated_style_classes() -> None:
    """96.3% of the classes in the published EMS tree are this vocabulary."""
    rendered = tables.passthrough(soup(
        '<table class="TableStyle-Table">'
        '<tr><td class="TableStyle-Table-BodyE-Column1-Body1">a</td></tr></table>'
    ))

    assert "TableStyle" not in rendered
    assert "class=" not in rendered
    assert ">a<" in rendered


def test_a_passthrough_table_scrubs_its_root_and_not_only_its_descendants() -> None:
    """`find_all(True)` returns descendants only.

    The predecessor scrubs exactly that way, and every one of the 530
    `ebx_definitionList` classes in its output sits on a `<table>` element that
    its own cleaner walked straight past. This is that off-by-one, pinned.
    """
    rendered = tables.passthrough(soup('<table class="TableStyle-Table"><tr><td>a</td></tr></table>'))

    assert "TableStyle-Table" not in rendered


def test_a_passthrough_table_keeps_the_classes_that_carry_meaning() -> None:
    """`varname` and `MCXref xref` are what a later phase reads; the band is not."""
    rendered = tables.passthrough(soup(
        '<table class="TableStyle-Table"><tr>'
        '<td class="TableStyle-Table-Body-Body1"><span class="varname">EMSHOME</span></td>'
        '<td><a class="MCXref xref" href="x.htm">see</a></td>'
        "</tr></table>"
    ))

    assert 'class="varname"' in rendered
    assert 'class="MCXref xref"' in rendered
    assert "TableStyle" not in rendered


def test_a_passthrough_table_keeps_an_engines_own_vocabulary_when_it_passes_one() -> None:
    """In WebWorks the class name *is* the markup -- see `webworks.KEEP_CLASSES`."""
    html = '<table><tr><td><span class="Code">tibemsd</span></td></tr></table>'

    shared = tables.passthrough(soup(html))
    engine = tables.passthrough(soup(html), tables.SEMANTIC_CLASSES | frozenset({"Code"}))

    assert 'class="Code"' not in shared
    assert 'class="Code"' in engine


def test_a_scrubbed_class_is_removed_rather_than_emptied() -> None:
    """`class=""` is neither the old shape nor the clean one."""
    rendered = tables.passthrough(soup('<table><tr><td class="TableStyle-x">a</td></tr></table>'))

    assert 'class=""' not in rendered


def test_a_passthrough_table_drops_its_layout_attributes() -> None:
    """Phase 23 reversed Phase 21's deferral. Phase 21's argument was about
    sequencing -- verify the classes alone, so a regression cannot be ambiguous
    about which change caused it -- and the sequence has happened."""
    rendered = tables.passthrough(soup(
        '<table border="0" cellpadding="5" width="100%" class="TableStyle-Table">'
        '<tr><td valign="top">a</td></tr></table>'
    ))

    assert rendered == "<table><tr><td>a</td></tr></table>"


def test_a_passthrough_table_drops_the_stylesheet_nothing_published() -> None:
    """812 of these in the EMS tree, every one pointing at a `TableStyles` folder
    that exists nowhere under `output/`. The link checker reads `href` and `src`,
    so a dead reference inside a `style` attribute is invisible to it."""
    rendered = tables.passthrough(soup(
        '<table style="mc-table-style: '
        "url('../Resources/TableStyles/Table.css');\"><tr><td>a</td></tr></table>"
    ))

    assert "mc-table-style" not in rendered
    assert "style=" not in rendered


def test_a_generated_column_tooltip_goes_and_an_authored_one_stays() -> None:
    """`title` renders. 1,696 `<col title="C1">` means a reader hovering a column
    border is shown "C1" -- so it is dropped where the authoring tool generates it
    and kept where a human wrote it, which is not a distinction a single rule can
    make about the attribute alone."""
    rendered = tables.passthrough(soup(
        '<table><col title="C1"/><tr><td>'
        '<a href="x.htm" title="Read this first">go</a></td></tr></table>'
    ))

    assert 'title="C1"' not in rendered
    assert 'title="Read this first"' in rendered


def test_a_column_left_holding_nothing_is_removed_with_its_group() -> None:
    """Once the widths are gone a `<col/>` carries no information, and keeping
    1,696 empty ones would be keeping the skeleton of the decision."""
    rendered = tables.passthrough(soup(
        '<table><colgroup><col style="width: 169px;" title="C1"/></colgroup>'
        "<tr><td>a</td></tr></table>"
    ))

    assert "<col" not in rendered
    assert "<colgroup" not in rendered


def test_a_column_that_still_says_what_it_covers_survives() -> None:
    """`span` is structure, not styling -- it says how many columns the rule
    applies to, which is the same category as `colspan`."""
    rendered = tables.passthrough(soup(
        '<table><colgroup><col span="2" style="width: 40px;"/></colgroup>'
        "<tr><td>a</td></tr></table>"
    ))

    assert '<col span="2"/>' in rendered
    assert "width" not in rendered


def test_a_passthrough_table_keeps_what_the_cell_covers_and_where_it_points() -> None:
    """The keep-list is structure and content. A dropped `rowspan` would silently
    change the shape of the table, which is the failure `passthrough` exists to
    avoid in the first place."""
    rendered = tables.passthrough(soup(
        '<table><tr><th scope="col" id="h1" abbr="Nm">N</th></tr>'
        '<tr><td rowspan="2" colspan="3" headers="h1" bgcolor="#eee">'
        '<a href="p.md#x">p</a></td></tr></table>'
    ))

    for kept in ('scope="col"', 'id="h1"', 'rowspan="2"', 'colspan="3"',
                 'headers="h1"', 'href="p.md#x"'):
        assert kept in rendered
    assert "bgcolor" not in rendered
    assert "abbr=" not in rendered


def test_the_authoring_tools_own_plumbing_goes_whatever_it_is_called() -> None:
    """A keep-list, so `data-mc-*` and a stray `xmlns` need no naming -- which is
    the point, because the next engine's plumbing has a different name."""
    rendered = tables.passthrough(soup(
        '<table xmlns="http://www.w3.org/1999/xhtml">'
        '<tr><td data-mc-conditions="Default.Print" data-mc-autonum="Table 1">'
        "a</td></tr></table>"
    ))

    assert "data-mc" not in rendered
    assert "xmlns" not in rendered


def test_a_th_first_row_is_the_header_without_being_told() -> None:
    model = tables.read(soup("<table><tr><th>a</th><th>b</th></tr><tr><td>1</td><td>2</td></tr></table>"))

    assert model.header_row == 0
    rendered = tables.to_pipe(model, lambda cell: cell.get_text())
    assert rendered.splitlines()[0] == "| a | b |"


def test_a_headerless_table_gets_an_empty_header_not_a_promoted_row() -> None:
    """Promoting a data row relabels the column with a value."""
    model = tables.read(soup("<table><tr><td>1</td><td>2</td></tr></table>"))

    lines = tables.to_pipe(model, lambda cell: cell.get_text()).splitlines()
    assert lines == ["|  |  |", "| --- | --- |", "| 1 | 2 |"]


def test_a_pipe_and_a_newline_survive_a_cell() -> None:
    assert tables.escape("a | b\nc") == r"a \| b c"


def test_a_hard_break_in_a_cell_is_a_br_and_not_a_backslash() -> None:
    """The walk's break is `\\` plus a newline; folding only the newline printed
    `call to\\ [tibems...]` in 42 pipe rows (R8-05). At the cell's end it goes."""
    assert tables.escape("one\\\ntwo\\\n") == "one<br>two"
    assert render(
        "<table><tr><th>a</th><th>b</th></tr><tr><td>x</td><td>one<br/>two<br/></td></tr></table>"
    ).splitlines()[-1] == "| x | one<br>two |"


@pytest.mark.parametrize("cell", [
    "<ul><li><code>Error</code>: A human readable error message.</li>"
    "<li><code>Topic</code>: The current topic.</li></ul>",
    "<pre>INSERT INTO &lt;table_name&gt;\n  [(column1 [, ...])]</pre>",
    "<div><ul><li>one</li><li>two</li></ul></div>",
    "<div><p>First paragraph.</p><p>Second paragraph.</p></div>",
])
def test_a_cell_holding_a_list_or_code_anywhere_is_multi_block(cell: str) -> None:
    """Streaming 11.2.1's ClusterPubSubAdapter ran two bullets into one line and
    ActiveSpaces' SQL INSERT syntax became escaped prose: a lone `<ul>`, a lone
    `<pre>` and `div > ul` each counted as one block (R8-02, 2,183 cells)."""
    model = tables.read(soup(f"<table><tr><th>a</th><th>b</th></tr><tr><td>x</td><td>{cell}</td></tr></table>"))

    assert tables.unsafe_reason(model) is tables.Unsafe.MULTI_BLOCK


def test_a_cell_holding_a_list_passes_through_with_its_items_apart() -> None:
    rendered = render(
        "<table><tr><th>a</th><th>b</th></tr>"
        "<tr><td>x</td><td><ul><li>one</li><li>two</li></ul></td></tr></table>"
    )

    assert "<li>one</li><li>two</li>" in rendered
    assert "onetwo" not in rendered


def test_a_passthrough_table_has_no_blank_and_no_indented_line() -> None:
    """A GFM HTML block ends at its first blank line, and the next line, indented
    by Flare's tabs, rendered as a code block holding a literal `</td>`: EMS 10.4.0
    `ems-message-properti.md` and 153 other tables (R8-03). The `<col>`s `scrub`
    removes leave their indentation behind as separate text nodes."""
    rendered = render(
        '<table>\n\t<col style="width: 169px;" />\n\t<col style="width: 300px;" />\n'
        '\t<tr>\n\t\t<td rowspan="2">\n\t\t\t<p>Sent by TIBCO Rendezvous.\n\n\n'
        "\t\t\t  </p>\n\t\t</td>\n\t\t<td>y</td>\n\t</tr>\n\t<tr>\n\t\t<td>z</td>\n\t</tr>\n</table>"
    )

    assert not re.search(r"\n[ \t]*\n", rendered)
    assert not re.search(r"^(?: {4}|\t)", rendered, re.MULTILINE)
    assert "<p>Sent by TIBCO Rendezvous.\n</p>" in rendered


def test_a_pre_in_a_passthrough_table_keeps_its_blank_lines_as_content() -> None:
    """Whitespace is content in a `<pre>`, so an empty line is written as the
    newline it stands for rather than folded away -- and is no longer empty."""
    rendered = render(
        "<table><tr><td rowspan='2'><pre>first\n\n    indented</pre></td><td>y</td></tr>"
        "<tr><td>z&nbsp;&nbsp;w</td></tr></table>"
    )

    assert "<pre>first\n&#10;    indented</pre>" in rendered
    assert not re.search(r"\n[ \t]*\n", rendered)
    # `&nbsp;` is content too; WebWorks indents code lines with it.
    assert "z\xa0\xa0w" in rendered


def test_a_pipe_table_keeps_its_caption_as_an_italic_line_ahead_of_it() -> None:
    """TRA 5.13.0 `Advanced_Panel_1.md` lost "Processing Instruction": `read`
    sees rows and cells, and 237 captions vanished on the pipe path (R8-06)."""
    rendered = render(
        "<table><caption><p class='TableTitle'><a name='T1'></a>Processing Instruction</p></caption>"
        "<tr><th>Field</th></tr><tr><td>Name</td></tr></table>"
    )

    assert rendered == '<a id="T1"></a>\n\n*Processing Instruction*\n\n| Field |\n| --- |\n| Name |'
    # The target is taken from the tag, not from the collapsed caption text: one
    # EMS target has a pasted table, newlines and all, in its name.
    pasted = render(
        "<table><caption><a name='Event_Value_\n   _Description_'></a>Values</caption>"
        "<tr><th>Field</th></tr><tr><td>Name</td></tr></table>"
    )
    assert pasted.startswith('<a id="Event_Value_\n   _Description_"></a>\n\n*Values*')


def test_a_thead_row_of_td_cells_is_the_header() -> None:
    """TRA 5.13.0 `tramodify_Utility` showed "Parameter | Description" as a data
    row under a blank header: only an all-`<th>` row counted (R8-06)."""
    model = tables.read(soup(
        "<table><thead><tr><td>Parameter</td><td>Description</td></tr></thead>"
        "<tbody><tr><td>-v</td><td>Verbose.</td></tr></tbody></table>"
    ))

    assert model.header_row == 0
    assert tables.to_pipe(model, lambda cell: cell.get_text()).splitlines() == [
        "| Parameter | Description |", "| --- | --- |", "| -v | Verbose. |",
    ]


# -- the markdown walk (§5.1, invariant 13) -----------------------------------


def render(html: str, renderer: markdown.Renderer | None = None) -> str:
    return (renderer or markdown.Renderer()).render(markdown.parse(html).body)


def test_a_cdata_section_survives_the_parser_as_its_own_text() -> None:
    """`lxml` deletes `<![CDATA[...]]>` outright -- CDATA is not a thing in HTML.

    130 files of a 3,411-file sample carry 300 sections and 170 of them hold only
    the space between a word and the `<span>` after it, so the parser's answer is
    "ensure that thelibjvm library".
    """
    assert render("<p>ensure that the<![CDATA[ ]]><span>libjvm</span> library</p>") == (
        "ensure that the libjvm library"
    )


def test_markup_inside_a_cdata_section_stays_text() -> None:
    """None of the 300 sampled sections hold markup, and an unsampled one is text.

    Only the `<` is escaped: a bare `>` mid-line starts nothing, and one that leads
    a line is `escape_leading`'s to catch.
    """
    assert render("<p><![CDATA[<b>literal</b>]]></p>") == r"\<b>literal\</b>"


def test_a_comment_is_not_prose() -> None:
    """`Comment` is a `NavigableString` subclass, so the obvious isinstance is true.

    Corpus topics carry commented-out markup beside their content; emitting it is
    the difference between a paragraph and a paragraph followed by a stylesheet.
    """
    assert markdown.is_text(BeautifulSoup("<p>x</p>", "html.parser").p.string)
    assert render("<p>kept<!-- .style { color: red } --></p>") == "kept"


def test_an_ordered_list_honours_its_start() -> None:
    """A procedure that resumes at step 3 is numbered from 3 (R5-02)."""
    assert render("<ol start='3'><li>Run it.</li><li>Check it.</li></ol>") == (
        "3. Run it.\n4. Check it."
    )
    assert render("<ol start='x'><li>Run it.</li></ol>") == "1. Run it."
    assert render("<ul start='3'><li>Run it.</li></ul>") == "- Run it."


def test_a_lettered_list_keeps_its_letters_as_html_around_markdown() -> None:
    """DocBook's `numeration="loweralpha"` sub-steps read "2" where the prose
    says "step b": GFM draws only `1.` (R8-14, 980 lists in Streaming). The
    blank lines keep each item's body Markdown inside the HTML."""
    rendered = render(
        '<ol><li><p>Configure:</p><ol type="a"><li><p>Open <b>File</b>.</p></li>'
        "<li><p>Save.</p></li></ol></li></ol>"
    )

    assert rendered == (
        "1. Configure:\n\n"
        '   <ol type="a">\n   <li>\n\n   Open **File**.\n\n   </li>\n'
        "   <li>\n\n   Save.\n\n   </li>\n   </ol>"
    )
    assert render('<ol type="i" start="4"><li>Four.</li></ol>') == (
        '<ol type="i" start="4">\n<li>\n\nFour.\n\n</li>\n</ol>'
    )
    # `1` is what GFM draws anyway, and an unordered list has no numbering.
    assert render('<ol type="1"><li>One.</li></ol>') == "1. One."
    assert render('<ul type="a"><li>One.</li></ul>') == "- One."


def test_a_break_at_the_end_of_a_block_prints_nothing() -> None:
    """`strip` took the break's newline and left its backslash: DocBook's
    `<br class="figure-break">` alone made a paragraph of `\\`, six of them in
    Streaming 11.1.0 `sec-ldap.md` (R8-05, 2,064 in the families)."""
    assert render("<p>Before.<br/></p><p><br class='figure-break'/></p><p>After.</p>") == (
        "Before.\n\nAfter."
    )
    assert render("<p>one<br/>two</p>") == "one\\\ntwo"


def test_a_break_at_the_end_of_bold_moves_outside_the_markers() -> None:
    """`**Warning\\**`: the backslash escaped the closing marker (R8-05)."""
    assert render("<p><b>Warning: Action required<br/></b>You must update.</p>") == (
        "**Warning: Action required**\\\nYou must update."
    )


def test_a_break_in_a_heading_is_a_space() -> None:
    """A heading is one line; a break split it into a heading and a paragraph."""
    assert render("<h2>Part one<br/>part two</h2>") == "## Part one part two"


def test_content_written_straight_into_a_list_with_no_item_leads_it() -> None:
    """ActiveSpaces 5.2.0 `Registering-the-ActiveSpaces-JDBC-Driver...`: the
    sentence and the code sit directly in `<ol class="steps">`, and the output
    was `**Procedure**` over nothing (R8-01)."""
    rendered = render(
        '<ol class="steps"><p>Use the following code snippet:</p>'
        "<pre>// Register the ActiveSpaces JDBC Driver\nClass.forName(name);</pre></ol>"
    )

    assert rendered == (
        "Use the following code snippet:\n\n"
        "```\n// Register the ActiveSpaces JDBC Driver\nClass.forName(name);\n```"
    )


def test_content_between_list_items_belongs_to_the_item_before_it() -> None:
    """EMS 10.5.1 `optional-post-instal2.htm` lost its note between steps 2 and 3,
    and TRA 5.13.0 `Upgrade_Security_Vendor` both FIPS branches, a `<ul>` written
    straight into a `<ul>` (R8-01)."""
    steps = render(
        "<ol><li>Run the script.</li><p><div class='note'>This script only works when your "
        "EMS_HOME path ends with ems/10.5.</div></p><li>Restart the server.</li></ol>"
    )
    nested = render(
        "<ul><li>Use the default Java security vendor.</li>"
        "<ul><li>Set: TIBCO_SECURITY_VENDOR = j2se</li></ul></ul>"
    )

    assert steps == (
        "1. Run the script.\n\n"
        "   This script only works when your EMS_HOME path ends with ems/10.5.\n\n"
        "2. Restart the server."
    )
    assert nested == "- Use the default Java security vendor.\n\n  - Set: TIBCO_SECURITY_VENDOR = j2se"


@pytest.mark.parametrize(("html", "expected"), [
    ("<p>are <b>tcp</b> and <b>ssl</b><b>.</b> For example</p>",
     "are **tcp** and **ssl**<!-- -->**.** For example"),
    ("<p><b>Default value:</b><i>none</i></p>", "**Default value:**<!-- -->*none*"),
    ("<p><code>-user &lt;user_name&gt;</code><code>-password &lt;pwd&gt;</code></p>",
     "`-user <user_name>`<!-- -->`-password <pwd>`"),
    # A closer after punctuation cannot close against a word, nor an opener
    # before punctuation open after one.
    ("<p><b>Note:</b>restart it.</p>", "**Note:**<!-- -->restart it."),
    ("<p>the<b>(optional)</b> flag</p>", "the<!-- -->**(optional)** flag"),
    # Nothing is added where the runs already read apart.
    ("<p><b>a</b> <i>b</i> <code>c</code>, <b>d</b>.</p>", "**a** *b* `c`, **d**."),
])
def test_adjacent_inline_runs_stay_apart(html: str, expected: str) -> None:
    """`**ssl****.**` and `**Default value:***none*` read as literal asterisks,
    and two code spans as one holding two backticks: 353 and 849 in the families
    (R8-07). An empty comment between them renders as nothing."""
    assert render(html) == expected


def test_adjacent_runs_in_a_heading_keep_its_slug() -> None:
    """The seam is a tag, so the slug rule strips it with the rest."""
    rendered = render("<h2><b>ssl</b><b>Config</b></h2>")

    assert rendered == "## **ssl**<!-- -->**Config**"
    assert references.anchors(rendered) == {"sslconfig"}


def test_embedded_media_is_counted_and_linked_when_its_url_is_absolute() -> None:
    """An `<iframe>` of a video reached the output as nothing (R8-13)."""
    renderer = markdown.Renderer()
    rendered = render(
        '<p>Watch:</p><iframe src="https://www.youtube.com/embed/x"></iframe>'
        '<video src="clip.mp4">Your browser cannot play this.</video>',
        renderer,
    )

    assert rendered == (
        "Watch:\n\n[https://www.youtube.com/embed/x](https://www.youtube.com/embed/x)"
        "Your browser cannot play this."
    )
    assert renderer.unrendered == {"iframe": 1, "video": 1}
    assert markdown.Renderer().unrendered == {}


def test_a_passthrough_table_gets_its_references_resolved() -> None:
    """Invariant 13 does not stop at the edge of a pipe table.

    43% of Flare's tables cannot be a GFM one, and their HTML would otherwise ship
    `src="images/x.png"` -- a path in the *source* layout -- in the one branch
    where no hook was consulted.
    """

    class Resolving(markdown.Renderer):
        def image(self, tag):
            return "/assets/x.png"

        def link(self, tag):
            return None if tag.get("href") == "gone.htm" else "/docs/there.md"

    rendered = render(
        "<table><tr><td colspan='2'><img src='images/x.png'/>"
        "<a href='there.htm'>here</a><a href='gone.htm'>orphan</a></td></tr></table>",
        Resolving(),
    )

    assert 'src="/assets/x.png"' in rendered
    assert 'href="/docs/there.md"' in rendered
    # The text was authored and stays; only the claim that it leads somewhere goes.
    assert "gone.htm" not in rendered
    assert ">orphan<" in rendered


# -- anchor targets (Phase 16) ------------------------------------------------


def test_a_named_anchor_in_a_passthrough_table_survives_as_an_id() -> None:
    """1,092 of the `ems` tree's 1,763 missing anchors were targets in a table.

    `rewrite` unwrapped every href-less `<a>` as a link that leads nowhere. Most
    of them were not links at all -- they were the destinations the surviving
    `href="#ID-2FC4B4A1"` elsewhere in the corpus point at.
    """
    rendered = render(
        "<table><tr><td colspan='2'><a name='ID-2FC4B4A1'></a>Error 42</td></tr></table>"
    )

    assert '<a id="ID-2FC4B4A1"></a>' in rendered
    # `name=` is what HTML5 dropped, and what an AEM renderer will not resolve.
    assert "name=" not in rendered
    assert "Error 42" in rendered


def test_an_anchor_with_neither_href_nor_target_is_still_unwrapped() -> None:
    """The old behaviour, kept: an `<a>` that is neither a link nor a place."""
    rendered = render("<table><tr><td colspan='2'><a class='x'>words</a></td></tr></table>")

    assert "words" in rendered
    assert "<a" not in rendered


def test_a_named_anchor_in_prose_emits_its_target() -> None:
    """`_anchor` returned `""` for an empty one, deleting the destination."""
    assert render("<p><a name='ID-7B'></a>See below.</p>") == '<a id="ID-7B"></a>See below.'


def test_a_named_anchor_in_a_heading_is_hoisted_above_it() -> None:
    """Left in the line it would change the slug it was meant to sit beside.

    `slugify_heading` reads the raw title, so `## <a id="X"></a>Configuring Users`
    stops resolving `#configuring-users` -- breaking fragments that work today in
    the act of fixing 424 that do not.
    """
    rendered = render("<h2><a name='ID-2F'></a>Configuring Users</h2>")

    assert rendered == '<a id="ID-2F"></a>\n\n## Configuring Users'
    # Hoisting still matters, and for exactly the reason in the docstring: left in
    # the line, the marker's text would be folded into the heading's own slug.
    # The marker is no longer itself an anchor, though -- the platform ignores it
    # (Phase 29) -- so `#id-2f` is a fragment nothing can resolve.
    assert references.anchors(rendered) == {"configuring-users"}


def test_a_tables_own_target_is_hoisted_in_front_of_the_pipe_table() -> None:
    """Flare writes it between `<col>` and `<thead>`, which is in no cell.

    `tables.read` sees rows and cells, so a pipe table drops it -- while the
    passthrough branch, which walks the whole subtree, always kept it.
    """
    rendered = render(
        "<table><col/><a name='ID-00002B38'></a>"
        "<thead><tr><th>Name</th></tr></thead>"
        "<tbody><tr><td>host</td></tr></tbody></table>"
    )

    assert rendered.startswith('<a id="ID-00002B38"></a>\n\n| Name |')


def test_a_named_anchor_inside_a_code_span_is_hoisted_out_of_it() -> None:
    """100 of the `ems` tree's missing anchors were a target inside `<code>`.

    Backticks are not a place, so the marker leads the span the way it leads a
    heading -- and the span renders exactly as it did before.
    """
    rendered = render("<p><code><a name='tibemsd_P'></a>tibemsd </code> is the daemon.</p>")

    assert rendered == '<a id="tibemsd_P"></a>`tibemsd` is the daemon.'


def test_an_anchor_carrying_both_a_target_and_a_link_keeps_both() -> None:
    """Zero of the `ems` corpus's 49,587 links do this. Correctness, not coverage."""
    rendered = render("<p><a name='ID-9C' href='there.htm'>here</a></p>", Linking())

    assert rendered == '<a id="ID-9C"></a>[here](/docs/there.htm)'


# -- the code-span link swallow (Phase 8) -------------------------------------


class Linking(markdown.Renderer):
    """A hook that resolves everything except `gone.htm`, which it refuses."""

    def link(self, tag):
        href = str(tag.get("href") or "")
        return None if href == "gone.htm" else f"/docs/{href}"


def test_a_link_alone_in_a_code_span_inverts_the_nesting() -> None:
    """The 7,470 of 7,654 that GFM can express, and it expresses them by swapping.

    Rendering a code span from its text meant the `<a>` never reached `link()`, so
    the reference was neither resolved nor reported as dangling -- never dropped,
    never classified. Every one of the 7,470 is the span's direct child.
    """
    assert render("<p><code><a href='t.htm'>tibems_status</a></code></p>", Linking()) == (
        "[`tibems_status`](/docs/t.htm)"
    )


def test_the_url_comes_from_the_hook_and_never_from_the_href() -> None:
    """Invariant 13 does not stop at a code span, any more than at a pipe table."""
    assert render("<p><code><a href='t.htm'>x</a></code></p>", Linking()) == (
        "[`x`](/docs/t.htm)"
    )
    assert render("<p><code><a href='t.htm'>x</a></code></p>") == "[`x`](t.htm)"


def test_a_refused_link_in_a_code_span_renders_exactly_what_it_used_to() -> None:
    """A `javascript:` skin button or an unresolvable target. This adds links only."""
    plain = render("<p><code>drop</code></p>")
    assert render("<p><code><a href='gone.htm'>drop</a></code></p>", Linking()) == plain


def test_a_bracket_inside_the_code_does_not_close_the_link_text() -> None:
    """CommonMark binds a code span tighter than a link, so `]` is safe unescaped.

    Asserted rather than assumed: if it were not true the emitted link text would
    end at the bracket and the remainder would render as prose.
    """
    assert render("<p><code><a href='t.htm'>a]b</a></code></p>", Linking()) == (
        "[`a]b`](/docs/t.htm)"
    )


def test_a_span_shared_between_code_and_a_link_is_emitted_as_html() -> None:
    """184 of the 7,654. GFM cannot put a link inside a code span; HTML can.

    `<code>mode=<a>sync</a></code>` is one code token, part of which is a link.
    Splitting it into two adjacent spans would invent typography the author did
    not write, so this takes `_KEEP_AS_HTML`'s branch for `_KEEP_AS_HTML`'s reason.
    """
    assert render("<p><code>mode=<a href='s.htm'>sync</a></code></p>", Linking()) == (
        '<code>mode=<a href="/docs/s.htm">sync</a></code>'
    )


def test_a_shared_span_is_rebuilt_rather_than_dumped() -> None:
    """The authoring tool's classes and wrappers do not reach the output."""
    rendered = render(
        "<p><code><span class='memberNameLink'><a href='s.htm'>go</a></span>()</code></p>",
        Linking(),
    )
    assert rendered == '<code><a href="/docs/s.htm">go</a>()</code>'


def test_a_shared_span_keeps_the_words_of_a_link_the_hook_refused() -> None:
    assert render("<p><code>see <a href='gone.htm'>it</a></code></p>", Linking()) == (
        "<code>see it</code>"
    )


def test_two_links_in_one_code_span_both_survive() -> None:
    """Eight spans in the measured corpus, and the branch that would have lost them."""
    rendered = render(
        "<p><code><a href='c.htm'>commit</a> and <a href='a.htm'>autocommit</a></code></p>",
        Linking(),
    )
    assert rendered == (
        '<code><a href="/docs/c.htm">commit</a> and <a href="/docs/a.htm">autocommit</a></code>'
    )


def test_a_code_span_with_no_link_is_untouched() -> None:
    assert render("<p><code>plain</code></p>", Linking()) == "`plain`"


def test_a_link_inside_a_fence_keeps_its_words_and_is_counted() -> None:
    """The decision, pinned rather than the accident.

    4,860 of the 12,514 swallowed references are inside a `<pre>`, and GFM has no
    syntax that puts a link inside a fence. Emitting the block as passthrough HTML
    -- one call, exactly what `table` does -- would recover them and cost every
    reader a copy-pasteable code block. The residue is counted instead, and the
    driver reports it as `CODE_LINK_FLATTENED`.
    """
    renderer = Linking()
    rendered = render(
        "<pre><a href='t.htm'>tibems_status</a> tibems_GetAllowClose(void);</pre>", renderer
    )
    assert rendered == "```\ntibems_status tibems_GetAllowClose(void);\n```"
    assert renderer.flattened_links == 1


def test_a_fence_with_no_link_counts_nothing() -> None:
    renderer = Linking()
    render("<pre>plain</pre>", renderer)
    assert renderer.flattened_links == 0


# -- assets (§6.4 steps 3-7, invariant 13) ------------------------------------


def flare_unit(tmp_path: Path) -> Path:
    """A Flare output root with one of each of the five step-3 branches in it."""
    return build_tree(tmp_path / "tree", {
        "guide/Data/HelpSystem.xml": "<x/>",
        "guide/Content/topic.htm": page(),
        "guide/Content/images/shot.png": "png",
        "guide/Content/images/Cased.PNG": "png",
        "guide/Skins/Default/logo.gif": "gif",
        "guide/Content/images/never-referenced.png": "orphan",
        "pdf/guide.pdf": "pdf",
    }) / "guide"


def copier_for(tmp_path: Path) -> tuple[AssetCopier, Path]:
    root = flare_unit(tmp_path)
    return AssetCopier(root, SourceEngine.FLARE, tmp_path / "out" / "guide"), root


def test_a_resolved_reference_produces_a_link_and_a_copy_from_one_call(tmp_path: Path) -> None:
    """Invariant 13: the copy set *is* what the Markdown references."""
    copier, root = copier_for(tmp_path)

    resolution = copier.resolve(
        root / "Content" / "topic.htm", PurePosixPath("Content/topic.md"), "images/shot.png"
    )

    assert resolution.outcome is AssetOutcome.RESOLVED
    assert resolution.url == "images/shot.png"
    assert resolution.target == PurePosixPath("Content/images/shot.png")
    assert copier.copy() == 1
    assert (tmp_path / "out" / "guide" / "Content" / "images" / "shot.png").is_file()


def test_a_dangling_reference_emits_neither_link_nor_copy_and_is_counted(tmp_path: Path) -> None:
    copier, root = copier_for(tmp_path)

    resolution = copier.resolve(
        root / "Content" / "topic.htm", PurePosixPath("Content/topic.md"), "images/gone.png"
    )

    assert resolution.outcome is AssetOutcome.DANGLING
    assert not resolution.emits
    assert copier.copy_set == {}
    # Grouped by top segment, not just totalled: 2,706 of Flare's 2,905 come
    # from one tree that is broken in its own source.
    assert copier.counts.dangling_by_segment == {"Content": 1}


def test_chrome_is_dropped_before_it_can_be_reported_missing(tmp_path: Path) -> None:
    """Skin is checked first; otherwise 76.2% of WebWorks goes in the failure column."""
    copier, root = copier_for(tmp_path)

    present = copier.resolve(
        root / "Content" / "topic.htm", PurePosixPath("Content/topic.md"), "../Skins/Default/logo.gif"
    )
    absent = copier.resolve(
        root / "Content" / "topic.htm", PurePosixPath("Content/topic.md"), "../Skins/Default/gone.gif"
    )

    assert present.outcome is AssetOutcome.SKIN
    assert absent.outcome is AssetOutcome.SKIN
    assert copier.counts.dangling == 0
    assert copier.counts.skin == 2


def test_an_escaping_reference_is_handed_on_with_its_resolved_source_path(tmp_path: Path) -> None:
    """§10.7: Stage 7 routes it; this stage does not emit it. 279 in the Flare sample."""
    copier, root = copier_for(tmp_path)

    resolution = copier.resolve(
        root / "Content" / "topic.htm", PurePosixPath("Content/topic.md"), "../../pdf/guide.pdf"
    )

    assert resolution.outcome is AssetOutcome.ESCAPED
    assert not resolution.emits
    assert copier.escaped[0][0] == root.parent / "pdf" / "guide.pdf"


def test_an_external_reference_is_emitted_unchanged_and_never_copied(tmp_path: Path) -> None:
    copier, root = copier_for(tmp_path)

    resolution = copier.resolve(
        root / "Content" / "topic.htm", PurePosixPath("Content/topic.md"), "https://docs.example/a.png"
    )

    assert resolution.outcome is AssetOutcome.EXTERNAL
    assert resolution.url == "https://docs.example/a.png"
    assert copier.copy_set == {}


def test_case_is_checked_and_not_corrected(tmp_path: Path) -> None:
    """Works on this Windows cache, 404s after publishing. 14 corpus-wide."""
    copier, root = copier_for(tmp_path)

    resolution = copier.resolve(
        root / "Content" / "topic.htm", PurePosixPath("Content/topic.md"), "images/cased.png"
    )

    assert resolution.outcome is AssetOutcome.RESOLVED
    assert resolution.case_mismatch
    # Not corrected: the reference's own spelling is what gets emitted.
    assert resolution.url == "images/cased.png"


def test_assets_keep_their_source_relative_path(tmp_path: Path) -> None:
    """Flattening collides 5,328 times inside one Flare root."""
    copier, root = copier_for(tmp_path)

    copier.resolve(root / "Content" / "topic.htm", PurePosixPath("Content/topic.md"), "images/shot.png")

    assert list(copier.copy_set) == [PurePosixPath("Content/images/shot.png")]


def test_orphans_are_reported_and_never_copied(tmp_path: Path) -> None:
    """54.6% of Flare's images. Chrome and topics are not orphans."""
    copier, root = copier_for(tmp_path)
    copier.resolve(root / "Content" / "topic.htm", PurePosixPath("Content/topic.md"), "images/shot.png")

    orphans = copier.orphans()

    names = [str(path) for path, _size in orphans]
    assert names == ["Content/images/Cased.PNG", "Content/images/never-referenced.png"]
    assert copier.copy() == 1


def test_one_asset_referenced_twice_is_copied_once(tmp_path: Path) -> None:
    copier, root = copier_for(tmp_path)

    copier.resolve(root / "Content" / "topic.htm", PurePosixPath("Content/topic.md"), "images/shot.png")
    copier.resolve(root / "Content" / "other.htm", PurePosixPath("Content/other.md"), "images/shot.png")

    assert len(copier.copy_set) == 1
    assert copier.counts.resolved == 2


# -- CSH (§9.3-§9.5) ----------------------------------------------------------


def source(doc_set: str, *entries: tuple[str, str, str], status=CshStatus.OK) -> CshSource:
    return CshSource(
        path=Path(doc_set) / "Data" / "Alias.xml",
        fmt=CshFormat.FLARE_ALIAS,
        status=status,
        entries=[CshEntry(identifier, link, anchor) for identifier, link, anchor in entries],
        doc_set=doc_set,
    )


def test_an_identifier_resolves_inside_its_own_doc_set_first() -> None:
    sources = [source("main", ("install", "topics/Install.htm", ""))]
    output = {"main/topics/Install.htm": "topics/Install.md"}

    resolved = csh.resolve(sources, output)

    assert resolved.entries == {"install": "topics/Install.md"}
    assert resolved.rescued == 0
    assert resolved.unresolved == []


def test_the_version_wide_fallback_rescues_a_relnotes_alias_that_resolves_at_zero() -> None:
    """22% of Flare links dangle in their own doc-set; 205 in one BW release-notes file."""
    sources = [
        source("main", ("a", "topics/A.htm", ""), ("b", "topics/B.htm", "")),
        source("relnotes", ("install", "topics/Install.htm", "")),
    ]
    output = {
        "main/topics/A.htm": "topics/A.md",
        "main/topics/B.htm": "topics/B.md",
        "main/topics/Install.htm": "topics/Install.md",
    }

    resolved = csh.resolve(sources, output)

    assert resolved.entries["install"] == "topics/Install.md"
    assert resolved.rescued == 1


def test_the_anchor_is_appended_to_the_path_under_the_flat_schema() -> None:
    sources = [source("main", ("palette", "topics/Start.htm", "adb.palette"))]

    resolved = csh.resolve(sources, {"main/topics/Start.htm": "topics/Start.md"})

    assert resolved.entries == {"palette": "topics/Start.md#adb.palette"}


def test_case_only_identifier_collisions_stay_two_entries() -> None:
    """`GatewayInstances` and `gatewayInstances` are two live targets in BC 7.4/7.5."""
    sources = [source("main", ("GatewayInstances", "a.htm", ""), ("gatewayInstances", "b.htm", ""))]

    resolved = csh.resolve(sources, {"main/a.htm": "a.md", "main/b.htm": "b.md"})

    assert resolved.entries == {"GatewayInstances": "a.md", "gatewayInstances": "b.md"}


def test_an_ambiguous_identifier_takes_the_doc_set_with_the_most_entries() -> None:
    """`also` has nowhere to go in a flat map, so the winner has to be deterministic."""
    sources = [
        source("zz-main", ("shared", "a.htm", ""), ("other", "b.htm", "")),
        source("aa-side", ("shared", "a.htm", "")),
    ]
    output = {
        "zz-main/a.htm": "zz-main/a.md",
        "zz-main/b.htm": "zz-main/b.md",
        "aa-side/a.htm": "aa-side/a.md",
    }

    resolved = csh.resolve(sources, output)

    # Two entries beats one, so the alphabetically earlier doc-set loses -- which
    # is the point: the main help output wins over a sidecar, not the first name.
    assert resolved.entries["shared"] == "zz-main/a.md"
    assert [entry.identifier for entry in resolved.ambiguous] == ["shared"]
    assert resolved.ambiguous[0].dropped == ("aa-side/a.md",)


def test_the_same_target_from_two_doc_sets_is_not_a_conflict() -> None:
    sources = [source("main", ("x", "a.htm", "")), source("side", ("x", "../main/a.htm", ""))]

    resolved = csh.resolve(sources, {"main/a.htm": "a.md"})

    assert resolved.entries == {"x": "a.md"}
    assert resolved.ambiguous == []


def test_an_identifier_matching_no_produced_topic_is_kept_not_dropped() -> None:
    """Invariant 10: dropping it makes a broken Help button unfindable."""
    sources = [source("main", ("gone", "topics/Gone.htm", ""))]

    resolved = csh.resolve(sources, {})

    assert resolved.entries == {}
    assert resolved.unresolved[0].identifier == "gone"
    assert resolved.tallies["main"] == (1, 0)


def test_an_unreadable_source_is_counted_and_skipped() -> None:
    sources = [source("main", ("x", "a.htm", ""), status=CshStatus.UNPARSEABLE)]

    resolved = csh.resolve(sources, {"main/a.htm": "a.md"})

    assert resolved.empty
    assert resolved.unusable == {"unparseable": 1}


def test_a_digit_only_identifier_survives_as_a_string() -> None:
    """834 of 11,054 Flare names are digit-only; YAML 1.1 turns `1234` into an int."""
    rendered = csh.render({"1234": "a.md", "6.2": "b.md"})

    assert rendered == '"1234": "a.md"\n"6.2": "b.md"\n'


def test_a_version_with_no_resolved_identifier_gets_no_file(tmp_path: Path) -> None:
    """An empty map file is indistinguishable from a failed run (§9.4)."""
    target = tmp_path / "csh.yml"
    target.write_text("stale", encoding="utf-8")

    assert csh.write(target, {}) is False
    assert not target.exists()


def test_frontmatter_is_always_a_list_of_quoted_strings() -> None:
    assert csh.frontmatter_value(["only"]) == '["only"]'
    assert csh.frontmatter_value(["a", "1234"]) == '["a", "1234"]'


def test_identifiers_are_owned_by_source_path_before_conversion_runs() -> None:
    """§9.5: they reach the topic's first and only write."""
    sources = [source("main", ("a", "topics/T.htm#x", ""), ("b", "topics/T.htm", ""))]

    owned = csh.identifiers_by_source(sources)

    assert owned == {"main/topics/T.htm": ["a", "b"]}


# -- headings and definition lists (Phase 27) ---------------------------------


def _levels(html: str) -> list[str]:
    soup = markdown.parse(html)
    body = soup.body or soup
    headings.normalize(body)
    return [tag.name for tag in body.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])]


@pytest.mark.parametrize(
    ("levels", "expected"),
    [
        # The reported page: `Concepts/Sample-Programs.htm`. The `h6` sections are
        # second-level sections whose author picked the tag that looked right.
        ([1, 2, 2, 6, 6, 2, 6, 6], [1, 2, 2, 3, 3, 2, 3, 3]),
        # EMS `users-guide/DisasterRecovery.htm`, the whole page.
        ([1, 4, 4, 4], [1, 2, 2, 2]),
        # EMS `api/javadoc/javax/jms/package-summary.html`: a real two-deep tree
        # under a jump, which has to keep both of its levels.
        ([1, 3, 3, 4, 4, 3], [1, 2, 2, 3, 3, 2]),
        # ActiveSpaces `Administration/Using-User-Defined-TIBCO-FTL-Certificates.htm`.
        ([1, 2, 2, 4, 4, 4], [1, 2, 2, 3, 3, 3]),
        # Already sequential: the rule must be the identity on correct input, which
        # is what makes the 24,781-file re-conversion diffable.
        ([1, 2, 3, 2, 3, 4], [1, 2, 3, 2, 3, 4]),
        # A page whose shallowest heading is `h2` keeps it. Promoting to `h1` would
        # hand 921 DocBook pages a title level they never had.
        ([2, 4, 4, 3], [2, 3, 3, 3]),
        # The accepted limit: deep before shallow across a gap merges two levels.
        ([1, 4, 2], [1, 2, 2]),
    ],
)
def test_heading_levels_are_compacted_to_the_depth_the_page_nests_to(
    levels: list[int], expected: list[int]
) -> None:
    assert headings.compact(levels) == expected


def test_renumbering_moves_the_tag_and_nothing_else() -> None:
    """Text, order and `id` survive, because every slug and fragment depends on them."""
    html = '<body><h1 id="top">Sample Programs</h1><h6 id="java">Java Vector Store</h6></body>'
    soup = markdown.parse(html)
    body = soup.body

    assert headings.normalize(body) == 1
    assert [(t.name, t.get("id"), t.get_text()) for t in body.find_all(["h1", "h2"])] == [
        ("h1", "top", "Sample Programs"),
        ("h2", "java", "Java Vector Store"),
    ]


def test_a_heading_the_engine_will_consume_takes_no_rung() -> None:
    """DocBook's `<h3>Note</h3>` is an alert label, not a section (§5.6.7).

    Without the predicate it takes depth 2 and the real `h2` below it is pinned
    there too -- which is how the raw-HTML census charged Streaming with 4,990
    skipped levels it does not have.
    """
    html = ('<body><h1>Adapter</h1><div class="note"><h3>Note</h3><p>x</p></div>'
            '<h2>Introduction</h2><h4>Detail</h4></body>')
    soup = markdown.parse(html)
    body = soup.body

    def skip(tag):
        return any(p.name == "div" and "note" in (p.get("class") or []) for p in tag.parents)

    headings.normalize(body, skip=skip)

    assert [t.name for t in body.find_all(["h1", "h2", "h3", "h4"])] == ["h1", "h3", "h2", "h3"]


def test_an_empty_heading_takes_no_rung() -> None:
    """It emits nothing, so letting it hold a level is a gap with no heading in it.

    `tibco-administrator-enterprise-edition`'s `admin_server.4.063` carries an
    empty level-3 heading between its title and its first section, and it is why
    that page still read `#` then `###` after the first cut of Phase 27.
    """
    html = '<body><h1>AppStatusCheck</h1><h3></h3><h4>Purpose</h4></body>'
    soup = markdown.parse(html)
    body = soup.body

    headings.normalize(body)

    assert [t.name for t in body.find_all(["h1", "h2", "h3", "h4"])] == ["h1", "h3", "h2"]


def test_a_heading_holding_only_an_image_is_not_empty() -> None:
    """GFM renders `# ![Logo](a.png)`, so the rung is doing work."""
    html = '<body><h1>Top</h1><h4><img src="a.png" alt="Logo"></h4></body>'
    soup = markdown.parse(html)
    body = soup.body

    assert headings.normalize(body) == 1
    assert [t.name for t in body.find_all(["h1", "h2", "h3", "h4"])] == ["h1", "h2"]


def test_a_class_named_term_becomes_a_real_term() -> None:
    """The Flare-from-DITA shape, straight from `Concepts/Attributes-of-ActiveSpaces.htm`."""
    html = ('<body><div class="dl">'
            '<div class="dlentry"><span class="dt">Scalability</span>'
            '<div class="dd">You can scale up the system horizontally.</div></div>'
            '<div class="dlentry"><span class="dt">System of Record</span>'
            '<div class="dd">It spans across nodes in an enterprise.</div></div>'
            '</div></body>')
    soup = markdown.parse(html)
    body = soup.body

    assert deflists.normalize(body) == 2

    rendered = markdown.Renderer().render(body)
    assert "**Scalability**" in rendered
    assert "**System of Record**" in rendered
    assert "You can scale up the system horizontally." in rendered


def test_a_second_definition_is_not_a_second_term() -> None:
    """`Concepts/How-Is-the-Data-Stored-in-a-Data-Grid.htm`: one term, two `dd`s.

    The second opens `<b>Persistence on Nodes</b>`, which is a writer's emphasis
    inside a definition and must survive as one rather than being read as a term.
    """
    html = ('<body><div class="dl"><div class="dlentry"><span class="dt">Nodes</span>'
            '<div class="dd">A node is a process running within a computer.</div>'
            '<div class="dd"><b>Persistence on Nodes</b> Shared Nothing mode.</div>'
            '</div></div></body>')
    soup = markdown.parse(html)
    body = soup.body

    assert deflists.normalize(body) == 1
    assert [t.name for t in body.find_all(["dt", "dd"])] == ["dt", "dd", "dd"]

    rendered = markdown.Renderer().render(body)
    assert "**Nodes**" in rendered
    assert "**Persistence on Nodes** Shared Nothing mode." in rendered


def test_a_div_flavoured_term_is_retagged_too() -> None:
    """11 files write the term as a `div` rather than a `span`."""
    html = ('<body><div class="dl"><div class="dlentry"><div class="dt">Copysets</div>'
            '<div class="dd">A logical grouping of nodes.</div></div></div></body>')
    soup = markdown.parse(html)
    body = soup.body

    assert deflists.normalize(body) == 1
    assert "**Copysets**" in markdown.Renderer().render(body)


def test_a_real_definition_list_is_left_exactly_alone() -> None:
    """DocBook's `<dt><span class="term">` already renders correctly: 18,848 files."""
    html = ('<body><div class="variablelist"><dl>'
            '<dt><span class="term">CME_iLink Configuration</span></dt>'
            '<dd><p>The Edit button is a shortcut.</p></dd></dl></div></body>')
    soup = markdown.parse(html)
    body = soup.body
    before = str(body)

    assert deflists.normalize(body) == 0
    assert str(body) == before


def test_an_inline_role_that_is_not_a_term_is_not_a_term() -> None:
    """`span.varname` appears in 1,536 EMS files and is prose, not a definition."""
    html = '<body><p>Set <span class="varname">EMS_HOME</span> before starting.</p></body>'
    soup = markdown.parse(html)
    body = soup.body

    assert deflists.normalize(body) == 0
    assert markdown.Renderer().render(body) == "Set EMS_HOME before starting."


# -- fragment retargeting (Phase 30) -------------------------------------------


def test_a_marker_above_a_heading_belongs_to_that_heading() -> None:
    """Where `markdown.anchor_marker` hoists a cross-reference target: above the
    heading it labels, so the marker cannot pollute the heading's own slug."""
    text = '# Guide\n\n<a id="ID-2F"></a>\n\n## Cluster Awareness\n'

    assert fragments.marker_targets(text) == {"id-2f": "cluster-awareness"}


def test_a_marker_in_mid_section_belongs_to_the_section_it_is_in() -> None:
    """Nothing follows it before prose, so the enclosing heading is the closest
    thing a reader can actually be sent to."""
    text = '# Guide\n\n## Settings\n\nprose\n\n<a id="deep"></a>\n\nmore prose\n'

    assert fragments.marker_targets(text) == {"deep": "settings"}


def test_a_document_with_no_headings_offers_nothing() -> None:
    """There is no anchor to send anybody to, and inventing one would replace a
    link that fails visibly with one that fails quietly somewhere else."""
    assert fragments.marker_targets('<a id="x"></a>\n\njust prose\n') == {}


def test_a_marker_is_matched_case_insensitively() -> None:
    """Half the corpus capitalises its identifiers (`ID-2FC4B4A1`) and renderers
    fold anchor case, so a rewrite that did not would miss them."""
    targets = fragments.marker_targets('<a id="ID-2F"></a>\n\n# Top\n')

    assert targets == {"id-2f": "top"}


def test_a_marker_name_is_read_as_the_text_it_was_written_from() -> None:
    """`anchor_marker` HTML-escapes the name, so `R&D` is written `R&amp;D`; read
    back raw it matched no fragment naming the target (R8-08's neighbour)."""
    targets = fragments.marker_targets(f"{markdown.anchor_marker('R&D notes')}\n\n## Research\n")

    assert targets == {"r&d notes": "research"}


def test_every_reference_syntax_is_retargeted_and_code_is_left_alone() -> None:
    body = (
        "See [A](other.md#old) and [B](#old).\n\n"
        "`[C](x.md#old)` stays.\n\n"
        "```\n[D](y.md#old)\n```\n\n"
        '<a href="other.md#old">html</a>\n\n'
        "[ref]: other.md#old\n"
    )

    out, count = fragments.retarget(body, lambda path, fragment: "section-one")

    assert count == 4
    assert "](other.md#section-one)" in out
    assert "](#section-one)" in out
    assert '<a href="other.md#section-one">' in out
    assert "[ref]: other.md#section-one" in out
    # Untouched: a code span and a fence are prose, not references.
    assert "`[C](x.md#old)`" in out
    assert "[D](y.md#old)" in out


def test_a_fragment_the_resolver_cannot_place_is_left_exactly_as_written() -> None:
    """The common case and the important one: never guessed at, only reported."""
    body = "See [A](other.md#unknown).\n"

    out, count = fragments.retarget(body, lambda path, fragment: None)

    assert (out, count) == (body, 0)
