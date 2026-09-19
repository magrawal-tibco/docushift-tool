"""Click CLI entrypoint for DocuShift.

The command tree mirrors the pipeline in docs/architecture.md and the surface
documented in docs/user-guide.md. It is declared in full in Phase 1 so the console
script installs and ``--help`` is an accurate contract; each stage is wired up in
its own phase (see docs/planning.md). Unimplemented commands fail loudly -- a
``convert`` that exits 0 while converting nothing hides how far along the pipeline
actually is.

Functional so far: ``doctor`` (Phase 1), the whole ``catalog`` group including
``fetch`` (Phase 3), ``download`` and ``archive download`` (Phase 4a), and
``extract`` (Phase 4b-1, unpack and engine detection -- the inventory walk it
also owes is 4b-2). ``convert`` onward wait on Phases 5-7.
"""

from pathlib import Path

import click
import requests
from rich.console import Console
from rich.table import Table

from docushift import __version__
from docushift.catalog import CatalogError, CatalogManager
from docushift.config import ConfigManager
from docushift.discovery import DocsiteClient, DocsiteCrawler
from docushift.models import ReleaseStatus, ScopeSource, SourceEngine, ZipSource
from docushift.reporting.findings import REGISTRY, FindingsRun, Severity
from docushift.state import StateStore
from docushift.utils.slug import version_segment

console = Console()

DIR_PATH = click.Path(file_okay=False, path_type=Path)


def _pending(command: str, phase: str) -> None:
    """Aborts with a clear message for a command that is scaffolded but not built."""
    raise click.ClickException(
        f"`docushift {command}` is not implemented yet (scheduled for {phase}). "
        f"See docs/planning.md for the roadmap."
    )


def _no_selection(command: str) -> None:
    """Exits 1 for a selection that matched nothing -- `architecture.md` §7.4.

    Until Phase 7a every stage printed this and exited 0, which meant a typo in
    `--product` was indistinguishable from a clean run in any script that checked
    the status. Exit 1 is "you asked for nothing", not "something went wrong": a
    stage that ran and found errors still exits 0, because it did its work and the
    errors are in the report.

    `--dry-run` is deliberately not exempt. A dry run over an empty selection is
    the same mistake, discovered one command earlier.
    """
    console.print(
        f"[yellow]No convert-eligible versions match this selection.[/yellow] "
        f"`docushift catalog list --eligible-only` shows what `{command}` can work on."
    )
    raise click.exceptions.Exit(1)


def _scope_options(func):
    """Shared --bu / --family / --product / --version / --batch / --all selection options."""
    for option in reversed(
        [
            click.option("--all", "select_all", is_flag=True, help="Apply to the whole catalog."),
            click.option("--bu", default=None, help="Restrict to a business unit (tibco | ibi)."),
            click.option("--family", default=None, help="Restrict to a product family."),
            click.option("--product", "product", default=None, help="Restrict to one product (slug or product_code)."),
            click.option("--version", default=None, help="Restrict to a single version."),
            click.option(
                "--batch",
                default=None,
                help="Restrict to versions tagged with this convert_batch label, e.g. poc-1.",
            ),
        ]
    ):
        func = option(func)
    return func


@click.group()
@click.version_option(__version__, prog_name="docushift")
@click.option(
    "--root",
    type=DIR_PATH,
    default=None,
    help="Project root holding config/, cache/, and output/. Defaults to the current directory.",
)
@click.pass_context
def main(ctx: click.Context, root: Path | None) -> None:
    """DocuShift: TIBCO & ibi documentation migration pipeline (docs.tibco.com -> AEM GFM)."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = ConfigManager(root_dir=root)


# ---------------------------------------------------------------------------
# Catalog (Phases 2-3)
# ---------------------------------------------------------------------------


@main.group()
def catalog() -> None:
    """Discover, inspect, and edit config/products.csv and config/versions.csv."""


def _status_cell(ver) -> str:
    """One version's lifecycle status, rendered for a table.

    `unknown` prints blank rather than as a word: it is the majority state and it
    means the report is silent, which is not a finding. Only `retired` is coloured,
    because only `retired` stops the version converting.
    """
    if ver.release_status is ReleaseStatus.UNKNOWN:
        return ""
    if ver.release_status is ReleaseStatus.RETIRED:
        return f"[red]retired[/red]{f' {ver.retirement_date}' if ver.retirement_date else ''}"
    return f"[dim]{ver.release_status}[/dim]"


def _catalog_manager(ctx: click.Context) -> CatalogManager:
    cfg: ConfigManager = ctx.obj["config"]
    return CatalogManager(cfg.products_path, cfg.versions_path, StateStore(cfg.state_db_path), config=cfg)


@catalog.command("fetch")
@_scope_options
@click.option("--include-archived/--no-include-archived", default=True, help="Also inventory archived versions.")
@click.option("--allow-deletes", is_flag=True, help="Permit removal of versions discovery no longer returns.")
@click.option("--dry-run", is_flag=True, help="Report the merge plan without writing the CSVs.")
@click.pass_context
def catalog_fetch(
    ctx: click.Context,
    bu,
    family,
    product,
    version,
    batch,
    select_all,
    include_archived,
    allow_deletes,
    dry_run,
) -> None:
    """Fetch from docs.tibco.com and 3-way merge into the catalog CSVs."""
    if version:
        # Discovery works a whole product at a time, and the merge reads "absent
        # from this fetch" as deleted. Honouring --version would make every other
        # version of the product look removed.
        raise click.ClickException("`catalog fetch` works per product; drop --version (try --product instead).")
    if not any([select_all, bu, family, product, batch]):
        # A bare `catalog fetch` crawls the whole A-to-Z list (700+ entries). Make
        # that an explicit choice rather than the default.
        raise click.ClickException("Choose a scope: --all, or one of --bu / --family / --product / --batch.")

    cfg: ConfigManager = ctx.obj["config"]
    manager = _catalog_manager(ctx)

    # --product and --batch are resolved to crawl selectors up front so the crawler
    # can skip the per-product request entirely; --bu/--family cannot be, because
    # a product's family is not known until it has been classified.
    selectors: set[str] | None = None
    try:
        if product:
            selectors = _selectors(manager, [product])
        if batch:
            tagged = {p.slug for p, _ in manager.iter_versions(batch=batch)}
            if not tagged:
                raise click.ClickException(f"No catalog versions are tagged with batch '{batch}'.")
            batch_selectors = _selectors(manager, tagged)
            selectors = batch_selectors if selectors is None else selectors & batch_selectors
    except CatalogError as exc:
        raise click.ClickException(str(exc)) from exc

    crawler = DocsiteCrawler(DocsiteClient(cfg.load_docsite()), cfg, include_archived=include_archived)

    with console.status("Fetching product list from docs.tibco.com...") as status:
        def on_progress(index: int, total: int, slug: str) -> None:
            status.update(f"[{index}/{total}] {slug}")

        result = crawler.discover(bu=bu, family=family, selectors=selectors, on_progress=on_progress)

    for error in result.errors:
        console.print(f"[red]![/red] {error}")
    if not result.products:
        message = "Discovery returned no products; the catalog was left untouched."
        if selectors and not result.errors:
            # Almost always a code the A-to-Z list does not use as a slug, e.g.
            # `ems` is published as `tibco-enterprise-message-service`.
            message += (
                f" Nothing matched {', '.join(sorted(selectors))} -- if the product is not in the catalog yet,"
                f" pass its docs.tibco.com slug to --product."
            )
        raise click.ClickException(message)

    try:
        stats = manager.merge_fetch_results(result.products, allow_deletes=allow_deletes, dry_run=dry_run)
    except CatalogError as exc:
        raise click.ClickException(str(exc)) from exc

    findings = FindingsRun("catalog", batch=batch or "", store=None if dry_run else manager.state).start()
    if not dry_run:
        _record_discovery_metadata(manager, result)
    _record_catalog_findings(
        manager, findings, stats.products_fully_retired, scope_rules_conclusive=bool(select_all)
    )
    findings.finish()

    table = Table(title="Merge" + (" (dry run -- nothing written)" if dry_run else ""))
    table.add_column("Change")
    table.add_column("Count", justify="right")
    for label, count in stats.as_dict().items():
        if label in ("deletions_blocked", "scope_rules_unmatched", "products_fully_retired"):
            continue
        table.add_row(label.replace("_", " "), str(count))
    console.print(table)

    _report_retirements(stats)

    # Only conclusive over a fully fetched catalog: before that, a rule matches
    # nothing simply because its product has not been discovered yet.
    if select_all and stats.scope_rules_unmatched:
        console.print(
            f"[yellow]{len(stats.scope_rules_unmatched)} config/scope.yaml rule(s) matched no product:[/yellow] "
            + ", ".join(stats.scope_rules_unmatched[:12])
            + (" ..." if len(stats.scope_rules_unmatched) > 12 else "")
            + "\n[dim]Usually an upstream rename -- those products are no longer being excluded.[/dim]"
        )

    if result.unversioned or result.non_public:
        console.print(
            f"[dim]Skipped {result.unversioned} entries with no published versions "
            f"and {result.non_public} that are not publicly visible.[/dim]"
        )
    for note in manager.warnings():
        console.print(f"[yellow]WARN[/yellow] {note}")
    if result.errors:
        console.print(f"[yellow]{len(result.errors)} product(s) could not be reached and were left as-is.[/yellow]")
    _report_findings(findings)


def _resolve(manager: CatalogManager, selector: str) -> str:
    """`resolve_slug` with the ambiguity error surfaced as a CLI error, not a traceback."""
    try:
        return manager.resolve_slug(selector)
    except CatalogError as exc:
        raise click.ClickException(str(exc)) from exc


def _selectors(manager: CatalogManager, wanted) -> set[str]:
    """Expands what the user typed into the selectors the crawler can match.

    The crawler filters the A-to-Z list on either spelling, so both are passed:
    the resolved slug, and the raw token in case the catalog does not know it yet.
    That last case is what lets `--product <slug>` work before a first fetch.

    An ambiguous `product_code` raises out of `resolve_slug` rather than being
    silently narrowed to one of the products sharing it.
    """
    out: set[str] = set()
    for token in wanted:
        token = str(token).strip().lower()
        out.add(token)
        out.add(manager.resolve_slug(token))
    return out


def _record_discovery_metadata(manager: CatalogManager, result) -> None:
    """Parks docsite ids and folder paths in state.db rather than the CSVs.

    They are machine detail the download stage needs and a human editing a
    spreadsheet does not -- see docs/architecture.md §3.
    """
    if manager.state is None:
        return
    for slug, fields in result.product_metadata.items():
        for key, value in fields.items():
            manager.state.set_product_metadata(slug, key, value)
    for (slug, version), fields in result.version_metadata.items():
        for key, value in fields.items():
            manager.state.set_version_metadata(slug, version, key, value)


@catalog.command("list")
@_scope_options
@click.option("--eligible-only", is_flag=True, help="Only versions with convert_eligible=true.")
@click.option(
    "--out-of-scope",
    "out_of_scope",
    is_flag=True,
    help="Only products excluded from conversion (in_scope=false). See docs/architecture.md §3.10.",
)
@click.option(
    "--retired",
    is_flag=True,
    help="Only versions support has retired (release_status=retired). See docs/architecture.md §3.11.",
)
@click.pass_context
def catalog_list(
    ctx: click.Context, bu, family, product, version, batch, select_all, eligible_only, out_of_scope, retired
) -> None:
    """List catalog products and versions."""
    if out_of_scope and eligible_only:
        # `--eligible-only` filters out-of-scope products out entirely, so the two
        # flags together can only ever return nothing.
        raise click.ClickException("--out-of-scope and --eligible-only select disjoint sets; pass one.")
    if retired and eligible_only:
        # Same shape: the eligibility gate excludes retired versions outright.
        raise click.ClickException("--retired and --eligible-only select disjoint sets; pass one.")

    manager = _catalog_manager(ctx)
    try:
        pairs = manager.iter_versions(
            bu=bu,
            family=family,
            slug=manager.resolve_slug(product) if product else None,
            version=version,
            batch=batch,
            eligible_only=eligible_only,
        )
    except CatalogError as exc:
        raise click.ClickException(str(exc)) from exc
    if out_of_scope:
        pairs = [(p, v) for p, v in pairs if not p.in_scope]
    if retired:
        pairs = [(p, v) for p, v in pairs if v.release_status is ReleaseStatus.RETIRED]
    if not pairs:
        if out_of_scope:
            console.print("[green]No out-of-scope products in the catalog.[/green]")
            return
        if retired:
            console.print("[green]No retired versions in the catalog.[/green]")
            return
        console.print("[yellow]No matching catalog rows.[/yellow] Run `docushift catalog fetch` to populate.")
        return

    # The scope column earns its width only when something is actually excluded;
    # on a catalog with no exclusions it would be 250 blank cells.
    show_scope = any(not p.in_scope for p, _ in pairs)
    # Same rule for the lifecycle column: silence from the report is the norm for
    # 56% of versions, and a column of `unknown` would be noise.
    show_status = any(v.release_status is not ReleaseStatus.UNKNOWN for _, v in pairs)
    columns = ["Product", "BU", "Family", "Version", "Archived", "Eligible", "Batch", "Engine"]
    if show_scope:
        columns.insert(3, "Scope")
    if show_status:
        columns.insert(4 if show_scope else 3, "Status")

    table = Table(title=f"Catalog ({len(pairs)} versions)")
    for column in columns:
        table.add_column(column)
    for product, ver in pairs:
        row = [
            # The slug, not `product_code`: this column is what gets typed back at
            # `--product`, and only one of the two is guaranteed to name one product.
            product.slug,
            product.bu,
            product.family,
            ver.version,
            "yes" if ver.is_archived else "",
            "[green]yes[/green]" if ver.convert_eligible else "[dim]no[/dim]",
            ver.convert_batch or "[dim]-[/dim]",
            f"{ver.engine} ({ver.engine_source})",
        ]
        if show_scope:
            row.insert(3, "" if product.in_scope else f"[red]out[/red] ({product.scope_source})")
        if show_status:
            row.insert(4 if show_scope else 3, _status_cell(ver))
        table.add_row(*row)
    console.print(table)


def _report_retirements(stats) -> None:
    """Prints what the end-of-support rule cost this run -- docs/architecture.md §3.11.

    The emptied-product list gets its own line, in red, and is never truncated to a
    count. Everywhere else in this CLI a long list is trimmed with an ellipsis;
    here the list *is* the finding, because a product with no convertible version
    left publishes no documentation at all, and that is not something a reader
    should have to run a second command to discover.
    """
    if not stats.versions_retired:
        return
    console.print(
        f"[dim]{stats.versions_retired} in-scope eligible version(s) are retired and will be skipped "
        f"(config/eos.yaml).[/dim]"
    )
    if stats.products_fully_retired:
        console.print(
            f"[red]{len(stats.products_fully_retired)} product(s) have no convertible version left -- "
            f"every eligible version is retired:[/red]\n  "
            + "\n  ".join(stats.products_fully_retired)
        )


def _record_catalog_findings(
    manager: CatalogManager,
    findings: FindingsRun,
    emptied: list[str],
    *,
    scope_rules_conclusive: bool,
) -> None:
    """The four Stage.CATALOG codes, written to the run the caller opened.

    Every one of these was already computed and printed before Phase 7a -- the
    unmatched scope rules, the stale aliases, the emptied products -- and none of
    them survived the terminal scrollback. That is the whole gap 7a closes here:
    the numbers do not change, they just become rows somebody can query a week
    later.

    `scope_rules_conclusive` is the one judgement call. A rule matching nothing is
    only a finding over a fully fetched catalog; on a `--product ems` fetch it
    means the other 633 products were not looked at. `catalog eos` reads the
    catalog on disk and so is always conclusive.
    """
    if scope_rules_conclusive:
        for rule in manager.unmatched_scope_rules():
            findings.record(
                "SCOPE_RULE_UNMATCHED",
                slug=rule,
                message=f"config/scope.yaml excludes '{rule}', which matches no catalogued product",
            )
    for alias in manager.unmatched_eos_aliases():
        findings.record(
            "EOS_ALIAS_STALE",
            slug=alias,
            message=f"config/eos.yaml aliases '{alias}', which the active report does not mention",
        )
    for slug in emptied:
        findings.record(
            "EOS_PRODUCT_EMPTIED",
            slug=slug,
            message="every convert-eligible version is retired -- this product publishes nothing",
        )
    for product, version in manager.iter_versions():
        if version.convert_batch and not version.convert_eligible:
            findings.record(
                "BATCH_NOT_ELIGIBLE",
                slug=product.slug,
                version=version.version,
                message=f"tagged into batch '{version.convert_batch}' but convert_eligible is false",
            )


@catalog.command("eos")
@click.pass_context
def catalog_eos(ctx: click.Context) -> None:
    """Re-apply the end-of-support report to the catalog's release-status columns.

    `catalog fetch` does this too, but only as a side effect of re-crawling the
    docsite at two requests a second. When a new report lands and nothing else has
    changed, this is the whole update.
    """
    manager = _catalog_manager(ctx)
    findings = FindingsRun("catalog", store=manager.state).start()
    try:
        stats = manager.apply_eos()
    except (CatalogError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    # Conclusive here in a way it is not during a scoped fetch: this command reads
    # the catalog on disk, so a rule that matches nothing really matches nothing.
    _record_catalog_findings(
        manager, findings, stats.products_fully_retired, scope_rules_conclusive=True
    )
    findings.finish()

    summary = manager.triage_summary()
    counts = summary["release_status_counts"]
    table = Table(title="Release status (all catalogued versions)")
    table.add_column("release_status")
    table.add_column("Versions", justify="right")
    for status, count in counts.items():
        table.add_row(status, str(count))
    console.print(table)

    covered, total = manager.eos_coverage()
    console.print(f"[dim]The report carries rows for {covered} of {total} catalogued products.[/dim]")

    _report_retirements(stats)
    if not stats.versions_retired:
        # Printed next to the coverage line on purpose: "nothing retired" over 251
        # covered products is a result, over 3 it is a join that is not working.
        console.print("[green]No in-scope eligible version is retired by the current report.[/green]")
    for note in manager.warnings():
        if "eos.yaml" in note:
            console.print(f"[yellow]WARN[/yellow] {note}")
    _report_findings(findings)


def _report_findings(findings: FindingsRun) -> None:
    """The one line that makes a run's findings findable again."""
    summary = findings.summary()
    if not summary:
        return
    console.print(f"[dim]Recorded {summary} -- `docushift report --run {findings.run_id}`.[/dim]")


