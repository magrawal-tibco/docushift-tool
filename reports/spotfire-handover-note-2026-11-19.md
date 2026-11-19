# Spotfire Statistica and Data Virtualization: hand-over to Digital Platform, 19 Nov 2026

Both repositories are ready on `main` for the Spotfire site (AEM). They carry the same fixes as
the TIBCO and ibi repositories.

| Repository | Commit on `main` |
|---|---|
| [en-us-spotfire-statistica-userdocs](https://github.com/tibco/en-us-spotfire-statistica-userdocs) | [`0084f280`](https://github.com/tibco/en-us-spotfire-statistica-userdocs/commit/0084f280) |
| [en-us-spotfire-data-virtualization-userdocs](https://github.com/tibco/en-us-spotfire-data-virtualization-userdocs) | [`b7d0eed5`](https://github.com/tibco/en-us-spotfire-data-virtualization-userdocs/commit/b7d0eed5) |

## What is in them

- **Statistica family:** 17 versions across 11 products (online help, user guides, release
  information). **Data Virtualization:** 8.9.0, 8.8.1, 8.8.0.
- Redirect files (`301.yml`) in AEM's per-version shape, including document rows in the DAM. The
  product-level redirect file is gone.
- Note labels shown as "Note:"; backslashes and `<` written so AEM shows them as text; help menu
  titled "<product> <version>".
- **Data Science Workbench 14.4.0 is not published:** it was the same 14,250 pages as Statistica
  14.4.0. Its 13,933 old addresses (`docs.tibco.com/pub/dsc-stat/14.4.0/...`) redirect to the same
  pages under Statistica 14.4.0.
- **Data Virtualization:** the Data Virtualization team's link corrections for 8.9.0 are applied (88
  links per version, 8.8.x matched by page name); re-converted with the current converter
  (doubled headings, the "Text Escaping" page).

## Checked

Local checks of every version against the old site (there is no Spotfire staging site yet): no
errors. What remains is expected: menu entries placed under our grouping, and a few items from the
source documentation (Greek letters the source escaped twice now show as letters; a few topics the
packages never shipped).

## Open points

1. **Data Science Workbench 14.1.0 publishes the same pages as Statistica 14.1.0** (14,366). To
   decide whether it is dropped the same way as 14.4.0.
2. **Data Virtualization team, to confirm:** the link "ApplicantApplications" (Dynamics GP adapter)
   was answered with the singular page; we used the plural page `ApplicantApplications`, which exists.
   The 6 missing pictures stay out, as answered.
3. **Statistica is published one page per topic** (as converted; never merged). Grouping it the way
   the TIBCO help is grouped is a follow-up before the Spotfire site goes live.
4. Please tell us which branch and site the Spotfire build reads, and when a staging site is
   available, so the pages can be checked there.
