"""Unit tests for Stage 3: acquiring packages (docs/design.md §5.1, §5.2).

Every case runs offline against a fake session, and every ZIP is built in-process
rather than committed -- a binary fixture in git tells the next reader nothing
about why it is shaped the way it is, and the interesting archives here (a
truncated one, an HTML page under a `.zip` name, one carrying a `../` member) are
each two lines to construct.

The guarantee these turn on is `architecture.md` §3.8's: nothing but
`ConfigManager` decides where a package lands, and a failure is a reported outcome
rather than an exception that stops a 200-version batch.
"""

import io
import zipfile
from pathlib import Path

import pytest

from docushift.catalog import CatalogManager
from docushift.config import ConfigManager
from docushift.downloader import Outcome, PackageDownloader, sha256_of
from docushift.extractor import UnsafeArchiveError, safe_extract
from docushift.models import Product, ProductVersion, ZipSource
from tests.conftest import make_product, make_version

# -- fakes -------------------------------------------------------------------


class FakeResponse:
    """Just enough of `requests.Response` for the streaming path."""

    def __init__(
        self,
        body: bytes = b"",
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        truncate_after: int | None = None,
    ):
        self.body = body
        self.status_code = status_code
        self.headers = headers or {}
        # Bytes to hand over before raising, standing in for a connection dropped
        # mid-transfer.
        self.truncate_after = truncate_after
        self.closed = False

    def iter_content(self, chunk_size: int = 1):
        if self.truncate_after is not None:
            yield self.body[: self.truncate_after]
            raise OSError("connection reset by peer")
        yield self.body

    def close(self) -> None:
        self.closed = True


class FakeSession:
    """Replays a queued list of responses and records what was asked for."""

    def __init__(self, *responses: FakeResponse):
        self.responses = list(responses)
        self.calls: list[dict] = []

    def get(self, url, headers=None, stream=False, timeout=None):
        self.calls.append({"url": url, "headers": dict(headers or {})})
        if not self.responses:
            raise AssertionError(f"unexpected extra request for {url}")
        return self.responses.pop(0)


