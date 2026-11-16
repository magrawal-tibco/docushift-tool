# Origin URL templates for versions with no page rows — 2026-11-16 (DOCOPS-354, DOCOPS-322)

Every template below was checked in memory with the tool's own functions
(`origins.listing` on the cached Coveo sitemap, `origins.build`, `origins.listed`,
`origins.derive`) against the `state.db` output map. Nothing was fetched from the network.
Nothing was run (no convert, reframe, or sync), and `../tibco-docs-aem` was only read
(`git show origin/wip:…`).

An entry in `config/origin-urls.yaml` covers **every version of a product**. The file has
no way to scope an entry to one version. So each template was also checked against that
product's other converted versions.

Column meanings:
- **placed**: topics whose generated URL is listed in the sitemap.
- **rows**: rows `build` writes after the unfiled topics are dropped. These were counted
  with an empty move map, so reframe's `to` values will differ, but the `from` values will not.

## Declared (3 products, uncommitted)

### tibco-activation-service: `https://docs.tibco.com/pub/{folder_path}/doc/{path}`, drop 1

| Version | Placed | Rows | Notes |
|---|---|---|---|
| 1.1.0 | 32 / 36 | 29 | Was undeclared (32/36 is under the 90% coverage threshold). Published 301.yml has 0 page rows. |
| 1.0.0 | 30 / 32 | 27 | Already derives this exact template. Declaring it adds 1 unlisted row (`user-guide/Appendix_In-Product_Activation_with_License_Files.htm`). |

The 4 unlisted 1.1.0 topics are in the package but not in the sitemap. Because the
template is declared, they are still written (finding ORIGIN_URL_UNLISTED):
`deploying-activation-service`, `upgrading-your-tibco-products`,
`product-releases-that-support-activation`, `product-releases-that-support-activation-outage`.

Sample rows (1.1.0):
- `https://docs.tibco.com/pub/tibco-activation/1.1.0/doc/html/user-guide/using-cli.htm -> user-guide/using-cli.md`
- `https://docs.tibco.com/pub/tibco-activation/1.1.0/doc/html/_templates/Home.htm -> _templates/Home.md`

### tibco-businessconnect: `https://docs.tibco.com/pub/{folder_path}/doc/bcis/{path}`, drop 1

| Version | Placed | Rows | Notes |
|---|---|---|---|
| 7.5.0 | 524 / 524 | 507 | 0 unlisted. Published 301.yml has 0 page rows. |
| 7.4.0 | 523 / 523 | 504 | 0 unlisted. Published 301.yml has 0 page rows. |

There are no other BusinessConnect versions with an output map, because 7.3.1 and older
are retired.

**Not solved:** the docsite serves the same help twice, under `doc/bcis/html` and
`doc/bcgs/html`. That duplication is why derivation tied at 524 vs 524. A one-template
entry can map only one of the two. `bcis` is the copy the DOCOPS-322 sheet confirmed live.
About 570 `bcgs` URLs per version stay unmapped (ORIGIN_PAGE_UNMAPPED 591 for 7.4.0 and
631 for 7.5.0, including PDFs).

Sample rows (7.5.0):
- `https://docs.tibco.com/pub/bc/7.5.0/doc/bcis/html/Java_API_Reference.htm -> Java_API_Reference.md`
- `https://docs.tibco.com/pub/bc/7.5.0/doc/bcis/html/tpadmin/_User_Categories.htm -> tpadmin/_User_Categories.md`

### tibco-mdm: `https://docs.tibco.com/pub/{folder_path}/doc/{path}`, drop 1

| Version | Placed | Rows | Notes |
|---|---|---|---|
| 11.1.0 | 2688 / 2688 | 2665 | Was undeclared (runner-up 2549 put the margin under 10%). **The 2665 `from` URLs equal the 2665 page rows of the published hand-restored map exactly** (`origin/wip` ccabb06, 2681 rows including 16 documents): 0 only-published, 0 only-new. |
| 11.0.0 | 2695 / 2695 | 2524 | Same rows as today's derivation. |
| 10.0.0 | 7969 / 7969 | 2675 | Same rows as today's derivation. |
| 9.3.2 | 3055 / 3055 | 2690 | Same rows as today's derivation. |

