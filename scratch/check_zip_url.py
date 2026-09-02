import requests
import json

headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
resp = requests.get("https://docs.tibco.com/api/products/tibco-businessevents-enterprise-edition-6-4-0", headers=headers)
data = resp.json()["result"]["product"]

print("folder_path:", data.get("folder_path"))
print("short_name:", data.get("short_name"))
print("isArchiveExists:", data.get("isArchiveExists"))
print("published_date:", data.get("published_date"))
print("releaseDate:", data.get("releaseDate"))

# Check Documents list
docs = data.get("Documents", [])
print(f"Total Documents: {len(docs)}")
for d in docs[:5]:
    print("Document:", d.get("name"), "| path:", d.get("path") or d.get("file_path"), "| type:", d.get("type"))

# Check how zip is formed or downloaded:
# In docs.tibco.com, it is typically:
# https://docs.tibco.com/pub/{short_name}/{version_no}/doc/zip/tib_{short_name}_{version_no}_doc.zip
# or https://docs.tibco.com/pub/{folder_path}/doc/zip/...
print("folder_path pattern test:")
folder_path = data.get("folder_path")
version = data.get("version_no")
short_name = data.get("short_name")
candidates = [
    f"https://docs.tibco.com/pub/{folder_path}/doc/zip/{folder_path.replace('/', '_')}_doc.zip",
    f"https://docs.tibco.com/pub/{folder_path}/doc/zip/tib_{folder_path.replace('/', '_')}_doc.zip",
    f"https://docs.tibco.com/pub/{short_name}/{version}/doc/zip/tib_{short_name}_{version}_doc.zip"
]
for c in candidates:
    head_resp = requests.head(c, headers=headers)
    print(f"ZIP Check: {c} -> Status: {head_resp.status_code}")