def zip_bytes(members: dict[str, str] | None = None) -> bytes:
    """A readable ZIP, in memory."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, text in (members or {"docs/index.html": "<h1>hi</h1>"}).items():
            archive.writestr(name, text)
    return buffer.getvalue()


# -- fixtures ----------------------------------------------------------------


@pytest.fixture
def product(catalog: CatalogManager) -> Product:
    """One catalogued product with a single fetchable version."""
    built = make_product("tibco-ems", product_code="ems", family="messaging")
    built.versions = {"10.4.0": make_version("tibco-ems", "10.4.0", zip_url="https://docs.example/ems.zip")}
    catalog.merge_fetch_results([built])
    return catalog.get_product("tibco-ems")


@pytest.fixture
def version(product: Product) -> ProductVersion:
    return product.versions["10.4.0"]


def downloader(config: ConfigManager, catalog: CatalogManager, session: FakeSession) -> PackageDownloader:
    return PackageDownloader(config, catalog, session=session)


def target_of(config: ConfigManager, product: Product, version: ProductVersion) -> Path:
    return config.download_path(product.bu, product.family, product.slug, version.version)


# -- the short-circuits ------------------------------------------------------


def test_a_manual_row_is_never_fetched(
    config: ConfigManager, catalog: CatalogManager, product: Product, version: ProductVersion
) -> None:
    """The pin outranks even a live `zip_url`: the package is placed by hand."""
    version.zip_source = ZipSource.MANUAL
    session = FakeSession()

    result = downloader(config, catalog, session).download_one(product, version)

    assert result.outcome is Outcome.SKIPPED_MANUAL
    assert session.calls == []


def test_a_matching_checksum_short_circuits(
    config: ConfigManager, catalog: CatalogManager, product: Product, version: ProductVersion
) -> None:
    target = target_of(config, product, version)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(zip_bytes())
    catalog.state.set_version_state("tibco-ems", "10.4.0", checksum=sha256_of(target))
    session = FakeSession()

    result = downloader(config, catalog, session).download_one(product, version)

    assert result.outcome is Outcome.CURRENT
    assert session.calls == []


def test_force_refetches_a_current_package(
    config: ConfigManager, catalog: CatalogManager, product: Product, version: ProductVersion
) -> None:
    body = zip_bytes({"docs/new.html": "fresh"})
    target = target_of(config, product, version)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(zip_bytes())
    catalog.state.set_version_state("tibco-ems", "10.4.0", checksum=sha256_of(target))
    session = FakeSession(FakeResponse(body))

    result = downloader(config, catalog, session).download_one(product, version, force=True)

    assert result.outcome is Outcome.DOWNLOADED
    assert target.read_bytes() == body


def test_a_version_with_no_url_is_a_report_line(
    config: ConfigManager, catalog: CatalogManager, product: Product, version: ProductVersion
) -> None:
    """Not an abort: discovery genuinely misses some endpoints, and --from-file answers."""
    version.zip_url = ""
    session = FakeSession()

    result = downloader(config, catalog, session).download_one(product, version)

    assert result.outcome is Outcome.NO_URL
    assert "--from-file" in result.message


# -- the transfer ------------------------------------------------------------


def test_a_download_lands_at_the_derived_path_and_records_state(
    config: ConfigManager, catalog: CatalogManager, product: Product, version: ProductVersion
) -> None:
    body = zip_bytes()
    session = FakeSession(FakeResponse(body, headers={"ETag": '"abc"'}))

    result = downloader(config, catalog, session).download_one(product, version)

    target = target_of(config, product, version)
    assert result.outcome is Outcome.DOWNLOADED
    assert result.path == target
    assert target.read_bytes() == body
    assert not target.with_suffix(".zip.part").exists()

    recorded = catalog.state.get_version_state("tibco-ems", "10.4.0")
    assert recorded["checksum"] == sha256_of(target)
    assert recorded["zip_size"] == len(body)
    assert recorded["zip_etag"] == '"abc"'


def test_last_modified_stands_in_for_a_missing_etag(
    config: ConfigManager, catalog: CatalogManager, product: Product, version: ProductVersion
) -> None:
    """What matters is that the validator is comparable, not which header it came from."""
    stamp = "Tue, 04 Nov 2025 09:00:00 GMT"
    session = FakeSession(FakeResponse(zip_bytes(), headers={"Last-Modified": stamp}))

    downloader(config, catalog, session).download_one(product, version)

    assert catalog.state.get_version_state("tibco-ems", "10.4.0")["zip_etag"] == stamp


def test_a_resume_appends_against_a_matching_etag(
    config: ConfigManager, catalog: CatalogManager, product: Product, version: ProductVersion
) -> None:
    body = zip_bytes({"docs/index.html": "x" * 4000})
    split = 200
    target = target_of(config, product, version)
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(".zip.part")
    partial.write_bytes(body[:split])
    catalog.state.set_version_state("tibco-ems", "10.4.0", zip_etag='"abc"')
    session = FakeSession(FakeResponse(body[split:], status_code=206, headers={"ETag": '"abc"'}))

    result = downloader(config, catalog, session).download_one(product, version)

    assert result.resumed is True
    assert session.calls[0]["headers"]["Range"] == f"bytes={split}-"
    assert session.calls[0]["headers"]["If-Range"] == '"abc"'
    assert target.read_bytes() == body
    # The digest has to cover the bytes that were already on disk, not just the
    # appended ones -- otherwise the recorded checksum is of a file that does not
    # exist and every later re-run refetches.
    assert result.checksum == sha256_of(target)


def test_a_changed_file_restarts_instead_of_appending(
    config: ConfigManager, catalog: CatalogManager, product: Product, version: ProductVersion
) -> None:
    """A 200 to a Range request means the server declined it: the partial is stale.

    Appending across a changed file yields a corrupt archive that passes every
    length check there is, so the only safe reading of a declined range is to
    throw the prefix away.
    """
    fresh = zip_bytes({"docs/new.html": "rewritten upstream"})
    target = target_of(config, product, version)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.with_suffix(".zip.part").write_bytes(b"stale prefix from a different file")
    catalog.state.set_version_state("tibco-ems", "10.4.0", zip_etag='"old"')
    session = FakeSession(FakeResponse(fresh, status_code=200, headers={"ETag": '"new"'}))

    result = downloader(config, catalog, session).download_one(product, version)

    assert session.calls[0]["headers"]["If-Range"] == '"old"'
    assert result.resumed is False
    assert target.read_bytes() == fresh


def test_no_resume_is_attempted_without_a_recorded_validator(
    config: ConfigManager, catalog: CatalogManager, product: Product, version: ProductVersion
) -> None:
    """Without a validator there is no way to ask "still the same file?", so don't."""
    body = zip_bytes()
    target = target_of(config, product, version)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.with_suffix(".zip.part").write_bytes(b"orphaned prefix")
    session = FakeSession(FakeResponse(body))

    downloader(config, catalog, session).download_one(product, version)

    assert "Range" not in session.calls[0]["headers"]
    assert target.read_bytes() == body


