# Release R2: what is in it and how it goes out (plan, written Sat 14 Nov night)

> Read-only plan. Nothing here has been pushed, committed or changed. Numbers are from a fresh `git fetch` of every
> repo on Sat 14 Nov about 22:00. **R2 is approved on Thu 19 Nov; go-live Mon 23 Nov.**
> Pipeline rule (user): about 2,500 changed files per push at most; the next chunk of the same repo only after the
> previous one shows on staging; about 3 repos in flight at once; a push of up to about 2,000 files rebuilt in 2–3 h.

## 0. Summary

- **Size of R2.** About **40,700 files are known today**:
  - 29,200 committed on TIBCO `content-fix`;
  - 5,770 committed on ibi `content-fix`;
  - 4,735 from repair R002, applied in 23 TIBCO working trees but not committed yet;
  - about 960 from the Phase 80 moves still to come for BusinessWorks and Platform.

  The re-conversion for DOCOPS-370 and the Δ1 delta add an estimated **6,000–11,000**, so R2 comes to about **47,000–52,000 files**. Two items are not in that total:
  - Streaming, 4,800 files, already on `content-fix` but held;
  - the BW plug-in renames, 18,477 files, waiting for the AEM team.
- **Number of chunks.** There are **45 pushes from Mon to Wed**, in 39 slots: some slots carry two tiny repos together. **About 5 Δ1 pushes** follow on Thu. Sunday's Phase 80 families add 7 pushes, which are already planned. Streaming would add 2, and the BW plug-in renames 9.
- **Does it fit by Thu evening?** **Yes for everything except the BW plug-in renames**, with about 7–10 slots spare on Wed evening and Thu. Four conditions must hold:
  - `&#92;` is confirmed on Mon by 08:30;
  - the 370 syncs are committed by Mon evening;
  - ibi's refresh is on `wip` on Mon morning;
  - Δ1 is converted and synced by Wed evening.

  The BW plug-in renames need 9 pushes one after another in one repo. They fit only if the AEM answer comes by Tue morning and Streaming moves to R3, which leaves no buffer. **Recommendation: BW plug-in renames to R3 (Thu 26)** unless the answer is in by Mon evening.
- **Decision for Monday:** this plan **opens the R2 window from Mon 16**, not on Thu alone. At 3 repos in flight and 2–3 h per rebuild, Thu by itself has room for about 12 pushes, and R2 needs about 50. Rule 4 of §2 in the close-out plan ("merges to `wip` only in release windows") would need that exception.

## 1. What each repo holds

"cf→wip" means commits on `content-fix` that are not on `origin/wip`. "wip only" means commits by others on `origin/wip` that `content-fix` does not have; these must be merged first. Files are git's changed paths, with a rename counted once. For the AEM pipeline a rename is a delete plus an add, so the work is about twice the count.

### 1.1 TIBCO (`C:/github/tibco-docs-aem/`)