@catalog.command("show")
@click.option("--product", "product", required=True, help="Product to describe (slug or product_code).")
@click.pass_context
def catalog_show(ctx: click.Context, product: str) -> None:
    """Show one product and its full version history."""
    cfg: ConfigManager = ctx.obj["config"]
    manager = _catalog_manager(ctx)
    slug = _resolve(manager, product)
    found = manager.get_product(slug)
    if found is None:
        raise click.ClickException(f"No product '{product}' in the catalog.")
    product = found

    # An excluded product still prints its whole version history -- excluded is
    # not absent (§3.10) -- so the scope line has to say plainly that none of the
    # rows below will ever be converted, whatever their Eligible column says.
    scope = (
        "in_scope=true"
        if product.in_scope
        else f"[red]in_scope=false[/red] -- no version is ever converted; source: {product.scope_source}"
    )
    console.print(
        f"[bold]{product.display_name}[/bold] ({product.slug})\n"
        f"  bu={product.bu}  family={product.family} (source: {product.family_source})\n"
        f"  product_code={product.product_code}  custom_override={product.custom_override}\n"
        f"  {scope}\n"
        f"  workspace={cfg.family_dir(product.bu, product.family)}"
    )
    table = Table(title=f"{len(product.versions)} versions")
    for column in ("Version", "Archived", "Eligible", "Status", "Batch", "Released", "Engine", "ZIP"):
        table.add_column(column)
    for _, ver in manager.iter_versions(slug=slug):
        table.add_row(
            ver.version,
            "yes" if ver.is_archived else "",
            "yes" if ver.convert_eligible else "no",
            _status_cell(ver),
            ver.convert_batch or "-",
            ver.release_date or "-",
            f"{ver.engine} ({ver.engine_source})",
            # A manual row usually has no URL, so name the source rather than
            # printing a bare "-" that reads as "nothing to download".
            ver.zip_url or (f"[dim]{ver.zip_source}[/dim]" if ver.zip_source is not ZipSource.AUTO else "-"),
        )
    console.print(table)


@catalog.command("enable")
@click.option("--product", "product", required=True, help="Product to modify (slug or product_code).")
@click.option("--version", required=True, help="Version to modify.")
@click.option("--disable", is_flag=True, help="Set convert_eligible=false instead of true.")
@click.pass_context
def catalog_enable(ctx: click.Context, product: str, version: str, disable: bool) -> None:
    """Toggle convert_eligible for one product version."""
    manager = _catalog_manager(ctx)
    slug = _resolve(manager, product)
    if not manager.set_conversion_eligibility(slug, version, not disable):
        raise click.ClickException(f"No version '{version}' for product '{slug}'.")
    console.print(f"{slug}@{version}: convert_eligible = {'false' if disable else 'true'}")


@catalog.command("set")
@click.option("--product", "product", required=True, help="Product to modify (slug or product_code).")
@click.option("--version", default=None, help="Target a version row instead of the product row.")
@click.option("--bu", default=None, help="Set the business unit (products.csv).")
@click.option("--family", default=None, help="Set the family; also sets family_source=manual.")
@click.option("--display-name", default=None, help="Set the product display name.")
@click.option(
    "--in-scope/--out-of-scope",
    "in_scope",
    default=None,
    help="Include or exclude the whole product from conversion; also sets scope_source=manual, "
    "which outranks config/scope.yaml permanently.",
)
@click.option(
    "--engine",
    # Taken from the enum rather than retyped, so adding a generator in one place
    # is enough. The list includes the engines Stage 5 cannot convert: naming one
    # by hand is a legitimate correction of a bad detection, and it is more useful
    # in the sheet than `auto` even when nothing downstream acts on it.
    type=click.Choice([e.value for e in SourceEngine]),
    default=None,
    help="Override the detected engine; also sets engine_source=manual (permanent).",
)
@click.option("--zip-url", default=None, help="Override the resolved download endpoint.")
@click.option(
    "--zip-source",
    type=click.Choice(["auto", "manual"]),
    default=None,
    help="Mark the package as hand-supplied (manual) or fetchable (auto). See docs/user-guide.md.",
)
@click.option(
    "--release-status",
    "release_status",
    # From the enum for the same reason `--engine` is. Includes `unknown`, which is
    # the honest way to say "the report was wrong about this one" without asserting
    # a lifecycle stage nobody has verified.
    type=click.Choice([s.value for s in ReleaseStatus]),
    default=None,
    help="Override support's retirement verdict; also sets release_status_source=manual, "
    "which outranks the end-of-support report permanently. Only 'retired' blocks conversion.",
)
@click.option(
    "--batch",
    "convert_batch",
    default=None,
    help="Tag the version into a run label, e.g. poc-1. Pass '' to unschedule it.",
)
@click.pass_context
def catalog_set(
    ctx: click.Context,
    product,
    version,
    bu,
    family,
    display_name,
    in_scope,
    engine,
    zip_url,
    zip_source,
    release_status,
    convert_batch,
) -> None:
    """Set a catalog field, recording the change as a manual edit."""
    manager = _catalog_manager(ctx)
    product_edits = {
        "bu": bu,
        "family": family,
        "display_name": display_name,
        # `--in-scope/--out-of-scope` is a tri-state flag: None means untouched.
        # Passed on as a string because every set_product_field value is one.
        "in_scope": None if in_scope is None else str(in_scope).lower(),
    }
    version_edits = {
        "engine": engine,
        "zip_url": zip_url,
        "zip_source": zip_source,
        "release_status": release_status,
        "convert_batch": convert_batch,
    }

    if not any(v is not None for v in {**product_edits, **version_edits}.values()):
        raise click.ClickException("Nothing to set. Pass at least one field option.")
    if any(v is not None for v in version_edits.values()) and not version:
        raise click.ClickException(
            "--engine, --zip-url, --zip-source, --release-status and --batch are version fields; "
            "pass --version too."
        )

    slug = _resolve(manager, product)
    try:
        for name, value in product_edits.items():
            if value is not None and not manager.set_product_field(slug, name, value):
                raise click.ClickException(f"No product '{product}' in the catalog.")
        for name, value in version_edits.items():
            if value is not None and not manager.set_version_field(slug, version, name, value):
                raise click.ClickException(f"No version '{version}' for product '{slug}'.")
    except CatalogError as exc:
        raise click.ClickException(str(exc)) from exc

    console.print(f"Updated {slug}" + (f"@{version}" if version else ""))


