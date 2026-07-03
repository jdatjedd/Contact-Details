#!/usr/bin/env python3
"""
main.py

CLI entry point for store-scraper.

Usage:
    # From a file of URLs (one per line, # comments allowed)
    python main.py --input data/urls.txt --output output/results.csv

    # From explicit URLs on the command line
    python main.py --url https://store1.com --url https://store2.com

    # Both at once (deduplicated automatically)
    python main.py --input data/urls.txt --url https://extra-store.com

Options:
    --input PATH       Path to a text/CSV file with one URL per line
    --url URL          A single store URL (repeatable)
    --output PATH      Output CSV path (default: output/results.csv)
    --delay-min FLOAT  Minimum seconds between requests (default: 1.0)
    --delay-max FLOAT  Maximum seconds between requests (default: 3.0)
    --retries INT      Max retries per request (default: 3)
    --max-pages INT    Max extra pages (contact/about) checked per site (default: 3)
    --verbose          Enable debug logging
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List

from scraper.exporter import export_csv
from scraper.fetcher import Fetcher, FetchConfig
from scraper.pipeline import scrape_store

logger = logging.getLogger("store_scraper.cli")


def load_urls_from_file(path: str) -> List[str]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    urls = []
    for line in file_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Allow a simple CSV where the URL is the first column
        first_field = line.split(",")[0].strip()
        urls.append(first_field)
    return urls


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Scrape store contact info via raw HTTP and export to CSV."
    )
    parser.add_argument("--input", "-i", help="Path to file with one URL per line")
    parser.add_argument(
        "--url", "-u", action="append", default=[],
        help="A store URL to scrape (repeatable)",
    )
    parser.add_argument(
        "--output", "-o", default="output/results.csv",
        help="Output CSV path (default: output/results.csv)",
    )
    parser.add_argument("--delay-min", type=float, default=1.0)
    parser.add_argument("--delay-max", type=float, default=3.0)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument(
        "--max-pages", type=int, default=3,
        help="Max extra pages (contact/about/etc.) to check per site, "
             "beyond the homepage (default: 3)",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    urls: List[str] = []
    if args.input:
        urls.extend(load_urls_from_file(args.input))
    urls.extend(args.url)

    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            deduped.append(u)
    urls = deduped

    if not urls:
        logger.error(
            "No URLs provided. Use --input <file> and/or --url <url> "
            "(repeatable)."
        )
        sys.exit(1)

    logger.info("Scraping %d store URL(s)...", len(urls))

    fetch_config = FetchConfig(
        delay_min=args.delay_min,
        delay_max=args.delay_max,
        max_retries=args.retries,
    )
    fetcher = Fetcher(fetch_config)

    records = []
    for i, url in enumerate(urls, start=1):
        logger.info("[%d/%d] %s", i, len(urls), url)
        record = scrape_store(fetcher, url, max_extra_pages=args.max_pages)
        records.append(record)
        if record.error:
            logger.warning("  -> error: %s", record.error)
        else:
            logger.info(
                "  -> %s | emails=%d phones=%d catalog=%s",
                record.storeName, len(record.emails), len(record.phones),
                record.productCount,
            )

    output_path = export_csv(
        sorted(records, key=lambda r: r.score, reverse=True), args.output
    )
    logger.info("Done. Results written to %s", output_path)


if __name__ == "__main__":
    main()
