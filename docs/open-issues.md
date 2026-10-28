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

## AEM platform (every product)

Problems in how the staging site shows pages, found by the "nothing lost" check.
They affect every product, so they live here once rather than under each
product. The check records each one as already explained, so it does not hide a
new loss; the decisions are kept in the tool's triage file.

### Picture descriptions dropped when they contain `/`, `:` or `⌘`

- **Status:** Waiting
- **Owner:** AEM owners (tracked as DOCOPS-255)
- **Raised:** 23 Oct 2026
- **Blocks publishing:** no

The staging site shows some pictures without their description, the text a
screen reader reads out. On ibi™ AI Assistant 9.3.8 that is 5 of 16 pictures.
Every description it drops contains a slash, a colon or the ⌘ sign; every one it
keeps contains none of them. The converted pages carry the descriptions
correctly, so nothing needs to change on our side. When it is fixed, the check
stops reporting it.

### Notes shown without their "Note" or "Tip" label

- **Status:** In progress
- **Owner:** this project (tracked as DOCOPS-250)
- **Raised:** 22 Oct 2026
- **Blocks publishing:** no

The staging site did not understand the way notes were written, so readers saw
the note text with no label. The converter now writes notes the way the site
shows them, and the published products are being corrected one family at a time
(Statistica and ibi™ AI Assistant so far). Each product clears once the site
republishes it.

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

## ActiveMatrix Adapter Service Engine for PeopleSoft

### Counted as converted, but the converted files are gone

- **Status:** Open (deferred by decision, 5 Oct 2026)
- **Owner:** unassigned
- **Raised:** 5 Oct 2026
- **Blocks publishing:** no

Version 6.0.0 was converted in an early trial on 12 Sep 2026 from a folder supplied by
hand. Those converted files have since been deleted, but the tool still remembers the
conversion. So the versions sheet shows it as "converted" and never synced, and the
status report counts one more converted version than really exists.

The package has never been downloaded or unpacked in the working area, and the tool
does not yet know its help format. Fixing this means running the full sequence:
download, unpack, convert, then sync. The package sits at an unusual web address, so it
may have to be downloaded by hand. Decided on 5 Oct 2026 to leave it as it is for now.

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

- **Status:** Accepted
- **Owner:** unassigned
- **Raised:** 12 Oct 2026
- **Blocks publishing:** no

Both are built with Docusaurus, a help format the tool recognises but has no
converter for. On 22 Oct 2026 the user marked both versions as not for conversion,
so their online help is not migrated. Their PDFs and readme files are published.
Revisit if more Docusaurus products appear.

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

## BusinessWorks

### Container Edition Buildpack for PCF 2.2.1 has no package

- **Status:** Accepted
- **Owner:** unassigned
- **Raised:** 14 Oct 2026
- **Blocks publishing:** no

The docsite returns a web page instead of a ZIP, so there is nothing to convert. The version is
marked not eligible (decided by the user, 21 Oct 2026).

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

## ActiveMatrix BPM

### 4.3.0 and 4.2.0 online help not published: pages too deep for Windows

- **Status:** Open
- **Owner:** unassigned
- **Raised:** 17 Oct 2026
- **Blocks publishing:** yes, for the online help of 4.3.0 and 4.2.0 (their PDFs and API references are published)

The help nests topics up to nine folders deep, and 179 of its 1,340 pages would end up past
Windows' 260-character path limit in the publishing repo. That is too many to rename by hand,
so it needs a rule, planned as a phase. The main guide's folder is also named
"tibco-activematrix-bpm-2", which is a poor web address in its own right.

**4.2.0 joined on 22 Oct 2026.** It used to be refused at unpacking because two copies of a
sample settings file differed only in letter case. The user chose to keep
RESTServiceConfig.properties, the spelling the help links to and the only one 4.3.0 ships,
and a repaired copy of the package without the other one was supplied by hand. It then
unpacked, converted and merged (1,286 pages), and its PDFs, release notes and API reference
were published. Its online help is held the same way: 111 pages over the limit, longest 371.
The same naming rule will fix both versions.

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

