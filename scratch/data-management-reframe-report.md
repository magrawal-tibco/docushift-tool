# DocuShift findings -- reframe run 876

- **Command:** `docushift reframe`
- **Started:** 2026-10-15T05:31:16+00:00
- **Finished:** 2026-10-15T05:36:26+00:00
- **Exit code:** 0
- **Findings:** 23 warnings, 19 notes

## convert

### ORIGIN_PAGE_UNMAPPED (warning)

Live docsite pages no 301.yml row starts from -- API reference, PDFs, help-system frames -- each a 404 at cutover unless redirected elsewhere -- *planning.md Phase 33*

| Product | Path | Message |
| :--- | :--- | :--- |
| ibi-mdm-add-on-for-global-data-synchronization@4.0.0 |  | 9 live page(s) with no 301.yml row, e.g. https://docs.tibco.com/pub/cim-gdsn/4.0.0/TIB_cim-gdsn_4.0.0_readme.txt |
| tibco-mdm@11.1.0 |  | 199 live page(s) with no 301.yml row, e.g. https://docs.tibco.com/pub/mdm/11.1.0/TIB_cim_11.1.0_readme.txt |
| tibco-mdm@11.0.0 |  | 198 live page(s) with no 301.yml row, e.g. https://docs.tibco.com/pub/mdm/11.0.0/TIB_cim_11.0.0_readme.txt |
| tibco-mdm@10.0.0 |  | 195 live page(s) with no 301.yml row, e.g. https://docs.tibco.com/pub/mdm/10.0.0/TIB_cim_10.0.0_readme.txt |
| tibco-mdm@9.3.2 |  | 203 live page(s) with no 301.yml row, e.g. https://docs.tibco.com/pub/mdm/9.3.2/TIB_cim_9.3.2_LicenseActivationandConfiguration.pdf |
| tibco-mdm-studio@6.1.1 |  | 25 live page(s) with no 301.yml row, e.g. https://docs.tibco.com/pub/bstudio-mdm/6.1.1/TIB_bstudio-mdm_6.1.1_readme.txt |
| tibco-mdm-studio@6.1.0 |  | 19 live page(s) with no 301.yml row, e.g. https://docs.tibco.com/pub/bstudio-mdm/6.1.0/TIB_bstudio-mdm_6.1.0_readme.txt |
| tibco-mdm-studio@6.0.0 |  | 25 live page(s) with no 301.yml row, e.g. https://docs.tibco.com/pub/bstudio-mdm/6.0.0/TIB_bstudio-mdm_6.0.0_readme.txt |
| tibco-mdm-studio@5.3.0 |  | 24 live page(s) with no 301.yml row, e.g. https://docs.tibco.com/pub/bstudio-mdm/5.3.0/TIB_bstudio-mdm_5.3.0_readme.txt |
| tibco-mdm-studio@5.2.0 |  | 29 live page(s) with no 301.yml row, e.g. https://docs.tibco.com/pub/bstudio-mdm/5.2.0/TIB_bstudio-mdm_5.2.0_readme.txt |

## reframe

### REFRAME_LINK_UNRESOLVED (warning)

Relative references pointing outside the converted tree, left exactly as written; present before the merge -- *REFRAME-REQUIREMENTS.md R4, §8*

| Product | Path | Message |
| :--- | :--- | :--- |
| ibi-mdm-add-on-for-global-data-synchronization@4.0.0 |  | 2 relative reference(s) point outside the converted tree; present before the merge and left exactly as written |
| tibco-mdm@11.1.0 |  | 1 relative reference(s) point outside the converted tree; present before the merge and left exactly as written |
| tibco-mdm@11.0.0 |  | 1 relative reference(s) point outside the converted tree; present before the merge and left exactly as written |
| tibco-mdm@10.0.0 |  | 1 relative reference(s) point outside the converted tree; present before the merge and left exactly as written |
| tibco-mdm@9.3.2 |  | 1 relative reference(s) point outside the converted tree; present before the merge and left exactly as written |

### REFRAME_TOPIC_UNTOCKED (warning)

Topics absent from toc.yml, carried through unmerged and unreachable from navigation -- *REFRAME-REQUIREMENTS.md R3*

| Product | Path | Message |
| :--- | :--- | :--- |
| tibco-mdm@11.1.0 |  | 4 topic(s) absent from toc.yml, carried through as single-topic pages: html/_templates/Legal-and-Third-Party-Notices.md, html/_templates/documentation-and-support-services.md, relnotes/_templates/Legal-and-Third-Party-Notices.md, relnotes/_templates/documentation-and-support-services.md |
| tibco-mdm@11.0.0 |  | 4 topic(s) absent from toc.yml, carried through as single-topic pages: html/_templates/Legal-and-Third-Party-Notices.md, html/_templates/documentation-and-support-services.md, relnotes/_templates/Legal-and-Third-Party-Notices.md, relnotes/_templates/documentation-and-support-services.md |
| tibco-mdm@10.0.0 |  | 4 topic(s) absent from toc.yml, carried through as single-topic pages: html/_templates/Legal-and-Third-Party-Notices.md, html/_templates/TIBCO Documentation and Support Services.md, relnotes/_templates/Legal-and-Third-Party-Notices.md, relnotes/_templates/TIBCO_Documentation_and_Support_Services.md |
| tibco-mdm@9.3.2 |  | 1 topic(s) absent from toc.yml, carried through as single-topic pages: relnotes/_templates/Legal-and-Third-Party-Notices.md |
| tibco-mdm-studio@6.1.1 |  | 2 topic(s) absent from toc.yml, carried through as single-topic pages: relnotes/_templates/Legal-and-Third-Party-Notices.md, relnotes/_templates/documentation-and-support-services.md |
| tibco-mdm-studio@6.0.0 |  | 2 topic(s) absent from toc.yml, carried through as single-topic pages: relnotes/_templates/Important_Information.md, relnotes/_templates/TIBCO_Documentation_and_Support_Services.md |
| tibco-mdm-studio@5.3.0 |  | 1 topic(s) absent from toc.yml, carried through as single-topic pages: relnotes/_templates/Important_Information.md |
| tibco-mdm-studio@5.2.0 |  | 2 topic(s) absent from toc.yml, carried through as single-topic pages: relnotes/important-information.md, relnotes/tibco-documentation-and-support-services.md |

