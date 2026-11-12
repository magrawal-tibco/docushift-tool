# EMS: merging by menu depth, a draft for review (12 Nov 2026)

DOCOPS-367. A draft only; nothing is built or applied. If adopted, it is applied **after 30 Nov**, as EMS's per-product policy, one version per commit. All 7 EMS versions follow 10.5.1's layout through the existing pin.

## The rule

There is no word cap. Each chapter gets a **depth**:

- **Whole chapter:** one page for the chapter and everything under it.
- **One page per section:** the chapter's own text on one page, then one page for each section with everything under it.
- **One page per subsection:** the same, one level further down.

A page never holds only some of a parent's children.

How the depth is chosen:

1. **Narrative chapters, automatically:** the shallowest depth at which no page passes **5,000 words**.
2. **Reference chapters, set by hand, as an explicit policy line:**
   - C reference chapters over 5,000 words get one page per C type, never one per function; smaller ones stay whole.
   - The Administration Tool's command listing stays one page (Decision A).
3. **Whole guide** where it is short: Installation stays one page, as today.

## What it gives for EMS 10.5.1

| | Today (cap 3,000) | All-or-nothing at 3,000 | **This draft** |
|---|---|---|---|
| Pages | 159 | ~607 | **224** |
| Installation / User Guide / C reference | 1 / 95 / 58 | | **1 / 159 / 60** |
| Median page | ~1,336 words | 162 | **472** |
| Pages under 300 words | | ~half | **37%** |
| Pages over 5,000 words | | | **3** (Decisions A and B) |
| Pages holding only some of a parent's children | many (EMS Destinations: properties split 10 + 7) | 0 | **0** |

## Per chapter

| Guide | Chapter | Words | Depth | Pages | Largest page | How chosen |
|---|---|---|---|---|---|---|
| Installation | (whole guide) | 1,940 | Whole guide | 1 | 1,940 | set by hand |
| User Guide | Overview | 3,205 | Whole chapter | 1 | 3,205 | automatic: whole if it fits in 5,000 words |
| User Guide | Messages | 7,588 | One page per section | 14 | 1,878 | automatic: the shallowest depth under 5,000 words |
| User Guide | Destinations | 10,076 | One page per section | 11 | 4,472 | The 17 destination properties stay together on one page (4,472); today they are split 10 + 7 |
| User Guide | Getting Started | 2,370 | Whole chapter | 1 | 2,370 | automatic: whole if it fits in 5,000 words |
| User Guide | Running the EMS Server | 4,828 | Whole chapter | 1 | 4,828 | automatic: whole if it fits in 5,000 words |
| User Guide | Using the EMS Administration Tool | 13,116 | One page per section | 4 | 11,698 | **Decision A.** The 120-command listing stays one reference page (11,698 words); the alternative is one page per command (120 pages) |
| User Guide | REST Proxy | 7,743 | One page per subsection | 13 | 4,896 | automatic: the shallowest depth under 5,000 words |
| User Guide | Configuration Files | 20,560 | One page per subsection | 35 | 3,395 | One page per `tibemsd.conf` parameter group (17) and per other configuration file (13) |
| User Guide | Authentication and Permissions | 7,673 | One page per section | 10 | 2,302 | automatic: the shallowest depth under 5,000 words |
| User Guide | Extensible Security | 3,421 | Whole chapter | 1 | 3,421 | automatic: whole if it fits in 5,000 words |
| User Guide | JAAS Authentication Modules | 5,516 | One page per section | 7 | 3,346 | automatic: the shallowest depth under 5,000 words |
| User Guide | FTL Stores | 8,511 | One page per subsection | 15 | 2,135 | "Configuring and Deploying" splits into its 9 parts; the rest stay whole |
| User Guide | Developing an EMS Client Application | 7,363 | One page per section | 12 | 1,627 | automatic: the shallowest depth under 5,000 words |
| User Guide | The EMS Implementation of JNDI | 2,183 | Whole chapter | 1 | 2,183 | automatic: whole if it fits in 5,000 words |
| User Guide | Interoperation with Apache Pulsar | 1,713 | Whole chapter | 1 | 1,713 | automatic: whole if it fits in 5,000 words |
| User Guide | Interoperation with Apache Kafka | 2,315 | Whole chapter | 1 | 2,315 | automatic: whole if it fits in 5,000 words |
| User Guide | Interoperation with TIBCO FTL | 3,186 | Whole chapter | 1 | 3,186 | automatic: whole if it fits in 5,000 words |
| User Guide | Interoperation with TIBCO Rendezvous | 4,678 | Whole chapter | 1 | 4,678 | automatic: whole if it fits in 5,000 words |
| User Guide | Monitor Server Activity | 5,659 | One page per section | 6 | 1,607 | automatic: the shallowest depth under 5,000 words |
| User Guide | TLS Protocol | 4,186 | Whole chapter | 1 | 4,186 | automatic: whole if it fits in 5,000 words |
| User Guide | Fault Tolerance | 5,666 | One page per section | 9 | 1,069 | automatic: the shallowest depth under 5,000 words |
| User Guide | Routes | 5,600 | One page per section | 9 | 1,284 | automatic: the shallowest depth under 5,000 words |
| User Guide | Conversion of Server Configuration Files to JSON | 495 | Whole chapter | 1 | 495 | automatic: whole if it fits in 5,000 words |
| User Guide | Appendix A: License Caching and Expiration | 335 | Whole chapter | 1 | 335 | automatic: whole if it fits in 5,000 words |
| User Guide | Appendix B: Monitor Messages | 2,332 | Whole chapter | 1 | 2,332 | automatic: whole if it fits in 5,000 words |
| User Guide | Appendix C: Error and Status Messages | 109 | Whole chapter | 1 | 109 | automatic: whole if it fits in 5,000 words |
| C and COBOL Reference | Introduction | 454 | Whole chapter | 1 | 454 | automatic: whole if it fits in 5,000 words |
| C and COBOL Reference | Messages | 19,180 | One page per section | 20 | 7,851 | One page per C type; `tibemsMsg` is 7,851 words (42 functions). **Decision B** |
| C and COBOL Reference | Destination | 2,243 | Whole chapter | 1 | 2,243 | automatic: whole if it fits in 5,000 words |
| C and COBOL Reference | Consumer | 1,596 | Whole chapter | 1 | 1,596 | automatic: whole if it fits in 5,000 words |
| C and COBOL Reference | Producer | 3,544 | Whole chapter | 1 | 3,544 | automatic: whole if it fits in 5,000 words |
| C and COBOL Reference | Requestor | 615 | Whole chapter | 1 | 615 | automatic: whole if it fits in 5,000 words |
| C and COBOL Reference | Connection | 6,231 | One page per section | 8 | 2,479 | One page per C type |
| C and COBOL Reference | Connection Factory | 8,968 | One page per section | 5 | 5,590 | One page per C type; `tibemsConnectionFactory` is 5,590 words (34 functions). **Decision B** |
| C and COBOL Reference | Session | 5,204 | One page per section | 3 | 4,856 | One page per C type (`tibemsSession` 4,856) |
| C and COBOL Reference | Queue Browser | 572 | Whole chapter | 1 | 572 | automatic: whole if it fits in 5,000 words |
| C and COBOL Reference | Name Server Lookup | 823 | Whole chapter | 1 | 823 | automatic: whole if it fits in 5,000 words |
| C and COBOL Reference | XA—External Transaction Manager | 2,778 | Whole chapter | 1 | 2,778 | automatic: whole if it fits in 5,000 words |
| C and COBOL Reference | Types | 120 | Whole chapter | 1 | 120 | automatic: whole if it fits in 5,000 words |
| C and COBOL Reference | Utilities | 4,175 | Whole chapter | 1 | 4,175 | automatic: whole if it fits in 5,000 words |
| C and COBOL Reference | Administration | 14,447 | One page per section | 12 | 4,078 | One page per C type (11 info types) |
| C and COBOL Reference | Exception | 1,980 | Whole chapter | 1 | 1,980 | automatic: whole if it fits in 5,000 words |
| C and COBOL Reference | IBM z/OS and IBM i | 4,693 | Whole chapter | 1 | 4,693 | automatic: whole if it fits in 5,000 words |
| API Reference | API Documentation | 44 | Whole chapter | 1 | 44 | automatic: whole if it fits in 5,000 words |