@catalog.command("import")
@click.option("--allow-deletes", is_flag=True, help="Permit removal of rows that discovery no longer returns.")
@click.pass_context
def catalog_import(ctx: click.Context, allow_deletes: bool) -> None:
    """Re-import and normalize the CSVs, checking for spreadsheet damage."""
    manager = _catalog_manager(ctx)
    try:
        problems = manager.validate()
    except CatalogError as exc:
        raise click.ClickException(str(exc)) from exc

    if problems and not allow_deletes:
        for problem in problems:
            console.print(f"[red]![/red] {problem}")
        raise click.ClickException(
            f"{len(problems)} problem(s) found; nothing written. "
            f"Fix the CSVs, or re-run with --allow-deletes if the removals are intended."
        )
    for problem in problems:
        console.print(f"[yellow]![/yellow] {problem} [dim](allowed)[/dim]")

    # Warnings never block the write: an undeclared family is accepted and its
    # workspace folder auto-registered, per docs/architecture.md §4.2.
    for note in manager.warnings():
        console.print(f"[yellow]WARN[/yellow] {note}")

    manager.save()
    console.print("Catalog re-imported and normalized.")


@catalog.command("batches")
@click.pass_context
def catalog_batches(ctx: click.Context) -> None:
    """List the convert_batch labels in use and how many versions each selects."""
    counts = _catalog_manager(ctx).batches()
    if not counts:
        console.print(
            "[yellow]No versions are tagged into a batch.[/yellow]\n"
            "Tag some with `docushift catalog set --product <p> --version <v> --batch poc-1`, "
            "or by filling the convert_batch column in config/versions.csv."
        )
        return

    table = Table(title=f"Scheduled batches ({sum(counts.values())} versions)")
    table.add_column("convert_batch")
    table.add_column("Versions", justify="right")
    for label, count in counts.items():
        table.add_row(label, str(count))
    console.print(table)


@catalog.command("triage")
@click.pass_context
def catalog_triage(ctx: click.Context) -> None:
    """Report family classification progress and list unclassified products."""
    summary = _catalog_manager(ctx).triage_summary()
    total = summary["total"]
    if not total:
        console.print("[yellow]Catalog is empty.[/yellow] Run `docushift catalog fetch` to populate.")
        return

    table = Table(title=f"Family classification ({total} products)")
    table.add_column("family_source")
    table.add_column("Products", justify="right")
    for source, count in summary["counts"].items():
        table.add_row(source, str(count))
    console.print(table)

    unclassified = summary["unclassified"]
    console.print(f"\n[bold]{len(unclassified)} of {total}[/bold] products still need triage.")
    if unclassified:
        console.print("  " + ", ".join(unclassified[:40]) + (" ..." if len(unclassified) > 40 else ""))

    # Scope is reported next to triage because the two answer the same question
    # for a reviewer -- how much of the catalog is actually work -- and because an
    # out-of-scope product needs no family, so it should not read as a backlog.
    out_of_scope = summary["out_of_scope"]
    # `manual` is counted separately and not folded into the out-of-scope figure:
    # the same provenance covers a product pinned *into* scope against the rule
    # file, and reading those two as one number would misstate both.
    manual = summary["scope_counts"][str(ScopeSource.MANUAL)]
    console.print(
        f"\n[bold]{len(out_of_scope)} of {total}[/bold] products are out of scope "
        f"({summary['scope_counts'][str(ScopeSource.SCOPE_RULE)]} by config/scope.yaml); "
        f"{manual} carry a manual scope decision."
    )
    if out_of_scope:
        console.print("  " + ", ".join(out_of_scope[:40]) + (" ..." if len(out_of_scope) > 40 else ""))

    # Reported here for the same reason scope is: it is the other permanent gate,
    # and a reviewer asking "how much of this catalog is work" needs both numbers.
    retired_total = summary["release_status_counts"][str(ReleaseStatus.RETIRED)]
    console.print(
        f"\n[bold]{retired_total}[/bold] version(s) are retired, of which "
        f"[bold]{summary['versions_retired']}[/bold] would otherwise be converted."
    )
    if summary["products_fully_retired"]:
        console.print(
            f"[red]{len(summary['products_fully_retired'])} product(s) have no convertible version "
            f"left:[/red]\n  " + "\n  ".join(summary["products_fully_retired"])
        )


# ---------------------------------------------------------------------------
# Pipeline stages (Phases 4-7)
# ---------------------------------------------------------------------------


def _ingest_target(manager: CatalogManager, product, version):
    """Resolves `--from-file`'s `(product, version)`, adding the version row if needed.

    Both selectors are required: `--from-file` files one specific package, and a
    scope-shaped selector would silently pick one of several matches. The
    product/version asymmetry is `architecture.md` §3.8's -- an unknown product is
    an error, an unknown version on a known product is added with a warning.
    """
    if not product or not version:
        raise click.ClickException("--from-file needs both --product and --version.")
    slug = _resolve(manager, product)
    found = manager.get_product(slug)
    if found is None:
        raise click.ClickException(
            f"No product '{product}' in the catalog. A hand-supplied package still needs a "
            f"product row -- run `docushift catalog fetch --product {product}` first."
        )
    if version not in found.versions:
        console.print(
            f"[yellow]WARN[/yellow] {slug}: no version '{version}' in the catalog; adding the row. "
            f"You are holding the package, which is better evidence than discovery's silence."
        )
        try:
            manager.add_version(slug, version)
        except CatalogError as exc:
            raise click.ClickException(str(exc)) from exc
        found = manager.get_product(slug)
    return found, found.versions[version]


def _download_selection(manager: CatalogManager, bu, family, product, version, batch, select_all):
    """The versions a `download` invocation acts on, with the scope rules enforced."""
    if not any([select_all, bu, family, product, batch]):
        raise click.ClickException("Choose a scope: --all, or one of --bu / --family / --product / --batch.")
    try:
        return manager.iter_versions(
            bu=bu,
            family=family,
            slug=_resolve(manager, product) if product else None,
            version=version,
            batch=batch,
            eligible_only=True,
        )
    except CatalogError as exc:
        raise click.ClickException(str(exc)) from exc


def _report_download(stats) -> None:
    """The five-outcome summary every download run ends with."""
    from docushift.downloader import Outcome

    table = Table(title="Download")
    table.add_column("Outcome")
    table.add_column("Versions", justify="right")
    for outcome, label in (
        (Outcome.DOWNLOADED, "Downloaded"),
        (Outcome.CURRENT, "Already current"),
        (Outcome.SKIPPED_MANUAL, "Skipped (manual)"),
        (Outcome.NO_URL, "No zip_url"),
        (Outcome.FAILED, "Failed"),
    ):
        table.add_row(label, str(stats.count(outcome)))
    console.print(table)
    if stats.bytes_written:
        console.print(f"[dim]{stats.bytes_written / 1_048_576:.1f} MiB written.[/dim]")
    # Named individually rather than counted: "3 failed" out of 200 is not
    # actionable, and these are the rows a human has to do something about.
    for result in stats.results:
        if result.outcome is Outcome.NO_URL:
            console.print(f"[yellow]![/yellow] {result.slug}@{result.version}: {result.message}")
    for result in stats.failures:
        console.print(f"[red]![/red] {result.slug}@{result.version}: {result.message}")


@main.command()
@_scope_options
@click.option("--force", is_flag=True, help="Re-download even if the cached ZIP is current.")
@click.option(
    "--workers",
    type=int,
    default=None,
    help="Parallel downloads. Defaults to docsite.yaml's max_concurrent_requests.",
)
@click.option(
    "--from-file",
    "from_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="File a hand-obtained ZIP at the canonical path instead of fetching. Needs --product and --version.",
)
@click.option("--dry-run", is_flag=True, help="List what would be fetched without writing.")
@click.pass_context
def download(ctx, bu, family, product, version, batch, select_all, force, workers, from_file, dry_run) -> None:
    """Download convert_eligible packages into families/<locale>-<bu-slug>-<family-slug>/downloads/.

    Archived versions are never downloaded here -- pull one on demand with
    `docushift archive download` instead.
    """
    from docushift.downloader import Outcome, PackageDownloader

    cfg: ConfigManager = ctx.obj["config"]
    manager = _catalog_manager(ctx)

    if from_file:
        found, ver = _ingest_target(manager, product, version)
        downloader = PackageDownloader(cfg, manager)
        target = cfg.download_path(found.bu, found.family, found.slug, ver.version)
        try:
            result = downloader.ingest_file(found, ver, from_file, target)
        except (OSError, CatalogError) as exc:
            raise click.ClickException(str(exc)) from exc
        console.print(
            f"Filed {from_file} -> {result.path}\n"
            f"[dim]sha256 {result.checksum}  {result.size / 1_048_576:.1f} MiB  zip_source=manual[/dim]"
        )
        return

    pairs = _download_selection(manager, bu, family, product, version, batch, select_all)
    if not pairs:
        _no_selection("download")

    if dry_run:
        table = Table(title=f"Would download ({len(pairs)})")
        for column in ("Product", "Version", "Source", "Target"):
            table.add_column(column)
        for found, ver in pairs:
            source = str(ver.zip_source) if ver.zip_source is not ZipSource.AUTO else (ver.zip_url or "-")
            table.add_row(
                found.slug,
                ver.version,
                source,
                str(cfg.download_path(found.bu, found.family, found.slug, ver.version)),
            )
        console.print(table)
        return

    downloader = PackageDownloader(cfg, manager, workers=workers)
    console.print(f"Downloading {len(pairs)} version(s) with {downloader.workers} worker(s)...")

    def on_result(result) -> None:
        if result.outcome is Outcome.DOWNLOADED:
            note = " (resumed)" if result.resumed else ""
            console.print(
                f"  [green]v[/green] {result.slug}@{result.version} "
                f"{result.size / 1_048_576:.1f} MiB{note}"
            )
        elif result.outcome is Outcome.FAILED:
            console.print(f"  [red]x[/red] {result.slug}@{result.version}")

    _report_download(downloader.download_many(pairs, force=force, on_result=on_result))


