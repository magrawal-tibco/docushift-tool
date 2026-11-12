"""The "Where we stand" status: pure functions behind the first tab of
reports/conversion-status.html and the paste-ready reports/status-latest.md.

Closeout plan §8b. build_conversion_status.py reads the files and hands the rows in;
everything here is a function of its arguments, so it can be tested on small
fixtures. Standard library only, like the build script.

The hand-kept part is config/status-areas.yaml. It is read by `parse_simple_yaml`,
a reader for the small subset of YAML that file uses (block mappings and lists,
`[a, b]` lists, quoted or plain one-line scalars, `#` comments), so the page builds
without PyYAML. Anything outside that subset is an error, not a guess.
"""

import datetime as dt
import re

TEAMS = ("TechDocs", "Digital Platform", "Engineering")
STATUSES = ("done", "on track", "at risk", "blocked")
# A problem kind's owner from its triage decision (§8b). `logged` kinds follow their
# Jira issue's owner; `accepted` kinds are lived with, so nobody owes anything.
DECISION_TEAM = {"platform": "Digital Platform", "ours": "TechDocs", "source": "TechDocs", "unlogged": "TechDocs"}
OTHER_AREA = "other"
OTHER_AREA_NAME = "Building the conversion tool, and earlier work"


# -- the YAML subset -------------------------------------------------------------

_KEY = re.compile(r"^([A-Za-z_][\w-]*):(?:\s+(.*))?$")


def _strip_comment(line: str) -> str:
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"" and (i == 0 or line[i - 1] in " [,:-"):
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            return line[:i].rstrip()
    return line.rstrip()


def _scalar(text: str):
    text = text.strip()
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        return [_scalar(part) for part in inner.split(",")] if inner else []
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "'\"":
        return text[1:-1]
    if text in ("", "null", "~"):
        return None
    return text


def parse_simple_yaml(text: str):
    lines = []
    for number, raw in enumerate(text.splitlines(), 1):
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise ValueError(f"line {number}: indent with spaces, not tabs")
        body = _strip_comment(raw)
        if body.strip():
            lines.append([len(body) - len(body.lstrip()), body.strip(), number])
    if not lines:
        return None
    value, pos = _block(lines, 0, lines[0][0])
    if pos != len(lines):
        raise ValueError(f"line {lines[pos][2]}: unexpected indent")
    return value


def _block(lines: list, pos: int, indent: int):
    if lines[pos][1] == "-" or lines[pos][1].startswith("- "):
        return _sequence(lines, pos, indent)
    return _mapping(lines, pos, indent)


def _sequence(lines: list, pos: int, indent: int):
    items = []
    while pos < len(lines) and lines[pos][0] == indent and (lines[pos][1] == "-" or lines[pos][1].startswith("- ")):
        rest = lines[pos][1][1:].strip()
        if not rest:
            if pos + 1 >= len(lines) or lines[pos + 1][0] <= indent:
                items.append(None)
                pos += 1
            else:
                value, pos = _block(lines, pos + 1, lines[pos + 1][0])
                items.append(value)
        elif _KEY.match(rest) and not rest.startswith(("'", '"')):
            # "- key: value" opens a mapping whose keys line up with "key".
            lines[pos] = [indent + len(lines[pos][1]) - len(rest), rest, lines[pos][2]]
            value, pos = _mapping(lines, pos, lines[pos][0])
            items.append(value)
        else:
            items.append(_scalar(rest))
            pos += 1
    return items, pos


def _mapping(lines: list, pos: int, indent: int):
    out = {}
    while pos < len(lines) and lines[pos][0] == indent:
        match = _KEY.match(lines[pos][1])
        if not match:
            raise ValueError(f"line {lines[pos][2]}: expected 'key: value', got {lines[pos][1]!r}")
        key, rest = match.group(1), match.group(2)
        if key in out:
            raise ValueError(f"line {lines[pos][2]}: duplicate key {key!r}")
        pos += 1
        if rest is not None and rest.strip() not in ("", "|", ">", ">-"):
            out[key] = _scalar(rest)
        elif rest is not None and rest.strip() in ("|", ">", ">-"):
            raise ValueError(f"line {lines[pos - 1][2]}: multi-line text is not supported; keep it on one line")
        elif pos < len(lines) and (lines[pos][0] > indent or (
                lines[pos][0] == indent and (lines[pos][1] == "-" or lines[pos][1].startswith("- ")))):
            out[key], pos = _block(lines, pos, lines[pos][0])
        else:
            out[key] = None
    if pos < len(lines) and lines[pos][0] > indent:
        raise ValueError(f"line {lines[pos][2]}: unexpected indent")
    return out, pos


