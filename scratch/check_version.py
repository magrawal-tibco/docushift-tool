import requests
import json

headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
resp = requests.get("https://docs.tibco.com/api/products/tibco-businessevents-enterprise-edition-6-4-0", headers=headers)
data = resp.json()["result"]["product"]

print("Product Name:", data.get("name"))
print("Version:", data.get("version_no"))
print("Slug:", data.get("slug"))
print("Parent Slug:", data.get("parent_slug") or data.get("parent_name"))
print("Keys in product:", list(data.keys()))

# Check for download link or zip
for k in ["download_link", "zip_file", "zip_path", "doc_zip", "docs_link", "file_name", "url", "pdf_link"]:
    if k in data:
        print(f"{k}: {data[k]}")

# Check siblings or active versions in product data
print("\nActive versions/siblings info:")
if "siblings" in data:
    print("Siblings count:", len(data["siblings"]))
    for s in data["siblings"][:5]:
        print(" -", s.get("name"), "| version:", s.get("version_no"), "| slug:", s.get("slug"))

if "other_versions" in data:
    print("Other versions count:", len(data["other_versions"]))
