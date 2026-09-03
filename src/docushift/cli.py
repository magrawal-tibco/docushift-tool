"""Click CLI entrypoint for DocuShift.

The command tree mirrors the pipeline in docs/architecture.md and the surface
documented in docs/user-guide.md. It is declared in full in Phase 1 so the console
script installs and ``--help`` is an accurate contract; each stage is wired up in
its own phase (see docs/planning.md). Unimplemented commands fail loudly -- a
``convert`` that exits 0 while converting nothing hides how far along the pipeline
actually is.

``doctor`` is the only fully functional command in Phase 1.
"""

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from docushift import __version__
from docushift.config import ConfigManager

console = Console()

DIR_PATH = click.Path(file_okay=False, path_type=Path)


def _pending(command: str, phase: str) -> None:
    """Aborts with a clear message for a command that is scaffolded but not built."""
    raise click.ClickException(
        f"`docushift {command}` is not implemented yet (scheduled for {phase}). "
        f"See docs/planning.md for the roadmap."
    )


def _scope_options(func):
    """Shared --bu / --family / --product / --version / --all selection options."""
    for option in reversed(
        [
            click.option("--all", "select_all", is_flag=True, help="Apply to the whole catalog."),
            click.option("--bu", default=None, help="Restrict to a business unit (tibco | ibi)."),
            click.option("--family", default=None, help="Restrict to a product family."),
            click.option("--product", "product_code", default=None, help="Restrict to a single product."),
            click.option("--version", default=None, help="Restrict to a single version."),
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


@catalog.command("fetch")
@_scope_options
@click.option("--include-archived/--no-include-archived", default=True, help="Also inventory archived versions.")
@click.option("--dry-run", is_flag=True, help="Report the merge plan without writing the CSVs.")
def catalog_fetch(**kwargs) -> None:
    """Fetch from docs.tibco.com and 3-way merge into the catalog CSVs."""
    _pending("catalog fetch", "Phase 2 (merge) and Phase 3 (discovery)")


@catalog.command("list")
@_scope_options
@click.option("--eligible-only", is_flag=True, help="Only versions with convert_eligible=true.")
def catalog_list(**kwargs) -> None:
    """List catalog products and versions."""
    _pending("catalog list", "Phase 2")


@catalog.command("show")
@click.option("--product", "product_code", required=True, help="Product to describe.")
def catalog_show(product_code: str) -> None:
    """Show one product and its full version history."""
    _pending("catalog show", "Phase 2")


@catalog.command("enable")
@click.option("--product", "product_code", required=True, help="Product to modify.")
@click.option("--version", required=True, help="Version to modify.")
@click.option("--disable", is_flag=True, help="Set convert_eligible=false instead of true.")
def catalog_enable(product_code: str, version: str, disable: bool) -> None:
    """Toggle convert_eligible for one product version."""
    _pending("catalog enable", "Phase 2")


@catalog.command("set")
@click.option("--product", "product_code", required=True, help="Product to modify.")
@click.option("--version", default=None, help="Target a version row instead of the product row.")
@click.option("--bu", default=None, help="Set the business unit (products.csv).")
@click.option("--family", default=None, help="Set the family; also sets family_source=manual.")
@click.option(
    "--engine",
    type=click.Choice(["flare", "dita", "webworks", "docbook", "auto"]),
    default=None,
    help="Override the detected engine; also sets engine_source=manual (permanent).",
)
@click.option("--zip-url", default=None, help="Override the resolved download endpoint.")
def catalog_set(**kwargs) -> None:
    """Set a catalog field, recording the change as a manual edit."""
    _pending("catalog set", "Phase 2")


@catalog.command("import")
@click.option("--allow-deletes", is_flag=True, help="Permit removal of rows that discovery no longer returns.")
def catalog_import(allow_deletes: bool) -> None:
    """Re-import the CSVs, validating version keys against the last known set."""
    _pending("catalog import", "Phase 2")


@catalog.command("triage")
def catalog_triage() -> None:
    """Report family classification progress and list unclassified products."""
    _pending("catalog triage", "Phase 2")


# ---------------------------------------------------------------------------
# Pipeline stages (Phases 4-7)
# ---------------------------------------------------------------------------


@main.command()
@_scope_options
@click.option("--force", is_flag=True, help="Re-download even if the cached ZIP is current.")
def download(**kwargs) -> None:
    """Download convert_eligible packages into cache/downloads/."""
    _pending("download", "Phase 4")


@main.command()
@_scope_options
def extract(**kwargs) -> None:
    """Extract packages, catalog assets and CSH maps, and detect each version's engine."""
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
        ("downloads", cfg.cache_dir / "downloads"),
        ("extracted", cfg.cache_dir / "extracted"),
        ("output", cfg.output_dir),
        ("state.db", cfg.state_db_path),
    ]:
        present = "[green]yes[/green]" if path.exists() else "[yellow]no[/yellow]"
        table.add_row(label, str(path), present)

    console.print(table)


if __name__ == "__main__":
    main()