---

## General family

### API references wait on a resources repository

- **Status:** Open
- **Owner:** unassigned
- **Raised:** 21 Oct 2026
- **Blocks publishing:** yes, for the API references of Enterprise Administrator 2.4.2 and 2.4.3
  and Patterns 6.1.2 and 6.2.0 (their help, guides and release notes are published)

The General family's resources folder has no GitHub repository behind it, so what the run
placed there cannot be pushed. Once someone creates and clones the repository, the folder can be
pushed as it is.

---

## Health Essentials Cloud

### The Cloud version has no package

- **Status:** Accepted
- **Owner:** unassigned
- **Raised:** 21 Oct 2026
- **Blocks publishing:** no

The docsite returns a web page instead of a ZIP, so there is nothing to convert. The version is
marked not eligible (decided by the user, 21 Oct 2026).

---

## Patterns

### 5.7.1 is refused at unpacking: one folder in two letter cases

- **Status:** Accepted
- **Owner:** unassigned
- **Raised:** 21 Oct 2026
- **Blocks publishing:** no

The package holds the Learn user interface guide twice, in folders named "learning-UI" and
"learning-ui", with different text on all 40 pages. Rather than pick a copy, 5.7.1 is marked
not eligible; 6.2.0 and 6.1.2 are published (decided by the user, 21 Oct 2026).

---

## Statistica family

### Publishing never removes a version that stops being eligible

- **Status:** Open
- **Owner:** unassigned
- **Raised:** 22 Oct 2026
- **Blocks publishing:** no, but a withdrawn version stays published unless removed by hand

On 21 Oct 2026 the developers withdrew 22 Statistica and Data Science versions after
many had already been published. Publishing only adds and replaces versions, so the
withdrawn ones stayed. This time both Statistica publishing folders were deleted and
republished, leaving the 19 approved versions. A family that is already pushed cannot be
cleared that way, so the tool needs to remove withdrawn versions itself.

---

## Data Virtualization

### 102 errors per version in the source, waiting on the team

- **Status:** Waiting
- **Owner:** Data Virtualization docs team
- **Raised:** 23 Oct 2026; published with them 26 Oct 2026
- **Blocks publishing:** no

8.9.0, 8.8.1 and 8.8.0 were published on 26 Oct 2026 with the source's own errors as
they are, by the user's decision: 92 links pointing at the wrong page, 6 images missing
from the package, 4 web addresses without `https://`. Readers see the links' text with
no link and the pages without the images. The report and spreadsheet of suggested fixes
went to the team (`reports/data-virtualization-conversion-errors.md`). Once they confirm,
the corrections are applied and the versions republished. The 4 web addresses need no
one's answer.

### The check reads "lost" when nothing is lost

- **Status:** Open
- **Owner:** unassigned (tool)
- **Raised:** 26 Oct 2026
- **Blocks publishing:** no, but every Data Virtualization version reads "lost" on the status page

The check that compares published pages with the old site reported about 3,500 lost
contents entries per version. Looked at one by one, nothing was lost: the check
compares old entries that point at a heading inside a page with new entries that point
at the page; it matches folder names only in the source's exact capital letters; and it
reads the escaped form of text like `<install directory>` as different text. The check
needs fixing before its verdict means anything for this product, and the same causes
would hit any other product with the same source habits.

One real slip found along the way: on the XML "Text Escaping" page, three examples
whose point is the escaped form (`&amp;`, `&gt;`, `&quot;`) display as the plain
characters, in every version.

## WebFOCUS, Data Virtualization (translated documentation)

### Translated pages that are on the live site but not in any package

- **Status:** Waiting
- **Owner:** docs team
- **Raised:** 22 Oct 2026
- **Blocks publishing:** yes, for these translations only

The tool converts what the download packages contain. Three sets of Japanese
documentation are on docs.tibco.com but in no package, so they cannot be migrated:

- Data Virtualization 8.8.0 and 8.8.1, Japanese online help: 6,917 pages
- WebFOCUS Client 9.3.5 to 9.3.7, Japanese release notes: 252 pages
- WebFOCUS 9.1.2 to 9.3.4, Japanese PDFs: 121 files

