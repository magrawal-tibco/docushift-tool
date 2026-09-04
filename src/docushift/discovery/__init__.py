"""Stage 1: docs.tibco.com API crawler (Active & Archived versions).

`DocsiteClient` does the HTTP; `DocsiteCrawler` turns the payloads into
catalog-shaped `Product` records for `CatalogManager.merge_fetch_results()`.
The split is what lets the crawler be tested with no network -- see
docs/architecture.md §4.1.
"""

from docushift.discovery.client import DocsiteClient, DocsiteError
from docushift.discovery.crawler import CrawlResult, DocsiteCrawler

__all__ = ["CrawlResult", "DocsiteClient", "DocsiteCrawler", "DocsiteError"]
