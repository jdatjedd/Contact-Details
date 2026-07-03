"""
scraper/extractor.py

Pulls structured fields out of a fetched HTML page:
  storeName, emails, phones, facebook, instagram, twitter

Sources checked, in priority order for storeName:
  1. JSON-LD (schema.org Organization / Store / WebSite "name")
  2. <meta property="og:site_name">
  3. <title> tag (cleaned up)
"""

import json
import re
from typing import List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

# --- Regexes -----------------------------------------------------------

EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)

# Loosely matches international / US-style phone numbers with 7-15 digits,
# allowing spaces, dashes, dots, parens, and a leading +.
PHONE_RE = re.compile(
    r"(?<!\d)(\+?\d{1,3}[\s.\-]?)?(\(?\d{2,4}\)?[\s.\-]?){2,4}\d{2,4}(?!\d)"
)

# Domains/prefixes that show up in HTML but are not real contact emails
EMAIL_JUNK_PATTERNS = (
    "example.com", "sentry.io", "wixpress.com", "godaddy.com",
    "schema.org", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
    "yourname@", "email@", "name@",
)

SOCIAL_PATTERNS = {
    "facebook": re.compile(r"https?://(www\.)?facebook\.com/[^\s\"'<>]+", re.I),
    "instagram": re.compile(r"https?://(www\.)?instagram\.com/[^\s\"'<>]+", re.I),
    "twitter": re.compile(r"https?://(www\.)?(twitter\.com|x\.com)/[^\s\"'<>]+", re.I),
    "whatsapp": re.compile(
        r"https?://(wa\.me|api\.whatsapp\.com|web\.whatsapp\.com)/[^\s\"'<>]+", re.I
    ),
    "linkedin": re.compile(
        r"https?://([a-z]{2,3}\.)?linkedin\.com/(company|in|showcase)/[^\s\"'<>]+", re.I
    ),
}

# Marketplaces a brand might sell through *instead of* (or alongside) its own
# storefront. Used to flag "marketplace-only" sellers -- a Browntape OMS fit.
MARKETPLACE_PATTERNS = {
    "amazon": re.compile(r"https?://(www\.)?amazon\.(in|com)/[^\s\"'<>]+", re.I),
    "flipkart": re.compile(r"https?://(www\.)?flipkart\.com/[^\s\"'<>]+", re.I),
    "myntra": re.compile(r"https?://(www\.)?myntra\.com/[^\s\"'<>]+", re.I),
    "ajio": re.compile(r"https?://(www\.)?ajio\.com/[^\s\"'<>]+", re.I),
    "nykaa": re.compile(r"https?://(www\.)?nykaafashion\.com/[^\s\"'<>]+", re.I),
}

# Phrases that indicate a physical, multi-location retail presence -- a
# signal for the Zwing POS (brick-and-mortar) pitch.
STORE_LOCATOR_KEYWORDS = (
    "store locator", "find a store", "find our stores", "our stores",
    "store near you", "nearest store", "visit our store", "store timings",
)


def _clean_email_list(raw_emails: List[str]) -> List[str]:
    seen = set()
    cleaned = []
    for e in raw_emails:
        e_norm = e.strip().strip(".,;:").lower()
        if any(junk in e_norm for junk in EMAIL_JUNK_PATTERNS):
            continue
        if e_norm in seen:
            continue
        seen.add(e_norm)
        cleaned.append(e_norm)
    return cleaned


def _clean_phone_list(raw_phones: List[str]) -> List[str]:
    seen = set()
    cleaned = []
    for p in raw_phones:
        digits = re.sub(r"\D", "", p)
        # Require a plausible phone-number length
        if not (7 <= len(digits) <= 15):
            continue
        p_norm = p.strip()
        key = digits
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(p_norm)
    return cleaned


