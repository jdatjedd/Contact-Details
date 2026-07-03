import requests
from bs4 import BeautifulSoup
import urllib.parse

def extract_domains_from_sitemap(sitemap_url):
    urls = []
    try:
        response = requests.get(sitemap_url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(response.content, 'xml')
        # Find all location tags in the XML
        for loc in soup.find_all('loc'):
            url = loc.text.strip()
            # Basic filter logic (e.g., looking for brand or store patterns)
            urls.append(url)
        print(f"Extracted {len(urls)} links from sitemap.")
        return urls
    except Exception as e:
        print(f"Error parsing sitemap: {e}")
        return []

# Example target: Swap out for open directory sitemaps like Indian retail listings
# sitemap_target = "https://example-retail-directory.in/sitemap_brands.xml"
# brand_links = extract_domains_from_sitemap(sitemap_target)