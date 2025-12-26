"""
SEO Intelligence Agent - WordPress Client
Write layer for applying links as drafts/revisions.
"""

import requests
from typing import Dict, Any, List, Optional
import time
import logging
import re

logger = logging.getLogger(__name__)


class WPClient:
    """
    WordPress REST API client for writing changes.
    Always creates revisions/drafts - never auto-publishes.
    """
    
    def __init__(self, config: Dict[str, Any]):
        site = config.get('site', {})
        api = config.get('api', {})
        
        self.site_url = site.get('url', '').rstrip('/')
        self.api_base = f"{self.site_url}/wp-json/wp/v2"
        
        # Authentication required for writes
        username = api.get('username', '')
        password = api.get('app_password', '')
        
        if not username or not password:
            raise ValueError("WP credentials required for write operations")
        
        self.auth = (username, password)
        self.mode = api.get('mode', 'read_only')
        
        # Rate limiting
        self.rate_limit = 20  # Lower for writes
        self.request_count = 0
        self.window_start = time.time()
    
    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None
    ) -> Optional[Dict]:
        """Make authenticated request to WP API."""
        self._check_rate_limit()
        
        url = f"{self.api_base}/{endpoint}"
        
        try:
            if method == 'GET':
                response = requests.get(url, auth=self.auth, timeout=30)
            elif method == 'POST':
                response = requests.post(url, auth=self.auth, json=data, timeout=30)
            elif method == 'PUT':
                response = requests.put(url, auth=self.auth, json=data, timeout=30)
            else:
                return None
            
            self.request_count += 1
            
            if response.status_code in [200, 201]:
                return response.json()
            else:
                logger.error(f"WP API Error: {response.status_code} - {response.text[:200]}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"WP Request failed: {e}")
            return None
    
    def _check_rate_limit(self) -> None:
        """Enforce rate limiting."""
        elapsed = time.time() - self.window_start
        
        if elapsed >= 60:
            self.request_count = 0
            self.window_start = time.time()
        elif self.request_count >= self.rate_limit:
            sleep_time = 60 - elapsed
            logger.info(f"Rate limit... waiting {sleep_time:.1f}s")
            time.sleep(sleep_time)
            self.request_count = 0
            self.window_start = time.time()
    
    def apply_link(
        self,
        post_id: int,
        content_type: str,  # 'post' or 'page'
        anchor_text: str,
        target_url: str,
        as_draft: bool = True
    ) -> Optional[Dict]:
        """
        Apply a single internal link to a post/page.
        
        Args:
            post_id: WordPress post/page ID
            content_type: 'posts' or 'pages'
            anchor_text: Text to wrap with link
            target_url: Target URL for the link
            as_draft: If True, save as draft (not published)
            
        Returns:
            Updated post data or None if failed
        """
        if self.mode == 'read_only':
            logger.warning("Cannot apply link: mode is read_only")
            return None
        
        # Get current content
        endpoint = f"{content_type}/{post_id}"
        current = self._request('GET', endpoint)
        
        if not current:
            logger.error(f"Failed to fetch {content_type}/{post_id}")
            return None
        
        content = current.get('content', {}).get('raw', '')
        if not content:
            content = current.get('content', {}).get('rendered', '')
        
        # Find and replace anchor text with link
        new_content = self._inject_link(content, anchor_text, target_url)
        
        if new_content == content:
            logger.warning(f"Anchor '{anchor_text}' not found in content")
            return None
        
        # Update post
        update_data = {
            'content': new_content,
        }
        
        if as_draft:
            update_data['status'] = 'draft'
        
        result = self._request('POST', endpoint, update_data)
        
        if result:
            logger.info(f"✅ Applied link to {content_type}/{post_id}: '{anchor_text}' → {target_url}")
        
        return result
    
    def _inject_link(self, content: str, anchor: str, url: str) -> str:
        """
        Inject link into content at first occurrence of anchor.
        Only replaces if not already a link.
        """
        # Check if anchor is already linked
        link_pattern = rf'<a[^>]*>[^<]*{re.escape(anchor)}[^<]*</a>'
        if re.search(link_pattern, content, re.IGNORECASE):
            return content  # Already linked
        
        # Find and replace (first occurrence only, case-insensitive)
        pattern = re.compile(re.escape(anchor), re.IGNORECASE)
        
        def replacer(match):
            original = match.group(0)
            return f'<a href="{url}">{original}</a>'
        
        # Replace only first occurrence
        return pattern.sub(replacer, content, count=1)
    
    def apply_batch(
        self,
        payloads: List[Dict[str, Any]],
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Apply multiple links in batch.
        
        Args:
            payloads: List of dicts with post_id, content_type, anchor_text, target_url
            dry_run: If True, don't actually apply changes
            
        Returns:
            Summary of results
        """
        results = {
            'total': len(payloads),
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'details': []
        }
        
        for payload in payloads:
            if dry_run:
                results['skipped'] += 1
                results['details'].append({
                    'payload': payload,
                    'status': 'skipped (dry run)'
                })
                continue
            
            result = self.apply_link(
                post_id=payload['post_id'],
                content_type=payload['content_type'],
                anchor_text=payload['anchor_text'],
                target_url=payload['target_url']
            )
            
            if result:
                results['success'] += 1
                results['details'].append({
                    'payload': payload,
                    'status': 'success'
                })
            else:
                results['failed'] += 1
                results['details'].append({
                    'payload': payload,
                    'status': 'failed'
                })
        
        return results
    
    def test_connection(self) -> bool:
        """Test if authentication works."""
        result = self._request('GET', 'users/me')
        if result:
            logger.info(f"✅ Authenticated as: {result.get('name', 'Unknown')}")
            return True
        logger.error("❌ Authentication failed")
        return False
