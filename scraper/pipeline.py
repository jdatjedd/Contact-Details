"""
scraper/pipeline.py

Orchestrates the scrape of a single store end-to-end and returns a
StoreRecord.

To support multiple emails/phone numbers per site, this doesn't just parse
the homepage: it also visits a handful of likely contact/about pages
(discovered via on-page links, plus common fallback paths like
`/contact`, `/pages/contact-us`) and merges everything it finds.
"""

import logging
from urllib.parse import urlparse

from scraper.catalog import check_product_catalog
from scraper.extractor import (
    candidate_contact_urls,
    discover_contact_links,
    extract_domain,
    extract_fields,
    merge_fields,
)
from scraper.fetcher import Fetcher
from scraper.models import StoreRecord
from scraper.scoring import classify_pitch, compute_score

logger = logging.getLogger("store_scraper.pipeline")

# Homepage + at most this many extra pages (contact/about/etc.)
DEFAULT_MAX_EXTRA_PAGES = 3


def _normalize_url(url: str) -> str:
    url = url.strip()
    if not url:
        return url
    if not urlparse(url).scheme:
        url = "https://" + url
    return url


def scrape_store(
    fetcher: Fetcher,
    raw_url: str,
    max_extra_pages: int = DEFAULT_MAX_EXTRA_PAGES,
) -> StoreRecord:
    url = _normalize_url(raw_url)
    domain = extract_domain(url)

    resp = fetcher.get(url)
    if resp is None or resp.status_code >= 400:
        status = resp.status_code if resp is not None else "no response"
        logger.warning("Failed to fetch %s (%s)", url, status)
        return StoreRecord(
            url=url,
            domain=domain,
            storeName=domain,
            productCount="Unknown",
            error=f"fetch failed ({status})",
        )

    try:
        home_html = resp.text
    except Exception as exc:  # noqa: BLE001
        return StoreRecord(url=url, domain=domain, storeName=domain, error=str(exc))

    pages = [extract_fields(home_html, url)]

    # Figure out which extra pages to visit: prefer links actually found on
    # the homepage (nav/footer "Contact"/"About" links), then top up with
    # common predictable paths if we still have budget left.
    discovered = discover_contact_links(home_html, url, limit=max_extra_pages)
    extra_urls = list(discovered)
    if len(extra_urls) < max_extra_pages:
        for candidate in candidate_contact_urls(url):
            if candidate not in extra_urls and candidate != url:
                extra_urls.append(candidate)
            if len(extra_urls) >= max_extra_pages:
                break
    extra_urls = extra_urls[:max_extra_pages]

    for extra_url in extra_urls:
        extra_resp = fetcher.get(extra_url)
        if extra_resp is None or extra_resp.status_code >= 400:
            logger.debug("Skipping extra page %s (fetch failed)", extra_url)
            continue
        try:
            pages.append(extract_fields(extra_resp.text, extra_url))
        except Exception as exc:  # noqa: BLE001
            logger.debug("Skipping extra page %s (%s)", extra_url, exc)

    merged = merge_fields(pages)
    product_status = check_product_catalog(fetcher, f"{urlparse(url).scheme}://{domain}")

    record = StoreRecord(
        url=url,
        domain=merged["domain"],
        storeName=merged["storeName"],
        emails=merged["emails"],
        phones=merged["phones"],
        facebook=merged["facebook"],
        instagram=merged["instagram"],
        twitter=merged["twitter"],
        whatsapp=merged["whatsapp"],
        linkedin=merged["linkedin"],
        address=merged["address"],
        contactFormUrl=merged["contactFormUrl"],
        productCount=product_status,
    )

    has_store_locator = merged.get("hasStoreLocator", False)
    marketplace_links = merged.get("marketplaceLinks", [])
    record.score = compute_score(record, has_store_locator=has_store_locator)
    record.pitchType = classify_pitch(
        record, marketplace_links=marketplace_links, has_store_locator=has_store_locator
    )

    return record
