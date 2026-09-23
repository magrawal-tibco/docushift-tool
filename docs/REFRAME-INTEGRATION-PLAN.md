# Reframe — DocuShift Integration Plan

Companion to `REFRAME-REQUIREMENTS.md`. Read that first — it defines what Reframe does and why.
This document covers **how to land it in DocuShift**.

---

## 1. Objective

Land Reframe as a DocuShift stage that runs after Markdown conversion, merges granular Flare
topics into maintainable pages, and hands a review queue to writers.

---

## 2. What this plan does and does not assume

**Known and settled:**
- The team owns DocuShift and can add a stage natively
- Reframe runs only for the MadCap Flare engine (C1/C2)
- Version scope comes from existing conversion eligibility (C3)
- Markdown becomes the permanent authoring source after conversion — the merge runs once
- Reference-list pages are deferred to writer judgment, never auto-resolved (D1)

**Not known — you must determine these against the actual DocuShift codebase.** This plan was
written without access to it, so anything below about *where* code goes is a recommendation to
validate, not a specification:
- How stages are registered, ordered, and configured
- Where conversion-engine identity lives and how a stage reads it
- How eligibility exposes its version list
- Whether an existing manifest/report convention should be matched
- Whether stages can already fail the pipeline on validation
- Whether a stage can be invoked standalone against a frozen prior-stage output

§7 turns these into concrete questions.

---

## 3. Recommended integration shape

**Add Reframe as a discrete stage that DocuShift invokes — not as logic embedded in an existing
stage's core.**

Rationale:
- It must coordinate with whichever stage owns `toc.yml` and `metadata.yml`, since it rewrites
  both — so it has to be pipeline-aware.
- But it carries editorial policy (cap values, boundary rules, per-set TOC adapters) that will
  be tuned repeatedly. Embedding that in the converter means every tuning pass touches the
  converter.
- Keeping it independently runnable against a frozen upstream output preserves a fast
  iterate-and-eyeball loop, which matters a lot given the irreversibility (§6).

The proof-of-concept is already shaped this way. The work is formalizing the interface, not
restructuring the logic.

**Engine gate placement:** orchestrator skips Reframe for non-Flare engines *and* Reframe
asserts on engine at entry. Both. The standalone-run path is precisely where a wrong-doc-set
invocation happens, and the orchestrator isn't in that path.

---

## 4. Phasing

### Phase 0 — Contracts and gate · size S · blocking

Nothing else can be built cleanly until these are fixed.

- Engine gate (C1/C2), including the no-op passthrough path for non-Flare
- Stage interface: inputs, outputs, config location, how it reads engine + eligibility
- **Review-queue schema (R6)** — see §5, this is the one that matters
- Per-doc-set config shape, including the TOC schema adapter seam

*Exit:* a registered stage that correctly no-ops for non-Flare engines and passes through a
Flare set unchanged. No merging yet.

### Phase 1 — Port and retarget the packing algorithm · size M

- Port R1–R5 from the POC (`docrestruct/build_merged.py`)
- Apply the maintenance retarget: **subtree cohesion drives, MAX_WORDS caps only** (R1.2).
  Drop `MIN_WORDS` rather than wiring it up.
- Make the parser fence-aware (§7 of the requirements)
- Fix the three POC defects listed in requirements §10
- Layout pinning (R1.4) — only if §7-Q2 says eligibility can return multiple versions of one set
- Determinism check

*Exit:* reproduces the reference-corpus baseline in requirements §6, with page count allowed to
rise from the R1.2 change. All acceptance checks green.

### Phase 2 — Review queue and editorial pass · size M · critical path

- Emit `review-queue.csv` per R6
- Improve page-title derivation and flag `title-inherited` where it's still a guess (R7.1)
- Build whatever consumes the queue — skill, UI, or checklist (D4)

**Do not treat this as polish.** Because reference-list resolution is deferred to writers, the
queue is the only path by which the hardest ~25–30 pages get resolved. Phase 1 ships
deliberately incomplete without it.

*Exit:* a writer can work the queue end to end on the reference corpus and the resulting pages
are ones they'd sign off on.

### Phase 3 — Pipeline integration · size S–M

- Wire eligibility-driven version scoping
- Validation as a genuine pipeline fail condition, not just a printed report
- Per-doc-set configs for the sets actually queued for conversion
- Second TOC schema adapter, if a non-`items`/`path`/`children` set is in scope

*Exit:* a full pipeline run over a real doc set, engine-gated, validation-enforced.

### Phase 4 — Pilot with writer sign-off · size S

One real doc set, converted, queue worked, **explicit writer approval before publishing
redirects**. Given irreversibility, this gate is the point of the whole plan.

---

## 5. The one contract to get right first

Phase 1 and Phase 2 are more coupled than they look, and `review-queue.csv` is the seam. Get it
wrong and both sides need rework.

Before writing packing code, answer:
- What gets flagged, and on what exact threshold?
- What does the reviewer need in order to decide without opening the source tree?
- What does the reviewer hand back — an edit in place, or a directive Reframe re-runs on?

That last question is the sharp one. **Recommendation: edits in place.** Since Markdown is the
authoring source from conversion onward, a writer fixing a title or converting a list to a table
is simply authoring — durable, no re-run, no second source of truth. A directive-based loop
re-introduces a generated-artifact model that this migration exists to leave behind.

Budget an hour on this schema before building outward from it in both directions.

---

## 6. Risks

| risk | impact | mitigation |
|---|---|---|
| **Irreversibility** | A bad boundary is permanent — hand-edited pages plus published URLs | Phase 4 writer gate; determinism so review reflects what ships |
| **Editorial pass gets cut under schedule pressure** | The 16 reference-list pages ship as 60-heading walls; worst outcome of the whole project | Keep Phase 2 on the critical path explicitly; don't let Phase 1's green checks read as "done" |
| **Cross-version layout drift** | Versions get non-corresponding files; porting fixes stops being a clean diff, permanently | R1.4 pinning — decide early, it's cheap now and impossible later |
| **TOC schema variance** | Second doc set needs a different parser than the first | Adapter seam in Phase 0, not retrofitted |
| **Fence-unaware parsing** | Silent corruption of code samples | Fixed in Phase 1; add a corpus with fenced `#` lines to the test set |
| **Pre-existing defects attributed to Reframe** | Wasted debugging, false failures | Requirements §8 lists them; baseline the source tree before merging |

---

## 7. Questions for the DocuShift side

1. How does a stage read the **conversion engine** identity? Is there a config object, or does
   it need to be threaded in?
2. Can conversion eligibility return **more than one version of the same doc set** in a single
   run? This decides whether R1.4 layout pinning is required or dead weight.
3. Is there an existing **manifest/report convention** Reframe's four CSVs should conform to?
4. Can a stage **fail the pipeline** on its own validation, or is that orchestrator-level?
5. Where do **per-doc-set configs** live today, and is there a precedent for a stage carrying
   editorial policy?
6. Can a stage be **run standalone** against a frozen prior-stage output? The plan assumes yes;
   if not, Phase 1 iteration gets materially slower and that changes the estimate.
7. Which stage owns `toc.yml` and `metadata.yml` generation, and does anything downstream of
   Reframe consume them?

---

## 8. Definition of done

- Reframe is a registered stage that no-ops cleanly for non-Flare engines
- A Flare doc set converts with all acceptance checks in requirements §6 green
- The review queue has been worked by a writer, with sign-off, on at least one real set
- Redirects are published and deep links resolve to the correct anchors
- Per-doc-set config is externalized; no doc-set specifics hardcoded in the stage
