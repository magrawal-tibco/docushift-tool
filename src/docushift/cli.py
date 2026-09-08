"""Click CLI entrypoint for DocuShift.

The command tree mirrors the pipeline in docs/architecture.md and the surface
documented in docs/user-guide.md. It is declared in full in Phase 1 so the console
script installs and ``--help`` is an accurate contract; each stage is wired up in
its own phase (see docs/planning.md). Unimplemented commands fail loudly -- a
``convert`` that exits 0 while converting nothing hides how far along the pipeline
actually is.

Functional so far: ``doctor`` (Phase 1) and the whole ``catalog`` group including
``fetch`` (Phase 3). The pipeline stages wait on Phases 4-7.
"""

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from docushift import __version__
from docushift.catalog import CatalogError, CatalogManager
from docushift.config import ConfigManager
from docushift.discovery import DocsiteClient, DocsiteCrawler
from docushift.models import SourceEngine, ZipSource
from docushift.state import StateStore

console = Console()

DIR_PATH = click.Path(file_okay=False, path_type=Path)


def _pending(command: str, phase: str) -> None:
    """Aborts with a clear message for a command that is scaffolded but not built."""
    raise click.ClickException(
        f"`docushift {command}` is not implemented yet (scheduled for {phase}). "
        f"See docs/planning.md for the roadmap."
    )


