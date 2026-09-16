"""Reading the findings register back -- `architecture.md` §7.3, `design.md` §8.6.

`report` is a read layer over `runs` and `findings` and it adds no analysis of its
own. Everything it prints was decided by a stage, at the moment that stage could
still see what it was talking about -- which is the reason for the boundary §7.1
draws and this module honours: **nothing here reads the catalog.** A report that
resolved a slug against `products.csv` would be describing a run in terms of state
that has changed since the run, which is the confusion the `runs` table exists to
prevent.

Two shapes live here and nothing else does: the grouping (stage, then code, errors
before warnings before notes) and the Markdown export. The export is Markdown and
there is no JSON (decided 2026-09-10), and the consequence is a rule rather than a
habit: **tests assert against the `findings` table, never by parsing this output.**
A test that greps a rendered message pins the wording of every message in the tool.
Asserting that a *code* appears is fine -- the code is the contract, the message is
prose.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from docushift.reporting.findings import REGISTRY, Severity, Stage

# Errors first: the order a reader acts in, and the order §7.5 lists.
SEVERITY_ORDER: tuple[Severity, ...] = (Severity.ERROR, Severity.WARNING, Severity.NOTE)
_SEVERITY_RANK = {str(severity): index for index, severity in enumerate(SEVERITY_ORDER)}
_STAGE_RANK = {str(stage): index for index, stage in enumerate(Stage)}


@dataclass
class CodeGroup:
    """Every row one code contributed to one run."""

    code: str
    severity: str
    rows: list[dict[str, Any]] = field(default_factory=list)

    @property
    def occurrences(self) -> int:
        """Rows for an error or a warning; summed `count` for a note.

        The two are different questions and the register answers them differently
        on purpose (§7.1): you act on an error one at a time, and what a note is
        worth is its magnitude. 1,308 orphaned images is one row and 1,308
        occurrences, and printing "1" for it would be true and useless.
        """
        return sum(int(row.get("count") or 1) for row in self.rows)

    @property
    def registered(self):
        return REGISTRY.get(self.code)


@dataclass
class StageGroup:
    stage: str
    codes: list[CodeGroup] = field(default_factory=list)

    @property
    def rows(self) -> int:
        return sum(len(group.rows) for group in self.codes)


def group(rows: Iterable[dict[str, Any]]) -> list[StageGroup]:
    """Findings as the register's own shape: stage, then code, errors first.

    A code no longer in the register still groups -- it sorts last within its
    severity and keeps its recorded severity rather than being dropped. A row
    written before a code was retired is evidence about a run that happened, and
    `ARCHIVE_ALSO_LIVE`'s removal in 6d is the precedent for a code leaving.
    """
    stages: dict[str, dict[str, CodeGroup]] = {}
    for row in rows:
        by_code = stages.setdefault(str(row["stage"]), {})
        found = by_code.get(str(row["code"]))
        if found is None:
            found = CodeGroup(str(row["code"]), str(row["severity"]))
            by_code[str(row["code"])] = found
        found.rows.append(row)

    result = []
    for stage in sorted(stages, key=lambda name: (_STAGE_RANK.get(name, len(_STAGE_RANK)), name)):
        codes = sorted(
            stages[stage].values(),
            key=lambda item: (_SEVERITY_RANK.get(item.severity, len(_SEVERITY_RANK)), item.code),
        )
        result.append(StageGroup(stage, codes))
    return result


def tally(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    """`{severity: rows}` in severity order, zeroes omitted."""
    counts = dict.fromkeys((str(s) for s in SEVERITY_ORDER), 0)
    for row in rows:
        counts[str(row["severity"])] = counts.get(str(row["severity"]), 0) + 1
    return {severity: count for severity, count in counts.items() if count}


def summarize(rows: Sequence[dict[str, Any]]) -> str:
    """`3 errors, 12 warnings, 40 notes` -- the same line a stage run ends with."""
    counts = tally(rows)
    if not counts:
        return "no findings"
    return ", ".join(
        f"{count} {severity}{'' if count == 1 else 's'}" for severity, count in counts.items()
    )


def describe_run(run: dict[str, Any]) -> str:
    """One line naming the run a report is about."""
    scope = f" --batch {run['batch']}" if run.get("batch") else ""
    when = run.get("finished_at") or run.get("started_at") or ""
    unfinished = "" if run.get("finished_at") else " (did not finish)"
    return f"run {run['run_id']}: {run['command']}{scope}, {when}{unfinished}"


def _who(row: dict[str, Any]) -> str:
    slug, version = row.get("slug") or "", row.get("version") or ""
    if slug and version:
        return f"{slug}@{version}"
    return slug or version or "-"


def explain(code: str) -> list[str]:
    """The register entry for one code, including where it was promised.

    `Code.specified_in` has been carried since Phase 5a with nothing reading it.
    This is what it was recorded for: a finding traceable back to the sentence that
    owes it, rather than to a paraphrase of that sentence written here.
    """
    row = REGISTRY.get(code)
    if row is None:
        raise KeyError(code)
    return [
        f"{row.code}",
        f"  severity      {row.severity}",
        f"  stage         {row.stage}",
        f"  obligation    {row.obligation}",
        f"  specified in  {row.specified_in}",
    ]


def render_markdown(run: dict[str, Any], rows: Sequence[dict[str, Any]], filters: str = "") -> str:
    """The `--export` document. Markdown, and deliberately not a data format.

    An export is for somebody who was not at the terminal, so it repeats what the
    run was and what was filtered out of it -- a table of findings with no record
    of which filters produced it is the kind of artifact that gets forwarded and
    misread.
    """
    lines = [
        f"# DocuShift findings -- {run['command']} run {run['run_id']}",
        "",
        f"- **Command:** `docushift {run['command']}`" + (
            f" `--batch {run['batch']}`" if run.get("batch") else ""
        ),
        f"- **Started:** {run.get('started_at') or '-'}",
        f"- **Finished:** {run.get('finished_at') or '(did not finish)'}",
        f"- **Exit code:** {run['exit_code'] if run.get('exit_code') is not None else '-'}",
        f"- **Findings:** {summarize(rows)}",
    ]
    if filters:
        lines.append(f"- **Filtered by:** {filters}")
    lines.append("")

    if not rows:
        lines += ["No findings were recorded for this selection.", ""]
        return "\n".join(lines)

    for stage_group in group(rows):
        lines += [f"## {stage_group.stage}", ""]
        for code_group in stage_group.codes:
            registered = code_group.registered
            heading = f"### {code_group.code} ({code_group.severity})"
            lines += [heading, ""]
            if registered is not None:
                lines += [
                    f"{registered.obligation} -- *{registered.specified_in}*",
                    "",
                ]
            note = code_group.severity == str(Severity.NOTE)
            header = "| Product | Path | Count | Message |" if note else "| Product | Path | Message |"
            divider = "| :--- | :--- | ---: | :--- |" if note else "| :--- | :--- | :--- |"
            lines += [header, divider]
            for row in code_group.rows:
                cells = [_who(row), f"`{row['path']}`" if row.get("path") else "", ]
                if note:
                    cells.append(str(row.get("count") or 1))
                cells.append(str(row.get("message") or "").replace("|", "\\|"))
                lines.append("| " + " | ".join(cells) + " |")
            lines.append("")
    return "\n".join(lines)
