# Versions on docs.tibco.com that we have not published (17 Nov 2026)

**Question.** Control Plane 1.21.0 and 1.22.0 are on docs.tibco.com, but we have no converted docs for them. How many versions are like that, and why?

**How this was checked.** The tool's own discovery code read the live docsite today (668 products, 5,222 versions, no errors). Nothing in the catalog was changed: the result was written to `C:/tmp/docsite-check/`. It was compared with the catalog and with what is published. The full list is in `delta-missed-versions-2026-11-17.csv`, one row per version.

## The short answer

- **Nothing is missing from our catalog.** Every version on the docsite today is in it. No new versions have appeared since the Δ1 refresh on 15 Nov.
- **13 versions should have been converted but were not.** All 13 came in with the **5 Nov catalog refresh**. That refresh added them to the catalog, but no batch was ever scheduled to download them. The Δ1 plan assumed that everything up to 5 Nov was already handled, so these 13 fell through the gap. Control Plane 1.21.0 and 1.22.0 are two of them.
- Every other unpublished version is unpublished on purpose: out of scope, Karan said not to migrate it, support retired it, or it was not selected.

## Control Plane 1.21.0 and 1.22.0

- **1.21.0** is dated 16 Sep, but docs.tibco.com only made it public on **12 Oct**. That was three days after the 9 Oct refresh, so the 9 Oct refresh could not see it.
- **1.22.0** is dated 30 Oct and was made public on **5 Nov**.
- The 5 Nov refresh added both to the catalog, selected for conversion. Neither has been downloaded since: no batch list includes them.
- Karan's list for Control Plane stops at 1.20.0. He chose 1.18–1.20 to migrate, 1.17 and older not to. Under the closeout plan (§6a), newer versions are converted by default and go on a short list for him to confirm.

## Live versions not published, by reason

| Reason | Current | Archived | Total |
|---|---:|---:|---:|
| (a) Not in our catalog | 0 | 0 | **0** |
| (b) Out of scope | 438 | 864 | **1,302** |
| (c) Karan: do not migrate | 327 | 522 | **849** |
| (d) Selected, but not downloaded or converted | 13 | 0 | **13** |
| (e) Other: retired by support, or not selected | 571 | 1,639 | **2,210** |

For comparison, 848 live versions are published. "Archived" means the version is on the docsite's "Other Versions" page.

### By business unit (current versions only)

| BU | (b) | (c) | (d) | (e) |
|---|---:|---:|---:|---:|
| TIBCO | 122 (114 of them retired Flogo connectors) | 327 (Cloud 103, Integration Platform 88, BW plug-ins 68, BusinessWorks 63, Control Plane 5) | **11** | 473 |
| ibi | 0 | 0 | **2** | 89 |
| Spotfire | 274 (Spotfire analytics; Statistica scoped down 22 Oct) | 0 | 0 | 9 |
| EBX (onebx) / DataSynapse | 36 / 6 | 0 | 0 | 0 |

Group (e), current versions only: 330 were set not to convert by hand, 132 have "Migrate to new docsite" set to no on the business sheet, 92 were retired by support, and 17 have a manual "do not migrate".

## The 13 versions to act on (group d)

| Product | Version | Why it is waiting | Suggested action |
|---|---|---|---|
| Control Plane | 1.21.0, 1.22.0 | Never downloaded | Convert and publish in R2; add both to Karan's list to confirm |
| ActiveSpaces | 5.2.1, 5.1.2 | Never downloaded | Convert and publish in R2 |
| BW Plug-in for AI | 6.0.2 | Unpacked 12 Nov in a family batch, never converted | Convert and publish in R2 |
| Streaming (4 products) | 11.1.4 | Never downloaded | Download and convert now; publish with Streaming in R3 (decision D1) |
| GEMS | 1.2.0 | Never downloaded. 1.1.0 is in a help format we cannot convert (Docusaurus), so it was set not to convert on 23 Oct | Download and check the format; probably the same decision as 1.1.0 |
| Graphical ActiveSpaces (new product) | 1.1.0 | Never downloaded. Its sister product, Graphical Rendezvous, is Docusaurus | Download and check the format; user decides |
| ibi AI Assistant | 9.3.81 | Never downloaded; ibi was on hold until 16 Nov | Convert and publish with the ibi batches |
| ibi WebFOCUS Client | 9.2.8 | Never downloaded; ibi was on hold until 16 Nov | Convert and publish with the ibi batches |

## Next steps

1. Put the 13 into the next batch while the old site is still up (it goes offline 30 Nov). Add their ZIPs to the backup.
2. Send Control Plane 1.21.0 and 1.22.0 to Karan to confirm (his list stops at 1.20.0).
3. Make "schedule what the refresh added" a fixed step after every refresh, so Δ3 on 27 Nov cannot repeat this gap.