def _report_extract(stats) -> None:
    """The five-outcome summary, the engine tally, and the two lists a human acts on."""
    from docushift.extractor import ExtractOutcome
    from docushift.models import CONVERTIBLE_ENGINES, SourceEngine

    table = Table(title="Extract")
    table.add_column("Outcome")
    table.add_column("Versions", justify="right")
    for outcome, label in (
        (ExtractOutcome.EXTRACTED, "Extracted"),
        (ExtractOutcome.CURRENT, "Already current"),
        (ExtractOutcome.MEASURED, "Measured from cache"),
        (ExtractOutcome.NO_PACKAGE, "No package"),
        (ExtractOutcome.REFUSED, "Refused (unsafe archive)"),
        (ExtractOutcome.FAILED, "Failed"),
    ):
        table.add_row(label, str(stats.count(outcome)))
    console.print(table)
    if stats.files_written:
        console.print(f"[dim]{stats.files_written} file(s) written.[/dim]")

    tally = stats.engine_tally()
    if tally:
        engines = Table(title="Engines")
        engines.add_column("Engine")
        engines.add_column("Versions", justify="right")
        for engine, count in tally.items():
            engines.add_row(str(engine), str(count))
        console.print(engines)

    # Two lists, not one count, because they are two different facts (§7.3 step
    # 2). `auto` means the detector failed and is a bug to investigate; a named
    # engine with no handler is a scoping decision for a human. Collapsing them
    # into "23 versions will not convert" makes neither actionable.
    undetected = [r for r in stats.results if r.engine is SourceEngine.AUTO and r.path]
    unconvertible = [
        r for r in stats.results
        if r.path and r.engine is not SourceEngine.AUTO and r.engine not in CONVERTIBLE_ENGINES
    ]
    for result in undetected:
        console.print(
            f"[yellow]?[/yellow] {result.slug}@{result.version}: engine undetected (`auto`)"
        )
    for result in unconvertible:
        console.print(
            f"[yellow]![/yellow] {result.slug}@{result.version}: "
            f"{result.engine} is identified but has no converter"
        )
    _report_inventory(stats)

    for result in stats.results:
        if result.outcome is ExtractOutcome.NO_PACKAGE:
            console.print(f"[yellow]![/yellow] {result.slug}@{result.version}: {result.message}")
    for result in stats.failures:
        console.print(f"[red]x[/red] {result.slug}@{result.version}: {result.message}")


def _gb(size: int) -> str:
    return f"{size / 1_000_000_000:.3f} GB" if size >= 1_000_000_000 else f"{size / 1_000_000:.1f} MB"


def _report_inventory(stats) -> None:
    """The four §6.2/§6.3/§6.4 report blocks, in order.

    Every one of them names its version rather than only totalling, for the
    reason §7.3 gave for the two engine lists: a number nobody can trace back to
    a package is not something anybody can act on.
    """
    from docushift.engines.csh import CshStatus
    from docushift.extractor import AssetCategory, Destination

    measured = stats.measured
    if not measured:
        return

    sources, names = stats.csh_totals()
    console.print(f"[dim]CSH: {sources} source(s), {names} identifier(s).[/dim]")
    for result in measured:
        for source in result.inventory.csh_sources:
            if source.status in (CshStatus.UNPARSEABLE, CshStatus.UNREADABLE):
                # A located source that will not read is not the same fact as no
                # source at all, and only one of them is acceptable to find out
                # about after publishing (architecture.md §5.4.4).
                console.print(
                    f"[yellow]![/yellow] {result.slug}@{result.version}: "
                    f"{source.path.as_posix()} is {source.status}"
                )

    totals: dict[tuple[str, str], list[int]] = {}
    for result in measured:
        for _root, category, destination, files, size in result.inventory.rows():
            bucket = totals.setdefault((category, destination), [0, 0])
            bucket[0] += files
            bucket[1] += size
    if totals:
        table = Table(title="Assets")
        table.add_column("Category")
        table.add_column("Destination")
        table.add_column("Files", justify="right")
        table.add_column("Size", justify="right")
        order = {str(value): index for index, value in enumerate(AssetCategory)}
        place = {str(value): index for index, value in enumerate(Destination)}
        for (category, destination), (files, size) in sorted(
            totals.items(), key=lambda item: (place[item[0][1]], order[item[0][0]])
        ):
            table.add_row(category, destination, str(files), _gb(size))
        console.print(table)

    for result in measured:
        for segment, bucket in sorted(
            result.inventory.unclaimed.items(), key=lambda item: -item[1].files
        ):
            console.print(
                f"[yellow]?[/yellow] {result.slug}@{result.version}: {bucket.files} unclaimed "
                f"file(s) in {segment}/ ({_gb(bucket.bytes)}) -- no destination"
            )

    for result in measured:
        for directory, files in result.inventory.triage:
            # Reported, never classified: the files stay in `_doc_files` until a
            # human adds a marker. `api-exchange-gateway/` is why.
            console.print(
                f"[yellow]?[/yellow] {result.slug}@{result.version}: {directory}/ "
                f"{files} file(s), no known generator marker"
            )


@main.command()
@_scope_options
@click.option("--force", is_flag=True, help="Re-extract even if the package has not changed.")
@click.option(
    "--measure-only",
    is_flag=True,
    help="Walk trees already extracted and fill their inventory columns. No package needed.",
)
@click.option("--dry-run", is_flag=True, help="List what would be unpacked without writing.")
@click.pass_context
def extract(ctx, bu, family, product, version, batch, select_all, force, measure_only, dry_run) -> None:
    """Extract packages into the family workspace and detect their source engine.

    Extraction runs over the same selection as `download`, so an archived or
    ineligible version is never unpacked. Serial by design: two large unzips onto
    one disk contend rather than overlap.

    `--measure-only` is for a workspace whose trees outlived their packages: it
    fills `_has_csh`/`_api_files`/`_doc_files` from the tree on disk and unpacks
    nothing. The columns then describe what is there, not what is upstream.
    """
    from docushift.extractor import ExtractOutcome, PackageExtractor

    cfg: ConfigManager = ctx.obj["config"]
    manager = _catalog_manager(ctx)

    # Opposites, not variants: one insists on re-reading the package, the other
    # never opens it. Silently letting one win would make the run a guess.
    if measure_only and force:
        raise click.UsageError("--measure-only and --force are opposites; pass one.")

    pairs = _download_selection(manager, bu, family, product, version, batch, select_all)
    if not pairs:
        _no_selection("extract")

    if dry_run:
        verb = "measure" if measure_only else "extract"
        table = Table(title=f"Would {verb} ({len(pairs)})")
        for column in ("Product", "Version", "Package" if not measure_only else "Tree", "Target"):
            table.add_column(column)
        for found, ver in pairs:
            target = cfg.extract_path(found.bu, found.family, found.slug, ver.version)
            if measure_only:
                # The tree is the input here, so its absence -- not the ZIP's -- is
                # what the reader needs to see before committing to the run.
                present = target.is_dir()
                if present and ver.api_files is not None and ver.doc_files is not None:
                    state = "[dim]already measured[/dim]"
                else:
                    state = "present" if present else "[yellow]missing[/yellow]"
            else:
                source = cfg.download_path(found.bu, found.family, found.slug, ver.version)
                state = "present" if source.is_file() else "[yellow]missing[/yellow]"
            table.add_row(found.slug, ver.version, state, str(target))
        console.print(table)
        return

    findings = FindingsRun("extract", batch=batch or "", store=manager.state).start()
    extractor = PackageExtractor(cfg, manager, findings=findings)
    console.print(
        f"{'Measuring' if measure_only else 'Extracting'} {len(pairs)} version(s)..."
    )

    def on_result(result) -> None:
        # Flushed per version, so an unzip that dies on version 200 keeps the
        # findings of the first 199 (§7.1).
        findings.flush()
        if result.outcome is ExtractOutcome.EXTRACTED:
            roots = f", {result.roots} root(s)" if result.roots else ""
            console.print(
                f"  [green]v[/green] {result.slug}@{result.version} "
                f"{result.files} file(s), {result.engine}{roots}"
            )
        elif result.outcome is ExtractOutcome.MEASURED:
            inventory = result.inventory
            counted = f"{inventory.doc_files} doc file(s)" if inventory else "measured"
            console.print(
                f"  [green]v[/green] {result.slug}@{result.version} {counted}, {result.engine}"
            )
        elif result.outcome in (ExtractOutcome.FAILED, ExtractOutcome.REFUSED):
            console.print(f"  [red]x[/red] {result.slug}@{result.version}")

    try:
        _report_extract(extractor.extract_many(
            pairs, force=force, on_result=on_result, measure_only=measure_only,
        ))
    finally:
        findings.finish()
    _report_findings(findings)


def _report_convert(stats, findings) -> None:
    """The five-outcome summary, the two asset blocks, and the findings tally."""
    from docushift.converter import ConvertOutcome

    table = Table(title="Convert")
    table.add_column("Outcome")
    table.add_column("Versions", justify="right")
    for outcome, label in (
        (ConvertOutcome.CONVERTED, "Converted"),
        (ConvertOutcome.CURRENT, "Already current"),
        (ConvertOutcome.NO_TREE, "No extracted tree"),
        (ConvertOutcome.ENGINE_UNKNOWN, "Engine unknown"),
        (ConvertOutcome.FAILED, "Failed"),
    ):
        table.add_row(label, str(stats.count(outcome)))
    console.print(table)
    if stats.documents:
        console.print(f"[dim]{stats.documents} topic(s), {stats.assets} asset(s) written.[/dim]")
    if stats.out_files:
        # What the trees hold, not what this run wrote: the two differ on a
        # `current` version that was walked to fill blank columns.
        console.print(f"[dim]{stats.out_files} file(s) standing in the measured output tree(s).[/dim]")

    for result in stats.converted:
        counts = result.counts
        console.print(
            f"[dim]{result.slug}@{result.version}: {counts.resolved} resolved, "
            f"{counts.skin} skin, {counts.escaped} escaped, {counts.dangling} dangling, "
            f"{counts.case_mismatch} case-mismatch, {counts.orphan_files} orphan "
            f"({_gb(counts.orphan_bytes)})[/dim]"
        )
        if result.csh is not None and (result.csh.entries or result.csh.unresolved):
            rescued = f", {result.csh.rescued} rescued version-wide" if result.csh.rescued else ""
            console.print(
                f"[dim]{result.slug}@{result.version}: CSH {len(result.csh.entries)} resolved, "
                f"{len(result.csh.unresolved)} unresolved, "
                f"{len(result.csh.ambiguous)} ambiguous{rescued}[/dim]"
            )
        # Invariant 10: HTML the engine looked at and did not convert is a count
        # with a reason, never a silence. Flare's largest reasons are whole
        # directories -- 8,078 API files, an 8,004-file `ja` tree -- and a run that
        # writes 400 topics out of 9,000 files needs to say where the rest went.
        if result.skipped:
            reasons = ", ".join(
                f"{count} {reason}" for reason, count in sorted(result.skipped.items())
            )
            console.print(f"[dim]{result.slug}@{result.version}: skipped {reasons}[/dim]")

    # Named individually rather than counted, the same rule `download` and
    # `extract` follow: "23 versions will not convert" is not something a human
    # can act on, and these are exactly the rows somebody has to look at.
    for result in stats.results:
        if result.outcome in (ConvertOutcome.ENGINE_UNKNOWN, ConvertOutcome.NO_TREE):
            console.print(f"[yellow]![/yellow] {result.slug}@{result.version}: {result.message}")
    for result in stats.failures:
        console.print(f"[red]x[/red] {result.slug}@{result.version}: {result.message}")

    summary = findings.summary()
    if summary:
        console.print(f"[dim]Findings: {summary}.[/dim]")


