# DocuShift findings -- convert run 875

- **Command:** `docushift convert`
- **Started:** 2026-10-15T05:06:45+00:00
- **Finished:** 2026-10-15T05:31:13+00:00
- **Exit code:** 0
- **Findings:** 8 errors, 25 warnings, 58 notes

## convert

### REFERENCE_UNRESOLVED (error)

A reference producing neither link nor copy -- *design.md invariant 13*

| Product | Path | Message |
| :--- | :--- | :--- |
| tibco-mdm-studio@6.1.1 | `Process-Designer` | 2 reference(s) resolved to nothing |
| tibco-mdm-studio@6.1.1 | `Rulebase-Designer-Users-guide` | 1 reference(s) resolved to nothing |
| tibco-mdm-studio@6.1.1 | `relnotes/Rulebase-Designer-Users-guide` | 1 reference(s) resolved to nothing |
| tibco-mdm-studio@6.1.0 | `Rulebase-Designer-Users-guide` | 1 reference(s) resolved to nothing |
| tibco-mdm-studio@6.0.0 | `Rulebase-Designer-Users-guide` | 1 reference(s) resolved to nothing |
| tibco-mdm-studio@6.0.0 | `relnotes/Rulebase-Designer-Users-guide` | 1 reference(s) resolved to nothing |
| tibco-mdm-studio@5.3.0 | `Rulebase-Designer-Users-guide` | 1 reference(s) resolved to nothing |
| tibco-mdm-studio@5.3.0 | `relnotes/Rulebase-Designer-Users-guide` | 1 reference(s) resolved to nothing |

### ENGINE_UNKNOWN (warning)

auto, or a named engine with no handler -- skipped, not guessed -- *design.md invariant 7*

| Product | Path | Message |
| :--- | :--- | :--- |
| tibco-enterprise-mdm@1.0.0 |  | engine undetected (`auto`) |

### METADATA_MISMATCH (warning)

SuiteHelp release-version / release-date disagreeing with the catalog -- *planning.md Phase 6 contract*

| Product | Path | Message |
| :--- | :--- | :--- |
| tibco-mdm-studio@5.2.0 |  | homepage release-version 'Software Release 5.2' != catalog '5.2.0' |
| tibco-mdm-studio@5.2.0 | `relnotes` | homepage release-version 'Software Release 5.2.0' != catalog '5.2.0' |

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

### OUTPUT_COUNT_MISMATCH (warning)

Fewer Markdown files on disk than documents converted; two writes resolved to one path -- *planning.md Phase 13*

| Product | Path | Message |
| :--- | :--- | :--- |
| ibi-mdm-add-on-for-global-data-synchronization@4.0.0 |  | 141 document(s) converted but 140 Markdown file(s) on disk; 1 write(s) landed on another |
| tibco-mdm@11.1.0 |  | 2703 document(s) converted but 2700 Markdown file(s) on disk; 3 write(s) landed on another |
| tibco-mdm@11.0.0 |  | 2709 document(s) converted but 2706 Markdown file(s) on disk; 3 write(s) landed on another |
| tibco-mdm@10.0.0 |  | 7983 document(s) converted but 7980 Markdown file(s) on disk; 3 write(s) landed on another |
| tibco-mdm@9.3.2 |  | 3071 document(s) converted but 3068 Markdown file(s) on disk; 3 write(s) landed on another |
| tibco-mdm-studio@6.1.1 |  | 1859 document(s) converted but 1857 Markdown file(s) on disk; 2 write(s) landed on another |
| tibco-mdm-studio@6.1.0 |  | 941 document(s) converted but 940 Markdown file(s) on disk; 1 write(s) landed on another |
| tibco-mdm-studio@6.0.0 |  | 1823 document(s) converted but 1821 Markdown file(s) on disk; 2 write(s) landed on another |
| tibco-mdm-studio@5.3.0 |  | 1823 document(s) converted but 1821 Markdown file(s) on disk; 2 write(s) landed on another |

### TAIL_PAGE_MISSING (warning)

No support or no legal page in the TOC -- nothing is synthesized -- *architecture.md §5.1.5*

| Product | Path | Message |
| :--- | :--- | :--- |
| tibco-mdm@9.3.2 |  | no support page in the TOC |
| tibco-mdm@9.3.2 |  | no legal page in the TOC |
| tibco-mdm@9.3.2 | `relnotes` | no support page in the TOC |

### API_LINK_REWRITTEN (note)

Link into an api-reference tree pointed at its published -resources URL -- *design.md §10.7*

| Product | Path | Count | Message |
| :--- | :--- | ---: | :--- |
| tibco-mdm@11.1.0 |  | 1 | 0 link(s) rewritten to the -resources tree across 1 API tree(s) |
| tibco-mdm@11.0.0 |  | 1 | 0 link(s) rewritten to the -resources tree across 1 API tree(s) |
| tibco-mdm@10.0.0 |  | 1 | 0 link(s) rewritten to the -resources tree across 1 API tree(s) |
| tibco-mdm@9.3.2 |  | 1 | 0 link(s) rewritten to the -resources tree across 1 API tree(s) |

