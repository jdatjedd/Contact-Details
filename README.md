# store-scraper

Extracts contact/profile info from e-commerce store URLs using **raw HTTP**
(via `requests`) instead of a headless browser (no Puppeteer/Playwright).
Results are exported to CSV in a fixed schema.

## Output fields

| Field | Description |
|---|---|
| `storeName` | Store name from JSON-LD, `og:site_name`, or `<title>` |
| `domain` | Clean hostname of the store |
| `email` | First email found (primary contact) |
| `emails` | All emails found across the homepage + contact/about pages, `;`-separated |
| `phone` | First phone number found |
| `phones` | All phone numbers found across the homepage + contact/about pages, `;`-separated |
| `facebook` / `instagram` / `twitter` | Social profile URLs, if present |
| `whatsapp` | WhatsApp click-to-chat link (`wa.me/...` or `api.whatsapp.com/...`), if present |
| `linkedin` | LinkedIn company (or personal) page URL, if present |
| `address` | Postal address from JSON-LD `PostalAddress`, if present |
| `contactFormUrl` | URL of the first page found with a contact-style `<form>`, if no email is available |
| `productCount` | `Active`, `Hidden`, or `Unknown` — based on whether a public product catalog endpoint (`/products.json`) is reachable |
| `score` | 0-100 lead-completeness score (see below) |
| `pitchType` | `Full Suite`, `Browntape`, `Zwing POS`, or `Needs Review` (see below) |
| `url` | Source URL scraped |
| `scrapedAt` | UTC ISO-8601 timestamp of the scrape |

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
# From a file of URLs (one per line, # for comments)
python main.py --input data/sample_urls.txt --output output/results.csv

# From explicit URLs on the command line (repeatable)
python main.py --url https://store1.com --url https://store2.com

# Combine both — deduplicated automatically
python main.py --input data/sample_urls.txt --url https://extra-store.com

# Tune politeness / retries
python main.py --input data/sample_urls.txt --delay-min 2 --delay-max 5 --retries 5 -v

# Control how many extra pages (contact/about) are checked per site
python main.py --input data/sample_urls.txt --max-pages 5
```

## Multi-page contact discovery

A single homepage often doesn't have every email/phone number — many
stores put sales, support, and wholesale contacts on a separate `/contact`
or `/about` page. So for each site, the scraper:

1. Fetches the homepage and extracts whatever it finds there.
2. Looks for on-page nav/footer links whose text or URL suggests a
   contact/about page (`discover_contact_links`).
3. Tops up with common predictable paths (`/contact`, `/contact-us`,
   `/pages/contact-us`, `/about-us`, etc.) if fewer links were found than
   the `--max-pages` budget.
4. Fetches each extra page (same rate-limiting/retry rules apply) and
   merges the results: emails and phones are unioned and de-duplicated
   across all pages; the first non-empty social link and store name win.

`--max-pages` (default `3`) caps how many extra pages are visited per
site, keeping the added requests bounded and polite.

## How it works

1. **`scraper/fetcher.py`** — a `requests.Session`-based fetcher that rotates
   user agents, spaces out requests (configurable random delay), and retries
   with exponential backoff on `429`/`5xx`/network errors.
2. **`scraper/extractor.py`** — parses the fetched HTML with BeautifulSoup,
   pulling store name from JSON-LD / meta tags / title, and finding emails,
   phone numbers, and social links via `mailto:`/`tel:` links plus regex over
   the page text, with basic junk filtering (placeholder emails, image
   filenames, etc).
3. **`scraper/catalog.py`** — checks the store's `/products.json` endpoint to
   classify the catalog as `Active` / `Hidden` / `Unknown`. It does not
   attempt to bypass password screens or anti-bot challenges — a protected
   store is simply reported as `Hidden`.
4. **`scraper/pipeline.py`** — orchestrates the above into a single
   `StoreRecord` per URL.
5. **`scraper/exporter.py`** — writes all records to CSV.

## Notes on rate limiting & anti-bot behavior

- Requests are spaced out with a random delay (`--delay-min`/`--delay-max`)
  rather than fired back-to-back.
- On `429`/`5xx` responses, the fetcher backs off exponentially and retries
  up to `--retries` times before giving up on that URL (recorded as an
  `error` rather than crashing the whole run).
- This tool does **not** attempt to defeat CAPTCHAs, spoof TLS fingerprints,
  or otherwise circumvent bot-detection systems — if a site actively blocks
  the request, that URL is recorded as a failure/`Unknown` rather than
  forced through.
- Always check the target site's `robots.txt` and terms of service, and
  scrape only data you have a legitimate right to collect.

## Lead scoring & pitch tagging

Each record gets two extra fields to help triage a large CSV instead of
reading every row manually:

**`score` (0-100)** — how complete/reachable the lead is:

| Signal found | Points |
|---|---|
| Active online product catalog | +30 |
| At least one email | +20 |
| At least one phone number | +15 |
| Any social link (FB/IG/X/WhatsApp/LinkedIn) | +10 |
| Postal address | +10 |
| Store-locator page detected | +15 |

Output is sorted by `score` descending, so the most outreach-ready leads
are at the top of the CSV.

**`pitchType`** — which Ginesys product angle fits, based on the signals
above:

| Value | Meaning | Signal |
|---|---|---|
| `Full Suite` | Has its own active online catalog — full ERP+POS+OMS conversation | `/products.json` returns products |
| `Browntape` | Sells through marketplaces (Amazon/Flipkart/Myntra/Ajio) but has no independent storefront catalog | Marketplace links found, no active catalog |
| `Zwing POS` | Physical, multi-location presence but no working online catalog | Store-locator page found, no active catalog |
| `Needs Review` | Not enough signal to classify confidently | None of the above — a human should look before outreach |

**This is a heuristic for sorting, not a certainty.** A site with `Unknown`
catalog status just means the `/products.json` check failed or the store
isn't on that platform — always spot-check before treating `pitchType` as
final, especially for `Needs Review` rows.

## Tests

```bash
python -m pytest tests/
```

## Project layout

```
store-scraper/
├── main.py                  # CLI entry point
├── requirements.txt
├── scraper/
│   ├── fetcher.py            # raw HTTP + rate limiting + retries
│   ├── extractor.py          # HTML/JSON-LD parsing, email/phone/social regex
│   ├── catalog.py            # productCount (Active/Hidden) check
│   ├── pipeline.py           # orchestrates fetch -> extract -> record
│   ├── models.py             # StoreRecord dataclass
│   └── exporter.py           # CSV export
├── data/
│   └── sample_urls.txt
├── tests/
│   └── test_extractor.py
└── output/                   # CSV results land here
```