Decided by the user, 22 Oct 2026: ask the docs team for packages rather than copy the
pages from the live site. When a package arrives it goes through the normal
conversion into the matching translated repository. Data Virtualization's,
`loc-spotfire-data-virtualization-userdocs`, does not exist yet and must be created first.

---

## WebFOCUS

### Three gaps left in redirects from old web addresses

- **Status:** Open
- **Owner:** unassigned
- **Raised:** 25 Oct 2026; narrowed 26 Oct 2026
- **Blocks publishing:** no, but it blocks cutover for the pages named

Old-site page lists that mix five languages left 13 WebFOCUS and Reporting Server
versions with no redirects. Since 26 Oct the tool reads only the English pages, and
11 of them now have redirects. What is left:

- **App Studio 9.3.8** still has none: only 257 of its 323 pages are in the old
  site's English list, too few for the tool to trust a rule.
- **DSML Services 9.3.8** still has none: its page list has no English folder at all.
- **Client 9.3.8 and Reporting Server 9.3.8 release notes**: 66 pages each have no
  redirect. In 9.3.8 the release notes moved to their own address on the old site,
  apart from the main help, and the tool builds one address rule per version.

The fix for all three is the one DSML Services Container Edition got: someone
confirms the old address pattern once, it is recorded, and the redirects follow.

### Open Data Hub and Reporting Server: one link broken in the source

- **Status:** Not ours
- **Owner:** authoring team (not yet contacted)
- **Raised:** 25 Oct 2026
- **Blocks publishing:** no

In Open Data Hub 1.0.3 to 1.3.4 and Reporting Server 9.3.0 to 9.3.4, the shared z/OS
installation pages link to an
"Optional Low-Level Qualifier Changes" page that is not in the documents we receive.
The link is broken in the source, before any conversion.

### Translated 9.3.8 help: the Functions Reference menu points to pages that do not exist

- **Status:** Not ours
- **Owner:** authoring team (not yet contacted)
- **Raised:** 28 Oct 2026
- **Blocks publishing:** no

In the German, Spanish, French and Japanese WebFOCUS Client 9.3.8 help, the Functions
Reference menu is an older version than the English one. Instead of grouping functions
by category, it splits them into WebFOCUS Server, WebFOCUS Client and FOCUS sections.
About 1,070 of its entries in each language lead nowhere: the FOCUS section points to a
`focus-functions` folder, and the three section headings point to temporary pages, and
neither is in the documents we receive. The function pages themselves are there under
another folder and are published. These entries were already broken on the old site;
the full list is `reports/verify/ibi/ibi-webfocus-client/9.3.8-translated-menu-gaps.csv`.
The check counts them as a known source problem, not a loss.

### Client 9.1.0 and 9.1.1 packages include a help server by mistake

- **Status:** Not ours
- **Owner:** authoring team (not yet contacted)
- **Raised:** 25 Oct 2026
- **Blocks publishing:** no

The 9.1.0 and 9.1.1 download packages each carry a 530 MB zip file beside the PDF
guides. Inside is the installable help server customers deploy on their own systems,
not a document, and help should never ship as a zip. It was put in the package by
mistake. Our copy step published every file in that folder, so the zips reached the
WebFOCUS branch, and the repository host refused them for size. They were taken out
by hand on 25 Oct 2026; nothing else in any ibi package is like them.

Until the copy step skips such files, they come back on every copy of these two
versions and have to be taken out again before publishing.

## Legacy (ibi)

### Most Legacy products are still the first-draft format

- **Status:** Open
- **Owner:** docushift
- **Raised:** 27 Oct 2026
- **Blocks publishing:** no

The Legacy repository holds the first draft published on 16 Sep 2026. Only Omni-Gen,
Omni-Gen MDM, Omni-HealthData (re-published 27 Oct 2026) and iWay BAM and Trading Partner
Manager are in the current format: product labels with the product's name rather than
its short code, and index pages with the current headings. The rest of the family needs
a re-publish to match.
