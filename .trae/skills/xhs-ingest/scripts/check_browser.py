import json, urllib.request

CDP_URL = "http://localhost:9223"

req = urllib.request.Request(f'{CDP_URL}/json/list')
with urllib.request.urlopen(req, timeout=5) as resp:
    pages = json.loads(resp.read().decode())

for p in pages:
    if 'xiaohongshu.com' in p.get('url', ''):
        print(f"URL: {p['url']}")
        print(f"Title: {p.get('title', 'N/A')}")
        break
else:
    print("No xiaohongshu page found")
