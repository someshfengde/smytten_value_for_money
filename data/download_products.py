import requests
import json

# Smytten endpoint and headers
smytten_url = "https://route.smytten.com/discover_item/app/products/list"
headers = {
    "accept": "application/json",
    "content-type": "application/json"
}

# Base payload with collection id and pagination details
payload = {
    "page": {"pageId": 0},
    "timestamp": 0,
    "id": "67a1f0a3bbdd3d0001b493c8"
}

all_collections = []

for page in range(0, 64):
    payload["page"]["pageId"] = page
    print(f"Scraping page {page}...")
    
    response = requests.post(smytten_url, json=payload, headers=headers)
    if response.status_code == 200:
        data = response.json()
        content = data.get("content", None)
        if content is None:
            print("  No 'content' field found on this page.")
        elif isinstance(content, list):
            # Process assuming content is a list of category dictionaries.
            for category in content:
                if not isinstance(category, dict):
                    print("  Skipping non-dict category item:", category)
                    continue
                category_name = category.get("category_name", "Unknown Category")
                for subcategory in category.get("subcategories", []):
                    subcategory_name = subcategory.get("subcategory_name", "Unknown Subcategory")
                    collections = subcategory.get("collections", [])
                    for collection in collections:
                        # Add context from parent category and subcategory.
                        collection["category_name"] = category_name
                        collection["subcategory_name"] = subcategory_name
                        all_collections.append(collection)
            print(f"  Total collections scraped so far: {len(all_collections)}")
        elif isinstance(content, dict):
            # In some cases, 'content' might be a dict.
            if not content:
                print(f"  Empty content dict on page {page}.")
            elif "products" in content:
                # In case the dict holds products directly.
                products = content.get("products", [])
                print(f"  Found {len(products)} products on page {page} via 'products' key.")
                all_collections.extend(products)
            else:
                # For debugging unexpected dict structures.
                print(f"  Unexpected content dict structure on page {page}: {json.dumps(content, indent=2)[:300]}")
        else:
            print(f"  Unexpected type for 'content': {type(content)} on page {page}")
    else:
        print(f"  Error on page {page}: HTTP {response.status_code}")

print(f"Total collections scraped: {len(all_collections)}")

# Save the aggregated data to a JSON file.
with open("all_collections.json", "w", encoding="utf-8") as f:
    json.dump(all_collections, f, ensure_ascii=False, indent=4)