@main.command()
@_scope_options
@click.option("--force", is_flag=True, help="Re-convert even if the extracted tree has not changed.")
@click.option("--dry-run", is_flag=True, help="List what would be converted without writing.")
@click.option("--input", "input_dir", type=DIR_PATH, default=None, help="Convert a standalone extracted folder.")
@click.option("--output", "output_dir", type=DIR_PATH, default=None, help="Destination for the converted GFM.")
@click.pass_context
def convert(ctx, bu, family, product, version, batch, select_all, force, dry_run, input_dir, output_dir) -> None:
    """Convert extracted HTML to AEM-ready GFM in output/.

    Runs over the same selection as `download` and `extract`, narrowed to what has
    actually been extracted: a version with no tree is a report line, not an abort.
    A version whose engine has no registered converter is skipped and named --
    never guessed at.
    """
    from docushift.converter import ConvertOutcome, DocumentConverter

    cfg: ConfigManager = ctx.obj["config"]
    manager = _catalog_manager(ctx)

    if (input_dir is None) != (output_dir is None):
        raise click.ClickException("--input and --output are used together, or not at all.")
    if input_dir is not None and not (product and version):
        raise click.ClickException("--input needs --product and --version to name the catalog row.")

    pairs = _download_selection(manager, bu, family, product, version, batch, select_all)
    if not pairs:
        _no_selection("convert")

    if dry_run:
        table = Table(title=f"Would convert ({len(pairs)})")
        for column in ("Product", "Version", "Engine", "Tree", "Target"):
            table.add_column(column)
        for found, ver in pairs:
            tree = input_dir or cfg.extract_path(found.bu, found.family, found.slug, ver.version)
            target = output_dir or cfg.output_path(found.bu, found.family, found.slug, ver.version)
            table.add_row(
                found.slug,
                ver.version,
                str(ver.engine),
                "present" if tree.is_dir() else "[yellow]missing[/yellow]",
                str(target),
            )
        console.print(table)
        return

    findings = FindingsRun("convert", batch=batch or "", store=manager.state).start()
    converter = DocumentConverter(cfg, manager, findings=findings)
    console.print(f"Converting {len(pairs)} version(s)...")

    def on_result(result) -> None:
        if result.outcome is ConvertOutcome.CONVERTED:
            console.print(
                f"  [green]v[/green] {result.slug}@{result.version} "
                f"{result.documents} topic(s), {result.assets} asset(s), {result.units} unit(s), "
                f"{result.nav_nodes} nav node(s)"
                + (f", {result.generated} generated" if result.generated else "")
                + f" -> {result.out_files} file(s)"
            )
        elif result.outcome is ConvertOutcome.FAILED:
            console.print(f"  [red]x[/red] {result.slug}@{result.version}")

    if input_dir is not None:
        found, ver = pairs[0]
        stats_results = [
            converter.convert_one(found, ver, force=force, tree=input_dir, output=output_dir)
        ]
        from docushift.converter import ConvertStats

        stats = ConvertStats(results=stats_results)
        on_result(stats_results[0])
    else:
        stats = converter.convert_many(pairs, force=force, on_result=on_result)

    findings.finish()
    _report_convert(stats, findings)


def _who(result) -> str:
    """`ems@8.6.0`, or plain `ems` for a row about the product rather than a version.

    6d's `archives` folder spans every version a product ever had, so it carries no
    version string -- and `ems@` reads as a version this tool failed to name.
    """
    return f"{result.slug}@{result.version}" if result.version else result.slug


def _report_sync(stats, findings) -> None:
    """The five-outcome summary, what was written above the versions, and findings.

    Counted in **rows, not versions**, since 6c: a run reports one row per
    (version, doc-class) that had something to say, so a version with converted
    help and two folders of PDFs contributes three. The per-doc-class column is
    what makes that readable rather than merely inflated.

    6d's two columns come last and are not `DOC_CLASSES`: they are the other tree,
    and `archives` is not even per-version. They appear only for the products that
    have them -- 13 of 422 for `api-references` -- so the common run's table is the
    same width it was.
    """
    from docushift.sync import API_REFERENCES, ARCHIVES, DOC_CLASSES, SyncOutcome

    columns = (*DOC_CLASSES, API_REFERENCES, ARCHIVES)
    seen = [name for name in columns if any(r.doc_class == name for r in stats.results)]
    table = Table(title="Sync")
    table.add_column("Outcome")
    table.add_column("Rows", justify="right")
    for name in seen:
        table.add_column(name, justify="right")
    for outcome, label in (
        (SyncOutcome.SYNCED, "Synced"),
        (SyncOutcome.CURRENT, "Already current"),
        (SyncOutcome.NO_OUTPUT, "No source tree"),
        (SyncOutcome.SKIPPED, "Skipped"),
        (SyncOutcome.FAILED, "Failed"),
    ):
        rows = [r for r in stats.results if r.outcome is outcome]
        table.add_row(
            label,
            str(len(rows)),
            *[str(sum(1 for r in rows if r.doc_class == name)) for name in seen],
        )
    console.print(table)
    if stats.files:
        console.print(f"[dim]{stats.files} file(s), {_gb(stats.bytes)} copied.[/dim]")
    console.print(
        f"[dim]{stats.products} product metadata.yml, {stats.dropdowns} version.yml written.[/dim]"
    )

    # Named individually rather than counted, the rule `convert` follows: these are
    # exactly the rows somebody has to look at.
    for path in stats.unparsed:
        console.print(f"[yellow]![/yellow] {path}: could not be parsed, left unchanged")
    for result in stats.results:
        if result.outcome in (SyncOutcome.NO_OUTPUT, SyncOutcome.SKIPPED):
            console.print(f"[yellow]![/yellow] {_who(result)}: {result.message}")
    for result in stats.failures:
        console.print(f"[red]x[/red] {_who(result)}: {result.message}")

    summary = findings.summary()
    if summary:
        console.print(f"[dim]Findings: {summary}.[/dim]")


@main.command()
@_scope_options
@click.option("--target-dir", type=DIR_PATH, required=True, help="Target GitHub workspace directory.")
@click.option("--force", is_flag=True, help="Re-copy even where the published tree already matches.")
@click.option("--dry-run", is_flag=True, help="Show what would be copied without writing.")
@click.pass_context
def sync(ctx, bu, family, product, version, batch, select_all, target_dir, force, dry_run) -> None:
    """Distribute converted output and shipped documents into a target workspace.

    Runs over the same selection as `convert`: a version with no output tree is a
    report line, not an abort. Places all four doc-classes -- `online-help` from
    the converted tree, and `user-guides`, `release-information` and
    `reference-documents` from the *extracted* one, so a version that never
    converted still publishes the PDFs it shipped.

    Writes a second tree where the family has one: `api-references/` (copied
    verbatim from the extracted package) and `archives/` (built from the catalog's
    archived rows) go to the `-resources` sibling. English only -- the localized
    tree carries every language and an API reference has none.

    Filesystem only. This writes the trees and reports what it wrote; it creates no
    repository and runs no git command (`architecture.md` §6.0).
    """
    from docushift.sync import ONLINE_HELP, WorkspaceDistributor

    cfg: ConfigManager = ctx.obj["config"]
    manager = _catalog_manager(ctx)

    pairs = _download_selection(manager, bu, family, product, version, batch, select_all)
    if not pairs:
        _no_selection("sync")

    distributor = WorkspaceDistributor(cfg, manager)

    if dry_run:
        from docushift.sync import apirefs, router
        from docushift.sync import archives as archive_index
        from docushift.sync import documents as document_index

        resources = cfg.publishes_resources()
        table = Table(title=f"Would sync ({len(pairs)})")
        for column in ("Product", "Version", "Converted", "Documents", "API refs", "Destination"):
            table.add_column(column)
        for found, ver in pairs:
            source = cfg.output_path(found.bu, found.family, found.slug, ver.version)
            tree = cfg.extract_path(found.bu, found.family, found.slug, ver.version)
            segment = version_segment(ver.version)
            destination = distributor.doc_class_dir(found, target_dir, ONLINE_HELP) / segment
            grouped = (
                document_index.group(router.route_version(tree, ver.engine))
                if tree.is_dir() else {}
            )
            roots = (
                apirefs.select(tree, distributor.api_roots(found.slug, ver.version, tree))
                if resources and tree.is_dir() else []
            )
            table.add_row(
                found.slug,
                ver.version,
                "present" if source.is_dir() else "[yellow]missing[/yellow]",
                ", ".join(f"{name} {len(files)}" for name, files in grouped.items()) or "[dim]-[/dim]",
                ", ".join(root.name for root in roots) or "[dim]-[/dim]",
                str(destination),
            )
        console.print(table)

        # Per product, not per version: the folder has no version segment, and one
        # line per selected version would repeat one product's history N times.
        if resources:
            for found in {p.slug: p for p, _ in pairs}.values():
                entries = archive_index.entries_for(
                    found, cfg.archive_dir(found.bu, found.family)
                )
                if entries:
                    console.print(
                        f"[dim]{found.slug}: {len(entries)} archived version(s) -> "
                        f"{distributor.resources_dir(found, target_dir) / archive_index.ARCHIVES}"
                        f"[/dim]"
                    )
        return

    findings = FindingsRun("sync", batch=batch or "", store=manager.state).start()
    distributor.findings = findings
    console.print(f"Syncing {len(pairs)} version(s) into {target_dir}...")

    from docushift.sync import SyncOutcome

    def on_result(result) -> None:
        if result.outcome is SyncOutcome.SYNCED:
            where = f"{result.doc_class}/{result.segment}" if result.segment else result.doc_class
            console.print(
                f"  [green]v[/green] {_who(result)} -> {where} "
                f"{result.files} file(s), {_gb(result.bytes)}"
            )
        elif result.outcome is SyncOutcome.FAILED:
            console.print(f"  [red]x[/red] {_who(result)} ({result.doc_class})")

    stats = distributor.sync_many(pairs, target_dir, force=force, on_result=on_result)
    findings.finish()
    _report_sync(stats, findings)


