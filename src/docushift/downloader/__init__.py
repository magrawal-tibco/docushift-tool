"""Stage 3: Resumable package downloader & cache manager.

Built in Phase 4a. See docs/design.md §5.
"""

from docushift.downloader.fetcher import (
    DownloadResult,
    DownloadStats,
    Outcome,
    PackageDownloader,
    sha256_of,
)

__all__ = ["DownloadResult", "DownloadStats", "Outcome", "PackageDownloader", "sha256_of"]
