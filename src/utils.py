"""
SEO Intelligence Agent - Utility Functions
"""

import os
from typing import Dict, Any


def ensure_dir(path: str) -> None:
    """Create directory if it doesn't exist."""
    if path and not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def deep_merge_dicts(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge two dictionaries.
    Override values take precedence.
    """
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dicts(result[key], value)
        else:
            result[key] = value
    
    return result


def normalize_url(url: str, site_url: str = "") -> str:
    """
    Normalize URL for consistent comparison.
    - Lowercase path
    - Ensure trailing slash
    - Strip tracking params
    """
    from urllib.parse import urlparse, parse_qs
    
    # Handle relative URLs
    if url.startswith('/'):
        full_url = site_url.rstrip('/') + url
    else:
        full_url = url
    
    parsed = urlparse(full_url)
    
    # Clean path
    clean_path = parsed.path.lower().rstrip('/') + '/'
    if clean_path == '//':
        clean_path = '/'
    
    return clean_path


def extract_text_from_html(html: str) -> str:
    """Extract plain text from HTML content."""
    import re
    
    # Remove script and style tags
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', html)
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text
