import requests
import json

headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
resp = requests.get("https://docs.tibco.com/api/products/archive/tibco-businessevents-enterprise-edition", headers=headers)
data = resp.json()["result"]["product"]

print("Archive Product:", data.get("name"))
print("Archived children count:", len(data.get("children", [])))
for ch in data.get("children", [])[:10]:
    print(" - Version:", ch.get("version_no"), "| Name:", ch.get("name"), "| folder_path:", ch.get("folder_path"), "| isArchive:", ch.get("isArchive"))
