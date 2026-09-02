import requests
import json

headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

api_endpoints = [
    "https://docs.tibco.com/api/a_to_z",
    "https://docs.tibco.com/api/bu_category_products",
    "https://docs.tibco.com/api/products/tibco-businessevents-enterprise-edition-6-4-0",
    "https://docs.tibco.com/api/products/archive/tibco-businessevents-enterprise-edition",
    "https://docs.tibco.com/api/product_list_by_suites"
]

for url in api_endpoints:
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        print("="*60)
        print(f"URL: {url} | Status: {resp.status_code}")
        if resp.status_code == 200:
            try:
                data = resp.json()
                print("JSON Type:", type(data))
                if isinstance(data, list):
                    print("List len:", len(data))
                    if data:
                        print("Sample item:", json.dumps(data[0], indent=2)[:400])
                elif isinstance(data, dict):
                    print("Dict keys:", list(data.keys()))
                    print("Sample data:", json.dumps(data, indent=2)[:400])
            except Exception as e:
                print("Failed to parse JSON:", e, resp.text[:200])
    except Exception as e:
        print(f"Error fetching {url}: {e}")