| Repo | cf→wip: sha, subject, files | wip only (others) | Files committed | Coming (not committed) | R2 items |
|---|---|---|---|---|---|
| tib-messaging-userdocs | `bdca327` Phase 80 (96) | – | 96 | R002 11; 370 2 versions (≤7) | P80, R002, 370 |
| tib-messaging-userdocs-resources | `c4ffac8` Phase 80 (145) | – | 145 | – | P80 |
| tib-adapters-userdocs | `bf9bd99` Phase 80 (632) | – | 632 | R002 39 | P80, R002 |
| tib-fulfillment-userdocs | `8415181` Phase 80 (845) | – | 845 | R002 201; 370 2 versions (≤440) | P80, R002, 370 |
| tib-fulfillment-userdocs-resources | `9dfe5ee` Phase 80 (3) | – | 3 | – | P80 |
| tib-mft-userdocs | `fbfb772` Phase 80 (970) | – | 970 | R002 76; 370 6 versions (≤1,762) | P80, R002, 370 |
| tib-mft-userdocs-resources | `796fe65` Phase 80 (12) | – | 12 | – | P80 |
| tib-businessconnect-userdocs | `4bad5b4` Phase 80 (**2,757**, too big: split, §2) | – | 2,757 | R002 229; 370 5 versions (≤211) | P80, R002, 370 |
| tib-businessconnect-userdocs-resources | `a88dca5` Phase 80 (248) | – | 248 | – | P80 |
| tib-general-userdocs-resources | `ec07c55` Phase 80 archives, tibbr (3) | – | 3 | – | P80 |
| tib-businessevents-userdocs-resources | `103d6eb` Phase 80 archives (6) | – | 6 | – | P80 |
| tib-businessevents-userdocs | `349053c` BE 6.3.2 default pages, heading links (24); `c068219` BE 6.4.0 same (27) | – | 51 | R002 6; 370 BE 6.3.1, 6.3.2, 6.4.0 (≤1,213) | 349/343/362/363, R002, 370 |
| tib-businessworks-userdocs | `25cb6b2` K2 premium-subscription (10); `7184f3b` K2 BW Enterprise (24); `135c82f` K3 BW 5.15.0, 5.15.1, 6.11.0 (**3,692**, too big); `fc29228` K3 SmartMapper ES 6.0.0, 6.0.1 (943, long folder name); `e6d9a01` K3 BWCE 2.10.0 (1,482) | – | 6,151 | R002 291; 370 BW 5.16.1, 6.11.0, 6.12.0, 6.13.0 (≤2,238); Phase 80 949 (SmartMapper 943, premium 3, resources 3) | K2, K3, R002, 370, P80 |
| tib-businessworks-userdocs-resources | – | – | 0 | Phase 80 3 (SmartMapper) | P80 |
| tib-bw-plugin-userdocs | 23 K2 removals `39bc4080` … `0b8d0c1f` (4,537); `92daa485` K3 CICS 2.4.1, Files 8.2.0, SAP 8.6.0 (209) | `058df397` merge of PR #1 (6 Nov, **no file change**) | 4,746 | R002 515; 370 9 versions (≤215); **Phase 80 17,810 (waits for AEM)** | K2, K3, R002, 370, (P80) |
| tib-bw-plugin-userdocs-resources | `9e6d686` K2 ActiveAspects (509) | – | 509 | **Phase 80 667 (waits for AEM)** | K2, (P80) |
| tib-cloud-userdocs | `4bbfb90` K2 BW PAYG (63); `0519055` K2 Flogo PAYG (242) | – | 305 | R002 1 | K2, R002 |
| tib-ems-userdocs | `995f5cd` 10.4.0, `5a3962f` 10.4.1, `8008a79` 10.4.3, `734903a` 10.4.4, `e558ed2` 10.5.0 (anchors, default pages, heading links; 9–10 each); `28ce5b9` 10.5.1 by menu depth, Phase 78 (244) | **12 commits** by Digital Platform (8–12 Nov: link-rewrite and metadata probes, `16c0de2` "Fix Pulsar transports configuration links", `e358216` metadata.yml comment, `1cf931f` merge). **3 files conflict with `28ce5b9`** (10.5.1 Kafka, Pulsar, Jakarta overview) | 290 | R002 1 | 349/343/362/363, Phase 78, R002 |
| tib-platform-userdocs | `02b5801` Control Plane 1.3.0–1.5.1 (1,659); `72d5361` CP 1.6.0–1.9.0 (1,902); `31c2757` CP 1.10.0–1.13.0 (2,306); `5eaadda` CP 1.14.0–1.17.0 + version lists (2,541); `fad28d8` Platform 1.0.0, 1.1.0 (812). All K3 | – | 9,220 | R002 86; **370: 21 versions, including every K3 Control Plane version** (≤3,534); Phase 80 14 | K3, R002, 370, P80 |
| tib-tra-userdocs | `0e1f2cf` K2 Administrator EE (408); `1fd36ce` K2 Designer Add-in (774); `6a0badc` K2 Runtime Agent (1,037) | – | 2,219 | R002 52 | K2, R002 |
| tib-data-management-userdocs | – | `8451e0f`, `ccabb06` (Thiyagu's incremental-build probes, one HTML comment each; no overlap) | 0 | R002 539; 370 MDM 9.3.2, 11.0.0, 11.1.0 (≤2,007) | R002, 370 |
| tib-bpm-userdocs | – | – | 0 | R002 652; 370 Service Grid 3.4.3, 3.4.4 (≤974) | R002, 370 |
| tib-foresight-userdocs | – | – | 0 | R002 927; 370 4 versions (≤507) | R002, 370 |
| tib-flogo-userdocs | – | – | 0 | R002 118; 370 6 versions (≤970) | R002, 370 |
| tib-iprocess-userdocs | – | – | 0 | R002 421 | R002 |
| tib-ftl-userdocs | – | – | 0 | R002 164 | R002 |
| tib-activespaces-userdocs | – | – | 0 | R002 103 | R002 |
| tib-general-userdocs | – | – | 0 | R002 122; 370 1 version (≤3) | R002, 370 |
| tib-hawk-userdocs | – | – | 0 | R002 89; 370 1 version (≤7) | R002, 370 |
| tib-scribe-userdocs | – | – | 0 | R002 72; 370 1 version (≤38) | R002, 370 |
| tib-mainframe-userdocs | – | – | 0 | R002 20 | R002 |
| tib-streaming-userdocs (**held**) | `1cfa47a` R001 note labels (4,739: Spotfire Data Streams 1,180, Streaming 3,559); `ecff12b` DocBook menus (8); `e5a1c2d` 301.yml (10). Already on `origin/content-fix` | `0de0e42`, `4dd77f8` (link-rewrite probes; **1 file conflicts**: 11-1-0 `apiguide-contents.md`) | 4,757 | Phase 80 44; R002 not run. The 8 dirty files are line endings only | R001 backlog, P80 |
| hawk, activespaces (+res), ftl-res, iprocess-res, bpm-res, tra-res, ems-res, data-management-res, streaming-res, scribe, flogo, foresight, mainframe, general | level with `wip` (only R002 or 370 above) | – | – | – | – |

Notes:
- **R002 counts** are the working-tree changes at about 22:00 (`.md` only; Streaming's 8 are line endings, not R002). The commits ("one per repo") were not made yet when this was read, so they have no sha here. Each one sits **on top of** the commits above, so every later commit (370, Δ1, Phase 80) in that repo comes after it.
- **370 counts are upper bounds**: the source pages of the affected versions (`reports/fix-370-affected-2026-11-14.csv`, queue `cache/overnight/fix370.txt`). The real change is known only after sync. Sync commits **one commit per version**, so a large family can be chunked.
- **Commits not yet on `origin/content-fix`** (local only, safe to re-cut): BusinessWorks 5, bw-plugin 24, Platform 5, EMS 6, TRA 3, Cloud 2, BE 2, and each Phase 80 commit. Streaming's 3 and all ibi commits are already on `origin/content-fix`: do not rewrite them.
- **Spotfire/Statistica** (`main` only, no `wip`) and `tib-scribe-userdocs-resources` (on branch `wip`, no `content-fix`) are not in R2.
- **Held from R2 already:** Hybrid Integration Connectivity Add-on 3.11.0 (K3, no AEM repo); ~~the menu-title rollout (`docs_list_title`)~~ released (Wed 18): the title feeds the breadcrumbs, not the menu heading, so nothing blocks it. It is about one `toc.yml` per version and goes in each repo's R2 chunk.

### 1.2 ibi (`C:/github/ibi-docs-aem/`)

No weekend refresh is visible yet: the newest `origin/wip` commit in every ibi repo is from 10–11 Nov. Fetch again on Mon before anything.

| Repo | cf→wip: sha, subject, files | wip only (others) | Files | Coming | R2 items |
|---|---|---|---|---|---|
| ibi-wf-reporting-server-userdocs | `8452d4e3` Reporting Server doubled headings removed (**4,831**: 9 versions of 516–556; too big) | 5 (Thiyagu's `toc.yml` touches, 10 Nov; 2 merges) | 4,831 | – | R1 backlog |
| ibi-webfocus-userdocs | `efd0cca1` WebFOCUS Client doubled headings removed (519) | 11 (Thiyagu's `toc.yml`/appendix fixes 6–11 Nov) | 519 | 349: WFC 9.3.0–9.3.8, one page each | R1 backlog, 349 |
| loc-ibi-webfocus-userdocs | `4221ba61` one note label (375); `513f8fe3` 301.yml/csh.yml (42) | `22cc189a` (`toc.yml` touch, 22) | 417 | 349: WFC 9.3.5 translations | R1 backlog, 349 |
| ibi-focus-userdocs | – | 11 (`toc.yml` touches, `control.yml`, PR #3 by Pavan) | 0 | 349: FOCUS 9.3.0–9.3.8, one page each | 349 |
| ibi-container-editions-userdocs | – | 6 | 0 | – (180 dirty files, WFCE 9.3.7/9.3.8, **line endings only**: discard) | merge only |
| ibi-di-ism-userdocs | – | 9 | 0 | – | merge only |
| ibi-legacy-userdocs | – | 4 | 0 | – | merge only |
| loc-ibi-wf-reporting-server-userdocs | – | 1 (merge) | 0 | – | merge only |

### 1.3 Totals

| | Files |
|---|---|
| TIBCO committed, not on `wip` (without Streaming) | 29,208 |
| ibi committed, not on `wip` | 5,767 |
| R002, applied, not committed | 4,735 |
| Phase 80 still to apply: BusinessWorks 949, Platform 14 | 963 |
| **Known** | **≈ 40,700** |
| 370 sync (68 versions; ≤ about 16,000 source pages) | est. 3,000–6,000 |
| Δ1 (16 new versions, from Sun/Mon refresh) | est. 3,000–5,000 |
| ibi 349 re-conversions | ≈ 50–150 |
| **R2 total** | **≈ 47,000–52,000** |
| Not counted: Streaming (4,757 + 44) | 4,801 |
| Not counted: BW plug-in renames | 18,477 |

## 2. How a chunk is pushed (recipe)

`git push origin <sha>:wip` works only where `wip` has no commits of its own (a fast-forward). Seven TIBCO and ibi repos have commits of their own, so one method is used everywhere. It is safe and keeps others' commits:

```
cd C:/github/tibco-docs-aem/<repo>
git fetch origin
git log --oneline HEAD..origin/wip          # anything new from Digital Platform? then merge it in
git switch -c r2/push origin/wip            # first chunk only; later chunks: git switch r2/push
git merge --no-edit <chunk-sha>             # fast-forwards where wip has nothing of its own
git diff --stat origin/wip HEAD | tail -1   # about 2,500 files or fewer
git push origin HEAD:wip
```

- **Too big for one chunk, already pushed to `origin/content-fix`** (`8452d4e3`, Streaming `1cfa47a`), or **wanted before its neighbours**:
  - take part of it by path: `git checkout <big-sha> -- en-us/<folder> …`, then `git commit -m "<subject>, part 1 of 2"`, then push;
  - the next chunk is `git merge <big-sha>`, which brings the rest.
  - This rewrites no history.
- **Final-state pieces (Platform, BusinessWorks).** Every K3 Control Plane version, Platform 1.1.0 and BW 6.11.0 are in the 370 re-convert queue, and the K3 SmartMapper folder is renamed by Phase 80. Pushing commit by commit would make AEM build those pages twice, or build SmartMapper at a long name and then move it.
  - So, once K3, R002, 370 and Phase 80 are all committed in the repo, take each chunk from the **final** tree: `git checkout content-fix -- en-us/<product>/<doc-type>/<version> …`.
  - That is one build per page, and 5 chunks instead of 7 for Platform.
- **After a repo's last chunk:**
  - `git switch content-fix && git merge --no-edit r2/push`;
  - `git diff origin/wip content-fix` must be empty;
  - push `content-fix`, then delete `r2/push`.
- Per the memory rules, pushes go to the user as `!` commands (forward slashes), each after a fresh `git fetch`.

**Merges to resolve once:**
- **EMS:** `28ce5b9` against Digital Platform's 3 probe edits in 10.5.1.
  - Take ours, which is the Phase 78 layout.
  - Keep their `metadata.yml` comment.
  - Check that the Pulsar transports link (to `stores-conf` `#transportsconf`) resolves, because their `16c0de2` hand-fixed it with an `<a href>`.
- **Streaming:** 1 file (`11-1-0/apiguide/apiguide-contents.md`); take ours.
- **bw-plugin:** the merge is empty.
- **Data Management:** no overlap, so Thiyagu's probes are kept.

**Splits proposed:**

| Commit | Files | Split into |
|---|---|---|
| BusinessConnect `4bad5b4` | 2,757 renames (5,430 for the pipeline) | (a) the `tibco-businessconnect-ce-*` and `-container-edition-*` folders, 1,654; (b) the rest, 1,103 |
| BusinessWorks `135c82f` K3 | 3,692 | 5.15.0 + 5.15.1 (1,990) with the K2 commits; 6.11.0 (1,678) separately, after 370 |
| Platform `5eaadda` | 2,541 | as is (2 % over), or move 1.17.0 (644) into PLAT-5 |
| Reporting Server `8452d4e3` | 4,831 | 9.3.0–9.3.3 (2,217); 9.3.4–9.3.8 + `redirects.yml` (2,614) |
| Streaming `1cfa47a` | 4,739 | Spotfire Data Streams + Streaming 11.1.x (≈2,500); the remaining Streaming versions + `ecff12b` + `e5a1c2d` + Phase 80 (≈2,300) |
| BW plug-ins Phase 80 (not committed) | 17,810 + 667 | One commit per product group with `move_publish_folders.py --product …`, 8 groups of 1,900–2,350 in catalog order (activeaspects…cassandra; kafka…data-conversion; database…pub-sub; cloud-storage…large-xml; ldap…oracle-ebs; oracle-fusion…sap-hana plus the last 6; sap-solutions…smpp; snowflake…patterns), plus resources 667 |

## 3. Push schedule, Mon 16 – Thu 19

Waves leave every 3 h (08:30, 11:30, 14:30, 17:30, 20:30). A wave leaves only when the previous chunks of the same repos show on staging. The 20:30 wave is checked at 08:00 the next morning. **Three slots per wave**; two tiny repos (together under 300 files) share one slot.

**Gate tags:**
- **[92]** `&#92;` confirmed on staging (Foresight test page `53c7ee8`). Everything carrying R002 waits for it.
- **[370]** D5 puts 370 in R2, and that repo's 370 sync is committed.
- **[ibi]** ibi refresh on `wip` and fetched.
- **[DP]** Thiyagu is told before Data Management is pushed (he is testing builds on its `wip`).
- **[P80]** that repo's Phase 80 moves are committed.
- **[D7]** Δ1 list decided on Mon, versions synced.
- **[BWP]** AEM answers on the 50-character limit.
- **[STR]** Streaming goes in R2.

**Before Mon W1:**
- **Sun 15**, as planned and one family at a time: Phase 80 for Messaging (`bdca327` + `c4ffac8`), Adapters (`bf9bd99`), Fulfillment (`8415181` + `9dfe5ee`) and MFT (`fbfb772` + `796fe65`). That is 7 pushes in 4 steps, without R002, because each is a prefix of its repo.
- If any of them is not out by Mon 08:30, it takes the first Monday slots and the grid below shifts by one wave per family.
- If BusinessConnect and the archives do go out on Sunday, pull Wed W2–W3 forward into their Mon slots.

| When | Slot A | Slot B | Slot C |
|---|---|---|---|
| **Mon W1 08:30** | **BC-1** `4bad5b4` part a, 1,654 renames (path piece) | **TRA-1** up to R002, `0e1f2cf`→R002: 2,271 [92] | **EMS-1** merge `origin/wip` + `995f5cd`→R002: ≈300 [92] |
| Mon W2 11:30 | **BC-2** rest of `4bad5b4`, 1,103 | **BCres-1** `a88dca5`, 248 | **Cloud-1** `4bbfb90`→R002: 306 [92] |
| Mon W3 14:30 | **ARCH-1** `ec07c55` (3) + `103d6eb` (6), two repos | **WFRS-1** merge + `8452d4e3` 9.3.0–9.3.3: 2,217 [ibi] | **BWPres-1** `9e6d686`, 509 |
| Mon W4 17:30 | **WFRS-2** merge `8452d4e3` (rest): 2,614 [ibi] | **WF-1** merge + `efd0cca1` + 349 WFC: ≈530 [ibi] | **AS-1 + FTL-1** R002 103 + 164 [92] |
| Mon W5 20:30 | **BWP-1** merge + `39bc4080`→`33a0932c` (12 K2 commits): 2,423 | **LOCWF-1** merge + `4221ba61`, `513f8fe3` + 9.3.5 translations: ≈430 [ibi] | **FOCUS-1** merge + 349 FOCUS 9.3.x: ≈20 [ibi] |
| **Tue W1 08:30** | **PLAT-1** final CP 1.3.0–1.5.1: ≈1,660 [370][P80] | **BW-1** `25cb6b2`, `7184f3b` + final 5.15.0/5.15.1: ≈2,030 [92] | **BWP-2** `3aab5a02`→`92daa485` (11 K2 + K3): 2,323 |
| Tue W2 11:30 | **PLAT-2** final CP 1.6.0–1.9.0: ≈1,900 | **BW-2** final BWCE 2.10.0: ≈1,480 | **DM-1** merge probes + R002 + 370 (≤2,546; if over, MDM 11.x goes to DM-2) [92][370][DP] |
| Tue W3 14:30 | **PLAT-3** final CP 1.10.0–1.13.0: ≈2,310 | **BW-3** final BW 6.11.0 + version lists + R002 rest: ≈2,000 [370] | **BWP-3** R002 + 370: ≈730 [92][370] |
| Tue W4 17:30 | **PLAT-4** final CP 1.14.0–1.17.0: ≈2,540 | **BW-4** SmartMapper at new name (943) + premium (3) + 370 on 5.16.1, 6.12.0, 6.13.0; **+ BWres** (3) [370][P80] | **BPM-1** R002 652 + 370 ≤974 [92][370] |
| Tue W5 20:30 | **PLAT-5** Platform 1.0.0/1.1.0 + 370 on CP 1.18–1.20, CLI + R002 + P80: ≈2,000 | **FOR-1** R002 927 + 370 ≤507 [92][370] | **MFT-1** R002 76 + 370 ≤1,762 [92][370] |
| **Wed W1 08:30** | **FLOGO-1** R002 118 + 370 ≤970 | **BE-1** `349053c`, `c068219` + R002 + 370 ≤1,213 | **FUL-1** R002 201 + 370 ≤440 |
| Wed W2 11:30 | **BC-3** R002 229 + 370 ≤211 | **iP-1** R002 421 | **DM-2** if needed; else **MF-1 + ADP-1** |
| Wed W3 14:30 | **MF-1 + ADP-1** R002 20 + 39 | **MSG-1 + HAWK-1** R002/370 18 + 96 | **GEN-1 + SCR-1** R002/370 125 + 110 |
| Wed W4 17:30 | **STR-1** [STR] merge + `1cfa47a` part 1: ≈2,500 | spare (BWP-P80 if [BWP]) | spare |
| Wed W5 20:30 | **STR-2** [STR] rest + `ecff12b`, `e5a1c2d` + P80: ≈2,300 | spare | spare |
| **Thu W1 08:30** | **Δ1-a** [D7] | **Δ1-b** [D7] | **Δ1-c** [D7] |
| Thu W2 11:30 | **Δ1-d** [D7] | **Δ1-e** [D7] | re-push buffer |
| Thu W3 14:30 | re-push buffer | re-push buffer | re-push buffer |
| Thu W4 17:30 | **last push of R2** (shows about 20:30) | – | – |

Notes on the grid:
- **Chains** (each step waits for the one before): Platform 5, BusinessWorks 4, bw-plugin 3, Reporting Server 2, Data Management 1–2, Streaming 2. Platform is the critical path. It cannot start before the 370 sync, because every K3 Control Plane version is re-converted, so the **370 syncs must be committed by Mon ~20:00**. If they land on Tue morning, Platform ends Wed morning and BPM, Foresight and MFT slip one wave each, which still fits.
- **Δ1** gets one push per repo its 16 versions land in (assumed 5 repos). Any version not synced by Wed 20:00 goes to R3/R4. If a Δ1 version lands in Platform, BusinessWorks or bw-plugin, it rides the last chunk of that chain only if it is synced before that chunk; otherwise it is a Thu push.
- **If `&#92;` is not confirmed** on Mon morning, the R002 commit sits on top of every TIBCO repo. Push only the prefixes before it (TRA `6a0badc`, Cloud `0519055`, EMS `28ce5b9`, bw-plugin K2 and K3, BusinessWorks K2 + 5.15.x taken from `135c82f` rather than the final tree). Then take R002 out of the local history before 370 is committed on top: all R002 commits are local only.
- **BW plug-in renames [BWP].** They need 9 pushes, 8 of them one after another in one repo (§2). Starting Tue W4 after BWP-3 shows, they end Thu W1, and they push BPM, Foresight, MFT and Wed W1–W3 into the Wed/Thu spares and buffer. **This fits only with Streaming in R3 and no failed build.** Recommendation: R3 unless the answer is in by Mon evening.
  - Until then, 2 of bw-plugin's 3 K3 additions (Files 8.2.0, SAP 8.6.0) are served at the cut-off 50-character address. CICS's folder is 49 characters and is fine.

## 4. Risks, and the check after each chunk

**Risks:**
1. **A build that never shows** (as Data Management did on Fri: an underscore in the repo name, now renamed).
   - At +3 h, probe again at +4 h.
   - At **+6 h, stop that repo's chain** and send Digital Platform the sha and time. Other repos go on.
   - Data Management and its resources are still to be checked: their first build since the rename was Thiyagu's.
2. **Others' commits on `wip`.** Always `git fetch` and `git log HEAD..origin/wip` right before a push. A plain `<sha>:wip` push to EMS, bw-plugin, Data Management, Streaming or any ibi repo is refused (not a fast-forward). **Never force.**
3. **EMS merge loses Digital Platform's Pulsar link fix** (`16c0de2`). Check that link on staging after EMS-1.
4. **Renames cost double.** BC-1 is 1,654 renames (3,300 deletes and adds). Hawk (116) and ActiveSpaces (159) showed in about 2 h, but no large rename has been through yet. Watch BC-1's time before pushing BC-2.
5. **`&#92;` not confirmed:** see §3. Every TIBCO repo's later commits sit after R002.
6. **370 sizes are unknown until sync.** Keep one commit per version so a large repo (Platform, BusinessWorks, Data Management, MFT) can be split.
7. **Δ1 is the tightest item.**
   - The refresh is Sun/Mon, downloads Mon night, conversion Tue–Wed.
   - It lands on Thu, the day of the approval, so a failed Δ1 version must not hold R2. It goes to R3.
8. **ibi refresh**:
   - It may overlap the doubled-heading commits (`8452d4e3`, `efd0cca1`). If the merge conflicts widely, re-run the heading fix on the refreshed pages instead of resolving by hand.
   - Discard the 180 line-ending-only files in container-editions before merging.
9. **Final-state pieces** (Platform, BusinessWorks) are not commits from `content-fix`. After the last one, `git diff r2/push content-fix` must be empty apart from Digital Platform's files. That is the proof nothing was left out.
10. **Batch 4 on Thu night** checks R2, so everything must show by about 21:00 Thu. The last push is Thu 17:30.

**Check after each chunk**: staging `https://stg-docs.tibco.com` or `https://stg-docs.ibi.com`, with a page address of `/us/en/<folder>/<doc-type>/<version-dashed>/<page>.html`. Always fetch fresh, bypassing the cache.
1. Take two pages from the chunk: `git diff --name-only --diff-filter=AMR <previous wip> <pushed sha>`, the first and the last `.md`.
2. **Shown** when both return 200 and the footer reads "Last published: <today>", plus the marker for the kind of change:

| Change | Marker on staging |
|---|---|
| Phase 80 rename | New short address serves 200; the old long one no longer serves the page. For **MFT**, which was not served at all, this is the first time its pages appear |
| K2 removal | A removed version gives 404, e.g. TRA `tibco-administrator-enterprise-edition/online-help/5-12-2/`, Cloud `tibco-cloud-integration-flogo-payg/online-help/2-11-0/` |
| K3 addition | New version's first page 200, e.g. `tibco-control-plane/online-help/1-3-0/`, `tibco-businessworks-container-edition/online-help/2-10-0/`, `tibco-businessworks-smartmapper-enterprise-server/online-help/6-0-1/` |
| R002 | A page from the repo's R002 commit shows a single `\` in prose and `<host>`-style placeholders as `<…>` |
| 370 | The version's example page from `reports/fix-370-affected-2026-11-14.csv` shows the list content that was missing |
| Phase 78 | EMS 10.5.1 shows the new nested pages (217); the Pulsar transports link resolves |
| 349 / 343 / 362 / 363 | The version's `default`/`index` page exists; a heading-with-code link lands on its heading |
| ibi doubled headings | A Reporting Server 9.3.x page shows its title once |

## 5. What you approve

**Mon 16 (morning slot), so the schedule can start:**
1. Open R2 from Mon (exception to rule 4).
2. `&#92;` reads right on the Foresight test page, so R002 goes in.
3. D5 includes 370, and D7 sets the Δ1 list.
4. Streaming: R2 (Wed evening) or R3.
5. BW plug-in renames: R3 unless the AEM answer is in by Mon evening.

**Thu 19, one yes or no:**
- **"R2 is complete"**: every chunk in §3 shows on staging (list with times), or the ones that did not are named;
- the last wave goes (Δ1 and any re-push) by 17:30;
- whatever did not make it moves to **R3 (Thu 26)**: BW plug-in renames, Streaming, Hybrid Integration Connectivity Add-on, the menu-title rollout, and Δ1 versions that did not convert cleanly;
- **Batch 4** starts that night.
