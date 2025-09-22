"""
Rate limiting utility for security
"""
from flask import request, jsonify, flash, redirect, url_for
from functools import wraps
import time
from collections import defaultdict, deque

class RateLimiter:
    def __init__(self):
        # Store for each IP: deque of timestamps  
        self.requests = defaultdict(deque)
        # Store for login attempts per IP
        self.login_attempts = defaultdict(deque)
    
    def is_allowed(self, key, max_requests=60, window=60):
        """Check if request is allowed (default: 60 requests per minute)"""
        now = time.time()
        
        # Clean old requests outside window
        while self.requests[key] and self.requests[key][0] < now - window:
            self.requests[key].popleft()
        
        # Check if limit exceeded
        if len(self.requests[key]) >= max_requests:
            return False
        
        # Add current request
        self.requests[key].append(now)
        return True
    
    def is_login_allowed(self, ip, max_attempts=5, window=300):
        """Check login attempts (default: 5 attempts per 5 minutes)"""
        now = time.time()
        
        # Clean old attempts
        while self.login_attempts[ip] and self.login_attempts[ip][0] < now - window:
            self.login_attempts[ip].popleft()
        
        return len(self.login_attempts[ip]) < max_attempts
    
    def record_login_attempt(self, ip):
        """Record a failed login attempt"""
        self.login_attempts[ip].append(time.time())

# Global rate limiter instance
rate_limiter = RateLimiter()

def rate_limit(max_requests=60, window=60):
    """Decorator for rate limiting routes"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # Get client IP (handle proxy headers)
            client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
            if client_ip:
                client_ip = client_ip.split(',')[0].strip()
            
            if not rate_limiter.is_allowed(client_ip, max_requests, window):
                return jsonify({
                    'error': 'Rate limit exceeded',
                    'message': f'Maximum {max_requests} requests per {window} seconds'
                }), 429
            
            return f(*args, **kwargs)
        return decorated
    return decorator

def login_rate_limit(max_attempts=5, window=300):
    """Decorator for login rate limiting"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
            if client_ip:
                client_ip = client_ip.split(',')[0].strip()
            
            if not rate_limiter.is_login_allowed(client_ip, max_attempts, window):
                flash(f"Muitas tentativas de login. Tente novamente em {window//60} minutos.", "error")
                return redirect(url_for('auth.login'))
            
            return f(*args, **kwargs)
        return decorated
    return decorator