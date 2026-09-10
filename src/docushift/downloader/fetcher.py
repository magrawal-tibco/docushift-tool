"""Stage 3: acquiring packages into the families workspace.

Implements `docs/design.md` §5.1 (download one version) and §5.2 (ingest a
hand-supplied one). The path is never accepted from a caller -- it is derived
from `(bu, family, slug, version)` by `ConfigManager`, which is the invariant
that lets Stage 4 find a package without being told where it is.

Concurrency is a thread pool over versions, default width from `docsite.yaml`'s
`crawl.max_concurrent_requests`. Streaming a ZIP to disk is I/O-bound, so threads
cost nothing here and the resume logic stays ordinary synchronous code. The
rate-limit floor is shared across workers rather than applied per worker, and it
paces request *starts* only (`utils.http.Throttle`).
"""

import hashlib
import shutil
import zipfile
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

import requests

from docushift.catalog import CatalogManager
from docushift.config import ConfigManager
from docushift.models import ConversionStatus, Product, ProductVersion, ZipSource
from docushift.utils.http import Throttle, build_session

# Read in 1 MiB blocks. The corpus's packages run to 900 MB, so the hash is
# computed on the way past rather than in a second pass over the file.
_CHUNK = 1024 * 1024

# `Accept` for a package request. The crawler's `application/json` would be a
# lie here, and some CDNs honour it.
_ZIP_ACCEPT = "application/octet-stream, application/zip;q=0.9, */*;q=0.8"


class Outcome(StrEnum):
    """What happened to one version. Every run reports these five counts."""

    DOWNLOADED = "downloaded"
    # Present with a checksum that still matches -- the cheap re-run path.
    CURRENT = "current"
    # Pinned `zip_source=manual`: the package is placed by hand and must not be fetched.
    SKIPPED_MANUAL = "skipped-manual"
    # Eligible, but there is nothing to fetch from.
    NO_URL = "no-url"
    FAILED = "failed"


@dataclass
class _Transfer:
    """What one completed stream produced. Internal to this module."""

    size: int
    checksum: str
    etag: str
    resumed: bool


@dataclass
class DownloadResult:
    """One version's outcome, for the report and for the tests."""

    slug: str
    version: str
    outcome: Outcome
    path: Path | None = None
    size: int = 0
    checksum: str = ""
    message: str = ""
    resumed: bool = False


@dataclass
class DownloadStats:
    """Run totals, in the order the summary table prints them."""

    results: list[DownloadResult] = field(default_factory=list)

    def count(self, outcome: Outcome) -> int:
        return sum(1 for r in self.results if r.outcome is outcome)

    @property
    def bytes_written(self) -> int:
        return sum(r.size for r in self.results if r.outcome is Outcome.DOWNLOADED)

    @property
    def failures(self) -> list[DownloadResult]:
        return [r for r in self.results if r.outcome is Outcome.FAILED]