# -- status-areas.yaml -----------------------------------------------------------

def _as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def load_areas(text: str) -> dict:
    """The hand-kept file, checked: teams and statuses from the fixed lists only."""
    doc = parse_simple_yaml(text) or {}
    for key in ("go_live", "old_site_off", "areas"):
        if not doc.get(key):
            raise ValueError(f"status-areas.yaml: '{key}' is missing")
    owners = doc.get("jira_owner") or {}
    for key, team in owners.items():
        if team not in TEAMS:
            raise ValueError(f"status-areas.yaml: jira_owner {key}: unknown team {team!r}")
    seen = set()
    areas = []
    for raw in doc["areas"]:
        area = {
            "id": raw.get("id") or "", "name": raw.get("name") or "", "team": raw.get("team") or "",
            "status": raw.get("status") or "", "note": raw.get("note") or "", "plan": raw.get("plan") or "",
            "next": raw.get("next") or "", "nextStep": raw.get("next_step") or "",
            "jira": _as_list(raw.get("jira")), "labels": _as_list(raw.get("jira_labels")),
            "measure": raw.get("measure") or "", "waiting": [],
        }
        where = f"status-areas.yaml: area {area['id'] or area['name']!r}"
        if not area["id"] or not area["name"]:
            raise ValueError(f"{where}: needs an id and a name")
        if area["id"] in seen or area["id"] == OTHER_AREA:
            raise ValueError(f"{where}: id used twice or reserved")
        seen.add(area["id"])
        if area["team"] not in TEAMS:
            raise ValueError(f"{where}: team must be one of {', '.join(TEAMS)}, not {area['team']!r}")
        if area["status"] not in STATUSES:
            raise ValueError(f"{where}: status must be one of {', '.join(STATUSES)}, not {area['status']!r}")
        for w in _as_list(raw.get("waiting_on")):
            if (w or {}).get("team") not in TEAMS or not w.get("what"):
                raise ValueError(f"{where}: each waiting_on item needs a known team and a 'what'")
            area["waiting"].append({"team": w["team"], "what": w["what"], "due": w.get("due") or ""})
        areas.append(area)
    return {"goLive": doc["go_live"], "oldSiteOff": doc["old_site_off"], "owners": owners, "areas": areas}


# -- headline --------------------------------------------------------------------

def headline(versions: list[dict], today: dt.date, go_live: str, old_site_off: str) -> dict:
    """Days left, and per BU: in the migration, converted, placed, checked on staging.

    `versions` rows: {bu, inMig, converted, published, staging} with booleans; only
    rows in the migration count anywhere.
    """
    by_bu: dict[str, dict] = {}
    keys = ("inMig", "converted", "published", "staging")
    for v in versions:
        if not v["inMig"]:
            continue
        row = by_bu.setdefault(v["bu"], {"bu": v["bu"], **{k: 0 for k in keys}})
        for k in keys:
            row[k] += bool(v[k])
    rows = sorted(by_bu.values(), key=lambda r: -r["inMig"])
    total = {"bu": "All", **{k: sum(r[k] for r in rows) for k in keys}}
    return {
        "daysToGoLive": (dt.date.fromisoformat(go_live) - today).days,
        "daysToOldSiteOff": (dt.date.fromisoformat(old_site_off) - today).days,
        "goLive": go_live, "oldSiteOff": old_site_off, "byBu": rows, "total": total,
    }


# -- Jira: which area each sub-task counts under ----------------------------------

