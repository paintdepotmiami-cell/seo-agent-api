import time
from typing import Any, Optional

class SimpleCache:
    def __init__(self, default_ttl: int = 900): # 15 minutos de memoria
        self._storage = {}
        self.default_ttl = default_ttl

    def get(self, key: str) -> Optional[Any]:
        entry = self._storage.get(key)
        if not entry: return None
        # Invalidar si expiró
        if time.time() > entry['expires_at']:
            del self._storage[key]
            return None
        return entry['data']

    def set(self, key: str, data: Any, ttl: int = None):
        expiration = time.time() + (ttl or self.default_ttl)
        self._storage[key] = {'data': data, 'expires_at': expiration}
    
    def clear(self):
        """Clear all cache."""
        count = len(self._storage)
        self._storage = {}
        return count
    
    def stats(self):
        return {"total_entries": len(self._storage)}

# Instancia Global
memory_cache = SimpleCache()
