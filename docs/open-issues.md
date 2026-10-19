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

## Spotfire Data Science – Author, ActiveMatrix Adapter Service Engine for PeopleSoft

### Counted as converted, but the converted files are gone

- **Status:** Open (deferred by decision, 5 Oct 2026)
- **Owner:** unassigned
- **Raised:** 5 Oct 2026
- **Blocks publishing:** no

One version of each product, Data Science – Author 1.4.0 and the PeopleSoft adapter
6.0.0, was converted in an early trial on 12 Sep 2026 from a folder supplied by hand.
Those converted files have since been deleted, but the tool still remembers the
conversion. So the versions sheet shows both as "converted" and never synced, and the
status report counts two more converted versions than really exist.

Neither package has ever been downloaded or unpacked in the working area, and the tool
does not yet know their help format. Fixing this means running the full sequence for
both: download, unpack, convert, then sync. The PeopleSoft package sits at an unusual
web address, so it may have to be downloaded by hand. Decided on 5 Oct 2026 to leave
both as they are for now.

---

## Silver Fabric Enabler for ActiveSpaces

### The whole guide set appears twice in the navigation

- **Status:** Fixed, 4 Oct 2026 — the duplicate copy is no longer converted
  (commit 731ad26); the re-run output holds each guide once, 46 pages, down from 97
- **Owner:** unassigned
- **Raised:** 2 Oct 2026
- **Blocks publishing:** no longer

Version 1.2.0's converted output holds both guides — Installation and User's
Guide — twice, once under an `html` folder and once without it, and the
navigation lists both copies one after the other. A reader would see every chapter
twice. Found while comparing DocuShift's navigation with the old tool's; the old
tool never converted this product, so there is nothing to compare against. The
cause is in how this older help format's folders are discovered, not in the
navigation itself, and it has not been looked into yet.

---

## Messaging Manager

### Online help for 4.0.0 and 3.1.1 not published

- **Status:** Open
- **Owner:** unassigned
- **Raised:** 12 Oct 2026
- **Blocks publishing:** yes, for the online help (the PDFs are published)

Three command pages in the User's Guide are titled with a single symbol: `!`, `/`
and `#`. When topics are merged into larger pages, each topic gets a link target
built from its title, and a title made only of symbols produces an empty one. The
Getting Started page then holds several topics with the same empty target, and the
safety check rightly refuses to publish it. The fix is a small tool change: fall
back to the topic's file name (exclamation point, forward slash, pound sign) when
the title gives nothing usable. Not yet planned.

---

## eFTL Enterprise Edition

### Link to the Python API page is broken in every version

- **Status:** Open
- **Owner:** unassigned
- **Raised:** 12 Oct 2026
- **Blocks publishing:** no

In all six published versions (7.1.0 to 7.3.0), the API Documentation page links to
the Python connection page. That page sits in the API reference folder but was not
recognised as part of it, so it was neither converted nor linked to its published
copy. Readers who follow the link get nothing. The API reference itself is
published; the link needs pointing at it, which is a tool change.

---

## FTL Enterprise Edition

### 7.1.1 is missing its .NET API reference

- **Status:** Open
- **Owner:** unassigned
- **Raised:** 12 Oct 2026
- **Blocks publishing:** no

Version 7.1.1 ships its .NET API reference loose at the top of the package instead
of in an API folder, about 206 generated pages. The tool did not recognise them as
an API reference and skipped them, so this version publishes without it. The prose
help is complete, and the other five versions are not affected.

---

## GEMS, Graphical Rendezvous

### Help format not supported

- **Status:** Open
- **Owner:** unassigned
- **Raised:** 12 Oct 2026
- **Blocks publishing:** yes, for the online help of GEMS 1.1.0 and Graphical Rendezvous 1.1.0

Both are built with Docusaurus, a help format the tool recognises but has no
converter for. Their PDFs and readme files are published; the online help is not.
To decide: mark them out of scope, or build a converter. Two versions are unlikely
to justify a converter on their own.

---

## Messaging Suite

### No package for 1.23.0

- **Status:** Open
- **Owner:** unassigned
- **Raised:** 12 Oct 2026
- **Blocks publishing:** yes, for this one version

The documentation site does not return a package for 1.23.0, while 1.21.0, 1.22.0
and 1.24.0 onwards all download normally. Every Messaging Suite package holds only
PDFs, so what is missing is a handful of PDFs. To decide: mark the version out of
scope, or get the package by hand.

