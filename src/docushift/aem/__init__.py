"""Stage 6: reserved, and currently holding nothing.

Both halves of Stage 6 landed elsewhere, for reasons the code settled rather than
the plan. **Navigation synthesis is in `converter/navigation.py`**, inside the
conversion run: the node list exists only while the engines' units are in hand and
the pages it generates have to reach the staging tree before the swap.
**The distributor and `version.yml` are in `sync/`** (Phase 6b) -- everything that
lives above a version folder needs a `--target-dir`, which makes it Stage 7 work by
every test that matters: the same selection, the same five outcomes, the same swap.

What is left for this package is 6c's document router, if it turns out to belong
here rather than beside the distributor. See docs/planning.md.
"""
