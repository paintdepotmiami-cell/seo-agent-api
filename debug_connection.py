"""
Debug script to test WordPress API connection
"""
import requests
import yaml

# Load config
with open("config/projects/pavers_miami.yaml") as f:
    conf = yaml.safe_load(f)

base_url = conf['site']['url'].rstrip('/')
api_conf = conf.get('api', {})

print(f"🕵️ Testing connection to: {base_url}")
print(f"   Username: {api_conf.get('username', 'NOT SET')}")

# Headers to mimic browser
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

# Auth if available
auth = None
if api_conf.get('username') and api_conf.get('app_password'):
    auth = (api_conf['username'], api_conf['app_password'])
    print("   Auth: Using credentials")

# Test endpoints
endpoints = {
    "posts": "wp/v2/posts",
    "pages": "wp/v2/pages",
}

for label, ep in endpoints.items():
    url = f"{base_url}/wp-json/{ep}"
    print(f"\n📡 Testing '{label}' -> {url} ...")
    try:
        r = requests.get(url, headers=headers, auth=auth, params={"per_page": 2}, timeout=30)
        print(f"   Status: {r.status_code}")
        print(f"   Content-Type: {r.headers.get('Content-Type', 'Unknown')[:50]}")
        
        if r.status_code == 200:
            try:
                data = r.json()
                if data and len(data) > 0:
                    title = data[0].get('title', {}).get('rendered', 'No title')
                    print(f"   ✅ SUCCESS! Found: '{title[:50]}'")
                    print(f"   Total items in response: {len(data)}")
                else:
                    print("   ⚠️ OK (200) but empty list.")
            except Exception as e:
                print(f"   ❌ JSON parse error: {e}")
                print(f"   Response preview: {r.text[:200]}")
        else:
            print(f"   ❌ HTTP ERROR {r.status_code}")
            print(f"   Response preview: {r.text[:200]}")
    except Exception as e:
        print(f"   🔥 EXCEPTION: {e}")

print("\n" + "="*50)
print("If you see HTML responses, SiteGround WAF is blocking Python requests.")
print("Try: pip install cloudscraper")