---

## Rendezvous

### Some links land on the wrong section of the right page

- **Status:** Open
- **Owner:** unassigned
- **Raised:** 12 Oct 2026
- **Blocks publishing:** no

Several long Rendezvous pages repeat the same section heading, for example
"Forward RVCM administrative messages across network boundaries". A link meant for
a later occurrence opens the page at the first one. Measured on 12 Oct 2026: 288
links across 8.8.0, 8.8.1 and 9.0.0. The reader reaches the right page, then has to
scroll. To decide: accept it, or change the tool so repeated headings get distinct
link targets.

---

## Cloud API Modeler

### Three links point to topics readers cannot reach

- **Status:** Open
- **Owner:** unassigned (editorial)
- **Raised:** 12 Oct 2026
- **Blocks publishing:** no

In 1.5.0, three pages link to topics the original help shipped but never listed in
its table of contents: Security (from Managing Resources), Modes of Editing (from
Modeling an API) and Managing Requests (from Reference Schema). Those topics are
kept aside and not published, so the three links go nowhere. A writer should either
add the topics to the navigation or remove the links.

---

## Foresight Instream

### 9.4.0: two Business Rules pages still show the previous release's text

- **Status:** Open; accepted for now
- **Owner:** unassigned
- **Raised:** 13 Oct 2026
- **Blocks publishing:** no (9.4.0 is published)

The 9.4.0 help keeps an older copy of the Business Rules guide alongside the current
one. The current pages carry a different file name, and the tool now matches the usual
renaming, so the guide shows the current text. Two pages, Local Variables and ICD
Business Rules, were renamed in a way that could also fit a different page with the
same title, so they were not matched and still show the 9.3.0 text. Matching them by
hand is a one-line change each, if anyone needs it.

---

## Foresight Transaction Insight

### 5.4.0: the hotfix addendum is not in the online help

- **Status:** Open; published without it
- **Owner:** unassigned
- **Raised:** 13 Oct 2026
- **Blocks publishing:** no

5.4.0's table of contents does not list the release notes or the hotfix addendum
(43 pages), and no other page links to them. The release notes also ship as a PDF,
which is published. The hotfix addendum has no PDF, so it reaches readers only if
someone decides to add it to the navigation by hand.

---

## BusinessWorks plug-ins

### SAP BTP 6.0.0 and OData for SAP S/4HANA 6.3.0 and 6.4.0 lost their navigation

- **Status:** Open; not investigated
- **Owner:** unassigned
- **Raised:** 13 Oct 2026
- **Blocks publishing:** yes, for these three versions (not published; marked out of date)

