import os
import sys
import csv
from urllib.parse import urlparse

# Force local workspace module visibility
current_workspace = os.path.dirname(os.path.abspath(__file__))
if current_workspace not in sys.path:
    sys.path.insert(0, current_workspace)

# Import the correct architectural units from your local scraper modules
from scraper.pipeline import scrape_store
from scraper.fetcher import Fetcher

# ==========================================
# DATASET: The 50-Site Multi-Segment Pack
# ==========================================
STARTER_PACK_URLS = [
    # Segment A: Mid-to-Large D2C Brands (Full Suite Fits)
    "https://www.snitch.co.in", "https://www.thesouledstore.com", "https://www.bewakoof.com",
    "https://bummer.in", "https://www.damensch.com", "https://blissclub.in",
    "https://fablestreet.com", "https://www.bombayshirtcompany.com", "https://neemans.com",
    "https://www.solethreads.com", "https://suta.in", "https://www.faballey.com",
    "https://www.thelabellife.com", "https://www.powerlook.in", "https://www.rareabbit.in",
    "https://www.vegnonveg.com", "https://www.superkicks.in", "https://www.urbanmonkey.com",
    
    # Segment B: Brick-and-Mortar Heavy Footprints (Zwing mPOS / Web POS Fits)
    "https://www.shoppersstop.com", "https://www.pantaloons.com", "https://www.maxfashion.in",
    "https://www.manyavar.com", "https://www.fabindia.com", "https://www.blackberrys.com",
    "https://www.peterengland.com", "https://www.louisphilippe.com", "https://www.vanheusenindia.com",
    "https://www.allensolly.com", "https://www.woodlandworldwide.com", "https://www.bata.com/in/",
    "https://www.metroshoes.com", "https://www.mochishoes.com", "https://www.cantabilinternational.com",
    "https:// Montecarlo.in", "https://www.spykar.com",
    
    # Segment C: Omnichannel & Marketplace Heavy (Browntape Fits)
    "https://www.campusshoes.com", "https://www.sparxshoes.com", "https://www.khadims.com",
    "https://www.libertyshoesonline.com", "https://www.westsidestores.com", "https://www.wforwoman.com",
    "https://www.aurelia.com", "https://www.chumbak.com", "https://www.libas.in"
]

def clean_and_validate_urls(raw_urls):
    """Normalizes and deduplicates an incoming list of URLs."""
    valid_urls = []
    for url in raw_urls:
        url = url.strip()
        if not url or url.startswith("#"):
            continue
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        
        parsed = urlparse(url)
        if parsed.netloc:
            clean_url = f"https://{parsed.netloc}{parsed.path}".rstrip("/")
            if clean_url not in valid_urls:
                valid_urls.append(clean_url)
    return valid_urls

