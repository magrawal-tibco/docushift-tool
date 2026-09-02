import requests
import json

headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
resp = requests.get("https://docs.tibco.com/api/products/archive/tibco-businessevents-enterprise-edition", headers=headers)
data = resp.json()["result"]["product"]
sample_child = data["children"][0]
print("Child keys:", list(sample_child.keys()))
print("Sample child data:", json.dumps(sample_child, indent=2))
