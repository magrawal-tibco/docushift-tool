"""`config/verify-triage.yaml`: what each kind of `verify` finding is (Phase 58).

A rollout re-runs `verify` over weeks. Without a record of what is already
understood, every run re-raises the same 61 unlabelled notes and 5 dropped alt
texts, and a new loss drowns among them. Each entry here matches findings and says
what they are:

- `ours`     -- this project fixes it (a phase, or a run like `fix-callouts`);
- `platform` -- the AEM owners fix it; carries their Jira key;
- `source`   -- it is in the documents we received;
- `accepted` -- a difference someone decided to live with; says who and why.

Triage never removes a finding: the report still lists it, with its decision.
It changes only how the finding counts toward a version's status
(`design.md` §8.10). A malformed entry stops the run with its position, because a
silently ignored decision is how a known problem comes back as a new one.
"""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path

import yaml

DECISIONS = ("ours", "platform", "source", "accepted")


class TriageError(ValueError):
    """`verify-triage.yaml` is malformed; the message names the entry."""


@dataclass(frozen=True)
class Entry:
    code: str
    decision: str
    reason: str
    slug: str = "*"
    version: str = "*"
    path: str = "*"
    ticket: str = ""

    def matches(self, code: str, slug: str, version: str, path: str) -> bool:
        return (code == self.code and fnmatchcase(slug, self.slug)
                and fnmatchcase(version, self.version) and fnmatchcase(path, self.path))

    @property
    def label(self) -> str:
        return f"{self.decision} {self.ticket}".strip()


def load(path: Path) -> list[Entry]:
    """The entries in `path`, in file order. A missing file is an empty triage."""
    if not path.is_file():
        return []
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise TriageError(f"{path.name}: not valid YAML: {exc}") from exc
    rows = document.get("triage") if isinstance(document, dict) else None
    if not isinstance(rows, list):
        raise TriageError(f"{path.name}: needs a top-level `triage:` list")
    entries: list[Entry] = []
    for number, row in enumerate(rows, 1):
        where = f"{path.name}: entry {number}"
        if not isinstance(row, dict):
            raise TriageError(f"{where}: not a mapping")
        code, decision, reason = (str(row.get(k) or "").strip() for k in ("code", "decision", "reason"))
        if not code.startswith("VERIFY_"):
            raise TriageError(f"{where}: `code` must be a VERIFY_ finding code, got {code!r}")
        if decision not in DECISIONS:
            raise TriageError(f"{where}: `decision` must be one of {', '.join(DECISIONS)}, got {decision!r}")
        if not reason:
            raise TriageError(f"{where}: `reason` is required -- a decision nobody can explain is not one")
        if decision == "platform" and not str(row.get("ticket") or "").strip():
            raise TriageError(f"{where}: a `platform` decision needs the owners' `ticket`")
        entries.append(Entry(
            code, decision, reason,
            str(row.get("slug") or "*"), str(row.get("version") or "*"),
            str(row.get("path") or "*"), str(row.get("ticket") or "").strip(),
        ))
    return entries


def match(entries: list[Entry], code: str, slug: str, version: str, path: str) -> Entry | None:
    """The first entry that matches, or None. File order is precedence."""
    return next((e for e in entries if e.matches(code, slug, version, path)), None)