### ASSET_ORPHANED (note)

Unreferenced asset -- 54.6% is normal for Flare -- *architecture.md §5.5.7*

| Product | Path | Count | Message |
| :--- | :--- | ---: | :--- |
| ibi-mdm-add-on-for-global-data-synchronization@4.0.0 |  | 155 | 155 unreferenced file(s), 4618821 bytes |
| tibco-mdm@11.1.0 |  | 1218 | 320 unreferenced file(s), 17559949 bytes |
| tibco-mdm@11.0.0 |  | 1026 | 151 unreferenced file(s), 12498801 bytes |
| tibco-mdm@10.0.0 |  | 2107 | 696 unreferenced file(s), 27936245 bytes |
| tibco-mdm@9.3.2 |  | 1022 | 154 unreferenced file(s), 11774515 bytes |
| tibco-mdm-studio@6.1.1 |  | 3395 | 1703 unreferenced file(s), 44461990 bytes |
| tibco-mdm-studio@6.1.0 |  | 1696 | 1696 unreferenced file(s), 45294170 bytes |
| tibco-mdm-studio@6.0.0 |  | 3300 | 1681 unreferenced file(s), 41951606 bytes |
| tibco-mdm-studio@5.3.0 |  | 3172 | 1586 unreferenced file(s), 35730781 bytes |
| tibco-mdm-studio@5.2.0 |  | 2 | 1 unreferenced file(s), 1809408 bytes |

### CSH_AMBIGUOUS (note)

Identifier claimed by 2+ doc-sets; first ordered doc-set wins -- *planning.md Phase 6 contract*

| Product | Path | Count | Message |
| :--- | :--- | ---: | :--- |
| tibco-mdm@10.0.0 | `Users-guide/Subset-Rules.md` | 138 | 100 also resolved to html/Users-guide/Subset-Rules.md, relnotes/Users-guide/Subset-Rules.md |

### DEFINITION_TERM_RECOVERED (note)

Definition terms marked up as class="dt" rather than <dt>, retagged so they publish as terms instead of as prose -- *planning.md Phase 27*

| Product | Path | Count | Message |
| :--- | :--- | ---: | :--- |
| tibco-mdm-studio@6.1.1 |  | 7 | 7 definition term(s) recovered from class-named markup and published as terms |
| tibco-mdm-studio@6.1.0 |  | 5 | 5 definition term(s) recovered from class-named markup and published as terms |
| tibco-mdm-studio@6.0.0 |  | 7 | 7 definition term(s) recovered from class-named markup and published as terms |
| tibco-mdm-studio@5.3.0 |  | 7 | 7 definition term(s) recovered from class-named markup and published as terms |

### ELEMENT_UNRENDERED (note)

Embedded media with no Markdown form (iframe, video, svg ...); an absolute URL became a link, anything else kept only its fallback text -- *Phase 34 (R8-13)*

| Product | Path | Count | Message |
| :--- | :--- | ---: | :--- |
| tibco-mdm@11.1.0 |  | 6 | 6 embedded element(s) with no Markdown form (iframe 6); an absolute URL became a link, anything else kept only its fallback text |
| tibco-mdm@11.0.0 |  | 6 | 6 embedded element(s) with no Markdown form (iframe 6); an absolute URL became a link, anything else kept only its fallback text |
| tibco-mdm@10.0.0 |  | 21 | 21 embedded element(s) with no Markdown form (iframe 21); an absolute URL became a link, anything else kept only its fallback text |
| tibco-mdm@9.3.2 |  | 9 | 9 embedded element(s) with no Markdown form (iframe 9); an absolute URL became a link, anything else kept only its fallback text |

### FRAGMENT_RETARGETED (note)

Cross-references pointed at a heading instead of an inert anchor marker the platform does not honour -- *planning.md Phase 30*

| Product | Path | Count | Message |
| :--- | :--- | ---: | :--- |
| ibi-mdm-add-on-for-global-data-synchronization@4.0.0 |  | 2 | 2 cross-reference(s) pointed at a heading instead of an inert anchor marker the platform does not honour |
| tibco-mdm@11.1.0 |  | 44 | 44 cross-reference(s) pointed at a heading instead of an inert anchor marker the platform does not honour |
| tibco-mdm@11.0.0 |  | 44 | 44 cross-reference(s) pointed at a heading instead of an inert anchor marker the platform does not honour |
| tibco-mdm@10.0.0 |  | 126 | 126 cross-reference(s) pointed at a heading instead of an inert anchor marker the platform does not honour |
| tibco-mdm@9.3.2 |  | 46 | 46 cross-reference(s) pointed at a heading instead of an inert anchor marker the platform does not honour |
| tibco-mdm-studio@6.1.1 |  | 28 | 28 cross-reference(s) pointed at a heading instead of an inert anchor marker the platform does not honour |
| tibco-mdm-studio@6.1.0 |  | 14 | 14 cross-reference(s) pointed at a heading instead of an inert anchor marker the platform does not honour |
| tibco-mdm-studio@6.0.0 |  | 28 | 28 cross-reference(s) pointed at a heading instead of an inert anchor marker the platform does not honour |
| tibco-mdm-studio@5.3.0 |  | 28 | 28 cross-reference(s) pointed at a heading instead of an inert anchor marker the platform does not honour |
| tibco-mdm-studio@5.2.0 |  | 15 | 15 cross-reference(s) pointed at a heading instead of an inert anchor marker the platform does not honour |

