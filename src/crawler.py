"""
SEO Intelligence Agent - WordPress Crawler
Read-only crawler for WordPress REST API.
"""

import requests
from typing import Dict, Any, List, Optional
import time
import re


class WPCrawler:
    """
    WordPress REST API crawler.
    Fetches all posts and pages for analysis.
    """
    
    def __init__(self, config: Dict[str, Any], max_items: int = 500):
        site = config.get('site', {})
        self.site_url = site.get('url', '').rstrip('/')
        self.api_base = f"{self.site_url}/wp-json/wp/v2"
        self.max_items = max_items
        
        # Optional auth
        api_conf = config.get('api', {})
        username = api_conf.get('username', '')
        password = api_conf.get('app_password', '')
        
        if username and password:
            self.auth = (username, password)
        else:
            self.auth = None
        
        # Rate limiting
        self.rate_limit = 30
        self.request_count = 0
        self.window_start = time.time()
    
    def _request(self, endpoint: str, params: Optional[Dict] = None, retry_count: int = 0) -> Optional[List]:
        """Make GET request to WP REST API with retry logic."""
        self._check_rate_limit()
        
        url = f"{self.api_base}/{endpoint}"
        max_retries = 3
        
        # Headers to avoid Cloudflare/WAF blocking
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
        }
        
        try:
            response = requests.get(
                url, 
                auth=self.auth, 
                params=params, 
                headers=headers,
                timeout=60,  # Longer timeout
                allow_redirects=True
            )
            self.request_count += 1
            
            # Log response info for debugging
            content_type = response.headers.get('Content-Type', '')
            print(f"📡 {endpoint}: {response.status_code} | Type: {content_type[:50]}")
            
            # Check if response is HTML (Cloudflare challenge)
            if 'text/html' in content_type:
                if retry_count < max_retries:
                    print(f"⚠️ Got HTML instead of JSON, retrying ({retry_count + 1}/{max_retries})...")
                    time.sleep(2)  # Wait before retry
                    return self._request(endpoint, params, retry_count + 1)
                else:
                    print(f"❌ Still getting HTML after {max_retries} retries. Cloudflare may be blocking.")
                    print(f"   Response preview: {response.text[:200]}")
                    return None
            
            # Accept 200, 201, 202 as success
            if response.status_code in [200, 201, 202]:
                if not response.text.strip():
                    print(f"⚠️ Empty response body")
                    return []
                    
                try:
                    data = response.json()
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict):
                        # Some WP responses are dicts with data key
                        return data.get('data', [data])
                    return []
                except Exception as e:
                    print(f"❌ JSON parse error: {e}")
                    print(f"   Response: {response.text[:200]}")
                    return None
            else:
                print(f"❌ API Error: {response.status_code} - {response.text[:200]}")
                return None
                
        except requests.RequestException as e:
            print(f"❌ Request failed: {e}")
            if retry_count < max_retries:
                print(f"   Retrying ({retry_count + 1}/{max_retries})...")
                time.sleep(2)
                return self._request(endpoint, params, retry_count + 1)
            return None
    
    def _check_rate_limit(self) -> None:
        """Enforce rate limiting."""
        elapsed = time.time() - self.window_start
        
        if elapsed >= 60:
            self.request_count = 0
            self.window_start = time.time()
        elif self.request_count >= self.rate_limit:
            sleep_time = 60 - elapsed
            print(f"Rate limit... waiting {sleep_time:.1f}s")
            time.sleep(sleep_time)
            self.request_count = 0
            self.window_start = time.time()
    
    def fetch_all(self) -> List[Dict[str, Any]]:
        """
        Fetch all posts and pages from WordPress.
        
        Returns:
            List of page data dicts
        """
        all_content = []
        
        # Fetch posts
        posts = self._fetch_content_type('posts')
        all_content.extend(posts)
        
        # Fetch pages
        pages = self._fetch_content_type('pages')
        all_content.extend(pages)
        
        # Limit total items
        if len(all_content) > self.max_items:
            all_content = all_content[:self.max_items]
        
        print(f"📄 Fetched {len(all_content)} items from WordPress")
        return all_content
    
    def _fetch_content_type(self, content_type: str) -> List[Dict[str, Any]]:
        """Fetch all items of a content type."""
        items = []
        page = 1
        per_page = 100
        
        while len(items) < self.max_items:
            result = self._request(content_type, params={
                'per_page': per_page,
                'page': page,
                'status': 'publish',
                '_fields': 'id,slug,title,link,content,modified'
            })
            
            if not result:
                break
            
            for item in result:
                processed = self._process_item(item, content_type)
                items.append(processed)
            
            if len(result) < per_page:
                break
            
            page += 1
        
        return items
    
    def _process_item(self, item: Dict, content_type: str) -> Dict[str, Any]:
        """Process raw WP API response into standard format."""
        content_html = item.get('content', {}).get('rendered', '')
        
        return {
            'id': item.get('id'),
            'url': item.get('link', ''),
            'slug': item.get('slug', ''),
            'title': item.get('title', {}).get('rendered', 'Untitled'),
            'content_html': content_html,
            'content_text': self._extract_text(content_html),
            'type': content_type,
            'modified': item.get('modified', ''),
            'existing_links': self._extract_links(content_html),
            'depth': 2  # Default depth, could be calculated
        }
    
    def _extract_text(self, html: str) -> str:
        """Extract plain text from HTML."""
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', html)
        return re.sub(r'\s+', ' ', text).strip()
    
    def _extract_links(self, html: str) -> List[str]:
        """Extract internal links from HTML."""
        pattern = rf'href=["\']({re.escape(self.site_url)}[^"\']*|/[^"\']*)["\']'
        matches = re.findall(pattern, html, re.IGNORECASE)
        
        links = []
        for match in matches:
            if match.startswith('/'):
                links.append(match)
            else:
                links.append(match.replace(self.site_url, ''))
        return links
    
    def test_connection(self) -> bool:
        """Test if WordPress connection works."""
        result = self._request('users', params={'per_page': 1})
        if result is not None:
            print(f"✅ Connected to {self.site_url}")
            return True
        print(f"❌ Connection failed to {self.site_url}")
        return False
