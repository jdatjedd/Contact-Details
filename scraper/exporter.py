"""
scraper/exporter.py

Writes a list of StoreRecord objects out to CSV.
"""

import csv
import logging
from pathlib import Path
from typing import List

from scraper.models import CSV_FIELDNAMES, StoreRecord

logger = logging.getLogger("store_scraper.exporter")


def export_csv(records: List[StoreRecord], output_path: str) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        for record in records:
            writer.writerow(record.to_dict())

    logger.info("Wrote %d records to %s", len(records), path)
    return str(path)
