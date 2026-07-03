"""
tests/test_extractor.py

Offline tests -- no network calls. Run with: python -m pytest tests/
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.extractor import (  # noqa: E402
    extract_fields,
    extract_domain,
    discover_contact_links,
    merge_fields,
)
from scraper.models import StoreRecord  # noqa: E402
from scraper.scoring import classify_pitch, compute_score  # noqa: E402

SAMPLE_HTML = """
<html>
<head>
<title>Acme Widgets - Home</title>
<meta property="og:site_name" content="Acme Widgets Co">
<script type="application/ld+json">
{"@context": "https://schema.org", "@type": "Organization", "name": "Acme Widgets Official",
 "address": {"@type": "PostalAddress", "streetAddress": "12 MG Road",
             "addressLocality": "Gurugram", "addressRegion": "Haryana",
             "postalCode": "122001", "addressCountry": "IN"}}
</script>
</head>
<body>
<p>Contact us: <a href="mailto:sales@acmewidgets.com">sales@acmewidgets.com</a></p>
<p>Or support@acmewidgets.com for help.</p>
<p>Call us: <a href="tel:+15551234567">+1 (555) 123-4567</a></p>
<a href="https://facebook.com/acmewidgets">Facebook</a>
<a href="https://instagram.com/acmewidgets">Instagram</a>
<a href="https://x.com/acmewidgets">X</a>
<a href="https://wa.me/919876543210">WhatsApp</a>
<a href="https://www.linkedin.com/company/acmewidgets">LinkedIn</a>
<form id="contact-form" action="/contact-submit">
  <input type="email" name="email">
  <button type="submit">Send</button>
</form>
</body>
</html>
"""


def test_extract_domain():
    assert extract_domain("https://www.acmewidgets.com/collections/all") == "acmewidgets.com"


def test_extract_fields():
    result = extract_fields(SAMPLE_HTML, "https://www.acmewidgets.com")

    assert result["storeName"] == "Acme Widgets Official"  # JSON-LD wins
    assert "sales@acmewidgets.com" in result["emails"]
    assert "support@acmewidgets.com" in result["emails"]
    assert any("555" in p for p in result["phones"])
    assert result["facebook"] == "https://facebook.com/acmewidgets"
    assert result["instagram"] == "https://instagram.com/acmewidgets"
    assert result["twitter"] == "https://x.com/acmewidgets"
    assert result["whatsapp"] == "https://wa.me/919876543210"
    assert result["linkedin"] == "https://www.linkedin.com/company/acmewidgets"
    assert result["address"] == "12 MG Road, Gurugram, Haryana, 122001, IN"
    assert result["hasContactForm"] is True


HOMEPAGE_WITH_NAV = """
<html><body>
<nav>
  <a href="/pages/contact-us">Contact Us</a>
  <a href="/about">About</a>
  <a href="/collections/all">Shop</a>
</nav>
<a href="mailto:hello@acmewidgets.com">hello@acmewidgets.com</a>
</body></html>
"""

CONTACT_PAGE_HTML = """
<html><body>
<p>Sales: sales@acmewidgets.com</p>
<p>Wholesale enquiries: wholesale@acmewidgets.com</p>
<p>Phone: <a href="tel:+442071234567">+44 20 7123 4567</a> or (555) 987-6543</p>
</body></html>
"""


def test_discover_contact_links_same_domain_only():
    links = discover_contact_links(HOMEPAGE_WITH_NAV, "https://acmewidgets.com", limit=5)
    assert "https://acmewidgets.com/pages/contact-us" in links
    assert "https://acmewidgets.com/about" in links
    assert not any("collections" in link for link in links)


def test_merge_fields_aggregates_across_pages():
    home_fields = extract_fields(HOMEPAGE_WITH_NAV, "https://acmewidgets.com")
    contact_fields = extract_fields(
        CONTACT_PAGE_HTML, "https://acmewidgets.com/pages/contact-us"
    )
    merged = merge_fields([home_fields, contact_fields])

    assert "hello@acmewidgets.com" in merged["emails"]
    assert "sales@acmewidgets.com" in merged["emails"]
    assert "wholesale@acmewidgets.com" in merged["emails"]
    assert len(merged["emails"]) == 3

    assert len(merged["phones"]) == 2  # UK number + US number, deduped by digits


def test_pitch_full_suite_for_active_catalog():
    record = StoreRecord(
        url="https://acmewidgets.com", emails=["a@acmewidgets.com"],
        phones=["+15551234567"], productCount="Active",
    )
    assert classify_pitch(record) == "Full Suite"
    assert compute_score(record) >= 65  # catalog + email + phone


def test_pitch_browntape_for_marketplace_only_seller():
    record = StoreRecord(
        url="https://someseller.example", emails=["seller@someseller.example"],
        productCount="Hidden",
    )
    pitch = classify_pitch(record, marketplace_links=["amazon", "flipkart"])
    assert pitch == "Browntape"


def test_pitch_zwing_for_brick_and_mortar():
    record = StoreRecord(
        url="https://localshop.example", phones=["+911234567890"],
        productCount="Hidden",
    )
    pitch = classify_pitch(record, has_store_locator=True)
    assert pitch == "Zwing POS"


def test_pitch_needs_review_when_ambiguous():
    record = StoreRecord(url="https://mystery.example", productCount="Unknown")
    assert classify_pitch(record) == "Needs Review"


if __name__ == "__main__":
    test_extract_domain()
    test_extract_fields()
    test_discover_contact_links_same_domain_only()
    test_merge_fields_aggregates_across_pages()
    test_pitch_full_suite_for_active_catalog()
    test_pitch_browntape_for_marketplace_only_seller()
    test_pitch_zwing_for_brick_and_mortar()
    test_pitch_needs_review_when_ambiguous()
    print("All tests passed.")