def test_a_truncated_transfer_leaves_a_part_and_no_canonical_file(
    config: ConfigManager, catalog: CatalogManager, product: Product, version: ProductVersion
) -> None:
    """The prefix is kept so the next run can resume; the canonical path stays empty.

    A truncated file at the canonical path would be trusted by the step-3 checksum
    test on the very next run, which is the failure the atomic move exists to stop.
    """
    body = zip_bytes({"docs/index.html": "y" * 4000})
    session = FakeSession(FakeResponse(body, headers={"ETag": '"abc"'}, truncate_after=300))

    result = downloader(config, catalog, session).download_one(product, version)

    target = target_of(config, product, version)
    assert result.outcome is Outcome.FAILED
    assert not target.exists()
    assert target.with_suffix(".zip.part").stat().st_size == 300
    assert catalog.state.get_version_state("tibco-ems", "10.4.0")["error"]


def test_an_html_page_under_a_zip_name_is_rejected_before_the_move(
    config: ConfigManager, catalog: CatalogManager, product: Product, version: ProductVersion
) -> None:
    """The single most common real failure, and it arrives as a cheerful HTTP 200."""
    session = FakeSession(FakeResponse(b"<html><body>Please sign in</body></html>"))

    result = downloader(config, catalog, session).download_one(product, version)

    target = target_of(config, product, version)
    assert result.outcome is Outcome.FAILED
    assert "readable ZIP" in result.message
    assert not target.exists()
    # Not a resumable prefix of anything -- a whole wrong answer, so it is removed.
    assert not target.with_suffix(".zip.part").exists()


def test_an_http_error_is_a_recorded_outcome_not_an_exception(
    config: ConfigManager, catalog: CatalogManager, product: Product, version: ProductVersion
) -> None:
    session = FakeSession(FakeResponse(b"", status_code=404))

    result = downloader(config, catalog, session).download_one(product, version)

    assert result.outcome is Outcome.FAILED
    assert "404" in result.message


# -- a run -------------------------------------------------------------------


def test_download_many_reports_every_outcome(
    config: ConfigManager, catalog: CatalogManager, product: Product
) -> None:
    """One unreachable product must not stop the batch."""
    good = product.versions["10.4.0"]
    broken = make_version("tibco-ems", "9.0.0", zip_url="https://docs.example/broken.zip")
    session = FakeSession(FakeResponse(zip_bytes()), FakeResponse(b"", status_code=503))

    stats = downloader(config, catalog, session).download_many([(product, good), (product, broken)])

    assert stats.count(Outcome.DOWNLOADED) == 1
    assert stats.count(Outcome.FAILED) == 1
    assert len(stats.failures) == 1
    assert stats.bytes_written > 0


def test_an_empty_selection_makes_no_requests(config: ConfigManager, catalog: CatalogManager) -> None:
    session = FakeSession()

    stats = downloader(config, catalog, session).download_many([])

    assert stats.results == []
    assert session.calls == []


# -- hand-supplied packages (design.md §5.2) ---------------------------------


def test_from_file_copies_rather_than_moves(
    config: ConfigManager,
    catalog: CatalogManager,
    product: Product,
    version: ProductVersion,
    tmp_path: Path,
) -> None:
    """The user's own copy is not the tool's to consume."""
    source = tmp_path / "handed-over.zip"
    source.write_bytes(zip_bytes())
    target = target_of(config, product, version)

    result = downloader(config, catalog, FakeSession()).ingest_file(product, version, source, target)

    assert result.outcome is Outcome.DOWNLOADED
    assert source.exists()
    assert target.read_bytes() == source.read_bytes()
    assert not target.with_suffix(".zip.part").exists()


