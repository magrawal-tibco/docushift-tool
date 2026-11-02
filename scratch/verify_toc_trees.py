"""Print the old TOC tree (old_toc reader) beside the published toc.yml tree, top levels only.

    python scratch/verify_toc_trees.py <product-slug> <version> [depth]
"""
import sys
from pathlib import Path

sys.path.insert(0, "src")
from docushift.catalog import CatalogManager  # noqa: E402
from docushift.config import ConfigManager  # noqa: E402
from docushift.engines.roots import find_output_roots  # noqa: E402
from docushift.models import SourceEngine  # noqa: E402
from docushift.verify import driver, old_toc  # noqa: E402

slug, version = sys.argv[1], sys.argv[2]
depth = int(sys.argv[3]) if len(sys.argv) > 3 else 2
cfg = ConfigManager(root_dir=Path("."))
state = cfg.state_store()
catalog = CatalogManager(cfg.products_path, cfg.versions_path, state, config=cfg).load()
product = catalog.products[slug]
ver = product.versions[version]
extracted = cfg.extract_path(product.bu, product.family, slug, version)
outmap = state.get_output_map(slug, version)
redirects = driver._redirects(cfg.reframed_path(product.bu, product.family, slug, version))


def key_of(source):
    out = outmap[source]
    return redirects.get(out, out)


engine = ver.engine
roots = find_output_roots(extracted, engine)
print("engine", engine, "roots", [r.relative_to(extracted).as_posix() for r in roots])
reader = old_toc.READERS.get(engine)
old = reader(roots, extracted, outmap, key_of, lambda k, a: f"{k}#{a}" if a and "#" not in k else k) \
    if reader else None


def show(node, level=0):
    for child in node.children:
        print("  " * level + f"- {child.title!r} -> {child.key}")
        if level + 1 < depth:
            show(child, level + 1)


print("=== OLD", old.unchecked if old else "")
show(old.tree)
seg = driver.version_segment(version)
folder = next(Path("C:/github/tibco-docs-aem").glob(f"*/en-us/{slug}/online-help/{seg}"))
print("=== NEW", folder)
show(driver._toc_tree(folder / "toc.yml"))