def assign_issues(issues: list[dict], areas: list[dict]) -> dict[str, str]:
    """Each non-canceled sub-task under exactly one area, so the rows add up.

    An issue named in an area's `jira` wins; then a label in its `jira_labels`; then
    the nearest ancestor named in an area. The first area that matches wins.
    Anything else is "other".
    """
    by_key = {i["key"]: i for i in issues}
    direct: dict[str, str] = {}
    for area in areas:
        for key in area["jira"]:
            direct.setdefault(key, area["id"])
    out = {}
    for issue in issues:
        if issue["type"] != "Sub-task" or issue["status"] == "Canceled":
            continue
        area = direct.get(issue["key"])
        if area is None:
            area = next((a["id"] for a in areas if set(a["labels"]) & set(issue["labels"])), None)
        key, seen = issue["parent"], set()
        while area is None and key and key not in seen:
            area = direct.get(key)
            seen.add(key)
            key = by_key.get(key, {}).get("parent")
        out[issue["key"]] = area or OTHER_AREA
    return out


def effort(issues: list[dict], areas: list[dict]) -> dict:
    """Story points done / in progress / to do per area and in total, and the age."""
    assigned = assign_issues(issues, areas)
    by_key = {i["key"]: i for i in issues}
    names = {a["id"]: a["name"] for a in areas} | {OTHER_AREA: OTHER_AREA_NAME}
    rows = {aid: {"id": aid, "name": names[aid], "done": 0.0, "doing": 0.0, "todo": 0.0, "issues": 0}
            for aid in names}
    bucket = {"done": "done", "indeterminate": "doing", "new": "todo"}
    for key, aid in assigned.items():
        issue = by_key[key]
        row = rows[aid]
        row[bucket.get(issue["category"], "todo")] += float(issue["sp"] or 0)
        row["issues"] += 1
    ordered = [rows[a["id"]] for a in areas] + [rows[OTHER_AREA]]
    total = {k: sum(r[k] for r in ordered) for k in ("done", "doing", "todo", "issues")}
    first = min((i["created"] for i in issues if i.get("created")), default="")
    missing = sorted({k for a in areas for k in a["jira"] if k not in by_key}, key=_key_number)
    return {"rows": ordered, "total": total, "firstIssue": first, "missing": missing, "assigned": assigned}


def _key_number(key: str) -> int:
    tail = key.rsplit("-", 1)[-1]
    return int(tail) if tail.isdigit() else 0


# -- areas: done and left ---------------------------------------------------------

def area_rows(areas: list[dict], measures: dict, issues: list[dict], assigned: dict, owners: dict) -> list[dict]:
    """One row per area: the hand-kept fields, its measure, and its Jira issues."""
    by_key = {i["key"]: i for i in issues}
    rows = []
    for area in areas:
        mine = sorted((by_key[k] for k, a in assigned.items() if a == area["id"]), key=lambda i: _key_number(i["key"]))
        open_issues = [{"key": i["key"], "summary": i["summary"], "status": i["status"], "due": i["due"],
                        "team": owners.get(i["key"], area["team"])} for i in mine if i["category"] != "done"]
        measure = measures.get(area["measure"])
        if measure is None and mine:
            done = sum(1 for i in mine if i["category"] == "done")
            measure = {"done": done, "total": len(mine), "unit": "Jira items", "detail": ""}
        rows.append({**area, "measure": measure, "openIssues": open_issues,
                     "keys": area["jira"] or [], "issueCount": len(mine)})
    return rows


def karan_measure(changes: list[dict], versions: dict) -> dict:
    """Karan's list applied: additions in the repositories, removals gone from them.

    `changes` rows: {action, slug, version}, the action "add" or "remove", perhaps
    followed by a note such as "(retired)"; `versions` maps
    (slug, version) -> {migrate_decision, published}.
    """
    written = added = removed = 0
    action = {id(c): c["action"].split()[0] for c in changes}
    adds = sum(1 for c in changes if action[id(c)] == "add")
    for c in changes:
        v = versions.get((c["slug"], c["version"]))
        if v is None:
            continue
        add = action[id(c)] == "add"
        written += v["migrate_decision"] == ("migrate" if add else "do_not_migrate")
        added += add and v["published"]
        removed += not add and not v["published"]
    removes = len(changes) - adds
    return {"done": added + removed, "total": len(changes), "unit": "changes",
            "detail": f"decisions written into the catalog: {written} of {len(changes)}; "
                      f"added: {added} of {adds}; removed: {removed} of {removes}"}