Side effect: the declaration changes each version's fingerprint, so the next MDM reframe
rebuilds all four versions. Only 11.1.0's map changes.

Sample rows (11.1.0):
- `https://docs.tibco.com/pub/mdm/11.1.0/doc/Custom-installation/Custom-installation/JBossWildFly-Oracle-EMS.htm -> Custom-installation/JBossWildFly-Oracle-EMS.md`
- `https://docs.tibco.com/pub/mdm/11.1.0/doc/relnotes/_templates/documentation-and-support-services.htm -> relnotes/_templates/documentation-and-support-services.md`

## Not declared: blocked by the file format (one template per product, not per version)

### tibco-businessconnect-trading-community-management 6.2.0 and 6.1.0

- **6.2.0:** `https://docs.tibco.com/pub/{folder_path}/doc/bctcm/{path}`, drop 1, places
  108 / 108. It ties with `doc/webclient/html`, the same duplication as BusinessConnect.
  `bctcm` is the copy the sheet confirmed.
- **6.1.0 (and 6.1.1):** cannot be mapped by any one-template entry, for two reasons:
  - Its `zip_url` sits at `pub/bctcm/` with no version, so `{folder_path}` is `bctcm`.
  - Its sources split between two served roots: `html/…` goes to
    `pub/bctcm/6.1.0/doc/bctcm/html/…`, and `tib_bctcm_client/…` goes to
    `pub/bctcm/6.1.0/doc/webclient/html/tib_bctcm_client/…`.
- If the 6.2.0 entry were declared, it would also apply to 6.1.0 and 6.1.1. It would write
  81 and 150 rows from URLs that never existed (0 in the sitemap, e.g.
  `https://docs.tibco.com/pub/bctcm/doc/bctcm/html/…`). Those rows would also hide 6.1.0
  from the SYNC_ORIGIN_NO_PAGE_ROWS check, the warning that found this problem. So it is
  left out.

### tibco-businessconnect-partner-management-portal 1.0.0

- The 1.0.0 sitemap, and its go-URLs (`reports/redirects/go-urls-2026-10-26.csv`), serve
  this version from **`/emp/`**, not `/pub/`, e.g.
  `https://docs.tibco.com/emp/bcce-pmp/1.0.0/doc/html-client/…`.
- Derivation refuses it because the folder guard requires `pub/bcce-pmp/1.0.0`, which is
  why it found 0 / 0.
- `https://docs.tibco.com/emp/{folder_path}/doc/{path}`, drop 1, places 134 / 134 for 1.0.0.
  But the same entry places 0 / 134 for 1.1.0 and 1.1.1, which derive correctly under
  `/pub/` today. Declaring it would break them, so it is left out.

### What would unblock both

A per-version override in `origins.declaration`, which needs a small code change and a
test. For example:

```yaml
tibco-businessconnect-partner-management-portal:
  versions:
    "1.0.0": {template: "https://docs.tibco.com/emp/{folder_path}/doc/{path}", drop_segments: 1}
tibco-businessconnect-trading-community-management:
  versions:
    "6.2.0": {template: "https://docs.tibco.com/pub/{folder_path}/doc/bctcm/{path}", drop_segments: 1}
```

BCTCM 6.1.0 needs more than this, because it has two served roots and no version in its
folder. It would need either a template that can name a subtree per source prefix, or a
corrected `zip_url` plus two rules.

## Commands after this edit (not run)

```
docushift reframe --product tibco-activation-service --version 1.1.0
docushift reframe --product tibco-businessconnect --version 7.4.0
docushift reframe --product tibco-businessconnect --version 7.5.0
docushift reframe --product tibco-mdm --version 11.1.0
```

After that, sync and publish as usual. BusinessConnect's local, unpushed Phase 80 commit
4bad5b4 in `en-us-tib-businessconnect-userdocs` has to be resolved first.

Tests: `python -m pytest -q tests/unit -k origin`: 67 passed.