def test_from_file_pins_the_row_manual_and_records_its_origin(
    config: ConfigManager,
    catalog: CatalogManager,
    product: Product,
    version: ProductVersion,
    tmp_path: Path,
) -> None:
    """Provenance lives in the CSV, never in a filesystem check: families/ is git-ignored."""
    source = tmp_path / "handed-over.zip"
    source.write_bytes(zip_bytes())

    downloader(config, catalog, FakeSession()).ingest_file(
        product, version, source, target_of(config, product, version)
    )

    assert catalog.get_product("tibco-ems").versions["10.4.0"].zip_source is ZipSource.MANUAL
    origin = catalog.state.get_version_metadata("tibco-ems", "10.4.0")["zip_origin_path"]
    assert Path(origin) == source.resolve()


def test_from_file_leaves_zip_source_alone_for_an_archive_pull(
    config: ConfigManager,
    catalog: CatalogManager,
    product: Product,
    version: ProductVersion,
    tmp_path: Path,
) -> None:
    """`zip_source` states where the *pipeline's* package comes from, and a reference
    ZIP pulled outside the working set is not that."""
    source = tmp_path / "handed-over.zip"
    source.write_bytes(zip_bytes())
    target = config.archive_path(product.bu, product.family, product.slug, version.version)

    downloader(config, catalog, FakeSession()).ingest_file(product, version, source, target, pin_manual=False)

    assert catalog.get_product("tibco-ems").versions["10.4.0"].zip_source is not ZipSource.MANUAL
    assert target.exists()


def test_from_file_rejects_something_that_is_not_a_zip(
    config: ConfigManager,
    catalog: CatalogManager,
    product: Product,
    version: ProductVersion,
    tmp_path: Path,
) -> None:
    source = tmp_path / "handed-over.zip"
    source.write_text("<html>sign in</html>", encoding="utf-8")
    target = target_of(config, product, version)

    with pytest.raises(OSError, match="readable ZIP"):
        downloader(config, catalog, FakeSession()).ingest_file(product, version, source, target)

    assert not target.exists()


def test_from_file_reports_a_missing_source(
    config: ConfigManager, catalog: CatalogManager, product: Product, version: ProductVersion, tmp_path: Path
) -> None:
    with pytest.raises(FileNotFoundError):
        downloader(config, catalog, FakeSession()).ingest_file(
            product, version, tmp_path / "absent.zip", target_of(config, product, version)
        )


# -- safe extraction (design.md §6.1 step 2) ---------------------------------


def test_safe_extract_writes_every_member(tmp_path: Path) -> None:
    archive = tmp_path / "pkg.zip"
    archive.write_bytes(zip_bytes({"docs/index.html": "hi", "docs/img/logo.png": "png"}))

    written = safe_extract(archive, tmp_path / "out")

    assert written == 2
    assert (tmp_path / "out" / "docs" / "index.html").read_text(encoding="utf-8") == "hi"


@pytest.mark.parametrize(
    "member",
    ["../escape.txt", "docs/../../escape.txt", "/etc/passwd", "C:/Windows/evil.txt"],
    ids=["parent", "nested-parent", "absolute", "drive-letter"],
)
def test_safe_extract_refuses_a_member_that_escapes_the_target(tmp_path: Path, member: str) -> None:
    archive = tmp_path / "pkg.zip"
    archive.write_bytes(zip_bytes({"docs/index.html": "hi", member: "owned"}))

    with pytest.raises(UnsafeArchiveError):
        safe_extract(archive, tmp_path / "out")


def test_a_refused_archive_leaves_nothing_behind(tmp_path: Path) -> None:
    """Every member is checked before any is written, so a malicious archive cannot
    leave half a tree on disk before being refused."""
    archive = tmp_path / "pkg.zip"
    archive.write_bytes(zip_bytes({"docs/index.html": "hi", "../escape.txt": "owned"}))

    with pytest.raises(UnsafeArchiveError):
        safe_extract(archive, tmp_path / "out")

    assert list((tmp_path / "out").iterdir()) == []