@main.command()
@click.option("--target-dir", type=DIR_PATH, required=True, help="Synced workspace to validate.")
@click.option("--product", "product", default=None, help="Restrict to one published product slug.")
@click.option("--version", default=None, help="Restrict to one version (10.4.0 or 10-4-0).")
@click.option("--doc-class", "doc_class", default=None, help="Restrict to one doc-class folder.")
@click.option(
    "--check-external",
    is_flag=True,
    help="Also request every absolute URL once. Off by default; no network without it.",
)
@click.option("--dry-run", is_flag=True, help="List what would be walked, reading no file.")
@click.pass_context
def validate(ctx, target_dir, product, version, doc_class, check_external, dry_run) -> None:
    """Check a published workspace for broken links, bad anchors and AEM artifacts.

    Reads the target directory and nothing else. The selectors filter *directory
    names*, not catalog rows, so a tree another machine synced validates with no
    `versions.csv` agreement required -- which is the point, because a published
    tree outlives the row that produced it.

    The only command in the tool that gates: it exits 1 if and only if it recorded
    at least one error. Warnings and notes do not change the exit code, and a
    selection that matched no published folder exits 1 like every other stage.

    Writes nothing into the target. There is no `--fix`: the published tree is
    regenerated by `sync`, and a repair applied here would be reverted by the next
    run.
    """
    from docushift.validation import Validator

    # The `StateStore` directly, and no `CatalogManager`: §7.1 says this command
    # reads the target and the database records the run. Constructing a catalog
    # here would make a target whose products left `versions.csv` unvalidatable,
    # which is the one tree somebody most wants checked.
    cfg: ConfigManager = ctx.obj["config"]
    validator = Validator(target_dir)
    selection = validator.selection(product, version, doc_class)
    folders = [folder for entry in selection for folder in entry.versions]
    if not folders:
        console.print(
            f"[yellow]No published version folders match this selection in {target_dir}.[/yellow] "
            f"`docushift status --target-dir {target_dir}` shows what is on the shelf."
        )
        raise click.exceptions.Exit(1)

    if dry_run:
        table = Table(title=f"Would validate ({len(folders)})")
        for column in ("Tree", "Product", "Doc-class", "Version"):
            table.add_column(column)
        for folder in folders:
            table.add_row(folder.tree, folder.slug, folder.doc_class, folder.segment or "[dim]-[/dim]")
        console.print(table)
        residue = sum(len(entry.residue) for entry in selection)
        if residue:
            console.print(f"[dim]{residue} .part folder(s) would be skipped as sync residue.[/dim]")
        return

    findings = FindingsRun("validate", store=StateStore(cfg.state_db_path)).start()
    validator.findings = findings
    console.print(f"Validating {len(folders)} published folder(s) in {target_dir}...")

    def on_folder(result) -> None:
        if not result.findings:
            return
        marker = "[red]x[/red]" if result.errors else "[yellow]![/yellow]"
        console.print(
            f"  {marker} {result.folder.relative.as_posix()} "
            f"{len(result.findings)} finding(s), {result.errors} error(s)"
        )

    stats = validator.run(
        product, version, doc_class,
        on_folder=on_folder,
        fetch=_external_fetcher(cfg) if check_external else None,
        selection=selection,
    )
    errors = findings.counts()[Severity.ERROR]
    findings.finish(exit_code=1 if errors else 0)
    _report_validate(stats, findings, check_external)
    if errors:
        raise click.exceptions.Exit(1)


def _external_fetcher(cfg: ConfigManager):
    """`--check-external`'s request policy: HEAD, then GET, then it is dead.

    The docsite's own policy, through `utils/http.py` -- the same retry rules, the
    same `User-Agent`, the same politeness floor the crawler and the downloader
    share. A third copy of the retry configuration is how two of them end up
    disagreeing about what a 429 means.

    Built only when the flag is set, which is what makes "no network without it" a
    property of the code rather than a promise: with the flag off there is no
    session to make a call with.

    HEAD first and GET after, because a meaningful share of documentation hosts
    answer 405 to HEAD, and a linter that called those dead would be reporting on
    the server's taste rather than on the link.
    """
    from docushift.utils.http import Throttle, build_session

    crawl = dict(cfg.load_docsite().get("crawl") or {})
    timeout = float(crawl.get("timeout_seconds", 30))
    throttle = Throttle.from_crawl(crawl)
    session = build_session(crawl, accept="*/*")

    def fetch(url: str) -> bool:
        throttle.wait()
        try:
            response = session.head(url, timeout=timeout, allow_redirects=True)
            if response.status_code == 405 or response.status_code >= 500:
                throttle.wait()
                response = session.get(url, timeout=timeout, allow_redirects=True, stream=True)
                response.close()
            return response.status_code < 400
        except requests.RequestException:
            return False

    return fetch


def _report_validate(stats, findings: FindingsRun, checked_external: bool) -> None:
    """The run's counts, then its findings, grouped the way `report` groups them."""
    table = Table(title="Validate")
    for column, justify in (
        ("Walked", "right"), ("Files", "right"), ("References", "right"),
        ("HTML", "right"), ("External", "right"), ("Tree-rooted", "right"),
        ("Anchors", "right"),
    ):
        table.add_column(column, justify=justify)
    table.add_row(
        f"{stats.folders} folder(s)",
        str(stats.files),
        str(stats.references),
        str(stats.html),
        str(stats.absolute),
        str(stats.tree_rooted),
        f"{stats.anchors_matched}/{stats.fragments}",
    )
    console.print(table)
    if stats.residue:
        console.print(f"[dim]{stats.residue} .part folder(s) skipped as sync residue.[/dim]")
    if stats.dropped:
        console.print(
            f"[dim]{stats.dropped} help identifier(s) dropped against a prior version; "
            f"`docushift csh report --since` lists them.[/dim]"
        )
    if checked_external:
        console.print(f"[dim]{stats.external_checked} distinct external URL(s) requested.[/dim]")

    from docushift.reporting import report as views

    rows = [
        {"stage": str(f.stage), "severity": str(f.severity), "code": f.code,
         "slug": f.slug, "version": f.version, "path": f.path,
         "message": f.message, "count": f.count}
        for f in findings.all
    ]
    for stage_group in views.group(rows):
        for code_group in stage_group.codes:
            colour = {"error": "red", "warning": "yellow"}.get(code_group.severity, "dim")
            console.print(
                f"[{colour}]{code_group.code}[/{colour}] "
                f"{len(code_group.rows)} row(s), {code_group.occurrences} occurrence(s)"
            )
            # Errors are named individually -- they are exactly the rows somebody
            # has to look at, and the gate is about them. Warnings and notes are
            # counted here and read back with `report --run last`.
            if code_group.severity != str(Severity.ERROR):
                continue
            for row in code_group.rows:
                console.print(f"  [red]x[/red] {row['path']}: {row['message']}")

    summary = findings.summary()
    console.print(f"[dim]Findings: {summary or 'none'}.[/dim]")


# ---------------------------------------------------------------------------
# Context-sensitive help, as the shelf has it (Phase 7c)
# ---------------------------------------------------------------------------


@main.group("csh")
def csh_group() -> None:
    """Context-sensitive help on a published tree: what is mapped, and what moved.

    Takes `--target-dir` like `validate`, and reads the catalog nowhere. That is a
    deliberate override of the original plan's "coverage across a batch": a batch
    is a `versions.csv` column, and `docushift report --run last --code
    CSH_UNRESOLVED` already answers "did CSH come through for the batch I just
    converted" from the run's own findings. What had no reader is the shelf --
    which identifiers are published, where they point, and what changed since the
    version before.
    """


def _published(target_dir: Path, product, version, doc_class, command: str):
    """The walk every `csh` subcommand starts with. Exits 1 on an empty selection.

    **The `-resources` sibling is skipped.** `transforms/csh.py` writes `csh.yml`
    into the version's Markdown output root, which `sync` places in the docs tree
    and nowhere else; the resources tree holds copied API-reference trees and the
    archive index, neither of which has a help map or ever will. Walking it would
    double the row count of `csh report` to print zeroes, and would build a
    `FolderIndex` over a Javadoc frame set to look for frontmatter that is not
    there.
    """
    from docushift.validation.tree import walk

    selection = [
        entry for entry in walk(target_dir, product, version, doc_class)
        if not entry.is_resources
    ]
    if not any(entry.versions for entry in selection):
        console.print(
            f"[yellow]No published version folders match this selection in "
            f"{target_dir}'s docs tree(s).[/yellow] `{command}` reads the docs tree "
            f"only -- a help map is never published into `-resources`. "
            f"`docushift status --target-dir {target_dir}` shows what is on the shelf."
        )
        raise click.exceptions.Exit(1)
    return selection


def _target_options(func):
    """The three selectors `validate` takes, shared by all three subcommands."""
    func = click.option("--doc-class", "doc_class", default=None,
                        help="Restrict to one doc-class folder.")(func)
    func = click.option("--version", default=None,
                        help="Restrict to one version (10.4.0 or 10-4-0).")(func)
    func = click.option("--product", "product", default=None,
                        help="Restrict to one published product slug.")(func)
    func = click.option("--target-dir", type=DIR_PATH, required=True,
                        help="Synced workspace to read.")(func)
    return func


@csh_group.command("list")
@_target_options
@click.option(
    "--identifier",
    default=None,
    help="Look one identifier up across every published version in the selection.",
)
def csh_list(target_dir: Path, product, version, doc_class, identifier) -> None:
    """Every help identifier in the selection, with its target and whether it is there.

    `--identifier` is the query worth building the command for. A support engineer
    arrives with "the Help button for `Gateway.BusinessAgreements` is broken in
    6.11.0" and wants to know where it went; this answers that across the whole
    shelf in one call. Without it the command is `cat csh.yml` with extra steps.

    The lookup is byte-exact, because `GatewayInstances` and `gatewayInstances` are
    two different live help targets in the corpus (`design.md` §9.1). A case-only
    near-miss is reported as such rather than matched.
    """
    from docushift.validation import csh as check

    selection = _published(target_dir, product, version, doc_class, "csh list")
    maps = [
        check.load(folder)
        for entry in selection for folder in entry.versions if folder.segment
    ]
    if identifier is not None:
        _csh_lookup(maps, identifier)
        return

    total = sum(len(found.entries) for found in maps)
    carrying = [found for found in maps if found.entries]
    if total > _CSH_LIST_LIMIT:
        console.print(
            f"[yellow]{total} identifiers across {len(carrying)} version folder(s) "
            f"-- too many to read.[/yellow] Narrow with --product/--version, or use "
            f"--identifier to look one up."
        )
        for found in carrying:
            console.print(
                f"  {found.folder.relative.as_posix()}  "
                f"[bold]{len(found.entries)}[/bold] identifier(s)"
            )
        return

    if not carrying:
        console.print(
            f"[dim]No `csh.yml` in {len(maps)} version folder(s). "
            f"A version whose package shipped no help map gets no file (§9.4).[/dim]"
        )
        return
    for found in carrying:
        table = Table(title=found.folder.relative.as_posix())
        table.add_column("Identifier")
        table.add_column("Target")
        table.add_column("On disk", justify="center")
        for key in sorted(found.entries):
            target = found.entries[key]
            there = (found.folder.path / target.partition("#")[0]).is_file()
            table.add_row(key, target, "[green]yes[/green]" if there else "[red]no[/red]")
        console.print(table)


# Above this, a listing stops being something a person reads and the command says
# so instead of filling the scrollback. The corpus's largest single map is 223
# identifiers, so a whole product's versions fit and a whole tree does not.
_CSH_LIST_LIMIT = 400


def _csh_lookup(maps, identifier: str) -> None:
    """`--identifier`: every version that carries it, and every one that nearly does."""
    hits = [(found, found.entries[identifier]) for found in maps if identifier in found.entries]
    folded = identifier.lower()
    near = [
        (found, key) for found in maps for key in found.entries
        if key != identifier and key.lower() == folded
    ]
    if not hits and not near:
        console.print(
            f"[yellow]{identifier} is in no published `csh.yml` in this selection.[/yellow]"
        )
        return
    if hits:
        table = Table(title=identifier)
        table.add_column("Product")
        table.add_column("Version")
        table.add_column("Target")
        table.add_column("On disk", justify="center")
        for found, target in hits:
            there = (found.folder.path / target.partition("#")[0]).is_file()
            table.add_row(
                found.folder.slug, found.folder.segment or "-", target,
                "[green]yes[/green]" if there else "[red]no[/red]",
            )
        console.print(table)
    # Named rather than matched: two identifiers differing only in case are two
    # help targets, and silently folding them is how one Help button answers for
    # the other.
    for found, key in near:
        console.print(
            f"[dim]{found.folder.slug}@{found.folder.segment or '-'} carries "
            f"[bold]{key}[/bold], which differs only in case.[/dim]"
        )
    versions = {found.folder.segment for found, _ in hits}
    missing = [
        found.folder for found in maps
        if found.entries and found.folder.segment not in versions
    ]
    for folder in missing:
        console.print(
            f"[yellow]![/yellow] {folder.slug}@{folder.segment} has a help map "
            f"and does not carry {identifier}."
        )


