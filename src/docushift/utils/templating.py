"""One Jinja environment for every artifact DocuShift renders.

Stage 6a rendered `toc.yml`, `index.md` and `metadata.yml` from an environment
private to `converter/navigation.py`. Stage 6b renders `version.yml` and a second
`metadata.yml` from `sync/`, and a second environment configured by hand is the
kind of duplication that fails quietly: the `yaml` filter registered in one and
forgotten in the other produces valid YAML that parses into the wrong value, not
an error. So the configuration lives here and both stages ask for it.

Three settings, each of them load-bearing:

- **`StrictUndefined`** -- a template referencing a variable the caller did not
  pass raises instead of rendering an empty string. A missing `title` should be a
  traceback, not a `toc.yml` with a blank node.
- **`keep_trailing_newline`** -- YAML files end with one.
- **`autoescape=False`** -- nothing here is HTML, and escaping `&` into `&amp;`
  inside a Markdown body would corrupt it.

The `yaml` filter is `transforms.csh.quote`: an *unconditional* double-quoted
scalar, because a conditional quote is a branch and a branch can be wrong about
`6.2`, `yes` or `1234`.
"""

from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, Template

from docushift.transforms.csh import quote


@lru_cache(maxsize=8)
def environment(templates: Path) -> Environment:
    """One environment per template directory. Cached: a batch is 1,800 versions."""
    env = Environment(
        loader=FileSystemLoader(str(templates)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        autoescape=False,
    )
    env.filters["yaml"] = quote
    return env


def template(templates: Path, name: str) -> Template:
    """Loads one template from `config/aem_templates/`."""
    return environment(templates).get_template(name)
