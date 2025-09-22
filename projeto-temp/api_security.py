# api_security.py - Sistema de segurança para API REST

from functools import wraps
from collections import defaultdict
from datetime import datetime, timedelta
import time
from flask import request, jsonify, session

# Rate limiting simples
class RateLimiter:
    """Rate limiter simples baseado em IP"""
    
    def __init__(self, max_requests: int = 100, window_minutes: int = 15):
        self.max_requests = max_requests
        self.window_seconds = window_minutes * 60
        self.requests = defaultdict(list)  # IP -> list of timestamps
    
    def is_allowed(self, identifier: str) -> bool:
        """Verifica se o identificador pode fazer uma requisição"""
        now = time.time()
        
        # Limpar requisições antigas
        self.requests[identifier] = [
            timestamp for timestamp in self.requests[identifier]
            if now - timestamp < self.window_seconds
        ]
        
        # Verificar limite
        if len(self.requests[identifier]) >= self.max_requests:
            return False
        
        # Adicionar requisição atual
        self.requests[identifier].append(now)
        return True
    
    def get_remaining_requests(self, identifier: str) -> int:
        """Retorna quantas requisições restam para o identificador"""
        now = time.time()
        self.requests[identifier] = [
            timestamp for timestamp in self.requests[identifier]
            if now - timestamp < self.window_seconds
        ]
        return max(0, self.max_requests - len(self.requests[identifier]))

# Instância global do rate limiter
rate_limiter = RateLimiter(max_requests=60, window_minutes=15)  # 60 req/15min

def api_rate_limit(f):
    """Decorator para rate limiting da API"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Identificar cliente (IP + User-Agent)
        client_ip = request.environ.get('REMOTE_ADDR', 'unknown')
        user_agent = request.headers.get('User-Agent', '')
        client_id = f"{client_ip}_{hash(user_agent) % 10000}"
        
        if not rate_limiter.is_allowed(client_id):
            return jsonify({
                'success': False,
                'error': 'Rate limit exceeded. Try again later.',
                'timestamp': datetime.now().isoformat()
            }), 429
        
        # Adicionar headers de rate limit
        response = f(*args, **kwargs)
        if isinstance(response, tuple):
            response_data, status_code = response
            remaining = rate_limiter.get_remaining_requests(client_id)
            response_data.headers['X-RateLimit-Remaining'] = str(remaining)
            response_data.headers['X-RateLimit-Limit'] = str(rate_limiter.max_requests)
            return response_data, status_code
        else:
            remaining = rate_limiter.get_remaining_requests(client_id)
            response.headers['X-RateLimit-Remaining'] = str(remaining)
            response.headers['X-RateLimit-Limit'] = str(rate_limiter.max_requests)
            return response
    
    return decorated_function

def validate_api_key(api_key: str) -> bool:
    """Valida se uma API key é válida"""
    # API keys válidas (em produção, estes devem estar em variáveis de ambiente)
    valid_keys = [
        'helpdesk_demo_api_key_2025',
        'helpdesk_admin_api_2025',
        'helpdesk_readonly_api_2025'
    ]
    return api_key in valid_keys

def get_api_key_permissions(api_key: str) -> dict:
    """Retorna as permissões de uma API key"""
    permissions = {
        'helpdesk_demo_api_key_2025': {
            'read': True,
            'write': True,
            'admin': False,
            'description': 'Demo API Key'
        },
        'helpdesk_admin_api_2025': {
            'read': True,
            'write': True,
            'admin': True,
            'description': 'Admin API Key'
        },
        'helpdesk_readonly_api_2025': {
            'read': True,
            'write': False,
            'admin': False,
            'description': 'Read-only API Key'
        }
    }
    return permissions.get(api_key, {'read': False, 'write': False, 'admin': False})

def enhanced_api_auth(required_permission: str = 'read'):
    """Decorator avançado para autenticação API"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Verificar API key no header
            api_key = request.headers.get('X-API-Key')
            
            if api_key and validate_api_key(api_key):
                permissions = get_api_key_permissions(api_key)
                
                # Verificar permissão requerida
                if permissions.get(required_permission, False):
                    # Log da requisição autenticada via API key
                    try:
                        from enhanced_logging import log_api_request
                        log_api_request(request.path, request.method, 200, 0, {
                            'auth_method': 'api_key',
                            'api_key_desc': permissions['description']
                        })
                    except:
                        pass
                    
                    return f(*args, **kwargs)
                else:
                    return jsonify({
                        'success': False,
                        'error': f'API key does not have {required_permission} permission',
                        'timestamp': datetime.now().isoformat()
                    }), 403
            
            # Fallback: verificar sessão ativa para usuários logados
            if 'user_id' in session:
                try:
                    from models import User
                    user = User.query.get(session['user_id'])
                    
                    if user:
                        # Verificar permissões baseadas no role
                        user_permissions = {
                            'admin': {'read': True, 'write': True, 'admin': True},
                            'operador': {'read': True, 'write': True, 'admin': False},
                            'user': {'read': False, 'write': False, 'admin': False}
                        }
                        
                        role_perms = user_permissions.get(user.role, {'read': False, 'write': False, 'admin': False})
                        
                        if role_perms.get(required_permission, False):
                            # Log da requisição autenticada via sessão
                            try:
                                from enhanced_logging import log_api_request
                                log_api_request(request.path, request.method, 200, 0, {
                                    'auth_method': 'session',
                                    'user_role': user.role,
                                    'username': user.username
                                })
                            except:
                                pass
                            
                            return f(*args, **kwargs)
                        else:
                            return jsonify({
                                'success': False,
                                'error': f'User role {user.role} does not have {required_permission} permission',
                                'timestamp': datetime.now().isoformat()
                            }), 403
                except Exception as e:
                    return jsonify({
                        'success': False,
                        'error': 'Authentication verification failed',
                        'timestamp': datetime.now().isoformat()
                    }), 500
            
            # Sem autenticação válida
            return jsonify({
                'success': False,
                'error': 'API key or valid session required',
                'hint': 'Include X-API-Key header or login via web interface',
                'timestamp': datetime.now().isoformat()
            }), 401
        
        return decorated_function
    return decorator

print("🔐 Sistema de segurança API carregado")
print("🚦 Rate limiting: 60 req/15min por IP")
print("🔑 API keys configuradas para demo/admin/readonly")