def problem_kinds(kinds: list[dict], owners: dict, default_team: str = "TechDocs") -> dict:
    """Problem kinds by owning team, counted by triage decision.

    `kinds` are ISSUES.csv rows: one per triage entry, plus one per code not yet
    sorted (`unlogged`). Entries logged under one Jira issue are one kind, so a kind
    with a Jira key counts once per key; an entry without one counts on its own.
    """
    teams = {t: {"kinds": 0, "byDecision": {}} for t in TEAMS}
    seen = set()
    accepted = 0
    for k in kinds:
        decision = k["decision"] if k["kind"] == "triaged" else "unlogged"
        if decision == "accepted":
            accepted += 1
            continue
        if decision == "logged":
            team = owners.get(k["jira"], default_team)
        else:
            team = DECISION_TEAM.get(decision, default_team)
        if k["jira"] and decision in ("logged", "ours", "platform"):
            unit = (decision, k["jira"])
        else:
            unit = (decision, k["code"], k["scope"])
        if unit in seen:
            continue
        seen.add(unit)
        row = teams[team]
        row["kinds"] += 1
        row["byDecision"][decision] = row["byDecision"].get(decision, 0) + 1
    unlogged = sum(1 for k in kinds if k["kind"] != "triaged")
    return {"teams": teams, "accepted": accepted, "unlogged": unlogged, "entries": len(kinds)}


# -- the plan's decisions table -------------------------------------------------

_DAY = re.compile(r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun) (\d{1,2})\b")


def open_decisions(plan_text: str, month: str) -> list[dict]:
    """Rows of the plan's "Decisions" table whose answer is not yet given.

    An answered row starts its answer in bold (`**Yes**`); an open one names the day
    it is due ("Fri 20"), read as that day of `month` (YYYY-MM).
    """
    section = re.search(r"^## [\d.a-z]*\s*Decisions\s*$(.*?)(?=^## )", plan_text, re.S | re.M)
    if not section:
        return []
    out = []
    for line in section.group(1).splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3 or not re.fullmatch(r"D\d+", cells[0]):
            continue
        answer = cells[2]
        if answer.startswith("**"):
            continue
        day = _DAY.search(answer)
        due = f"{month}-{int(day.group(1)):02d}" if day else ""
        out.append({"id": cells[0], "what": cells[1], "answer": answer, "due": due})
    return out


_PLAIN = [
    (re.compile(r"`([^`]*)`"), r"\1"),
    (re.compile(r"\*\*([^*]*)\*\*"), r"\1"),
    (re.compile(r"\bR([1-4])\b"), r"release \1"),
    (re.compile(r"Δ1"), "the 16 Nov catalog refresh"),
    (re.compile(r"Δ3"), "the last catalog refresh"),
    (re.compile(r"\s*\(§[^)]*\)"), ""),
    (re.compile(r"\bcontent-fix\b"), "the review branch"),
]


def plain(text: str) -> str:
    """Plan wording for a business reader: no release codes, section signs or code marks."""
    for pattern, repl in _PLAIN:
        text = pattern.sub(repl, text)
    return text


# -- pending by team -------------------------------------------------------------

def _sort_due(due: str) -> tuple:
    return (0, due) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", due or "") else (1, due or "")


def pending_by_team(rows: list[dict], decisions: list[dict], kinds: dict) -> dict:
    """What each team owes: dated items, open Jira issues per area, problem kinds."""
    out = {t: {"items": [], "issues": [], "kinds": kinds["teams"][t]} for t in TEAMS}
    for area in rows:
        # A next step the area's own team already owes, on the same day, as a
        # waiting_on item is said once.
        repeated = any(w["team"] == area["team"] and w["due"] == area["next"] for w in area["waiting"])
        if area["status"] != "done" and area["nextStep"] and not repeated:
            out[area["team"]]["items"].append(
                {"area": area["name"], "what": area["nextStep"], "due": area["next"], "status": area["status"]})
        for w in area["waiting"]:
            out[w["team"]]["items"].append({"area": area["name"], "what": w["what"], "due": w["due"], "status": ""})
        for issue in area["openIssues"]:
            out[issue["team"]]["issues"].append({**issue, "area": area["name"]})
    for d in decisions:
        out["TechDocs"]["items"].append({"area": "Decisions", "what": f"Decide: {d['what']}", "due": d["due"],
                                         "status": "", "decision": d["id"]})
    for team in out.values():
        team["items"].sort(key=lambda i: _sort_due(i["due"]))
    return out


