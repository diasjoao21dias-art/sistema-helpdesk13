"""
Simple caching utility for improved performance
"""
from flask import current_app
import time
from functools import wraps
import json
import hashlib

class SimpleCache:
    def __init__(self):
        self.cache = {}
        self.timeouts = {}
    
    def get(self, key):
        """Get value from cache"""
        if key in self.cache:
            # Check if expired
            if key in self.timeouts and time.time() > self.timeouts[key]:
                del self.cache[key]
                del self.timeouts[key]
                return None
            return self.cache[key]
        return None
    
    def set(self, key, value, timeout=300):
        """Set value in cache with timeout (default 5 minutes)"""
        self.cache[key] = value
        if timeout:
            self.timeouts[key] = time.time() + timeout
    
    def delete(self, key):
        """Delete key from cache"""
        if key in self.cache:
            del self.cache[key]
        if key in self.timeouts:
            del self.timeouts[key]
    
    def clear(self):
        """Clear all cache"""
        self.cache.clear()
        self.timeouts.clear()

# Global cache instance
cache = SimpleCache()

def cached(timeout=300, key_prefix=''):
    """Decorator for caching function results"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # Generate cache key
            key_data = f"{key_prefix}:{f.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"
            cache_key = hashlib.md5(key_data.encode()).hexdigest()
            
            # Try to get from cache
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            # Execute function and cache result
            result = f(*args, **kwargs)
            cache.set(cache_key, result, timeout)
            return result
        return decorated
    return decorator