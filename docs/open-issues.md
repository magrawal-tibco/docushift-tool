# Open Issues by Product

What we know is outstanding for each product, and what we have decided to do
about it. Written in plain language for a business reader — no code, no command
names.

## What belongs here, and what does not

**This file holds judgement, not detection.** The tool already finds broken
links, missing anchors, redirect problems and unread review queues on every run,
and it can print that list against any product on demand. Copying those findings
into this file by hand would guarantee it goes stale: someone fixes a link, the
tool stops reporting it, and this page still says it is open.

So a finding is only written down here when there is something a machine cannot
work out — **do we accept it, who owns it, what is it waiting on, does it block
publishing**. If the answer to all four is obvious and nobody needs to act, leave
it to the tool and keep this page short. A tracker nobody trusts is worse than no
tracker, and the way it loses trust is by filling up.

## How to keep it

- One section per product, newest issue at the top of its section.
- Every issue carries a **status**, an **owner** and a **raised** date. "Owner:
  unassigned" is a legitimate and useful answer; a missing owner line is not.
- **Closing an issue means deleting it**, in the same change that fixes it. The
  history is kept by version control, so the page itself stays a list of what is
  open rather than an archive of what once was.
- **Blocks publishing** is the field that matters most. It is the difference
  between something a writer schedules and something that stops a release.

| Status | Means |
| :--- | :--- |
| **Open** | Needs doing, nobody is doing it yet. |
| **In progress** | Somebody is on it now. |
| **Accepted** | We know, we have decided to live with it. Revisit if the situation changes. |
| **Waiting** | Blocked on somebody outside this project — usually the authoring team. |
| **Not ours** | The problem is in the source documents we receive. Reported onward; we cannot fix it here. |

---

## ActiveSpaces

### Never published to the real destination

- **Status:** Open
- **Owner:** unassigned
- **Raised:** 29 Sep 2026
- **Blocks publishing:** n/a — this *is* the publishing step

The product has only ever been published to a temporary location used for
checking. Publishing it for real is a deliberate decision that has not been
taken.

**What changed on 29 Sep 2026:** this used to be blocked on the page review as
well. It no longer is. The merged pages were accepted that day, so whenever
somebody does decide to publish for real, what goes out is the merged set — 46
pages for the newest version in place of 334 separate topics — together with
1,957 forwarding addresses per version that send every old topic link to its new
home. That is now a decision about timing and about who owns the destination,
and nothing else is holding it up.

### Web address template not recorded

- **Status:** Open
- **Owner:** unassigned
- **Raised:** 29 Sep 2026
- **Blocks publishing:** no, but old links will not be redirected

We have not recorded where ActiveSpaces documentation currently lives on the
public website. Without it, the tool cannot build the map that sends readers from
an old page address to its new one, so existing links and bookmarks would break
on the day we switch over.

This cannot be guessed. Somebody has to open the live site, confirm the real
address format, and record it. Sixteen other products are in the same position.

---

## Enterprise Message Service, ActiveSpaces

### 340 redirects differ only in capital letters

- **Status:** Accepted
- **Owner:** unassigned
- **Raised:** 29 Sep 2026 (count revised 30 Sep 2026)
- **Blocks publishing:** no

For 340 pages, the old address and the new address are the same except for
capital letters. On a web server that treats capitals and lower case as the same
thing, such a redirect can point at itself and loop.

**This was thirty-one, and it is now 340.** Two reasons, both expected: ActiveSpaces
joined the set of products publishing merged pages on 29 Sep, and the 30 Sep
change to how pages are grouped means many more topics now become a page named
after themselves — and it is that renaming, lower-casing the file name, that
creates the pair. Checked on 30 Sep: **all 340 are the capital-letters case and
none is a redirect pointing at a genuinely different live page.**

Still harmless as things stand, and still a property of how pages are named
rather than a fault in any one of them. The decision it needs is a single one
about the destination web server — does it treat capitals as significant? — and
then a tidy-up pass. Not worth holding anything up for.

---

## Enterprise Message Service, Administrator

### Eight links broken in the source documents

- **Status:** Not ours
- **Owner:** authoring team (not yet contacted)
- **Raised:** 29 Sep 2026
- **Blocks publishing:** no

Eight links point at parts of a page that do not exist. These are mistakes in the
documents we receive, not something the conversion introduced, and the same broken
links are live on the current website today. We cannot fix them without changing
somebody else's source material.

Nobody has raised these with the authoring team yet.

---

## GridServer Manager, HPC Cloud Adapter

### Out of scope, and old working copies are still on disk

- **Status:** Accepted
- **Owner:** unassigned
- **Raised:** 29 Sep 2026
- **Blocks publishing:** no

**DataSynapse is not being migrated.** Confirmed 29 Sep 2026. The whole product
line is marked out of scope, so it is not rebuilt when everything else is, and it
is never published.

One consequence to be aware of. The heading-numbering fault repaired across the
rest of the documentation on 29 Sep 2026 also affects two GridServer Manager
security pages, in versions 7.2.0 and 7.1.1, and those two were not repaired —
there is nothing to repair them into. More generally, the converted working
copies for DataSynapse still sitting in the tool's working area date from
19 Sep 2026 and no longer match anything current.

They are harmless where they are: nothing reads them and nothing publishes them.
They are recorded here only so that nobody who stumbles across them later mistakes
them for current work. **Deleting them is safe and has not been done**, because
removing files is not something to do on an assumption.

### Configured but not yet processed

- **Status:** Open
- **Owner:** unassigned
- **Raised:** 29 Sep 2026
- **Blocks publishing:** no

Both products are set up to keep their versions consistent with each other when
they are merged, but neither has reached that stage yet. Nothing is wrong; they
are simply next in line. The settings take effect the first time each is
processed.

---

## Everything, eventually

### Public web address for the new site not set

- **Status:** Open
- **Owner:** unassigned
- **Raised:** 29 Sep 2026
- **Blocks publishing:** no, but redirects are incomplete without it

We have not recorded the address the new documentation site will live at. Until we
do, redirects are written relative to the folder rather than as full web
addresses. They are correct as far as they go, and they will need regenerating
once the real address is known.

### Roughly a third of products may be filed under the wrong group

- **Status:** Open
- **Owner:** unassigned
- **Raised:** 28 Sep 2026
- **Blocks publishing:** no

Products are sorted into groups — messaging, integration, analytics and so on — and
the grouping decides where their files are stored and which repository they
publish to. Checking every product against the rules that are supposed to produce
those groupings showed that 313 of 669 disagree, and 208 of those are recorded as
having been sorted automatically when in fact no rule produces the value they
carry.

In practice this means a refresh of the product list could silently move those
products into a different group. Nothing is broken today and no product we are
actively working on is affected, but this needs a proper pass before the catalogue
is refreshed in bulk.