@csh_group.command("report")
@_target_options
@click.option(
    "--since",
    default=None,
    help="Print the full diff of one product's map against this version, identifier by identifier.",
)
def csh_report(target_dir: Path, product, version, doc_class, since) -> None:
    """Coverage across the shelf, and what changed between versions.

    One row per product: how many versions are published, how many carry a map,
    how many distinct identifiers and target pages there are, and how many
    identifiers were lost against the version below.

    `--since` prints the §7.6 comparison **in full** -- dropped, added and
    retargeted, every identifier named. That is the half the finding cannot carry:
    `CSH_IDENTIFIER_DROPPED` is one row per version with the magnitude in its
    count, because 784 per-identifier rows over the corpus would be 376 from two
    products re-keying their help. The register carries the magnitude; this
    carries the detail.
    """
    from docushift.validation import csh as check

    selection = _published(target_dir, product, version, doc_class, "csh report")
    coverages = [check.coverage(entry) for entry in selection if entry.versions]

    if since is not None:
        _csh_since(coverages, since)
        return

    table = Table(title=f"CSH coverage in {target_dir}")
    for column, justify in (
        ("Product", "left"), ("Published", "right"), ("Mapped", "right"),
        ("Identifiers", "right"), ("Pages", "right"), ("Compared", "right"),
        ("Dropped", "right"),
    ):
        table.add_column(column, justify=justify)
    for entry in coverages:
        dropped = f"[yellow]{entry.dropped}[/yellow]" if entry.dropped else "0"
        table.add_row(
            entry.slug, str(entry.published), str(entry.mapped), str(entry.identifiers),
            str(entry.pages), str(entry.comparable), dropped,
        )
    console.print(table)
    mapped = sum(entry.mapped for entry in coverages)
    published = sum(entry.published for entry in coverages)
    console.print(
        f"[dim]{mapped} of {published} published version folder(s) carry a help map; "
        f"{sum(e.comparable for e in coverages)} comparable pair(s), "
        f"{sum(e.dropped for e in coverages)} identifier(s) dropped.[/dim]"
    )


def _csh_since(coverages, since: str) -> None:
    """The full diff against one named version. Narrow on purpose."""
    from docushift.utils.slug import version_segment

    wanted = version_segment(since) or since
    shown = 0
    for entry in coverages:
        for change in entry.diffs:
            if change.prior.folder.segment != wanted:
                continue
            shown += 1
            before, after = change.prior.folder, change.current.folder
            console.print(
                f"[bold]{entry.slug}[/bold] {before.segment} -> {after.segment}"
                f"  [dim]({len(change.prior.entries)} -> {len(change.current.entries)} "
                f"identifiers)[/dim]"
            )
            for label, colour, keys in (
                ("dropped", "red", change.dropped),
                ("added", "green", change.added),
                ("retargeted", "yellow", change.retargeted),
            ):
                if not keys:
                    continue
                console.print(f"  [{colour}]{len(keys)} {label}[/{colour}]")
                for key in keys:
                    if label == "retargeted":
                        console.print(
                            f"    {key}: {change.prior.entries[key]} -> "
                            f"{change.current.entries[key]}"
                        )
                    elif label == "dropped":
                        console.print(f"    {key} [dim](was {change.prior.entries[key]})[/dim]")
                    else:
                        console.print(f"    {key} -> {change.current.entries[key]}")
            if change.wholesale:
                console.print(
                    "  [dim]More than 90% of the map went. That is usually a product "
                    "re-keying its help rather than losing it -- 15 of the corpus's 51 "
                    "dropping pairs look like this.[/dim]"
                )
    if not shown:
        console.print(
            f"[yellow]No published version in this selection has {wanted} directly "
            f"below it with a help map.[/yellow] `docushift csh report --target-dir …` "
            f"shows which products have a comparable pair."
        )


@csh_group.command("validate")
@_target_options
@click.pass_context
def csh_validate(ctx: click.Context, target_dir: Path, product, version, doc_class) -> None:
    """The CSH checks alone: `csh.yml`, the frontmatter mirror, and §7.6's regression.

    Runs exactly the functions `docushift validate` runs -- `validation/csh.py` is
    the only thing in the tool that reads a help map or compares two -- so the two
    commands cannot give different answers. What it does differently is skip the
    link, anchor, asset and artifact passes, which is its whole independent value
    and the phase claims no more for it.

    Gates by §7.4's one rule: exit 1 if and only if it recorded an error. On CSH
    that means a `csh.yml` value naming a file that is not there, or a map that
    would not parse. A dropped identifier is a warning and never fails a run --
    16% of the corpus's version upgrades drop at least one.
    """
    from docushift.validation import csh as check
    from docushift.validation.links import FolderIndex

    cfg: ConfigManager = ctx.obj["config"]
    selection = _published(target_dir, product, version, doc_class, "csh validate")
    findings = FindingsRun("csh validate", store=StateStore(cfg.state_db_path)).start()

    folders = 0
    mapped = 0
    for entry in selection:
        rows = list(check.check_regression(entry))
        for folder in entry.versions:
            folders += 1
            found = check.load(folder)
            mapped += int(bool(found.entries))
            rows.extend(check.check_map(found, FolderIndex(folder.path)))
        for finding in rows:
            findings.record(
                finding.code, finding.slug, finding.version, finding.path,
                finding.message, finding.count,
            )
        findings.flush()

    errors = findings.counts()[Severity.ERROR]
    findings.finish(exit_code=1 if errors else 0)
    console.print(
        f"Read {mapped} help map(s) in {folders} published folder(s) in {target_dir}."
    )
    for finding in findings.all:
        colour = {Severity.ERROR: "red", Severity.WARNING: "yellow"}.get(finding.severity, "dim")
        count = f" [dim]x{finding.count}[/dim]" if finding.count > 1 else ""
        console.print(f"[{colour}]{finding.code}[/{colour}] {finding.path}: {finding.message}{count}")
    console.print(f"[dim]Findings: {findings.summary() or 'none'}.[/dim]")
    if errors:
        raise click.exceptions.Exit(1)


@main.command()
@click.option("--bu", default=None, help="Restrict to a business unit (tibco | ibi).")
@click.option("--family", default=None, help="Restrict to a product family.")
@click.option(
    "--target-dir",
    type=DIR_PATH,
    default=None,
    help="Published workspace to count against. Without it there is no published row.",
)
@click.option("--engines", "by_engine", is_flag=True, help="Report engine resolution and what is still `auto`.")
@click.pass_context
def status(
    ctx: click.Context, bu: str | None, family: str | None, target_dir: Path | None, by_engine: bool
) -> None:
    """Where every version is in the pipeline, read from the catalog and state.db.

    Reports a `Published` row only with `--target-dir`, and counts it from the
    disk. Sync currency is compared against the target and never recorded
    (`architecture.md` §7.2), so the database cannot answer that question and this
    command does not pretend it can.

    Says nothing about findings -- that is `docushift report`. The two commands
    read different sources on purpose, so they cannot give two answers to one
    question.
    """
    from docushift.reporting import status as status_report

    cfg: ConfigManager = ctx.obj["config"]
    manager = _catalog_manager(ctx)

    published = None
    if target_dir is not None:
        published = status_report.published_counts(cfg, manager, target_dir, bu=bu, family=family)

    funnel = status_report.funnel(manager, bu=bu, family=family, published=published)
    if not funnel.catalogued:
        console.print("[yellow]No catalogued versions match. Run `docushift catalog fetch`.[/yellow]")
        return

    scope = ", ".join(filter(None, [f"bu={bu}" if bu else "", f"family={family}" if family else ""]))
    table = Table(title="Status" + (f" ({scope})" if scope else ""))
    table.add_column("Step")
    table.add_column("Versions", justify="right")
    table.add_column("of eligible", justify="right")
    table.add_column("Source", style="dim")
    # The share is measured against the eligible population, so the four gate rows
    # above it have no share to show -- they are what produce the denominator.
    gates = ("Catalogued", "In scope", "Not retired", "Convert eligible")
    for label, count, source in funnel.rows():
        share = f"{count / funnel.eligible:.0%}" if funnel.eligible and label not in gates else ""
        table.add_row(label, str(count), share, source)
    console.print(table)

    if funnel.converted > funnel.extracted:
        # Not a broken funnel: `convert --input` runs a tree this tool never
        # downloaded, so the output rows are real and the two steps above them are
        # genuinely empty. Said plainly, because a step that exceeds the one before
        # it reads as a bug.
        console.print(
            f"[dim]{funnel.converted - funnel.extracted} version(s) were converted from a tree this "
            f"workspace did not extract -- `convert --input`.[/dim]"
        )
    if funnel.errors:
        console.print(
            f"[yellow]{funnel.errors} version(s) carry a recorded error -- "
            f"`docushift report --run last` for what it was.[/yellow]"
        )
    if published is not None and not published:
        console.print(f"[dim]Nothing published under {target_dir} yet.[/dim]")

    if by_engine:
        engines = status_report.engines(manager, bu=bu, family=family)
        engine_table = Table(title="Engines (convert-eligible versions)")
        engine_table.add_column("Engine")
        engine_table.add_column("Versions", justify="right")
        for name, count in engines.rows():
            engine_table.add_row(name, str(count))
        console.print(engine_table)
        # Two lists, not one: `auto` is a detector that has not run, and a named
        # engine with no handler is a scoping call. See design.md invariant 7.
        if engines.undetermined:
            console.print(
                f"[yellow]{len(engines.undetermined)} version(s) still `auto` -- "
                f"run `docushift extract` to detect:[/yellow] "
                + _first(engines.undetermined)
            )
        if engines.unconvertible:
            console.print(
                f"[yellow]{len(engines.unconvertible)} version(s) name an engine with no "
                f"converter:[/yellow] " + _first(engines.unconvertible)
            )


def _first(items: list[str], limit: int = 12) -> str:
    """A long list, trimmed. The emptied-product list in §3.11 is the exception."""
    return ", ".join(items[:limit]) + (f" ... (+{len(items) - limit})" if len(items) > limit else "")


def _minute(stamp: str | None) -> str:
    """`2026-09-15T11:04:09+00:00` -> `2026-09-15 11:04`, so seven columns fit.

    The full stamp stays in the table and in the Markdown export; a run list is
    scanned, and a truncated ISO string with an ellipsis through it is worse than
    no seconds at all.
    """
    if not stamp:
        return ""
    return stamp.replace("T", " ")[:16]


def _resolve_run(store: StateStore, which: str) -> dict:
    """`last`, or a run id. A run that is not there is an error, never an empty report."""
    if which == "last":
        run = store.last_run()
        if run is None:
            raise click.ClickException(
                "No run has been recorded yet. Run a stage command -- `docushift convert`, "
                "`docushift extract` -- and its findings will be here."
            )
        return run
    try:
        run_id = int(which)
    except ValueError:
        raise click.ClickException(f"--run takes `last` or a run id, not '{which}'.") from None
    run = store.get_run(run_id)
    if run is None:
        raise click.ClickException(f"No run {run_id} in state.db. `docushift report --runs` lists them.")
    return run


