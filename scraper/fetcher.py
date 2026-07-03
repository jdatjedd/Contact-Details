"""
scraper/fetcher.py

Raw-HTTP fetching layer. No headless browser (Puppeteer/Playwright) is used
here on purpose -- everything goes through `requests`, which is faster and
far lighter on resources than driving a full browser.

Responsibilities:
  * Rotate a small pool of realistic desktop User-Agent strings
  * Respect a configurable delay between requests (rate limiting)
  * Retry on transient failures / 429 / 5xx with exponential backoff
  * Back off harder (and eventually skip) when a host keeps blocking us,
    instead of hammering it
"""

import logging
import random
import time
from dataclasses import dataclass
from typing import Optional

import requests

logger = logging.getLogger("store_scraper.fetcher")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


@dataclass
class FetchConfig:
    delay_min: float = 1.0       # seconds, minimum delay between requests
    delay_max: float = 3.0       # seconds, maximum delay between requests
    max_retries: int = 3
    backoff_base: float = 2.0    # exponential backoff base (seconds)
    timeout: float = 15.0
    max_response_bytes: int = 3_000_000  # don't read absurdly large pages


class Fetcher:
    """Thin wrapper around requests.Session with politeness + retry baked in."""

    def __init__(self, config: Optional[FetchConfig] = None):
        self.config = config or FetchConfig()
        self.session = requests.Session()
        self._last_request_ts = 0.0

    def _headers(self) -> dict:
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
        }

    def _respect_rate_limit(self):
        """Sleep just enough to keep requests spaced out."""
        elapsed = time.time() - self._last_request_ts
        min_gap = random.uniform(self.config.delay_min, self.config.delay_max)
        if elapsed < min_gap:
            time.sleep(min_gap - elapsed)

    def get(self, url: str) -> Optional[requests.Response]:
        """
        GET a URL with retry/backoff. Returns the Response on success,
        or None if all retries were exhausted.
        """
        last_exc = None
        for attempt in range(1, self.config.max_retries + 1):
            self._respect_rate_limit()
            self._last_request_ts = time.time()
            try:
                resp = self.session.get(
                    url,
                    headers=self._headers(),
                    timeout=self.config.timeout,
                    stream=True,
                )

                if resp.status_code in RETRYABLE_STATUS:
                    wait = self.config.backoff_base ** attempt + random.uniform(0, 1)
                    logger.warning(
                        "Got %s from %s (attempt %d/%d) -- backing off %.1fs",
                        resp.status_code, url, attempt, self.config.max_retries, wait,
                    )
                    time.sleep(wait)
                    continue

                # Cap how much we read to avoid huge pages blowing up memory
                content = resp.raw.read(self.config.max_response_bytes, decode_content=True)
                resp._content = content
                return resp

            except requests.RequestException as exc:
                last_exc = exc
                wait = self.config.backoff_base ** attempt + random.uniform(0, 1)
                logger.warning(
                    "Request error for %s (attempt %d/%d): %s -- retrying in %.1fs",
                    url, attempt, self.config.max_retries, exc, wait,
                )
                time.sleep(wait)

        logger.error("Giving up on %s after %d attempts (%s)",
                     url, self.config.max_retries, last_exc)
        return None
