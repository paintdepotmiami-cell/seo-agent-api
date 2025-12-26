"""
SEO Intelligence Agent - WordPress Connector
Read-only connector for WordPress REST API.
"""

import requests
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin
import time
import os


class WordPressConnector:
    """
    WordPress REST API connector.
    Read-only by default, with optional draft mode for applying links.
    """
    
    def __init__(
        self,
        site_url: str,
        username: str,
        app_password: str,
        mode: str = "read_only"  # read_only | apply_draft
    ):
        self.site_url = site_url.rstrip('/')
        self.api_base = f"{self.site_url}/wp-json/wp/v2"
        self.auth = (username, app_password)
        self.mode = mode
        
        # Rate limiting
        self.rate_limit = 30  # requests per minute
        self.request_count = 0
        self.window_start = time.time()
    
    def _request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None
    ) -> Optional[Dict]:
        """Make an authenticated request to the WP REST API."""
        self._check_rate_limit()
        
        url = f"{self.api_base}/{endpoint}"
        
        try:
            if method == 'GET':
                response = requests.get(url, auth=self.auth, params=params, timeout=30)
            elif method == 'POST':
                response = requests.post(url, auth=self.auth, json=json_data, timeout=30)
            elif method == 'PUT':
                response = requests.put(url, auth=self.auth, json=json_data, timeout=30)
            else:
                return None
            
            self.request_count += 1
            
            if response.status_code == 200 or response.status_code == 201:
                return response.json()
            else:
                print(f"API Error: {response.status_code} - {response.text}")
                return None
                
        except requests.RequestException as e:
            print(f"Request failed: {e}")
            return None
    
    def _check_rate_limit(self) -> None:
        """Enforce rate limiting."""
        current_time = time.time()
        elapsed = current_time - self.window_start
        
        if elapsed >= 60:
            # Reset window
            self.request_count = 0
            self.window_start = current_time
        elif self.request_count >= self.rate_limit:
            # Wait until window resets
            sleep_time = 60 - elapsed
            print(f"Rate limit reached. Waiting {sleep_time:.1f}s...")
            time.sleep(sleep_time)
            self.request_count = 0
            self.window_start = time.time()
    
    def test_connection(self) -> bool:
        """Test if connection to WordPress works."""
        result = self._request('GET', 'users/me')
        if result:
            print(f"✅ Connected as: {result.get('name', 'Unknown')}")
            return True
        print("❌ Connection failed")
        return False
    
    def get_all_posts(self, per_page: int = 100) -> List[Dict]:
        """Fetch all published posts."""
        all_posts = []
        page = 1
        
        while True:
            posts = self._request('GET', 'posts', params={
                'per_page': per_page,
                'page': page,
                'status': 'publish',
                '_fields': 'id,slug,title,link,content,modified,categories,tags'
            })
            
            if not posts:
                break
            
            all_posts.extend(posts)
            
            if len(posts) < per_page:
                break
            
            page += 1
        
        print(f"📄 Fetched {len(all_posts)} posts")
        return all_posts
    
    def get_all_pages(self, per_page: int = 100) -> List[Dict]:
        """Fetch all published pages."""
        all_pages = []
        page = 1
        
        while True:
            pages = self._request('GET', 'pages', params={
                'per_page': per_page,
                'page': page,
                'status': 'publish',
                '_fields': 'id,slug,title,link,content,modified,parent'
            })
            
            if not pages:
                break
            
            all_pages.extend(pages)
            
            if len(pages) < per_page:
                break
            
            page += 1
        
        print(f"📄 Fetched {len(all_pages)} pages")
        return all_pages
    
    def get_post_by_slug(self, slug: str) -> Optional[Dict]:
        """Get a single post by its slug."""
        result = self._request('GET', 'posts', params={
            'slug': slug,
            '_fields': 'id,slug,title,link,content,modified'
        })
        
        if result and len(result) > 0:
            return result[0]
        return None
    
    def get_page_by_slug(self, slug: str) -> Optional[Dict]:
        """Get a single page by its slug."""
        result = self._request('GET', 'pages', params={
            'slug': slug,
            '_fields': 'id,slug,title,link,content,modified'
        })
        
        if result and len(result) > 0:
            return result[0]
        return None
    
    def get_content_by_url(self, url: str) -> Optional[Dict]:
        """Get post or page content by URL."""
        # Extract slug from URL
        slug = url.rstrip('/').split('/')[-1]
        
        # Try as page first
        result = self.get_page_by_slug(slug)
        if result:
            return result
        
        # Try as post
        return self.get_post_by_slug(slug)
    
    def update_post_content(
        self, 
        post_id: int, 
        new_content: str,
        as_revision: bool = True
    ) -> Optional[Dict]:
        """
        Update post content.
        Only works in apply_draft mode.
        
        Args:
            post_id: WordPress post ID
            new_content: New HTML content
            as_revision: If True, creates a revision instead of publishing
        """
        if self.mode != 'apply_draft':
            print("⚠️ Cannot update: mode is read_only")
            return None
        
        data = {'content': new_content}
        
        if as_revision:
            data['status'] = 'draft'  # Keep as draft for review
        
        return self._request('POST', f'posts/{post_id}', json_data=data)
    
    def update_page_content(
        self, 
        page_id: int, 
        new_content: str,
        as_revision: bool = True
    ) -> Optional[Dict]:
        """
        Update page content.
        Only works in apply_draft mode.
        """
        if self.mode != 'apply_draft':
            print("⚠️ Cannot update: mode is read_only")
            return None
        
        data = {'content': new_content}
        
        if as_revision:
            data['status'] = 'draft'
        
        return self._request('POST', f'pages/{page_id}', json_data=data)
    
    def extract_internal_links(self, html_content: str) -> List[str]:
        """Extract all internal links from HTML content."""
        import re
        
        pattern = rf'href=["\']({re.escape(self.site_url)}[^"\']*|/[^"\']*)["\']'
        matches = re.findall(pattern, html_content)
        
        # Normalize to relative URLs
        links = []
        for match in matches:
            if match.startswith('/'):
                links.append(match)
            else:
                # Convert absolute to relative
                links.append(match.replace(self.site_url, ''))
        
        return links


def create_connector_from_env(env_path: str) -> Optional[WordPressConnector]:
    """Create connector from .env file."""
    from dotenv import load_dotenv
    
    load_dotenv(env_path)
    
    site_url = os.getenv('WP_URL')
    username = os.getenv('WP_USERNAME')
    password = os.getenv('WP_APP_PASSWORD')
    
    if not all([site_url, username, password]):
        print("❌ Missing credentials in .env file")
        return None
    
    return WordPressConnector(site_url, username, password)
