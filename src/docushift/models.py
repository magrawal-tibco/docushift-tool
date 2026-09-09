"""Data models for DocuShift.

These are the in-memory representation. The on-disk form is the CSV pair
`config/products.csv` + `config/versions.csv` (docs/architecture.md §3); volatile
machine state (etags, sizes, checksums, per-stage status, free-form metadata)
deliberately lives in `state.db` instead, so the CSVs stay stable enough to leave
open in a spreadsheet.
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class ConversionStatus(StrEnum):
    """Lifecycle status of a product version."""
    DISCOVERED = "DISCOVERED"
    DOWNLOADED = "DOWNLOADED"
    EXTRACTED = "EXTRACTED"
    CONVERTED = "CONVERTED"
    SYNCED = "SYNCED"
    ERROR = "ERROR"


class SourceEngine(StrEnum):
    """Source documentation generator engine.

    A property of a *version*, not a product -- see docs/architecture.md §3.4.

    Three kinds of value live here, and the distinction is the point of the
    column. `AUTO` means **not yet determined** -- never a guess. The four
    engines above the divider are ones Stage 5 converts. The rest are generators
    the detector can *name* but the pipeline cannot convert: recording them beats
    collapsing them into `AUTO`, because "we know what this is and have no
    handler" is a scoping decision for a human, while "we have no idea" is a
    detector bug. Both skip conversion; only one is worth investigating.

    The unconvertible set is what the 2026-09-08 corpus sweep actually found in
    the 408 versions that carried HTML and detected as `AUTO` -- see
    docs/design.md §7. `OTHER` is the honest slot for a `<meta name="generator">`
    string we have no name for; the raw string goes to `state.db`.
    """
    # Converted by a Stage 5 handler.
    FLARE = "flare"
    DITA = "dita"
    WEBWORKS = "webworks"
    DOCBOOK = "docbook"

    # Identified, but no handler -- recorded so the sheet can be reviewed.
    R_HELP = "r-help"
    ROBOHELP = "robohelp"
    FRONTPAGE = "frontpage"
    HELP_AND_MANUAL = "help-and-manual"
    MKDOCS = "mkdocs"
    DOCUSAURUS = "docusaurus"
    DOXIA = "doxia"
    OTHER = "other"

    AUTO = "auto"


CONVERTIBLE_ENGINES = frozenset(
    {SourceEngine.FLARE, SourceEngine.DITA, SourceEngine.WEBWORKS, SourceEngine.DOCBOOK}
)
"""Engines a Stage 5 handler exists or is planned for.

Membership -- not "is it `AUTO`" -- is what Stage 5 tests before converting.
Anything outside this set is skipped with a message naming the engine, which is
a different report line from the one `AUTO` produces.
"""


class EngineSource(StrEnum):
    """How a version's engine was arrived at. Precedence: manual > detected > auto."""
    MANUAL = "manual"
    DETECTED = "detected"
    AUTO = "auto"


class ZipSource(StrEnum):
    """Where a version's package comes from -- see docs/architecture.md §3.8.

    `MANUAL` means the ZIP was supplied by hand and sits at the canonical path
    already; the pipeline must never try to fetch it, and it is exempt from the
    "convert-eligible with no zip_url" check. The path itself is deliberately not
    stored: it is derivable from `(bu, family, product_code, version)`, whereas an
    absolute path in a shared CSV is valid on exactly one machine.
    """
    AUTO = "auto"
    MANUAL = "manual"


class FamilySource(StrEnum):
    """How a product's family was arrived at. Precedence: first listed wins."""
    MANUAL = "manual"
    TAXONOMY_RULE = "taxonomy_rule"
    DOCSITE_CATEGORY = "docsite_category"
    UNCLASSIFIED = "unclassified"


class ScopeSource(StrEnum):
    """How a product's `in_scope` value was arrived at -- docs/architecture.md §3.10.

    Precedence: first listed wins, exactly as `FamilySource` does. `MANUAL` is a
    human's edit and no fetch may touch it; `SCOPE_RULE` means the product's
    docsite slug is listed in `config/scope.yaml`; `DEFAULT` means listed nowhere,
    and is the value a merge resets to when a slug is removed from the rule file.
    """
    MANUAL = "manual"
    SCOPE_RULE = "scope_rule"
    DEFAULT = "default"


class ProductVersion(BaseModel):
    """One published version of a product -- one row of `versions.csv`.

    `convert_eligible` and `convert_batch` answer two different questions and are
    deliberately separate columns -- see docs/architecture.md §3.7. Eligibility is
    long-lived policy ("may this version ever be converted?"); the batch is
    scheduling ("is it in *this* run?"). Collapsing them would mean a three-version
    POC required flipping `convert_eligible` to false on every other row.
    """
    product_code: str
    version: str
    is_archived: bool = False
    convert_eligible: bool = True
    # Free-text run label, e.g. `poc-1` or `wave-2`. Empty means "not scheduled".
    # Opt-in by design: tagging three rows is the whole cost of scoping a POC.
    convert_batch: str = ""
    release_date: str | None = None
    engine: SourceEngine = SourceEngine.AUTO
    engine_source: EngineSource = EngineSource.AUTO
    zip_url: str | None = None
    zip_source: ZipSource = ZipSource.AUTO
    custom_override: bool = False

    # Stage 4 extraction inventory -- see docs/architecture.md §3.9. Every one is
    # optional because blank and zero are different answers: blank means this
    # version has never been extracted, `0` means it was and there was nothing
    # there. Defaulting them to 0/False would make the archived half of the
    # catalog indistinguishable from a corpus that genuinely ships no CSH.
    #
    # `has_csh` is not `csh_names > 0`: it records that a CSH *source file* was
    # found, while the count records what parsed out of it. `true` with `0` is the
    # empty-alias-file case, 55% of the observed corpus (§5.3.1). `has_api_ref`
    # against `api_files` carries no such nuance and is a filtering convenience;
    # `record_extract_inventory` writes each pair from one computation so they
    # cannot drift.
    has_csh: bool | None = None
    csh_names: int | None = None
    has_api_ref: bool | None = None
    api_files: int | None = None
    doc_files: int | None = None


class Product(BaseModel):
    """One product -- one row of `products.csv`, plus its versions.

    `in_scope` is the outermost of the three selection gates (§3.7): a product-level
    standing decision that no version of this product is ever converted. It is
    deliberately not expressible as `convert_eligible=false` on every version row,
    because next quarter's release arrives from a fetch defaulting to eligible --
    an exclusion written that way decays silently (§3.10).
    """
    product_code: str
    display_name: str
    bu: str = "tibco"
    family: str = "general"
    family_source: FamilySource = FamilySource.UNCLASSIFIED
    slug: str | None = None
    in_scope: bool = True
    scope_source: ScopeSource = ScopeSource.DEFAULT
    custom_override: bool = False
    versions: dict[str, ProductVersion] = Field(default_factory=dict)


class Catalog(BaseModel):
    """The master additive product catalog."""
    products: dict[str, Product] = Field(default_factory=dict)