## Decisions for you

- **A. Administration Tool command listing (120 commands, 11,698 words):**
  - **(1) One reference page**, each command a heading you can link to. This is the draft. Readers look commands up by name, and the old site's menu listed them all.
  - **(2) One page per command:** 120 pages, most of them 50–150 words.
  - **(3) Groups by area** (create/delete, show, set, add/remove, …): about 10 pages. These groups are not in the source menu, so they would have to be defined by hand.
- **B. The two big C types:** `tibemsMsg` (7,851 words, 42 functions) and `tibemsConnectionFactory` (5,590 words, 34 functions).
  - **Draft:** one page per type, like a class page in an API reference.
  - **Alternative:** one page per function for these two only, adding about 74 small pages.
- **C. The limit for narrative chapters:**
  - **5,000 (draft):** chapters such as Running the EMS Server (4,828), Rendezvous (4,678) and TLS (4,186) stay whole.
  - **4,000:** those three split by section, for about 30 more pages.
- **D. Installation:** keep it as one page (1,940 words, as today), or split it into 4 sections.

## How AI fits

For another product, the same table can be drafted automatically. The tool lists every chapter's sections, sizes and titles. A model labels each chapter **narrative** or **reference** (a list of commands, parameters, functions or properties) and proposes a depth with a one-line reason. You or the writers approve it, and the result becomes the product's policy lines. EMS's draft here was made that way, by hand-checked judgement on the numbers above.

## Cost of applying it to EMS (after 30 Nov)

- **What changes:** EMS has 7 published versions of about 160 pages each. Most pages change or are new: about 1,100 published pages regrouped into about 1,550.
- **What gets rebuilt with them, in the same run:** redirect files, help links, and in-page links.
- **Commits:** one version at a time, to stay gentle on the AEM pipeline; about 400 files each.
- **Checks:** the link and structure check, then a staging check per version.
- **Tool work:** a "depth" option in the merging step, per guide and per chapter, about a day with tests, under DOCOPS-367.

Data: `ems-levels.md`, `ems-structure.txt` and `levels.py` in this folder.
