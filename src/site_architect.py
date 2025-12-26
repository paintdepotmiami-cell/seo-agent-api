"""
SEO Intelligence Agent - Site Architect
Handles URL normalization and page type classification.
"""

from urllib.parse import urlparse, urlunparse, parse_qs
from typing import Tuple, Optional, Dict, Any
import re


class SiteArchitect:
    """
    Core module for site structure understanding.
    - Normalizes URLs for consistent comparison
    - Classifies pages by type (money_page, hub, permit, blog, etc.)
    """
    
    # Query params to always strip
    STRIP_PARAMS = {'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 
                    'utm_term', 'gclid', 'fbclid', 'ref', 'source'}
    
    def __init__(self, project_config: Dict[str, Any], global_rules: Dict[str, Any]):
        self.config = project_config
        self.global_rules = global_rules
        self.site_url = project_config['site']['url'].rstrip('/')
        self._build_url_index()
    
    def _build_url_index(self) -> None:
        """Pre-index all known URLs for fast classification."""
        self.url_index = {}
        kg = self.config.get('knowledge_graph', {})
        
        # Index service hubs
        for key, data in kg.get('service_hubs', {}).items():
            normalized = self.normalize_url(data['url'])
            self.url_index[normalized] = {
                'type': 'money_page',
                'subtype': key,
                'priority': data.get('priority', 2),
                'keywords': data.get('keywords', []),
                'title': data.get('title', '')
            }
        
        # Index permit hub
        authority = kg.get('authority_hubs', {})
        if 'permit_hub' in authority:
            hub = authority['permit_hub']
            normalized = self.normalize_url(hub['url'])
            self.url_index[normalized] = {
                'type': 'hub',
                'subtype': 'permit_hub',
                'priority': hub.get('priority', 1),
                'is_central_hub': hub.get('is_central_hub', True),
                'title': hub.get('title', '')
            }
        
        # Index permit pages
        for permit in authority.get('permit_pages', []):
            normalized = self.normalize_url(permit['url'])
            self.url_index[normalized] = {
                'type': 'permit_page',
                'subtype': permit.get('city', 'unknown'),
                'geo_terms': permit.get('geo_terms', []),
                'priority': 3
            }
        
        # Index materials
        for material in kg.get('materials', []):
            normalized = self.normalize_url(material['url'])
            self.url_index[normalized] = {
                'type': 'material',
                'subtype': material.get('name', ''),
                'priority': 2
            }
    
    def normalize_url(self, url: str) -> str:
        """
        Normalize URL for consistent comparison.
        - Ensures trailing slash
        - Lowercase path
        - Strips tracking params
        - Handles relative URLs
        """
        # Handle relative URLs
        if url.startswith('/'):
            url = self.site_url + url
        
        parsed = urlparse(url)
        
        # Clean path: lowercase, ensure trailing slash
        clean_path = parsed.path.lower().rstrip('/') + '/'
        if clean_path == '//':
            clean_path = '/'
        
        # Strip tracking params
        if parsed.query:
            params = parse_qs(parsed.query)
            clean_params = {k: v for k, v in params.items() 
                          if k.lower() not in self.STRIP_PARAMS 
                          and not k.lower().startswith('utm_')}
            # Reconstruct query string (empty if all stripped)
            query = '&'.join(f"{k}={v[0]}" for k, v in clean_params.items()) if clean_params else ''
        else:
            query = ''
        
        # Return path only (relative) for internal comparison
        return clean_path
    
    def classify_page(self, url: str) -> Tuple[str, Optional[str], Dict[str, Any]]:
        """
        Classify a page by its URL.
        
        Returns:
            Tuple of (page_type, subtype, metadata)
            
        Page types:
            - money_page: Core service pages
            - hub: Central authority pages
            - permit_page: City permit pages
            - material: Product/material pages
            - blog: Blog posts
            - project: Portfolio/case studies
            - utility: Contact, about, etc.
            - excluded: Never touch
        """
        normalized = self.normalize_url(url)
        
        # Check if in pre-built index
        if normalized in self.url_index:
            data = self.url_index[normalized]
            return data['type'], data.get('subtype'), data
        
        # Check exclusions
        if self._is_excluded(normalized):
            return 'excluded', None, {}
        
        # Pattern-based detection
        if '/blog/' in normalized or '/guide/' in normalized:
            return 'blog', None, {}
        if '/project' in normalized or '/portfolio/' in normalized:
            return 'project', None, {}
        if '/contact' in normalized or '/about' in normalized:
            return 'utility', None, {}
        
        # Default: could be a blog post or unknown page
        return 'unknown', None, {}
    
    def _is_excluded(self, url: str) -> bool:
        """Check if URL matches any exclusion pattern."""
        exclusions = self.config.get('exclusions', {})
        
        # Check exact URL matches
        for excluded_url in exclusions.get('urls', []):
            if self.normalize_url(excluded_url) == url:
                return True
        
        # Check patterns
        import fnmatch
        for pattern in exclusions.get('patterns', []):
            if fnmatch.fnmatch(url, pattern):
                return True
        
        return False
    
    def get_page_metadata(self, url: str) -> Dict[str, Any]:
        """Get full metadata for a known page."""
        normalized = self.normalize_url(url)
        return self.url_index.get(normalized, {})
    
    def is_permit_page(self, url: str) -> bool:
        """Check if URL is a permit page."""
        page_type, _, _ = self.classify_page(url)
        return page_type == 'permit_page'
    
    def is_money_page(self, url: str) -> bool:
        """Check if URL is a money page (core service)."""
        page_type, _, _ = self.classify_page(url)
        return page_type == 'money_page'
    
    def get_service_hub_for_keyword(self, keyword: str) -> Optional[str]:
        """Find the most relevant service hub for a keyword."""
        keyword_lower = keyword.lower()
        kg = self.config.get('knowledge_graph', {})
        
        for key, data in kg.get('service_hubs', {}).items():
            for kw in data.get('keywords', []):
                if kw.lower() in keyword_lower or keyword_lower in kw.lower():
                    return data['url']
        
        return None