def sha256_of(path: Path) -> str:
    """The sha256 of a file already on disk."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def _validator(response_headers: Any) -> str:
    """The server's best "is this still the same file" token.

    ETag first, `Last-Modified` as the fallback. Recorded in `state.db`'s
    `zip_etag` column either way -- what matters is that it is *comparable*, not
    which header it came from.
    """
    headers = response_headers or {}
    return str(headers.get("ETag") or headers.get("Last-Modified") or "").strip()


class PackageDownloader:
    """Fetches doc packages into `families/<family>/downloads/`.

    Construct once per run: the session and the throttle are shared by every
    worker, which is what makes the politeness floor a property of the run rather
    than of a thread.
    """

    def __init__(
        self,
        config: ConfigManager,
        catalog: CatalogManager,
        session: requests.Session | None = None,
        workers: int | None = None,
    ):
        self.config = config
        self.catalog = catalog
        crawl = dict(config.load_docsite().get("crawl") or {})
        self.timeout = float(crawl.get("timeout_seconds", 30))
        self.session = session if session is not None else build_session(crawl, accept=_ZIP_ACCEPT)
        self.throttle = Throttle.from_crawl(crawl)
        self.workers = int(workers or crawl.get("max_concurrent_requests", 4) or 4)

    # -- state ---------------------------------------------------------------

    def _record(self, slug: str, version: str, **fields: Any) -> None:
        if self.catalog.state is not None:
            self.catalog.state.set_version_state(slug, version, **fields)

    def _recorded_state(self, slug: str, version: str) -> dict[str, Any]:
        if self.catalog.state is None:
            return {}
        return self.catalog.state.get_version_state(slug, version) or {}

    # -- one version ----------------------------------------------------------

    def download_one(self, product: Product, version: ProductVersion, force: bool = False) -> DownloadResult:
        """`design.md` §5.1, in order. Never raises -- a failure is a recorded outcome.

        One unreachable product must not stop a 200-version batch, so every
        failure path returns a result rather than propagating.
        """
        slug, number = product.slug, version.version
        target = self.config.download_path(product.bu, product.family, slug, number)

        # Step 2: the manual pin wins over everything, including --force. The file
        # is expected to be at the path already; fetching would overwrite a
        # hand-obtained package with whatever the stale URL now serves.
        if version.zip_source is ZipSource.MANUAL:
            return DownloadResult(slug, number, Outcome.SKIPPED_MANUAL, path=target)

        # Step 3: present and unchanged. The only thing between a resumed run over
        # a completed batch and a full re-fetch.
        recorded = self._recorded_state(slug, number)
        if (
            not force
            and target.exists()
            and recorded.get("checksum")
            and sha256_of(target) == recorded["checksum"]
        ):
            return DownloadResult(
                slug, number, Outcome.CURRENT, path=target,
                size=target.stat().st_size, checksum=recorded["checksum"],
            )

        if not version.zip_url:
            # A report line, not an abort: discovery genuinely fails to produce a
            # usable endpoint for some products, and `--from-file` is the answer.
            message = "no zip_url; supply the package with `download --from-file`"
            self._record(slug, number, status=ConversionStatus.ERROR, error=message)
            return DownloadResult(slug, number, Outcome.NO_URL, message=message)

        try:
            return self._fetch(product, version, target, force=force)
        except Exception as exc:  # noqa: BLE001 - every failure is a report line
            message = f"{type(exc).__name__}: {exc}"
            self._record(slug, number, status=ConversionStatus.ERROR, error=message)
            return DownloadResult(slug, number, Outcome.FAILED, message=message)

    def fetch_to(self, url: str, target: Path, known_etag: str | None = None, force: bool = False):
        """Streams one URL to one path, with resume, verification and an atomic move.

        The whole of `design.md` §5.1 steps 4-7, and deliberately free of the
        catalog: `download` wraps it with per-version state, and
        `archive download` -- which pulls a reference ZIP that has no pipeline
        lifecycle -- uses it directly. Returns `(size, checksum, etag, resumed)`
        as a `_Transfer`.
        """
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_suffix(target.suffix + ".part")

        # Step 4: resume, but only against a matching validator. Resuming across a
        # changed file produces a corrupt archive that passes every length check
        # there is, so a changed validator discards the partial and restarts.
        resume_from = 0
        if not force and partial.exists() and known_etag:
            resume_from = partial.stat().st_size

        headers: dict[str, str] = {}
        if resume_from:
            headers["Range"] = f"bytes={resume_from}-"
            headers["If-Range"] = str(known_etag)

        self.throttle.wait()
        response = self.session.get(url, headers=headers, stream=True, timeout=self.timeout)
        try:
            if response.status_code not in (200, 206):
                raise OSError(f"GET {url} returned HTTP {response.status_code}")

            etag = _validator(response.headers)
            # A 200 to a Range request means the server declined it -- the file
            # changed, or it never supported ranges. Either way the partial is
            # about a different file and must go.
            appending = response.status_code == 206 and resume_from > 0
            if not appending and partial.exists():
                partial.unlink()
                resume_from = 0

            digest = hashlib.sha256()
            if appending:
                # The hash covers the whole file, so the bytes already on disk have
                # to be fed through it before the new ones.
                with partial.open("rb") as handle:
                    for block in iter(lambda: handle.read(_CHUNK), b""):
                        digest.update(block)

            with partial.open("ab" if appending else "wb") as handle:
                for block in response.iter_content(chunk_size=_CHUNK):
                    if not block:
                        continue
                    handle.write(block)
                    digest.update(block)
        finally:
            response.close()

        # Step 6: a readable ZIP, checked before the move. The common real failure
        # is an HTML error page served as 200 under a `.zip` name; caught here it
        # is one line, caught at Stage 4 it is a baffling failure days later.
        if not zipfile.is_zipfile(partial):
            # The partial is not a resumable prefix of anything -- it is a whole
            # wrong answer, so unlike a transport failure it is removed.
            partial.unlink(missing_ok=True)
            raise OSError(
                f"{url} did not return a readable ZIP "
                f"(most often an error or sign-in page served as HTTP 200)"
            )

        # Step 7: atomic move. A killed run must never leave a truncated file at the
        # canonical path, where the step-3 checksum test would later trust it.
        partial.replace(target)
        return _Transfer(
            size=target.stat().st_size,
            checksum=digest.hexdigest(),
            etag=etag,
            resumed=resume_from > 0,
        )

    def _fetch(
        self, product: Product, version: ProductVersion, target: Path, force: bool
    ) -> DownloadResult:
        slug, number = product.slug, version.version
        recorded = self._recorded_state(slug, number)
        transfer = self.fetch_to(
            version.zip_url, target, known_etag=recorded.get("zip_etag"), force=force
        )
        self._record(
            slug,
            number,
            status=ConversionStatus.DOWNLOADED,
            download_path=str(target),
            checksum=transfer.checksum,
            zip_size=transfer.size,
            zip_etag=transfer.etag,
            error=None,
        )
        return DownloadResult(
            slug, number, Outcome.DOWNLOADED, path=target,
            size=transfer.size, checksum=transfer.checksum, resumed=transfer.resumed,
        )

    # -- a run ----------------------------------------------------------------

    def download_many(
        self,
        pairs: Iterable[tuple[Product, ProductVersion]],
        force: bool = False,
        on_result: Callable[[DownloadResult], None] | None = None,
    ) -> DownloadStats:
        """Runs the pool over a selection, in `iter_versions` order.

        Results are collected in completion order but the summary does not depend
        on order, and `on_result` fires from the worker thread that finished --
        which is the only place a progress line can be honest about what is done.
        """
        stats = DownloadStats()
        selection = list(pairs)
        if not selection:
            return stats

        width = max(1, min(self.workers, len(selection)))
        with ThreadPoolExecutor(max_workers=width) as pool:
            for result in pool.map(lambda pv: self.download_one(*pv, force=force), selection):
                stats.results.append(result)
                if on_result is not None:
                    on_result(result)
        return stats

    # -- hand-supplied packages (design.md §5.2) --------------------------------

    def ingest_file(
        self,
        product: Product,
        version: ProductVersion,
        source: Path,
        target: Path,
        pin_manual: bool = True,
    ) -> DownloadResult:
        """Files a hand-obtained ZIP at its canonical path.

        Validated before it is copied, and **copied rather than moved** -- the
        user's own copy is not the tool's to consume. There is no upstream checksum
        to compare against, so the computed one becomes authoritative for later
        "is this still the same file" checks.

        `pin_manual` is False for the archive variant: `zip_source` is a statement
        about the *pipeline's* package for a version, and an archived reference ZIP
        pulled outside the working set is not that.
        """
        slug, number = product.slug, version.version
        if not source.is_file():
            raise FileNotFoundError(f"No such file: {source}")
        if not zipfile.is_zipfile(source):
            raise OSError(
                f"{source} is not a readable ZIP. The usual cause is an HTML error or "
                f"sign-in page saved under a .zip name."
            )

        target.parent.mkdir(parents=True, exist_ok=True)
        # Copy via a temporary sibling and rename, so an interrupted copy cannot
        # leave a truncated file at a path the pipeline would treat as complete.
        staged = target.with_suffix(target.suffix + ".part")
        shutil.copyfile(source, staged)
        staged.replace(target)

        checksum = sha256_of(target)
        size = target.stat().st_size
        if pin_manual:
            self.catalog.set_version_field(slug, number, "zip_source", str(ZipSource.MANUAL))
        self._record(
            slug,
            number,
            status=ConversionStatus.DOWNLOADED,
            download_path=str(target),
            checksum=checksum,
            zip_size=size,
            error=None,
        )
        if self.catalog.state is not None:
            # Audit only, and deliberately in `version_metadata` rather than a new
            # `version_state` column: it is detail for the rows that have it, not a
            # field every version carries, so it costs no SCHEMA_VERSION bump.
            self.catalog.state.set_version_metadata(slug, number, "zip_origin_path", str(source.resolve()))
        return DownloadResult(slug, number, Outcome.DOWNLOADED, path=target, size=size, checksum=checksum)
