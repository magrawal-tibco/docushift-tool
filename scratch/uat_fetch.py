"""Fetch staging pages with the verify Fetcher (rate-limited) into C:/tmp/uat-retest/<name>.html.

    python scratch/uat_fetch.py name=url [name=url ...]
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "src")
from docushift.config import ConfigManager  # noqa: E402
from docushift.verify.fetch import Fetcher  # noqa: E402

docsite = ConfigManager(root_dir=Path(".")).load_docsite()
crawl = dict(docsite.get("crawl") or {})
own = dict(docsite.get("verify") or {})
if own.get("rate_limit_per_second") is not None:
    crawl["rate_limit_per_second"] = own["rate_limit_per_second"]
fetcher = Fetcher(Path(tempfile.mkdtemp(prefix="uat-")), crawl, refresh=True, workers=1)
out = Path("C:/tmp/uat-retest")
out.mkdir(parents=True, exist_ok=True)
for arg in sys.argv[1:]:
    name, url = arg.split("=", 1)
    got = fetcher.get(url)
    (out / f"{name}.html").write_bytes(got.body)
    print(name, got.status, len(got.body), url)