### HEADING_LEVEL_NORMALIZED (note)

Headings renumbered to close a level the source skipped; depth and order are unchanged -- *planning.md Phase 27*

| Product | Path | Count | Message |
| :--- | :--- | ---: | :--- |
| tibco-mdm-studio@6.1.1 |  | 12 | 12 heading(s) renumbered to close a level the source skipped |
| tibco-mdm-studio@6.1.0 |  | 8 | 8 heading(s) renumbered to close a level the source skipped |
| tibco-mdm-studio@6.0.0 |  | 13 | 13 heading(s) renumbered to close a level the source skipped |
| tibco-mdm-studio@5.3.0 |  | 13 | 13 heading(s) renumbered to close a level the source skipped |

### LANDING_PAGE_EMPTY (note)

A landing page with nothing past its hero -- a stub was generated -- *architecture.md §5.1.5*

| Product | Path | Count | Message |
| :--- | :--- | ---: | :--- |
| tibco-mdm@9.3.2 | `relnotes` | 1 | New-Features.htm has nothing past the hero; a stub was generated |

### NAV_NODE_DROPPED (note)

A navigation node with no page and no children -- DITA's lof/lot/ix, Flare's childless headless node -- or a Flare/WebWorks child repeating its parent's page with no bookmark of its own -- *planning.md Phase 5*

| Product | Path | Count | Message |
| :--- | :--- | ---: | :--- |
| tibco-mdm@11.1.0 | `html` | 5 | 1 node(s) with no page and no children |
| tibco-mdm@11.0.0 |  | 4 | 4 node(s) dropped assembling the version |
| tibco-mdm@10.0.0 |  | 4 | 4 node(s) dropped assembling the version |
| tibco-mdm@9.3.2 | `html` | 3 | 1 node(s) with no page and no children |
| tibco-mdm-studio@6.1.1 |  | 2 | 2 node(s) dropped assembling the version |
| tibco-mdm-studio@6.0.0 |  | 2 | 2 node(s) dropped assembling the version |
| tibco-mdm-studio@5.3.0 |  | 1 | 1 node(s) dropped assembling the version |
| tibco-mdm-studio@5.2.0 |  | 2 | 2 node(s) dropped assembling the version |

### TOC_ORPHAN (note)

Converted topics in no TOC entry, kept out of toc.yml and unmerged under unfiled/ -- 5.9% for Flare; left in an Unfiled node only when the version has no other TOC entry -- *architecture.md §5.1.4, Phase 43*

| Product | Path | Count | Message |
| :--- | :--- | ---: | :--- |
| ibi-mdm-add-on-for-global-data-synchronization@4.0.0 |  | 5 | 5 converted topic(s) in no TOC entry |
| tibco-mdm@11.1.0 |  | 23 | 2 converted topic(s) in no TOC entry |
| tibco-mdm@11.0.0 |  | 173 | 1 converted topic(s) in no TOC entry |
| tibco-mdm@10.0.0 |  | 5295 | 2497 converted topic(s) in no TOC entry |
| tibco-mdm@9.3.2 |  | 377 | 220 converted topic(s) in no TOC entry |
| tibco-mdm-studio@6.1.1 |  | 929 | 7 converted topic(s) in no TOC entry |
| tibco-mdm-studio@6.1.0 |  | 26 | 26 converted topic(s) in no TOC entry |
| tibco-mdm-studio@6.0.0 |  | 913 | 12 converted topic(s) in no TOC entry |
| tibco-mdm-studio@5.3.0 |  | 913 | 12 converted topic(s) in no TOC entry |

### TOPIC_LINK_DANGLING (note)

A cross-reference to a topic this run did not produce; text kept, link dropped -- *architecture.md §5.1.3*

| Product | Path | Count | Message |
| :--- | :--- | ---: | :--- |
| tibco-mdm@11.1.0 | `html` | 2 | Default-LDAP-Propert.htm -> Single-Sign-On-Prope-Map.htm |
| tibco-mdm@11.0.0 | `html` | 3 | Default-LDAP-Propert.htm -> Single-Sign-On-Prope-Map.htm |
| tibco-mdm-studio@5.2.0 |  | 1 | GUID-6CD0129C-7AF2-4ACB-BAE2-5A63B18368AB.html -> #GUID-581C904D-5A1B-403E-AEBF-1A8A87107246__missing-elem-id--GUID-0FB34FAA-A640-4784-A1E5-6F70EC5C0C67 (anchor absent; link kept, bookmark dropped) |