def _extract_jsonld_address(soup: BeautifulSoup) -> Optional[str]:
    for script in soup.find_all("script", {"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue

        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if not isinstance(item, dict):
                continue
            addr = item.get("address")
            if isinstance(addr, dict):
                parts = [
                    addr.get("streetAddress"),
                    addr.get("addressLocality"),
                    addr.get("addressRegion"),
                    addr.get("postalCode"),
                    addr.get("addressCountry"),
                ]
                parts = [str(p).strip() for p in parts if p]
                if parts:
                    return ", ".join(parts)
            elif isinstance(addr, str) and addr.strip():
                return addr.strip()
    return None


def _has_contact_form(soup: BeautifulSoup) -> bool:
    """
    Heuristic: does this page contain a <form> that looks like a contact
    form (has an email input, or its action/id/class mentions "contact")?
    """
    for form in soup.find_all("form"):
        action = (form.get("action") or "").lower()
        form_id = (form.get("id") or "").lower()
        form_class = " ".join(form.get("class") or []).lower()
        if any("contact" in field for field in (action, form_id, form_class)):
            return True
        if form.find("input", {"type": "email"}):
            return True
    return False


def _detect_marketplace_links(html: str) -> List[str]:
    found = []
    for name, pattern in MARKETPLACE_PATTERNS.items():
        if pattern.search(html):
            found.append(name)
    return found


def _detect_store_locator(soup: BeautifulSoup) -> bool:
    text = soup.get_text(" ").lower()
    if any(kw in text for kw in STORE_LOCATOR_KEYWORDS):
        return True
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        link_text = (a.get_text() or "").strip().lower()
        if any(kw.replace(" ", "-") in href or kw in link_text
               for kw in STORE_LOCATOR_KEYWORDS):
            return True
    return False


def _extract_jsonld_name(soup: BeautifulSoup) -> Optional[str]:
    for script in soup.find_all("script", {"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue

        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if not isinstance(item, dict):
                continue
            item_type = item.get("@type", "")
            if isinstance(item_type, list):
                type_match = any(
                    t in ("Organization", "Store", "WebSite", "OnlineStore")
                    for t in item_type
                )
            else:
                type_match = item_type in (
                    "Organization", "Store", "WebSite", "OnlineStore"
                )
            if type_match and item.get("name"):
                return str(item["name"]).strip()
    return None


def _extract_store_name(soup: BeautifulSoup, domain: str) -> str:
    name = _extract_jsonld_name(soup)
    if name:
        return name

    og_site = soup.find("meta", {"property": "og:site_name"})
    if og_site and og_site.get("content"):
        return og_site["content"].strip()

    if soup.title and soup.title.string:
        title = soup.title.string.strip()
        # Trim common " - Home" / " | Shop now" suffixes
        title = re.split(r"[\|\-–—:]", title)[0].strip()
        if title:
            return title

    return domain


def _extract_socials(html: str) -> dict:
    result = {
        "facebook": "", "instagram": "", "twitter": "",
        "whatsapp": "", "linkedin": "",
    }
    for key, pattern in SOCIAL_PATTERNS.items():
        match = pattern.search(html)
        if match:
            result[key] = match.group(0).rstrip("/\"'")
    return result


def extract_domain(url: str) -> str:
    netloc = urlparse(url).netloc or urlparse(f"//{url}").netloc
    return netloc.lower().lstrip("www.")


# Keywords used to spot "contact us" / "about us" style links in nav/footer
CONTACT_LINK_KEYWORDS = (
    "contact", "about", "support", "help", "customer-service",
    "customer-care", "reach-us", "get-in-touch",
)

# Common contact-page paths to try even if no matching link is found,
# since many storefronts (e.g. Shopify) use predictable URLs.
COMMON_CONTACT_PATHS = (
    "/contact", "/contact-us", "/pages/contact", "/pages/contact-us",
    "/about", "/about-us", "/pages/about", "/pages/about-us",
)


def discover_contact_links(html: str, base_url: str, limit: int = 5) -> List[str]:
    """
    Find same-domain links on the page whose href or link text suggests a
    contact/about page (these tend to carry additional emails/phones that
    don't appear on the homepage).
    """
    soup = BeautifulSoup(html, "lxml")
    base_domain = extract_domain(base_url)

    found = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue

        text = (a.get_text() or "").strip().lower()
        href_lower = href.lower()

        if not any(kw in href_lower or kw in text for kw in CONTACT_LINK_KEYWORDS):
            continue

        absolute = urljoin(base_url, href)
        if extract_domain(absolute) != base_domain:
            continue  # stay on the same site

        if absolute not in seen:
            seen.add(absolute)
            found.append(absolute)

        if len(found) >= limit:
            break

    return found


def candidate_contact_urls(base_url: str) -> List[str]:
    """Predictable contact/about paths to try as a fallback."""
    scheme_domain = f"{urlparse(base_url).scheme}://{extract_domain(base_url)}"
    return [scheme_domain + path for path in COMMON_CONTACT_PATHS]


def extract_fields(html: str, page_url: str) -> dict:
    """
    Parse a single HTML page and return a dict with:
    storeName, emails, phones, facebook, instagram, twitter, whatsapp,
    linkedin, address, hasContactForm, url
    """
    soup = BeautifulSoup(html, "lxml")
    domain = extract_domain(page_url)

    # Emails: mailto: links first (highest confidence), then body text
    mailto_emails = [
        a["href"].split("mailto:")[1].split("?")[0]
        for a in soup.select('a[href^="mailto:"]')
        if a.get("href")
    ]
    text_emails = EMAIL_RE.findall(soup.get_text(" "))
    emails = _clean_email_list(mailto_emails + text_emails)

    # Phones: tel: links first, then body text
    tel_phones = [
        a["href"].split("tel:")[1]
        for a in soup.select('a[href^="tel:"]')
        if a.get("href")
    ]
    text_phones = PHONE_RE.findall(soup.get_text(" "))
    # PHONE_RE with groups returns tuples; re-search plainly instead
    text_phones_plain = [m.group(0) for m in PHONE_RE.finditer(soup.get_text(" "))]
    phones = _clean_phone_list(tel_phones + text_phones_plain)

    socials = _extract_socials(html)
    store_name = _extract_store_name(soup, domain)
    address = _extract_jsonld_address(soup) or ""
    has_contact_form = _has_contact_form(soup)
    marketplace_links = _detect_marketplace_links(html)
    has_store_locator = _detect_store_locator(soup)

    return {
        "storeName": store_name,
        "domain": domain,
        "emails": emails,
        "phones": phones,
        "address": address,
        "hasContactForm": has_contact_form,
        "marketplaceLinks": marketplace_links,
        "hasStoreLocator": has_store_locator,
        "url": page_url,
        **socials,
    }


def merge_fields(pages: List[dict]) -> dict:
    """
    Combine extract_fields() results from multiple pages of the same site
    into one aggregated result: union of emails/phones (order-preserved,
    deduped), first non-empty social link, first non-empty address, the
    URL of the first page with a detected contact form, and the first
    non-fallback storeName found.
    """
    all_emails: List[str] = []
    all_phones: List[str] = []
    socials = {
        "facebook": "", "instagram": "", "twitter": "",
        "whatsapp": "", "linkedin": "",
    }
    store_name = ""
    domain = ""
    address = ""
    contact_form_url = ""
    marketplace_links: List[str] = []
    has_store_locator = False

    for page in pages:
        all_emails.extend(page.get("emails", []))
        all_phones.extend(page.get("phones", []))
        for key in socials:
            if not socials[key] and page.get(key):
                socials[key] = page[key]
        if not domain and page.get("domain"):
            domain = page["domain"]
        if not store_name and page.get("storeName") and page["storeName"] != domain:
            store_name = page["storeName"]
        if not address and page.get("address"):
            address = page["address"]
        if not contact_form_url and page.get("hasContactForm") and page.get("url"):
            contact_form_url = page["url"]
        for mkt in page.get("marketplaceLinks", []):
            if mkt not in marketplace_links:
                marketplace_links.append(mkt)
        if page.get("hasStoreLocator"):
            has_store_locator = True

    if not store_name:
        store_name = pages[0].get("storeName", "") if pages else domain

    return {
        "storeName": store_name,
        "domain": domain,
        "emails": _clean_email_list(all_emails),
        "phones": _clean_phone_list(all_phones),
        "address": address,
        "contactFormUrl": contact_form_url,
        "marketplaceLinks": marketplace_links,
        "hasStoreLocator": has_store_locator,
        **socials,
    }
