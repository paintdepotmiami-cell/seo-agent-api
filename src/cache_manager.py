"""
SEO Intelligence Agent - Cache Manager
Simple in-memory cache with TTL for API efficiency.
"""

import time
from typing import Any, Optional, Dict


class SimpleCache:
    """
    Simple in-memory cache with TTL expiration.
    Used to avoid re-computing expensive analyses.
    """
    
    def __init__(self, default_ttl: int = 900):  # 15 minutes default
        self._storage: Dict[str, Dict[str, Any]] = {}
        self.default_ttl = default_ttl
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get cached value if exists and not expired.
        
        Args:
            key: Cache key
            
        Returns:
            Cached data or None if expired/missing
        """
        entry = self._storage.get(key)
        if not entry:
            return None
        
        # Invalidate if expired
        if time.time() > entry['expires_at']:
            del self._storage[key]
            return None
        
        return entry['data']
    
    def set(self, key: str, data: Any, ttl: Optional[int] = None) -> None:
        """
        Store value in cache with TTL.
        
        Args:
            key: Cache key
            data: Data to cache
            ttl: Time to live in seconds (optional)
        """
        expiration = time.time() + (ttl or self.default_ttl)
        self._storage[key] = {
            'data': data,
            'expires_at': expiration,
            'created_at': time.time()
        }
    
    def invalidate(self, key: str) -> bool:
        """Remove key from cache."""
        if key in self._storage:
            del self._storage[key]
            return True
        return False
    
    def clear(self) -> int:
        """Clear all cached data. Returns count of cleared entries."""
        count = len(self._storage)
        self._storage.clear()
        return count
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        now = time.time()
        active = sum(1 for v in self._storage.values() if now < v['expires_at'])
        return {
            'total_entries': len(self._storage),
            'active_entries': active,
            'expired_entries': len(self._storage) - active
        }


# Global cache instance
memory_cache = SimpleCache()
