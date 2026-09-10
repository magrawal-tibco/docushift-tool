"""HTTP client for the `docs.tibco.com` REST API.

Every endpoint, template, and politeness setting comes from `config/docsite.yaml`
rather than being hardcoded, so a moved endpoint is a config edit rather than a
release (docs/architecture.md §2).

The client is deliberately thin -- it fetches and decodes JSON, and knows how to
build a ZIP URL. Interpreting the payloads is `crawler.py`'s job, which is what
lets the crawler be tested against canned records with no network at all.
"""

from typing import Any

import requests

from docushift.utils.http import Throttle, build_session

# Markers from the SSO interstitial docs.tibco.com serves (as HTTP 200) for
# products that are not publicly visible.
_AUTH_MARKERS = ("pureauth", "sign in", "signin", "log in", "login", "sso")


class DocsiteError(Exception):
    """A docsite request failed, or returned something that was not JSON."""


def _looks_like_auth_page(body: str) -> bool:
    head = str(body or "")[:2000].lower()
    return "<html" in head and any(marker in head for marker in _AUTH_MARKERS)


class DocsiteClient:
    """Fetches JSON from the docsite, politely.

    Rate limiting is a hard floor on the interval between requests rather than a
    token bucket -- see `utils.http.Throttle`, which the package downloader shares.
    """

    def __init__(self, docsite: dict[str, Any], session: requests.Session | None = None):
        self.base_url = str(docsite.get("base_url") or "https://docs.tibco.com").rstrip("/")
        self.endpoints: dict[str, str] = dict(docsite.get("endpoints") or {})
        self.zip_urls: dict[str, str] = dict(docsite.get("zip_urls") or {})

        crawl = dict(docsite.get("crawl") or {})
        self.timeout = float(crawl.get("timeout_seconds", 30))
        self._throttle_gate = Throttle.from_crawl(crawl)
        self.session = session if session is not None else build_session(crawl)

    # -- urls ----------------------------------------------------------------

    def url(self, path: str) -> str:
        """Absolutises a docsite path. An already-absolute URL passes through.

        The archive API returns `zipPath` values in both forms depending on the
        product, so this has to tolerate each.
        """
        text = str(path or "").strip()
        if text.startswith(("http://", "https://")):
            return text
        return f"{self.base_url}/{text.lstrip('/')}"

    def active_zip_url(self, folder_path: str) -> str | None:
        """Builds an active version's "Download All Docs" URL from its `folder_path`.

        `ems/10.4.0` -> `/pub/ems/10.4.0/doc/zip/tib_ems_10.4.0_doc.zip`. Returns
        `None` rather than a malformed URL when the product publishes no folder
        path -- a wrong URL would be recorded in the catalog and fail much later.
        """
        template = self.zip_urls.get("active_template")
        folder = str(folder_path or "").strip().strip("/")
        if not template or not folder:
            return None
        return self.url(template.format(folder_path=folder, folder_slug=folder.replace("/", "_")))

    # -- requests -------------------------------------------------------------

    def get_json(self, path: str) -> Any:
        """GETs a docsite path and decodes JSON, or raises `DocsiteError`."""
        url = self.url(path)
        self._throttle_gate.wait()
        try:
            response = self.session.get(url, timeout=self.timeout)
        except requests.RequestException as exc:
            raise DocsiteError(f"GET {url} failed: {exc}") from exc

        if response.status_code != 200:
            raise DocsiteError(f"GET {url} returned HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as exc:
            # Overwhelmingly this is an HTML page served with a 200, and nearly
            # always the SSO interstitial for a product that is not public. Saying
            # so is the difference between "the crawler is broken" and "this
            # product is employee-only".
            if _looks_like_auth_page(getattr(response, "text", "")):
                raise DocsiteError(f"GET {url} returned a sign-in page; this product is not public") from exc
            raise DocsiteError(f"GET {url} did not return JSON ({exc})") from exc

    def _endpoint(self, name: str, **params: str) -> str:
        template = self.endpoints.get(name)
        if not template:
            raise DocsiteError(f"config/docsite.yaml declares no '{name}' endpoint")
        return template.format(**params)

    # -- endpoints ------------------------------------------------------------

    def a_to_z(self) -> Any:
        """Every active public product: names, slugs, docsite ids."""
        return self.get_json(self._endpoint("a_to_z"))

    def product(self, slug: str) -> Any:
        """One product's active versions, folder paths, and archive flag."""
        return self.get_json(self._endpoint("product", slug=slug))

    def product_archive(self, slug: str) -> Any:
        """One product's archived "Other Versions" records."""
        return self.get_json(self._endpoint("product_archive", slug=slug))

    def product_list_by_suites(self) -> Any:
        """Suite groupings. Advisory only -- see architecture §3.3."""
        return self.get_json(self._endpoint("product_list_by_suites"))

    def bu_category_products(self) -> Any:
        """Category data. Advisory only -- most products carry none."""
        return self.get_json(self._endpoint("bu_category_products"))