# -- the text copy ---------------------------------------------------------------

def day_text(value: str) -> str:
    """An ISO date as "Fri 13 Nov"; other wording as it is; blank as "date to confirm"."""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value or ""):
        d = dt.date.fromisoformat(value)
        return f"{d.strftime('%a')} {d.day} {d.strftime('%b')}"
    return value or "date to confirm"


def _pct(n: int, d: int) -> str:
    return f"{round(n / d * 100)}%" if d else "-"


def _sp(n: float) -> str:
    return f"{n:g}"


def render_markdown(status: dict) -> str:
    """reports/status-latest.md: short, plain, ready to paste into an email or chat."""
    h = status["headline"]
    t = h["total"]
    lines = [
        "# Documentation migration: where we stand",
        "",
        f"As of {status['asOfText']}.",
        "",
        f"- **Go-live:** {day_text(h['goLive'])}, in {h['daysToGoLive']} days. "
        f"**Old site switched off:** {day_text(h['oldSiteOff'])}, in {h['daysToOldSiteOff']} days.",
        f"- **{t['inMig']:,} documentation versions are in the migration.** "
        f"Converted: {t['converted']:,} ({_pct(t['converted'], t['inMig'])}). "
        f"In the new site's repositories: {t['published']:,} ({_pct(t['published'], t['inMig'])}). "
        f"Checked page by page on the staging site: {t['staging']:,} of the {t['published']:,} in the repositories.",
    ]
    for r in h["byBu"]:
        lines.append(f"  - {r['bu']}: {r['inMig']:,} versions; {r['converted']:,} converted, "
                     f"{r['published']:,} in the repositories, {r['staging']:,} checked on staging.")
    lines += ["", "## Areas", ""]
    for a in status["areas"]:
        m = a["measure"]
        done = f" ({m['done']:,} of {m['total']:,} {m['unit']} done)" if m else ""
        nxt = f" Next, {day_text(a['next'])}: {a['nextStep']}." if a["nextStep"] and a["status"] != "done" else ""
        lines.append(f"- **{a['name']}**: {a['status']}{done}. {a['note']}{nxt} Owner: {a['team']}.")
    e = status["effort"]
    if e:
        tot = e["total"]
        lines += ["", "## Effort", "",
                  f"Work started {day_text(e['firstIssue'])}, {e['daysSinceFirst']} days ago. "
                  f"Effort logged in Jira: {_sp(tot['done'])} points done, {_sp(tot['doing'])} in progress, "
                  f"{_sp(tot['todo'])} still to do (one point is one 8-hour day; Jira as of {day_text(e['fetched'])}).",
                  ""]
        for r in e["rows"]:
            if r["issues"]:
                lines.append(f"- {r['name']}: {_sp(r['done'])} done, {_sp(r['doing'])} in progress, "
                             f"{_sp(r['todo'])} to do")
    else:
        lines += ["", "## Effort", "", "No Jira snapshot was found, so effort is not shown."]
    lines += ["", "## What each team owes", ""]
    for team, p in status["pending"].items():
        lines.append(f"**{team}**")
        lines.append("")
        for item in p["items"]:
            lines.append(f"- {day_text(item['due'])}, {item['area']}: {plain(item['what'])}")
        k = p["kinds"]
        if k["kinds"]:
            waiting = k["byDecision"].get("unlogged", 0)
            extra = f", {waiting} still to sort at the morning triage" if waiting else ""
            lines.append(f"- {k['kinds']} kinds of problem found by the checks{extra}")
        if p["issues"]:
            lines.append(f"- {len(p['issues'])} open items in Jira")
        if not (p["items"] or k["kinds"] or p["issues"]):
            lines.append("- Nothing open")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