### REFRAME_LAYOUT_UNPINNED (note)

More than one eligible version of this doc set and no pin in reframe.yaml; laid out on the newest eligible version, chosen automatically -- *REFRAME-REQUIREMENTS.md R1.4*

| Product | Path | Count | Message |
| :--- | :--- | ---: | :--- |
| tibco-mdm |  | 1 | no `pin_layout_to` in config/reframe.yaml; laid out on 11.1.0, the newest eligible version |
| tibco-mdm |  | 1 | no `pin_layout_to` in config/reframe.yaml; laid out on 11.1.0, the newest eligible version |
| tibco-mdm |  | 1 | no `pin_layout_to` in config/reframe.yaml; laid out on 11.1.0, the newest eligible version |
| tibco-mdm |  | 1 | no `pin_layout_to` in config/reframe.yaml; laid out on 11.1.0, the newest eligible version |
| tibco-mdm-studio |  | 1 | no `pin_layout_to` in config/reframe.yaml; laid out on 6.1.1, the newest eligible version |
| tibco-mdm-studio |  | 1 | no `pin_layout_to` in config/reframe.yaml; laid out on 6.1.1, the newest eligible version |
| tibco-mdm-studio |  | 1 | no `pin_layout_to` in config/reframe.yaml; laid out on 6.1.1, the newest eligible version |
| tibco-mdm-studio |  | 1 | no `pin_layout_to` in config/reframe.yaml; laid out on 6.1.1, the newest eligible version |
| tibco-mdm-studio |  | 1 | no `pin_layout_to` in config/reframe.yaml; laid out on 6.1.1, the newest eligible version |

### REFRAME_REVIEW_QUEUED (note)

Merged pages needing an editorial decision, listed in review-queue.csv -- *REFRAME-REQUIREMENTS.md R6*

| Product | Path | Count | Message |
| :--- | :--- | ---: | :--- |
| ibi-mdm-add-on-for-global-data-synchronization@4.0.0 | `review-queue.csv` | 1 | 12 of 29 page(s) need an editorial decision (flags across all pages: reference-list 1, oversized 1, title-inherited 15, heterogeneous 7, single-topic 14, shortened 4) |
| tibco-mdm@11.1.0 | `review-queue.csv` | 1 | 74 of 394 page(s) need an editorial decision (flags across all pages: reference-list 17, oversized 5, title-inherited 246, heterogeneous 1, single-topic 148, shortened 52) |
| tibco-mdm@11.0.0 | `review-queue.csv` | 1 | 231 of 503 page(s) need an editorial decision (flags across all pages: reference-list 16, oversized 6, title-inherited 218, heterogeneous 1, single-topic 285, shortened 209) |
| tibco-mdm@10.0.0 | `review-queue.csv` | 1 | 5365 of 5676 page(s) need an editorial decision (flags across all pages: reference-list 16, oversized 13, title-inherited 253, heterogeneous 1, single-topic 5423, shortened 5341) |
| tibco-mdm@9.3.2 | `review-queue.csv` | 1 | 431 of 756 page(s) need an editorial decision (flags across all pages: reference-list 16, oversized 12, title-inherited 253, heterogeneous 1, single-topic 503, shortened 406) |
| tibco-mdm-studio@6.1.1 | `review-queue.csv` | 1 | 917 of 1006 page(s) need an editorial decision (flags across all pages: reference-list 15, oversized 2, title-inherited 51, heterogeneous 1, single-topic 955, shortened 900) |
| tibco-mdm-studio@6.1.0 | `review-queue.csv` | 1 | 53 of 101 page(s) need an editorial decision (flags across all pages: reference-list 15, oversized 2, title-inherited 50, heterogeneous 14, single-topic 51, shortened 31) |
| tibco-mdm-studio@6.0.0 | `review-queue.csv` | 1 | 905 of 988 page(s) need an editorial decision (flags across all pages: reference-list 15, oversized 1, title-inherited 51, heterogeneous 1, single-topic 937, shortened 890) |
| tibco-mdm-studio@5.3.0 | `review-queue.csv` | 1 | 903 of 988 page(s) need an editorial decision (flags across all pages: reference-list 15, oversized 1, title-inherited 51, heterogeneous 1, single-topic 937, shortened 888) |
| tibco-mdm-studio@5.2.0 | `review-queue.csv` | 1 | 24 of 43 page(s) need an editorial decision (flags across all pages: reference-list 20, oversized 1, title-inherited 38, heterogeneous 7, single-topic 5, shortened 1) |
