"""
scraper/scoring.py

Turns the raw extracted signals for a store into two outreach-ready fields:

  score      - 0-100, how complete/reachable this lead is
  pitchType  - which Ginesys product angle fits this store best:
                 "Full Suite"    - has its own active online catalog
                                    (ERP + POS + OMS conversation)
                 "Browntape"     - sells through marketplaces
                                    (Amazon/Flipkart/Myntra/...) but has
                                    no independent storefront catalog
                 "Zwing POS"     - has a physical, multi-location presence
                                    (store locator found) but no working
                                    online catalog
                 "Needs Review"  - not enough signal to classify confidently;
                                    a human should look before outreach

This is a heuristic, not a certainty -- it's meant to help triage/sort a
CSV of leads, not to auto-decide anything. Always spot-check before a send.
"""

from typing import Optional

from scraper.models import StoreRecord

# Points awarded per signal found. Weighted toward "can we actually reach
# this lead" (contact info) over "nice to have" (extra socials).
SCORE_WEIGHTS = {
    "active_catalog": 30,
    "has_email": 20,
    "has_phone": 15,
    "has_social": 10,
    "has_address": 10,
    "has_store_locator": 15,
}


def compute_score(
    record: StoreRecord,
    has_store_locator: bool = False,
) -> int:
    score = 0

    if record.productCount == "Active":
        score += SCORE_WEIGHTS["active_catalog"]
    if record.emails:
        score += SCORE_WEIGHTS["has_email"]
    if record.phones:
        score += SCORE_WEIGHTS["has_phone"]
    if any([record.facebook, record.instagram, record.twitter,
            record.whatsapp, record.linkedin]):
        score += SCORE_WEIGHTS["has_social"]
    if record.address:
        score += SCORE_WEIGHTS["has_address"]
    if has_store_locator:
        score += SCORE_WEIGHTS["has_store_locator"]

    return min(score, 100)


def classify_pitch(
    record: StoreRecord,
    marketplace_links: Optional[list] = None,
    has_store_locator: bool = False,
) -> str:
    marketplace_links = marketplace_links or []
    has_own_catalog = record.productCount == "Active"
    has_marketplace_presence = bool(marketplace_links)
    has_contact_info = bool(record.emails or record.phones)

    if has_own_catalog:
        return "Full Suite"

    if has_marketplace_presence and not has_own_catalog:
        return "Browntape"

    if has_store_locator and not has_own_catalog:
        return "Zwing POS"

    if has_contact_info:
        # We reached the site and found *something*, but not enough of a
        # clear signal (no active catalog, no marketplace links, no store
        # locator) to confidently pick a pitch.
        return "Needs Review"

    return "Needs Review"
