"""Every text file the tool generates, written one way: UTF-8 with LF line endings.

**Line endings were an accident of which pass wrote a file last** (X2-07, X3-10).
`Path.write_text` without `newline=` writes CRLF on Windows, so every topic,
`toc.yml`, `metadata.yml` and `csh.yml` left convert as CRLF -- and then the
fragment pass rewrote only the pages whose anchors moved, with `newline=""`,
which is LF. Measured in `output\`: 16,061 pages CRLF and 6,589 LF, the split
following almost exactly which pages held a `](…#…)` link. One added or removed
cross-reference flipped a whole page, so a re-convert diff showed every line
changed, and a tree built on another OS differed in size from one built here,
which `sync`'s size-and-mtime comparison reads as stale.

LF everywhere, decided by the user 2026-10-05: it is what the sidecars written
through `reframe/manifest.write` and `origins.write` already used, it is the same
bytes on every OS, and Git and the publishing platform read it as written.

Carriage returns already *in* the text are folded too, not only the newlines
Python would translate. Converted bodies carry source text, and a `\\r\\n` from a
`<pre>` block written through a CRLF translation became `\\r\\r\\n`. CommonMark and
YAML both read a lone `\\r` as a line break, so folding it changes no rendering.

**Not for CSV.** `utils/csvio.write_rows` keeps the csv module's CRLF and the
BOM: those files are opened in Excel, RFC 4180 specifies CRLF, and the BOM is
what keeps `®` and `™` intact on a double-click open (`architecture.md` §3.6).
"""

from pathlib import Path


def lf(text: str) -> str:
    """`text` with every CRLF and lone CR folded to LF."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def write_text(path: Path, text: str) -> None:
    """Writes `text` to `path` as UTF-8 with LF line endings, on every platform."""
    path.write_text(lf(text), encoding="utf-8", newline="\n")
