"""
SEO Intelligence Agent - WordPress Crawler
Standard read-only crawler using WordPress REST API.
"""

import requests
import time
from typing import List, Dict, Any
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from src.transport import get_secure_session

import logging

logger = logging.getLogger("seo-agent")

class WPCrawler:
    def __init__(self, config: Dict[str, Any], max_items: int = 500):
        self.site_url = config['site']['url'].rstrip('/') + '/'
        self.max_items = config.get('knowledge_graph', {}).get('limits', {}).get('max_items', max_items)
        
        # Hardcoded content types for stability
        self.post_types = {
            "pages": "wp/v2/pages",
            "posts": "wp/v2/posts"
        }
        
        # Use centralized secure session
        self.session = get_secure_session()
        
        # Optional: Add Auth if present in config
        api_conf = config.get('api', {})
        if api_conf.get('username') and api_conf.get('app_password'):
            self.session.auth = (api_conf['username'], api_conf['app_password'])

    def fetch_all(self) -> List[Dict[str, Any]]:
        all_items = []
        logger.info(f"🕷️ Starting crawl on: {self.site_url}")
        
        for label, endpoint_suffix in self.post_types.items():
            endpoint = f"wp-json/{endpoint_suffix.lstrip('/')}"  # Ensure clean path
            try:
                items = self._fetch_endpoint(endpoint)
                all_items.extend(items)
                logger.info(f"   ✅ Fetched {len(items)} {label}")
            except Exception as e:
                logger.error(f"   ❌ Error fetching {label}: {str(e)}")

        return all_items

    def _fetch_endpoint(self, endpoint: str) -> List[Dict[str, Any]]:
        items = []
        page = 1
        per_page = 100 

        while True:
            if len(items) >= self.max_items:
                break

            url = urljoin(self.site_url, endpoint)
            
            try:
                resp = self.session.get(url, params={
                    "per_page": per_page,
                    "page": page,
                    "status": "publish"
                }, timeout=30)
                
                if resp.status_code == 400: # End of pagination
                    break
                
                if resp.status_code == 403:
                    logger.warning(f"      ⛔ 403 Forbidden on page {page}. WAF active.")
                    break

                resp.raise_for_status()
                batch = resp.json()

                if not batch:
                    break

                for item in batch:
                    items.append(self._normalize_item(item))

                page += 1
                time.sleep(0.2) # Small courtesy delay

            except Exception as e:
                logger.error(f"      ⚠️ Fetch error page {page}: {str(e)}")
                break

        return items

    def _normalize_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize WP JSON response."""
        html = item.get("content", {}).get("rendered", "")
        # Basic text extraction
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator=" ", strip=True)

        return {
            "id": item.get("id"),
            "url": item.get("link"),
            "slug": item.get("slug"),
            "title": item.get("title", {}).get("rendered", ""),
            "content_html": html,
            "content_text": text,
            "type": item.get("type"),
            "date": item.get("date"),
            "modified": item.get("modified"),
            "author_id": item.get("author")
        }