def _scope_options(func):
    """Shared --bu / --family / --product / --version / --batch / --all selection options."""
    for option in reversed(
        [
            click.option("--all", "select_all", is_flag=True, help="Apply to the whole catalog."),
            click.option("--bu", default=None, help="Restrict to a business unit (tibco | ibi)."),
            click.option("--family", default=None, help="Restrict to a product family."),
            click.option("--product", "product_code", default=None, help="Restrict to a single product."),
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
    product_code,
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
    if not any([select_all, bu, family, product_code, batch]):
        # A bare `catalog fetch` crawls the whole A-to-Z list (700+ entries). Make
        # that an explicit choice rather than the default.
        raise click.ClickException("Choose a scope: --all, or one of --bu / --family / --product / --batch.")

    cfg: ConfigManager = ctx.obj["config"]
    manager = _catalog_manager(ctx)

    # --product and --batch are resolved to crawl selectors up front so the crawler
    # can skip the per-product request entirely; --bu/--family cannot be, because
    # a product's family is not known until it has been classified.
    selectors: set[str] | None = None
    if product_code:
        selectors = _selectors(manager, [product_code])
    if batch:
        tagged = {p.product_code for p, _ in manager.iter_versions(batch=batch)}
        if not tagged:
            raise click.ClickException(f"No catalog versions are tagged with batch '{batch}'.")
        batch_selectors = _selectors(manager, tagged)
        selectors = batch_selectors if selectors is None else selectors & batch_selectors

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

    if not dry_run:
        _record_discovery_metadata(manager, result)

    table = Table(title="Merge" + (" (dry run -- nothing written)" if dry_run else ""))
    table.add_column("Change")
    table.add_column("Count", justify="right")
    for label, count in stats.as_dict().items():
        if label == "deletions_blocked":
            continue
        table.add_row(label.replace("_", " "), str(count))
    console.print(table)

    if result.unversioned or result.non_public:
        console.print(
            f"[dim]Skipped {result.unversioned} entries with no published versions "
            f"and {result.non_public} that are not publicly visible.[/dim]"
        )
    for note in manager.warnings():
        console.print(f"[yellow]WARN[/yellow] {note}")
    if result.errors:
        console.print(f"[yellow]{len(result.errors)} product(s) could not be reached and were left as-is.[/yellow]")


def _selectors(manager: CatalogManager, codes) -> set[str]:
    """Expands catalog product codes into the selectors the crawler can match.

    A product's code is rarely its docsite slug (`ems` is published as
    `tibco-enterprise-message-service`), so the slug already recorded in the
    catalog is passed alongside the code. A code with no catalog row is passed
    through on its own, which lets `--product <slug>` work before a first fetch.
    """
    out: set[str] = set()
    for code in codes:
        out.add(str(code).strip().lower())
        product = manager.get_product(code)
        if product and product.slug:
            out.add(product.slug.strip().lower())
    return out


def _record_discovery_metadata(manager: CatalogManager, result) -> None:
    """Parks docsite ids and folder paths in state.db rather than the CSVs.

    They are machine detail the download stage needs and a human editing a
    spreadsheet does not -- see docs/architecture.md §3.
    """
    if manager.state is None:
        return
    for code, fields in result.product_metadata.items():
        for key, value in fields.items():
            manager.state.set_product_metadata(code, key, value)
    for (code, version), fields in result.version_metadata.items():
        for key, value in fields.items():
            manager.state.set_version_metadata(code, version, key, value)


@catalog.command("list")
@_scope_options
@click.option("--eligible-only", is_flag=True, help="Only versions with convert_eligible=true.")
@click.pass_context
def catalog_list(ctx: click.Context, bu, family, product_code, version, batch, select_all, eligible_only) -> None:
    """List catalog products and versions."""
    pairs = _catalog_manager(ctx).iter_versions(
        bu=bu,
        family=family,
        product_code=product_code,
        version=version,
        batch=batch,
        eligible_only=eligible_only,
    )
    if not pairs:
        console.print("[yellow]No matching catalog rows.[/yellow] Run `docushift catalog fetch` to populate.")
        return

    table = Table(title=f"Catalog ({len(pairs)} versions)")
    for column in ("Product", "BU", "Family", "Version", "Archived", "Eligible", "Batch", "Engine"):
        table.add_column(column)
    for product, ver in pairs:
        table.add_row(
            product.product_code,
            product.bu,
            product.family,
            ver.version,
            "yes" if ver.is_archived else "",
            "[green]yes[/green]" if ver.convert_eligible else "[dim]no[/dim]",
            ver.convert_batch or "[dim]-[/dim]",
            f"{ver.engine} ({ver.engine_source})",
        )
    console.print(table)


@catalog.command("show")
@click.option("--product", "product_code", required=True, help="Product to describe.")
@click.pass_context
def catalog_show(ctx: click.Context, product_code: str) -> None:
    """Show one product and its full version history."""
    cfg: ConfigManager = ctx.obj["config"]
    manager = _catalog_manager(ctx)
    product = manager.get_product(product_code)
    if product is None:
        raise click.ClickException(f"No product '{product_code}' in the catalog.")

    console.print(
        f"[bold]{product.display_name}[/bold] ({product.product_code})\n"
        f"  bu={product.bu}  family={product.family} (source: {product.family_source})\n"
        f"  slug={product.slug or '-'}  custom_override={product.custom_override}\n"
        f"  workspace={cfg.family_dir(product.bu, product.family)}"
    )
    table = Table(title=f"{len(product.versions)} versions")
    for column in ("Version", "Archived", "Eligible", "Batch", "Released", "Engine", "ZIP"):
        table.add_column(column)
    for _, ver in manager.iter_versions(product_code=product_code):
        table.add_row(
            ver.version,
            "yes" if ver.is_archived else "",
            "yes" if ver.convert_eligible else "no",
            ver.convert_batch or "-",
            ver.release_date or "-",
            f"{ver.engine} ({ver.engine_source})",
            # A manual row usually has no URL, so name the source rather than
            # printing a bare "-" that reads as "nothing to download".
            ver.zip_url or (f"[dim]{ver.zip_source}[/dim]" if ver.zip_source is not ZipSource.AUTO else "-"),
        )
    console.print(table)


@catalog.command("enable")
@click.option("--product", "product_code", required=True, help="Product to modify.")
@click.option("--version", required=True, help="Version to modify.")
@click.option("--disable", is_flag=True, help="Set convert_eligible=false instead of true.")
@click.pass_context
def catalog_enable(ctx: click.Context, product_code: str, version: str, disable: bool) -> None:
    """Toggle convert_eligible for one product version."""
    if not _catalog_manager(ctx).set_conversion_eligibility(product_code, version, not disable):
        raise click.ClickException(f"No version '{version}' for product '{product_code}'.")
    console.print(f"{product_code}@{version}: convert_eligible = {'false' if disable else 'true'}")


@catalog.command("set")
@click.option("--product", "product_code", required=True, help="Product to modify.")
@click.option("--version", default=None, help="Target a version row instead of the product row.")
@click.option("--bu", default=None, help="Set the business unit (products.csv).")
@click.option("--family", default=None, help="Set the family; also sets family_source=manual.")
@click.option("--display-name", default=None, help="Set the product display name.")
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
    "--batch",
    "convert_batch",
    default=None,
    help="Tag the version into a run label, e.g. poc-1. Pass '' to unschedule it.",
)
@click.pass_context
def catalog_set(
    ctx: click.Context, product_code, version, bu, family, display_name, engine, zip_url, zip_source, convert_batch
) -> None:
    """Set a catalog field, recording the change as a manual edit."""
    manager = _catalog_manager(ctx)
    product_edits = {"bu": bu, "family": family, "display_name": display_name}
    version_edits = {
        "engine": engine,
        "zip_url": zip_url,
        "zip_source": zip_source,
        "convert_batch": convert_batch,
    }

    if not any(v is not None for v in {**product_edits, **version_edits}.values()):
        raise click.ClickException("Nothing to set. Pass at least one field option.")
    if any(v is not None for v in version_edits.values()) and not version:
        raise click.ClickException(
            "--engine, --zip-url, --zip-source and --batch are version fields; pass --version too."
        )

    try:
        for name, value in product_edits.items():
            if value is not None and not manager.set_product_field(product_code, name, value):
                raise click.ClickException(f"No product '{product_code}' in the catalog.")
        for name, value in version_edits.items():
            if value is not None and not manager.set_version_field(product_code, version, name, value):
                raise click.ClickException(f"No version '{version}' for product '{product_code}'.")
    except CatalogError as exc:
        raise click.ClickException(str(exc)) from exc

    console.print(f"Updated {product_code}" + (f"@{version}" if version else ""))


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


# ---------------------------------------------------------------------------
# Pipeline stages (Phases 4-7)
# ---------------------------------------------------------------------------


@main.command()
@_scope_options
@click.option("--force", is_flag=True, help="Re-download even if the cached ZIP is current.")
def download(**kwargs) -> None:
    """Download convert_eligible packages into families/<locale>-<bu>-<family>/downloads/.

    Archived versions are never downloaded here -- pull one on demand with
    `docushift archive download` instead.
    """
    _pending("download", "Phase 4")


@main.command()
@_scope_options
def extract(**kwargs) -> None:
    """Extract packages into the family workspace, catalog assets and CSH maps, and detect engines.

    Extraction runs over the same selection as `download`, so an archived or
    ineligible version is never unpacked.
    """
    _pending("extract", "Phase 4 (extraction) and Phase 5 (engine detection)")


@main.command()
@_scope_options
@click.option("--input", "input_dir", type=DIR_PATH, default=None, help="Convert a standalone extracted folder.")
@click.option("--output", "output_dir", type=DIR_PATH, default=None, help="Destination for the converted GFM.")
def convert(**kwargs) -> None:
    """Convert extracted HTML to AEM-ready GFM in output/."""
    _pending("convert", "Phase 5")


@main.command()
@_scope_options
@click.option("--target-dir", type=DIR_PATH, required=True, help="Target GitHub workspace directory.")
@click.option("--dry-run", is_flag=True, help="Show what would be copied without writing.")
def sync(**kwargs) -> None:
    """Distribute converted output into a target GitHub workspace."""
    _pending("sync", "Phase 6")


@main.command()
@click.option("--target-dir", type=DIR_PATH, required=True, help="Synced workspace to validate.")
def validate(target_dir: Path) -> None:
    """Check the synced output for broken links and missing assets."""
    _pending("validate", "Phase 7")


@main.command()
@click.option("--bu", default=None, help="Restrict to a business unit (tibco | ibi).")
@click.option("--family", default=None, help="Restrict to a product family.")
def status(bu: str | None, family: str | None) -> None:
    """Print the per-product migration status and delta dashboard."""
    _pending("status", "Phase 7 (needs the Phase 2 state engine)")


@main.command()
@click.option("--output", "output_path", type=click.Path(dir_okay=False, path_type=Path), default=None)
@click.option("--engines", "by_engine", is_flag=True, help="Report engine resolution and what is still `auto`.")
@click.option("--format", "fmt", type=click.Choice(["terminal", "markdown", "html"]), default="terminal")
def report(**kwargs) -> None:
    """Render the migration dashboard and exportable audit report."""
    _pending("report", "Phase 7")


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
@click.option("--product", "product_code", default=None, help="Restrict to a single product.")
@click.pass_context
def archive_list(ctx: click.Context, bu, family, product_code) -> None:
    """List archived versions and their ZIP endpoints."""
    pairs = [
        (product, ver)
        for product, ver in _catalog_manager(ctx).iter_versions(bu=bu, family=family, product_code=product_code)
        if ver.is_archived
    ]
    if not pairs:
        console.print("[yellow]No archived versions match.[/yellow]")
        return

    table = Table(title=f"Archived versions ({len(pairs)})")
    for column in ("Product", "Family", "Version", "Released", "Eligible", "ZIP"):
        table.add_column(column)
    for product, ver in pairs:
        table.add_row(
            product.product_code,
            product.family,
            ver.version,
            ver.release_date or "-",
            "[green]yes[/green]" if ver.convert_eligible else "[dim]no[/dim]",
            ver.zip_url or "[red]missing[/red]",
        )
    console.print(table)


@archive.command("download")
@click.option("--product", "product_code", required=True, help="Product whose archived version to pull.")
@click.option("--version", required=True, help="Archived version to pull.")
@click.option("--extract", "do_extract", is_flag=True, help="Also unpack it, which the pipeline will not do.")
@click.option("--dest", type=DIR_PATH, default=None, help="Override the destination directory.")
def archive_download(**kwargs) -> None:
    """Download one archived version's ZIP into families/<family>/archive/.

    Kept out of `downloads/` on purpose: that directory is the pipeline's working
    set, and a reference ZIP sitting in it would look to `extract` like a package
    awaiting conversion.
    """
    _pending("archive download", "Phase 4")


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
    console.print(
        f"\nlocale: [bold]{cfg.locale}[/bold]  |  family workspaces: "
        + (", ".join(workspaces) if workspaces else "[dim]none yet[/dim]")
    )


if __name__ == "__main__":
    main()
