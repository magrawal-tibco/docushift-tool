# Phase 34 review: findings index

Base: `review-base` (7dda975). Each unit's full findings file is beside this one.
**Proposed** is the reviewer's recommendation. **Decision** is the user's, and nothing
is fixed until it is filled in.

Severity: **S1** wrong output with no warning, or data loss · **S2** wrong output that is
reported, or a crash on real input · **S3** fragile but correct today · **S4** cleanup.

## Counts

| unit | S1 | S2 | S3 | S4 | total |
|---|---|---|---|---|---|
| R1 Foundations | 1 | 4 | 8 | 2 | 15 |
| R2 Catalog & discovery | 4 | 3 | 13 | 1 | 21 |
| R3 State & acquisition | 0 | 3 | 10 | 3 | 16 |
| **Batch 1** | **5** | **10** | **31** | **6** | **52** |

The orchestrator re-traced R1-01, R2-02 and R3-01 in the code; all three hold.

## Batch 1, grouped into fix themes

Triage approved by the user 2026-10-02, as proposed.

| theme | findings | proposed | decision |
|---|---|---|---|
| **A. Hand edits undone by the next fetch** | R2-01 (S1), R2-03 (S1) | fix | approved: fix 2026-10-02 |
| **B. A dry run, a failed save, or a partial fetch damages saved state** | R2-02 (S1), R2-05 (S2), R1-04 (S2), R3-11 | fix | approved: fix 2026-10-02 |
| **C. Valid situations abort the fetch as "deletions"** | R2-06 (S2), R2-07 (S2) | fix | approved: fix 2026-10-02 |
| **D. Published paths over 260 characters, written silently** | R1-01 (S1), R1-08 | fix | approved: fix 2026-10-02 |
| **E. Dates: epoch milliseconds, the bulk-migration date, "June 2023"** | R2-04 (S1), R1-05 (S2), R1-11, R2-08 | fix | approved: fix 2026-10-02 |
| **F. Zip-slip through a drive letter mid-path** | R3-01 (S2), R3-07 | fix | approved: fix 2026-10-02 |
| **G. A failed or partial extract leaves the old package's measurements in place** | R3-03 (S2), R3-04, R3-05, R3-08, R3-12 | fix | approved: fix 2026-10-02 |
| **H. Wrapped packages: documents reported "unclaimed"** | R3-02 (S2) | fix | approved: fix 2026-10-02 |
| **I. Blank `convert_eligible` reads as false** | R1-02 (S2) | fix | approved: fix 2026-10-02 |
| **J. C API function names publish as truncated MadCap stems** | R1-03 (S2) | fix | approved: fix 2026-10-02 |
| **K. Config entries dropped silently** | R1-06, R1-07 | fix (cheap) | approved: fix (cheap) 2026-10-02 |
| **L. Docs that contradict the code** | R1-12, R1-13, R2-19, R2-20, R3-16 | fix docs | approved: fix docs 2026-10-02 |
| **M. Fragile, correct today** | R1-09, R1-10, R2-10, R2-12, R2-13, R2-14, R2-15, R2-16, R2-17, R2-18, R3-06, R3-09, R3-10, R3-13 | defer to planning.md carried-forward items | approved: defer to planning.md carried-forward items 2026-10-02 |
| **N. Data, not code: 113 "unclassified" products already have a family typed in** | R2-09 | user to review in the catalog | approved: user to review in the catalog 2026-10-02 |
| **O. Cleanup (dead code, duplicates)** | R1-14, R1-15, R2-21, R3-14, R3-15 | one cleanup commit at the end of Phase 34 | approved: one cleanup commit at the end of Phase 34 2026-10-02 |
