import requests
import pandas as pd

API_KEY = "YOUR_GOOGLE_PLACES_API_KEY"
URL = "https://places.googleapis.com/v1/places:searchText"

# Commercial hubs across Maharashtra to mine for high-volume local retail
cities = [
    "Mumbai", "Pune", "Thane", "Nagpur", "Nashik", 
    "Aurangabad", "Kolhapur", "Solapur", "Amravati", "Jalgaon"
]

# Comprehensive corporate, national, and international brand exclusion list
NATIONAL_AND_GLOBAL_CHAINS = [
    # --- Mega Fast Fashion & Department Stores ---
    "zara", "h&m", "hm", "westside", "trends", "reliance", "max fashion", "max",
    "pantaloons", "shoppers stop", "lifestyle", "decathlon", "v-mart", "zudio", 
    "unqilo", "marks & spencer", "marks and spencer", "m&s", "globus", "fbb", "v2 retail",
    
    # --- Corporate Premium Apparel Brands ---
    "allen solly", "louis philippe", "van heusen", "peter england", "arrow", 
    "blackberrys", "raymond", "park avenue", "parx", "colorplus", "tommy hilfiger", 
    "calvin klein", "ck", "levis", "levi's", "pepe jeans", "spykar", "wrangler", 
    "lee", "ucb", "united colors of benetton", "jack & jones", "jack and jones",
    
    # --- Corporate Ethnic & Bridal Chains ---
    "manyavar", "mohey", "fabindia", "w for woman", "w", "aurelia", "biba", 
    "soch", "neerus", "neeru's", "global desi", "anita dongre", "ritu kumar", 
    "taneira", "kalyan silks", "pothys", "rmkv",
    
    # --- Footwear & Sports Giants ---
    "bata", "mochi", "metro shoes", "khadims", "liberty", "woodland", 
    "adidas", "nike", "puma", "skechers", "asics", "reebok", "under armour"
]

standalone_leads = []
'''
headers = {
    "Content-Type": "application/json",
    "X-Goog-Api-Key": API_KEY,
    "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.nationalPhoneNumber,places.rating,places.userRatingCount,places.primaryType"
}
'''
headers = {
    "Content-Type": "application/json",
    "X-Goog-Api-Key": API_KEY,
    # Crucial: NO spaces allowed after the commas here
    "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.nationalPhoneNumber,places.rating,places.userRatingCount,places.primaryType"
}
print("Starting deep lead extraction for standalone retail...")

for city in cities:
    print(f"Scanning {city}...")
    
    # Using high-intent search queries that skew toward traditional and local markets
    queries = [
        f"clothing store matching center saree emporium in {city} maharashtra",
        f"footwear shop multi brand apparel showroom in {city} maharashtra"
    ]
    
    for query in queries:
        payload = {"textQuery": query, "languageCode": "en"}
        response = requests.post(URL, json=payload, headers=headers)
        
        if response.status_code == 200:
            places = response.json().get("places", [])
            
            for place in places:
                name = place.get("displayName", {}).get("text", "")
                review_count = place.get("userRatingCount", 0)
                
                # Check 1: Must hit the high-footfall benchmark (>= 200 reviews)
                if review_count >= 200:
                    
                    # Check 2: Normalize string to prevent corporate matches
                    normalized_name = name.lower().strip()
                    
                    # Exact word matching to prevent accidentally filtering out local stores 
                    # (e.g., filtering out "Max" shouldn't filter out "Maximus Boutique")
                    is_chain = False
                    for chain in NATIONAL_AND_GLOBAL_CHAINS:
                        if chain in normalized_name:
                            # Verify if it is a standalone word or direct match
                            if f" {chain} " in f" {normalized_name} ":
                                is_chain = True
                                break
                    
                    if not is_chain:
                        lead = {
                            "Store Name": name,
                            "City": city,
                            "Total Reviews": review_count,
                            "Rating": place.get("rating", "N/A"),
                            "Phone": place.get("nationalPhoneNumber", "N/A"),
                            "Address": place.get("formattedAddress", "N/A")
                        }
                        # Prevent duplicate entries from multiple query structures
                        if lead not in standalone_leads:
                            standalone_leads.append(lead)
        else:
            print(f"Error querying for {city}: {response.status_code}")

# Output cleanly extracted data
if standalone_leads:
    df = pd.DataFrame(standalone_leads)
    df.to_csv("maharashtra_pure_standalone_retail.csv", index=False)
    print(f"\nSuccess! Filtered out corporate chains.")
    print(f"Saved {len(df)} highly qualified, independent retail leads to 'maharashtra_pure_standalone_retail.csv'.")
else:
    print("\nNo leads matched the strict criteria.")