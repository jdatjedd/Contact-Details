import csv
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

def harvest_nykaa_brands():
    target_url = "https://www.nykaafashion.com/cp/sitemap"
    output_csv = "nykaa_extracted_brands.csv"
    discovered_brands = []

    print("🚀 Initializing stealth headless browser pipeline...")
    
    with sync_playwright() as p:
        # Launch with specific arguments to bypass HTTP/2 stream fingerprinting
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-http2",                      # FORCES HTTP/1.1 to bypass Akamai stream dropping
                "--disable-blink-features=AutomationControlled", # Removes the navigator.webdriver flag
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )
        
        # Emulate a true clean desktop session context
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900},
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache"
            }
        )
        
        page = context.new_page()
        
        print(f"🌐 Navigating to {target_url}...")
        try:
            # Shift from 'networkidle' to 'domcontentloaded' to extract data before trackers block execution
            page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
            
            # Allow a brief structural pause for any trailing localized elements
            page.wait_for_timeout(3000)
            
            html_content = page.content()
            print("✅ Page HTML successfully captured without firewall blocks. Parsing DOM...")
            
        except Exception as e:
            print(f"❌ Playwright navigation failed: {e}")
            browser.close()
            return

        browser.close()

    # Pass the markup to BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    all_links = soup.find_all('a')
    
    for link in all_links:
        href = link.get('href', '').strip()
        brand_name = link.get_text(strip=True)
        
        if not href or not brand_name or len(brand_name) < 2:
            continue
            
        is_generic_tab = any(keyword in href.lower() for keyword in [
            '/cp/', '/lp/', '/women', '/men', '/kids', 'track-order', 
            'account', 'cart', 'terms', 'privacy', 'help', 'contact'
        ])
        
        if not is_generic_tab:
            absolute_url = urljoin("https://www.nykaafashion.com", href)
            discovered_brands.append({
                "Brand Name": brand_name,
                "Nykaa Marketplace URL": absolute_url
            })

    # Deduplicate entries based on Brand Name
    unique_brands = {b['Brand Name']: b for b in discovered_brands}.values()
    final_list = list(unique_brands)

    if final_list:
        keys = final_list[0].keys()
        with open(output_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(final_list)
        print(f"📝 Success! Extracted {len(final_list)} brands and saved to {output_csv}")
    else:
        print("⚠️ No brand links found. The structure may have changed, or an empty page was loaded.")

if __name__ == "__main__":
    harvest_nykaa_brands()