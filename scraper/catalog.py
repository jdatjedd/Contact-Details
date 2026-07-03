"""
scraper/catalog.py

Determines a coarse "productCount" status for a store:
  "Active" - a public product catalog endpoint responded with products
  "Hidden" - the store exists but the catalog is password-protected /
             blocked / empty
  "Unknown" - couldn't determine (request failed entirely)

This checks the common Shopify-style `/products.json` endpoint as a
lightweight signal. It intentionally does NOT attempt to bypass any
password screen or anti-bot challenge -- if a store is protected, it is
simply reported as "Hidden".
"""

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scraper.fetcher import Fetcher

logger = logging.getLogger("store_scraper.catalog")


def check_product_catalog(fetcher: "Fetcher", base_url: str) -> str:
    products_url = base_url.rstrip("/") + "/products.json"
    resp = fetcher.get(products_url)

    if resp is None:
        return "Unknown"

    if resp.status_code == 401 or resp.status_code == 403:
        return "Hidden"

    if resp.status_code != 200:
        return "Unknown"

    try:
        data = json.loads(resp.content)
    except (json.JSONDecodeError, ValueError):
        return "Unknown"

    products = data.get("products") if isinstance(data, dict) else None
    if isinstance(products, list) and len(products) > 0:
        return "Active"

    return "Hidden"