def process_nykaa_extracted_list():
    """Reads the extracted Nykaa CSV and auto-resolves brand names to Indian domains."""
    nykaa_csv = "nykaa_extracted_brands.csv"
    if not os.path.exists(nykaa_csv):
        print(f"\n❌ Error: '{nykaa_csv}' not found.")
        print("💡 Run 'python generate_mock_nykaa.py' first to build this asset.")
        return []

    print(f"\n📊 Parsing local marketplace data from {nykaa_csv}...")
    resolved_domains = []
    
    with open(nykaa_csv, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            brand_name = row.get("Brand Name", "").strip()
            if not brand_name:
                continue
            
            slug = brand_name.lower().replace(" ", "").replace("'", "").replace("&", "and")
            predicted_url = f"https://www.{slug}.in"
            
            if "souledstore" in slug:
                predicted_url = "https://www.thesouledstore.com"
            elif "shoppers" in slug:
                predicted_url = "https://www.shoppersstop.com"
            elif "jack" in slug and "jones" in slug:
                predicted_url = "https://www.jackjones.in"
            elif "levis" in slug:
                predicted_url = "https://www.levi.in"
                
            resolved_domains.append(predicted_url)
            
    return list(set(resolved_domains))

def run_multi_url_pipeline(urls, output_filename):
    """Loops through a collection of target websites, scrapes each, and exports sorted leads."""
    cleaned_list = clean_and_validate_urls(urls)
    if not cleaned_list:
        print("\n⚠️ Operation cancelled: No valid domains found.")
        return

    print(f"\n🚀 Launching Scraper Engine for {len(cleaned_list)} targets...")
    
    # Instantiate the Fetcher class dependency required by scrape_store
    fetcher_instance = Fetcher()
    processed_records = []

    for index, target_url in enumerate(cleaned_list, start=1):
        print(f" [{index}/{len(cleaned_list)}] Processing: {target_url}...")
        try:
            # Calls your local package pipeline logic
            store_record = scrape_store(fetcher=fetcher_instance, raw_url=target_url)
            
            # Convert the StoreRecord model object into a dictionary for CSV writing
            # Handling fallback tracking attributes safely if missing from object model maps
            record_dict = {
                "url": store_record.url,
                "domain": store_record.domain,
                "storeName": getattr(store_record, 'storeName', store_record.domain),
                "emails": ", ".join(getattr(store_record, 'emails', [])),
                "phones": ", ".join(getattr(store_record, 'phones', [])),
                "productCount": getattr(store_record, 'productCount', 'Unknown'),
                "score": getattr(store_record, 'score', 0),
                "pitchType": getattr(store_record, 'pitchType', 'Unclassified'),
                "error": getattr(store_record, 'error', '')
            }
            processed_records.append(record_dict)
        except Exception as e:
            print(f"  ❌ Error skipping {target_url}: {e}")

    if not processed_records:
        print("⚠️ No leads were successfully extracted.")
        return

    # Sort the data dynamically by Lead Score in descending order (highest score first)
    processed_records.sort(key=lambda x: x.get("score", 0), reverse=True)

    # Save to disk
    field_headers = ["url", "domain", "storeName", "emails", "phones", "productCount", "score", "pitchType", "error"]
    with open(output_filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=field_headers)
        writer.writeheader()
        writer.writerows(processed_records)

    print(f"\n✅ Operation Complete! Exported and sorted leads directly into: {output_filename}")

def display_menu():
    print("\n" + "="*55)
    print("      GINESYS ONE LEAD EXTRACTOR & SCORING PIPELINE")
    print("="*55)
    print("1) Run Curated 50-Site Starter Pack (Full Framework Verification)")
    print("2) Run Processed Nykaa Marketplace Brands (Auto-Domain Resolution)")
    print("3) Run Custom External Target File (targets.txt)")
    print("4) Exit Terminal")
    print("="*55)

def main():
    while True:
        display_menu()
        choice = input("Select an option (1-4): ").strip()
        
        if choice == "1":
            print("\n🔄 Selected Option 1: Curated 50-Site Starter Pack.")
            run_multi_url_pipeline(STARTER_PACK_URLS, "ginesys_starter_pack_scored.csv")
            
        elif choice == "2":
            print("\n🔄 Selected Option 2: Processing Nykaa Marketplace Records.")
            nykaa_domains = process_nykaa_extracted_list()
            if nykaa_domains:
                print(f"🎯 Auto-converted brand names into {len(nykaa_domains)} standalone domains.")
                run_multi_url_pipeline(nykaa_domains, "ginesys_nykaa_leads_scored.csv")
                
        elif choice == "3":
            print("\n🔄 Selected Option 3: Loading custom external targets.txt file.")
            filename = "targets.txt"
            if not os.path.exists(filename):
                with open(filename, "w") as f:
                    f.write("# Paste your target website domains here (one per line)\n")
                    f.write("https://www.snitch.co.in\n")
                print(f"📝 Template generated as '{filename}'. Add your domains to it and run choice 3 again.")
                continue
                
            with open(filename, "r") as f:
                external_urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
                
            print(f"🎯 Loaded {len(external_urls)} target entries from file.")
            run_multi_url_pipeline(external_urls, "ginesys_custom_leads_scored.csv")
            
        elif choice == "4":
            print("\n👋 Terminating extractor workspace pipeline. Safe selling!")
            break
        else:
            print("\n⚠️ Invalid selection. Input a value between 1 and 4.")

if __name__ == "__main__":
    main()