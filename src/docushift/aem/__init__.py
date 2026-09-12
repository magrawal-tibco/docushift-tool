"""Stage 6: the publishing side of AEM synthesis (version.yml, the distributor).

**Navigation synthesis is not here.** `toc.yml`, `metadata.yml` and the generated
landing and container pages are built by `converter/navigation.py`, inside the
conversion run: the node list exists only while the engines' units are in hand and
the pages it generates have to reach the staging tree before the swap. What is left
for this package is everything that lives *above* a version folder and needs a
`--target-dir` -- the per-doc-class `version.yml`, the document router, and the
distributor. Phases 6b-6d; see docs/planning.md.
"""
