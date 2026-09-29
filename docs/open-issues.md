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

### Merged pages not yet reviewed

- **Status:** Open
- **Owner:** unassigned
- **Raised:** 29 Sep 2026
- **Blocks publishing:** yes

The six versions have been merged into larger pages and the result has not been
read by a writer. Eighty-seven pages across the six versions are flagged for
review. Until somebody signs them off, the product is set to publish the older
un-merged pages, so nothing incorrect can reach readers — but the work of
merging is not yet delivering anything either.

The user began this review on 29 Sep 2026.

### Never published to the real destination

- **Status:** Open
- **Owner:** unassigned
- **Raised:** 29 Sep 2026
- **Blocks publishing:** n/a — this *is* the publishing step

The destination folder for ActiveSpaces exists but is empty. The product has only
ever been published to a temporary location used for checking. Publishing it for
real is a deliberate decision that has not been taken, and it is tied to the
review above: publishing today would put out the un-merged pages.

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

## Enterprise Message Service

### Thirty-one redirects differ only in capital letters

- **Status:** Accepted
- **Owner:** unassigned
- **Raised:** 29 Sep 2026
- **Blocks publishing:** no

For thirty-one pages, the old address and the new address are the same except for
capital letters. On a web server that treats capitals and lower case as the same
thing, such a redirect can point at itself and loop.

Harmless as things stand, and it pre-dates the recent merge work — it comes from
the way pages are named, not from anything we changed. Worth a tidy-up pass at
some point; not worth holding anything up for.

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