Converted on 7 Oct 2026, each came out with a table of contents of two entries (Home
and What's New), and 96–97% of its pages fell outside it. The source table of contents
in the docsite package is complete: 53 entries for SAP BTP 6.0.0. The extracted files
are gone from this workspace, so finding the cause needs a fresh download.

---

## Flogo

### 3.0.1 has no downloadable package

- **Status:** Open
- **Owner:** unassigned
- **Raised:** 14 Oct 2026
- **Blocks publishing:** yes, for 3.0.1

The docsite's package link for 3.0.1 returns a web page instead of a ZIP, most often a
sign-in or error page. The other five Flogo versions are published. A retry may work
once the docsite is fixed; otherwise the package has to be obtained by hand.

---

## BusinessWorks

### Container Edition Buildpack for PCF 2.2.1 and FormBuilder 5.3.2 have no package

- **Status:** Open
- **Owner:** unassigned
- **Raised:** 14 Oct 2026
- **Blocks publishing:** yes, for these two versions

As with Flogo 3.0.1, the docsite returns a web page instead of a ZIP.

---

## Fulfillment

### Product and Service Inventory 2.1.0 has no package

- **Status:** Open
- **Owner:** unassigned
- **Raised:** 14 Oct 2026
- **Blocks publishing:** yes, for 2.1.0

As with Flogo 3.0.1, the docsite returns a web page instead of a ZIP.

---

## Enterprise MDM

### 1.0.0 has no documentation

- **Status:** Accepted
- **Owner:** unassigned
- **Raised:** 15 Oct 2026
- **Blocks publishing:** no

The package holds only a readme and licence files, so there is no online help to
convert. The licence files are published as reference documents.

---

## Everything, eventually

### A withdrawn version stays in the drop-downs and redirect maps

- **Status:** Open
- **Owner:** unassigned
- **Raised:** 15 Oct 2026
- **Blocks publishing:** no

When a published version is made ineligible and its folders are removed by hand, the
next publish keeps its entries in the version drop-down and the redirect maps: the
tool treats an entry it no longer recognises as hand-written and leaves it alone. MDM
Studio 5.3.0's entries (4 drop-downs, about 2,700 redirects) were removed by hand on
15 Oct 2026. Withdrawing a version should be a tool step, so this is not repeated by
hand for every family.

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

---

## Business Studio Community Edition

### 4.2.0 has no package

- **Status:** Open
- **Owner:** unassigned
- **Raised:** 15 Oct 2026
- **Blocks publishing:** yes, for 4.2.0, the only Community Edition version

As with Flogo 3.0.1, the docsite returns a web page instead of a ZIP.

---

## ActiveMatrix BPM

### 4.3.0 online help not published: 179 pages too deep for Windows

- **Status:** Open
- **Owner:** unassigned
- **Raised:** 17 Oct 2026
- **Blocks publishing:** yes, for 4.3.0's online help (its PDFs and API reference are published)

The help nests topics up to nine folders deep, and 179 of its 1,340 pages would end up past
Windows' 260-character path limit in the publishing repo. That is too many to rename by hand,
so it needs a rule, planned as a phase. The main guide's folder is also named
"tibco-activematrix-bpm-2", which is a poor web address in its own right.

---

### 4.2.0 is refused at unpacking: two different files with one name

- **Status:** Open
- **Owner:** unassigned
- **Raised:** 15 Oct 2026
- **Blocks publishing:** yes, for 4.2.0

The package holds RESTServiceConfig.properties and restserviceconfig.properties in the
same folder, with different contents (507 and 568 bytes). Windows cannot keep both, and the
tool does not pick one on a writer's behalf. It is a configuration sample, not a help page,
so keeping either is likely harmless, but someone has to say which. 4.3.0 converted.

---

## Business Studio BPM Edition

### 5.6.0, 5.6.1 and 5.7.0 online help waits on three shorter folder names

- **Status:** Waiting, on approval of the proposed names
- **Owner:** unassigned
- **Raised:** 17 Oct 2026
- **Blocks publishing:** yes, for these three versions' online help (their PDFs are published)

Three pages per version would end up past Windows' 260-character path limit. Shorter names
for three folders in the case-data chapter fix all of them; the proposal is drafted for
review. 4.3.5 is published.

---

## Hawk

### Redtail 7.5.0 and 6.3.1 online help waits on six shorter folder names

- **Status:** Resolved, 19 Oct 2026
- **Owner:** unassigned
- **Raised:** 19 Oct 2026
- **Blocks publishing:** no longer; both versions' online help is published

Four of 7.5.0's 297 pages and two of 6.3.1's 582 would end up past Windows' 260-character
path limit in the publishing repo (the longest at 280). Few enough to rename by hand, as was
proposed for Business Studio BPM Edition. Several folders carry a "-2" suffix that is a poor
web address in its own right.

Resolved by three folder names written into each version's rename-map.csv, approved by the
user: `com-tibco-hawk-tibjms-hawklistener-microagent` → `hawklistener-microagent` (6.3.1),
`configuration-tibco-oi-hawk-redtail-enterprise` → `configuration-enterprise` and its `-2` twin
→ `configuration-ce` (7.5.0). Longest published path is now 259. The `-2` guide in 7.5.0 is the Container Edition's
installation guide (its pages cover containerized
components); the user confirmed it, and the guide was renamed `installation-configuration-administration-ce`
with the `-2` suffixes dropped from its 17 pages (longest path 255 within it). The redirect maps send
docs.tibco.com addresses to the new paths; the interim `-2` addresses, live for about an hour, get no
redirect.

---

## iProcess Suite

### 1.0.0 is a suite landing page only

- **Status:** Accepted
- **Owner:** unassigned
- **Raised:** 20 Oct 2026
- **Blocks publishing:** no

The iProcess Suite 1.0.0 entry on the documentation site is only a suite page, a single HTML page
with no documentation package. There is nothing to convert, so the version is marked not
eligible (confirmed by the user, 20 Oct 2026).
