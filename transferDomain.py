import json

with open("domains.txt", "r", encoding="utf-8") as f:
    domains = [line.strip() for line in f if line.strip()]

# Write one-line (horizontal) JSON to domains.json
with open("domains.json", "w", encoding="utf-8") as out:
    out.write(json.dumps(domains))
