"""Quick test of WordPress API with auth"""
import yaml
import requests
import ssl
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager

class TLSAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        ctx = ssl.create_default_context()
        ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        ctx.options |= ssl.OP_NO_SSLv2
        ctx.options |= ssl.OP_NO_SSLv3
        ctx.options |= ssl.OP_NO_TLSv1
        ctx.options |= ssl.OP_NO_TLSv1_1
        self.poolmanager = PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            ssl_version=ssl.PROTOCOL_TLSv1_2,
            ssl_context=ctx
        )

# Load config
with open("config/projects/pavers_miami.yaml") as f:
    config = yaml.safe_load(f)

print(f"Site: {config['site']['url']}")
print(f"API Config: {config.get('api', {})}")

api = config.get('api', {})
username = api.get('username', '')
password = api.get('app_password', '')

print(f"\nUsername: '{username}'")
print(f"Password: '{password[:10]}...' (truncated)")

# Create session with TLS adapter
session = requests.Session()
session.mount('https://', TLSAdapter())
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json"
})

# Set auth
if username and password:
    session.auth = (username, password)
    print(f"\n🔐 Auth set for: {username}")

# Test request
url = f"{config['site']['url'].rstrip('/')}/wp-json/wp/v2/posts"
print(f"\n🌐 Testing: {url}")

try:
    resp = session.get(url, params={"per_page": 1}, timeout=30)
    print(f"Status: {resp.status_code}")
    print(f"Content-Type: {resp.headers.get('Content-Type', 'Unknown')}")
    
    if resp.status_code == 200:
        data = resp.json()
        if data:
            print(f"✅ SUCCESS! Found: {data[0]['title']['rendered'][:50]}")
        else:
            print("⚠️ Empty response")
    else:
        print(f"❌ Error: {resp.text[:300]}")
        
except Exception as e:
    print(f"🔥 Exception: {e}")
