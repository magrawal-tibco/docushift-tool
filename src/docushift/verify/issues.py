"""Phase 77: every version's latest `verify` findings, re-triaged and grouped by kind.

A rollout over every published version finds the same problems many times. They
are logged in Jira one issue per *kind* and fixed later, so two things are read
back from each version's latest stored findings (`state.db`), with no request:

- `retriage`: the current `config/verify-triage.yaml` applied again, so an entry
  added after a wave (`decision: logged`, its Jira key) changes the versions'
  statuses without running the wave again;
- `build` / `write`: `reports/verify/ISSUES.csv` and `.html`, one row per kind --
  a triage entry, or, for findings no entry covers, their code. The unlogged rows
  come first: they are the candidates for new Jira issues.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import escape
from pathlib import Path, PurePosixPath

from docushift.utils.csvio import write_rows
from docushift.verify import triage

FILE = "ISSUES"
COLUMNS = ["kind", "code", "scope", "decision", "jira", "versions", "families", "findings",
           "example_version", "example_page", "example_message", "first_seen", "last_seen"]
_TAGS = re.compile(r"\s*\[(?:triage: [^\]]*|repair \S+ still needed here)\]")


@dataclass
class Tally:
    errors: int = 0
    warnings: int = 0
    explained: int = 0
    logged: int = 0

    @property
    def outcome(self) -> str:
        return triage.outcome(self.errors, self.warnings, self.logged, self.explained)


def page_of(path: str, target: str) -> str:
    """A stored finding's path, back to the version-relative form triage matches on.

    `verify` stores it from the target root (`<repo>/<locale>/<slug>/<class>/<segment>/<page>`);
    the version folder's last two parts mark where the page begins.
    """
    tail = "/".join(PurePosixPath(Path(target).as_posix()).parts[-2:]) if target else ""
    if tail and f"{tail}/" in path:
        return path.split(f"{tail}/", 1)[1]
    return "" if tail and path.endswith(tail) else path


def judged(rows: list[dict], entries, repair_states, target: str):
    """Each stored finding with the entry that now explains it (or None)."""
    for row in rows:
        decided, _ = triage.decide(entries, repair_states, row["code"], row["slug"], row["version"],
                                   page_of(row["path"], target))
        yield row, decided


def tally(rows: list[dict], entries, repair_states, target: str) -> Tally:
    out = Tally()
    for row, decided in judged(rows, entries, repair_states, target):
        if row["severity"] == "note":
            continue
        if decided is not None:
            out.explained += 1
            out.logged += decided.decision == "logged"
        elif row["severity"] == "error":
            out.errors += 1
        else:
            out.warnings += 1
    return out


def retriage(state, entries, repair_states) -> list[tuple[str, str, str, str]]:
    """Re-applies triage to every version's latest result. Returns the changes
    `(slug, version, old outcome, new outcome)`; nothing is fetched."""
    changed = []
    for (slug, version), row in sorted(state.verify_latest().items()):
        found = tally(state.verify_findings(slug, version, row["run_id"]), entries, repair_states,
                      row.get("target", ""))
        new = {**row, "errors": found.errors, "warnings": found.warnings,
               "explained": found.explained, "outcome": found.outcome}
        if (row["errors"], row["warnings"], row["explained"], row["outcome"]) != (
                new["errors"], new["warnings"], new["explained"], new["outcome"]):
            state.record_verify(new)
            changed.append((slug, version, row["outcome"], found.outcome))
    return changed


@dataclass
class Kind:
    kind: str
    code: str
    scope: str = ""
    decision: str = ""
    jira: str = ""
    versions: set = field(default_factory=set)
    families: set = field(default_factory=set)
    findings: int = 0
    example: tuple[str, str, str] = ("", "", "")
    first: str = ""
    last: str = ""


def build(state, entries, repair_states, family_of: dict[str, str],
          current: set[tuple[str, str]] | None = None) -> list[dict[str, str]]:
    """One row per kind over every version's latest result, unlogged kinds first.

    `current` limits it to versions whose result still stands: one re-published
    since (`stale`) was not what was checked, so its findings may be gone.
    """
    kinds: dict[tuple, Kind] = {}
    for (slug, version), row in state.verify_latest().items():
        if current is not None and (slug, version) not in current:
            continue
        day = str(row["at"])[:10]
        for found, decided in judged(state.verify_findings(slug, version, row["run_id"]), entries,
                                     repair_states, row.get("target", "")):
            if found["severity"] == "note":
                continue
            if decided is None:
                key = ("unlogged", found["code"])
                kind = kinds.setdefault(key, Kind("unlogged", found["code"], decision=found["severity"]))
            else:
                scope = " ".join(f"{k}={v}" for k, v in (("slug", decided.slug), ("version", decided.version),
                                                          ("path", decided.path)) if v != "*")
                key = ("entry", decided.code, scope, decided.decision, decided.ticket)
                kind = kinds.setdefault(key, Kind("triaged", decided.code, scope, decided.decision, decided.ticket))
            kind.versions.add(f"{slug} {version}")
            kind.families.add(family_of.get(slug, ""))
            kind.findings += int(found["count"] or 1)
            if not kind.example[0]:
                kind.example = (f"{slug} {version}", page_of(found["path"], row.get("target", "")),
                                _TAGS.sub("", found["message"]))
            kind.first = min(kind.first or day, day)
            kind.last = max(kind.last, day)
    ordered = sorted(kinds.values(), key=lambda k: (k.kind != "unlogged", -len(k.versions), k.code, k.scope))
    return [{"kind": k.kind, "code": k.code, "scope": k.scope, "decision": k.decision, "jira": k.jira,
             "versions": str(len(k.versions)), "families": " ".join(sorted(f for f in k.families if f)),
             "findings": str(k.findings), "example_version": k.example[0], "example_page": k.example[1],
             "example_message": k.example[2][:300], "first_seen": k.first, "last_seen": k.last}
            for k in ordered]


def write(root: Path, rows: list[dict[str, str]]) -> tuple[Path, Path]:
    folder = root / "verify"
    folder.mkdir(parents=True, exist_ok=True)
    csv_path, html_path = folder / f"{FILE}.csv", folder / f"{FILE}.html"
    write_rows(csv_path, COLUMNS, rows)
    unlogged = sum(1 for r in rows if r["kind"] == "unlogged")
    body = "".join("<tr>" + "".join(f"<td>{escape(r[c])}</td>" for c in COLUMNS) + "</tr>" for r in rows)
    html_path.write_text(
        "<!doctype html><meta charset='utf-8'><title>verify issues</title>"
        "<style>body{font-family:sans-serif}td,th{border:1px solid #ccc;padding:2px 6px;font-size:13px;"
        "vertical-align:top}table{border-collapse:collapse}</style>"
        f"<h1>verify: issues by kind</h1><p>{len(rows)} kind(s); {unlogged} not logged in Jira yet "
        "(listed first).</p><table><tr>" + "".join(f"<th>{c}</th>" for c in COLUMNS) + f"</tr>{body}</table>",
        encoding="utf-8", newline="\n")
    return csv_path, html_path