@main.command()
@click.option("--run", "which_run", default="last", help="Which run to report on: `last` or a run id.")
@click.option("--runs", "list_runs", is_flag=True, help="List recent runs and their finding counts.")
@click.option("--stage", default=None, help="Only findings discovered by this stage.")
@click.option(
    "--severity",
    type=click.Choice([str(s) for s in Severity]),
    default=None,
    help="Only findings at this severity.",
)
@click.option("--code", default=None, help="Only this finding code, e.g. TOPIC_LINK_DANGLING.")
@click.option("--slug", default=None, help="Only findings about this product slug.")
@click.option("--explain", "explain_code", default=None, help="Describe one code and stop.")
@click.option(
    "--export",
    "export_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write the report as Markdown to this file.",
)
@click.option("--prune", is_flag=True, help="Drop the findings of older runs. Use with --keep.")
@click.option("--keep", type=int, default=10, show_default=True, help="Runs to keep findings for.")
@click.pass_context
def report(
    ctx: click.Context,
    which_run: str,
    list_runs: bool,
    stage: str | None,
    severity: str | None,
    code: str | None,
    slug: str | None,
    explain_code: str | None,
    export_path: Path | None,
    prune: bool,
    keep: int,
) -> None:
    """What a run found: the findings register, read back.

    Reads `runs` and `findings` and nothing else -- not the catalog. A report
    resolving a slug against `products.csv` would describe a run in terms of state
    that has changed since the run, which is what the run table exists to prevent
    (`architecture.md` §7.3).

    Never gates. A run that reported errors did its work; exit 1 here means the run
    or the export path was the problem, not what was found.
    """
    from docushift.reporting import report as report_view

    cfg: ConfigManager = ctx.obj["config"]
    store = StateStore(cfg.state_db_path)

    if explain_code is not None:
        # Answered from the register, so it needs no run and no database -- which
        # is what makes `--explain` usable on a machine that has run nothing.
        try:
            for line in report_view.explain(explain_code.strip().upper()):
                console.print(line)
        except KeyError:
            raise click.ClickException(
                f"{explain_code} is not a registered finding code. "
                f"`docushift report --explain` takes one of {len(REGISTRY)} codes; "
                f"see docs/planning.md §7.5."
            ) from None
        return

    if prune:
        runs, rows = store.prune_findings(keep)
        console.print(
            f"Pruned {rows} finding(s) from {runs} run(s); "
            f"the newest {keep} keep theirs and every `runs` row is intact."
        )
        return

    if list_runs:
        recent = store.recent_runs()
        if not recent:
            console.print("[yellow]No runs recorded yet.[/yellow]")
            return
        table = Table(title="Recent runs")
        for column in ("Run", "Command", "Batch", "Started", "Finished", "Exit", "Findings"):
            table.add_column(column, justify="right" if column in ("Run", "Exit", "Findings") else "left")
        for row in recent:
            table.add_row(
                str(row["run_id"]),
                row["command"],
                row["batch"] or "",
                _minute(row["started_at"]),
                _minute(row["finished_at"]) or "[yellow]-[/yellow]",
                "" if row["exit_code"] is None else str(row["exit_code"]),
                str(row["findings"]),
            )
        console.print(table)
        return

    run = _resolve_run(store, which_run)
    rows = store.query_findings(
        run["run_id"], stage=stage, severity=severity, code=code, slug=slug
    )
    filters = ", ".join(
        f"{name}={value}"
        for name, value in (("stage", stage), ("severity", severity), ("code", code), ("slug", slug))
        if value
    )

    console.print(f"[bold]{report_view.describe_run(run)}[/bold]")
    if filters:
        console.print(f"[dim]Filtered by {filters}.[/dim]")
    console.print(f"[dim]{report_view.summarize(rows)}.[/dim]")

    if not rows:
        console.print("[green]Nothing to report for this selection.[/green]")
    for stage_group in report_view.group(rows):
        table = Table(title=stage_group.stage)
        table.add_column("Code")
        table.add_column("Severity")
        table.add_column("Rows", justify="right")
        table.add_column("Occurrences", justify="right")
        table.add_column("Obligation", style="dim")
        for group in stage_group.codes:
            registered = group.registered
            table.add_row(
                group.code,
                group.severity,
                str(len(group.rows)),
                str(group.occurrences),
                registered.obligation if registered is not None else "[yellow]retired code[/yellow]",
            )
        console.print(table)

    # Named individually only when the selection is narrow enough to be read. A
    # convert run over the whole catalog writes tens of thousands of rows, and
    # printing them is how a report stops being read at all.
    if (code or slug) and len(rows) <= 200:
        for row in rows:
            where = f"{row['slug']}@{row['version']}" if row["version"] else row["slug"]
            count = f" x{row['count']}" if (row["count"] or 1) > 1 else ""
            console.print(f"  [dim]{where}[/dim] {row['message']}{count}")

    if export_path is not None:
        text = report_view.render_markdown(run, rows, filters=filters)
        try:
            export_path.parent.mkdir(parents=True, exist_ok=True)
            export_path.write_text(text, encoding="utf-8")
        except OSError as exc:
            raise click.ClickException(f"Could not write {export_path}: {exc}") from exc
        console.print(f"Wrote {export_path}")


# ---------------------------------------------------------------------------
# Archived versions (on-demand, outside the pipeline)
# ---------------------------------------------------------------------------


@main.group()
def archive() -> None:
    """Work with archived versions, which the conversion pipeline deliberately skips.

    Archived versions are inventoried in the catalog for a complete product history
    but default to `convert_eligible=false`, so they are never downloaded or
    extracted by `download`/`extract`. This group is the escape hatch for pulling
    one when a question about an old release actually comes up.
    """


@archive.command("list")
@click.option("--bu", default=None, help="Restrict to a business unit (tibco | ibi).")
@click.option("--family", default=None, help="Restrict to a product family.")
@click.option("--product", "product", default=None, help="Restrict to one product (slug or product_code).")
@click.pass_context
def archive_list(ctx: click.Context, bu, family, product) -> None:
    """List archived versions and their ZIP endpoints."""
    manager = _catalog_manager(ctx)
    pairs = [
        (found, ver)
        for found, ver in manager.iter_versions(
            bu=bu, family=family, slug=_resolve(manager, product) if product else None
        )
        if ver.is_archived
    ]
    if not pairs:
        console.print("[yellow]No archived versions match.[/yellow]")
        return

    table = Table(title=f"Archived versions ({len(pairs)})")
    for column in ("Product", "Family", "Version", "Released", "Eligible", "ZIP"):
        table.add_column(column)
    for found, ver in pairs:
        table.add_row(
            found.slug,
            found.family,
            ver.version,
            ver.release_date or "-",
            "[green]yes[/green]" if ver.convert_eligible else "[dim]no[/dim]",
            ver.zip_url or "[red]missing[/red]",
        )
    console.print(table)


@archive.command("download")
@click.option("--product", "product", required=True, help="Product to pull (slug or product_code).")
@click.option("--version", required=True, help="Archived version to pull.")
@click.option(
    "--from-file",
    "from_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="File a hand-obtained ZIP at the archive path instead of fetching it.",
)
@click.option("--extract", "do_extract", is_flag=True, help="Also unpack it, within archive/.")
@click.option("--force", is_flag=True, help="Re-download even if the archived ZIP is already present.")
@click.pass_context
def archive_download(ctx, product, version, from_file, do_extract, force) -> None:
    """Pull one archived version's ZIP into families/<family>/archive/.

    Outside the pipeline's working set on purpose: an archived ZIP in `downloads/`
    would look to `extract` like a package awaiting conversion. `--extract` unpacks
    within `archive/` for the same reason, never into `extracted/`.
    """
    from docushift.downloader import PackageDownloader
    from docushift.extractor import UnsafeArchiveError, safe_extract

    cfg: ConfigManager = ctx.obj["config"]
    manager = _catalog_manager(ctx)

    found, ver = _ingest_target(manager, product, version) if from_file else _archive_target(manager, product, version)
    target = cfg.archive_path(found.bu, found.family, found.slug, ver.version)
    downloader = PackageDownloader(cfg, manager)

    if from_file:
        try:
            # `pin_manual=False`: `zip_source` states where the *pipeline's* package
            # for a version comes from, and a reference ZIP pulled outside the
            # working set is not that. Pinning here would make `download` skip a
            # version whose real package was never supplied.
            result = downloader.ingest_file(found, ver, from_file, target, pin_manual=False)
        except OSError as exc:
            raise click.ClickException(str(exc)) from exc
        console.print(f"Filed {from_file} -> {result.path}")
    elif target.exists() and not force:
        console.print(f"[dim]Already present: {target}[/dim]")
    else:
        if not ver.zip_url:
            # Archived `zipPath` values are the ones most likely to be missing or
            # stale, which is exactly why the same command takes --from-file.
            raise click.ClickException(
                f"{found.slug}@{ver.version} has no zip_url. Archived endpoints go stale -- "
                f"obtain the ZIP and re-run with --from-file <zip>."
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        console.print(f"Fetching {ver.zip_url}")
        try:
            result = downloader.fetch_to(ver.zip_url, target)
        except OSError as exc:
            raise click.ClickException(str(exc)) from exc
        console.print(f"Wrote {target} [dim]({result.size / 1_048_576:.1f} MiB, sha256 {result.checksum})[/dim]")

    if do_extract:
        destination = target.parent / f"{found.slug}-{ver.version}"
        try:
            written = safe_extract(target, destination)
        except (UnsafeArchiveError, OSError) as exc:
            raise click.ClickException(str(exc)) from exc
        console.print(f"Extracted {written} file(s) -> {destination}")


def _archive_target(manager: CatalogManager, product: str, version: str):
    """Resolves a `(product, version)` that must already be in the catalog."""
    slug = _resolve(manager, product)
    found = manager.get_product(slug)
    if found is None:
        raise click.ClickException(f"No product '{product}' in the catalog.")
    ver = found.versions.get(version)
    if ver is None:
        raise click.ClickException(
            f"No version '{version}' for product '{slug}'. Run `docushift catalog show "
            f"--product {slug}` to see what is catalogued."
        )
    return found, ver


@main.command()
@click.pass_context
def doctor(ctx: click.Context) -> None:
    """Verify the installation: resolved paths and which project artifacts exist."""
    cfg: ConfigManager = ctx.obj["config"]

    table = Table(title=f"DocuShift {__version__}")
    table.add_column("Artifact")
    table.add_column("Path")
    table.add_column("Present")

    for label, path in [
        ("root", cfg.root_dir),
        ("config", cfg.config_dir),
        ("taxonomy.yaml", cfg.taxonomy_path),
        ("docsite.yaml", cfg.docsite_path),
        ("publishing.yaml", cfg.publishing_path),
        ("aem_templates", cfg.aem_templates_dir),
        ("cache", cfg.cache_dir),
        ("families", cfg.families_dir),
        ("output", cfg.output_dir),
        ("state.db", cfg.state_db_path),
    ]:
        present = "[green]yes[/green]" if path.exists() else "[yellow]no[/yellow]"
        table.add_row(label, str(path), present)

    console.print(table)

    workspaces = sorted(p.name for p in cfg.families_dir.glob("*") if p.is_dir())
    publishing = cfg.load_publishing()
    # The suffix and the resources line are shown because they are what a workspace
    # name no longer tells you: `families/en-us-tib-messaging/` is not the name of
    # anything that gets published, and a locale change silently drops a whole tree.
    primary = cfg.publishes_resources()
    stem = f"{cfg.locale}-<bu>-<family>" if primary else f"{publishing['localized_prefix']}-<bu>-<family>"
    console.print(
        f"\nlocale: [bold]{cfg.locale}[/bold]  |  publishes to: [bold]{stem}-{publishing['docs_suffix']}[/bold]"
        + ("" if primary else " [dim](localized -- no -resources tree)[/dim]")
    )
    console.print("family workspaces: " + (", ".join(workspaces) if workspaces else "[dim]none yet[/dim]"))


if __name__ == "__main__":
    main()
