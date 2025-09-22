# enhanced_logging.py - Sistema de logs melhorado para o HelpDesk

import logging
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from functools import wraps
from flask import request, session, g

# Configuração do sistema de logs
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# Configurar loggers específicos
def setup_enhanced_logging():
    """Configura sistema de logging avançado"""
    
    # Logger principal do sistema
    system_logger = logging.getLogger('helpdesk_system')
    system_logger.setLevel(logging.INFO)
    
    # Handler para logs do sistema
    system_handler = logging.FileHandler(f'{LOG_DIR}/system.log', encoding='utf-8')
    system_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s'
    )
    system_handler.setFormatter(system_formatter)
    system_logger.addHandler(system_handler)
    
    # Logger para ações de usuários
    user_logger = logging.getLogger('helpdesk_users')
    user_logger.setLevel(logging.INFO)
    
    user_handler = logging.FileHandler(f'{LOG_DIR}/user_actions.log', encoding='utf-8')
    user_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    user_handler.setFormatter(user_formatter)
    user_logger.addHandler(user_handler)
    
    # Logger para API
    api_logger = logging.getLogger('helpdesk_api')
    api_logger.setLevel(logging.INFO)
    
    api_handler = logging.FileHandler(f'{LOG_DIR}/api.log', encoding='utf-8')
    api_formatter = logging.Formatter(
        '%(asctime)s - API - %(levelname)s - %(message)s'
    )
    api_handler.setFormatter(api_formatter)
    api_logger.addHandler(api_handler)
    
    # Logger para performance
    perf_logger = logging.getLogger('helpdesk_performance')
    perf_logger.setLevel(logging.INFO)
    
    perf_handler = logging.FileHandler(f'{LOG_DIR}/performance.log', encoding='utf-8')
    perf_formatter = logging.Formatter(
        '%(asctime)s - PERF - %(message)s'
    )
    perf_handler.setFormatter(perf_formatter)
    perf_logger.addHandler(perf_handler)
    
    return {
        'system': system_logger,
        'users': user_logger,
        'api': api_logger,
        'performance': perf_logger
    }

# Instâncias dos loggers
loggers = setup_enhanced_logging()

def log_user_action(action: str, details: Optional[Dict[str, Any]] = None, 
                   user_id: Optional[int] = None, username: Optional[str] = None):
    """Log de ação do usuário com detalhes"""
    try:
        log_data = {
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'user_id': user_id or session.get('user_id'),
            'username': username or session.get('username'),
            'ip_address': request.environ.get('REMOTE_ADDR'),
            'user_agent': request.headers.get('User-Agent'),
            'details': details or {}
        }
        
        message = f"User: {log_data['username']} | Action: {action} | IP: {log_data['ip_address']}"
        if details:
            message += f" | Details: {json.dumps(details)}"
            
        loggers['users'].info(message)
        
    except Exception as e:
        loggers['system'].error(f"Erro ao registrar ação do usuário: {e}")

def log_system_event(event: str, level: str = 'INFO', details: Optional[Dict[str, Any]] = None):
    """Log de evento do sistema"""
    try:
        log_data = {
            'timestamp': datetime.now().isoformat(),
            'event': event,
            'level': level,
            'details': details or {}
        }
        
        message = f"Event: {event}"
        if details:
            message += f" | Details: {json.dumps(details)}"
        
        if level.upper() == 'ERROR':
            loggers['system'].error(message)
        elif level.upper() == 'WARNING':
            loggers['system'].warning(message)
        else:
            loggers['system'].info(message)
            
    except Exception as e:
        print(f"Erro crítico no sistema de logs: {e}")

def log_api_request(endpoint: str, method: str, status_code: int, 
                   response_time: float, details: Optional[Dict[str, Any]] = None):
    """Log de requisição da API"""
    try:
        log_data = {
            'timestamp': datetime.now().isoformat(),
            'endpoint': endpoint,
            'method': method,
            'status_code': status_code,
            'response_time_ms': round(response_time * 1000, 2),
            'ip_address': request.environ.get('REMOTE_ADDR'),
            'user_agent': request.headers.get('User-Agent'),
            'details': details or {}
        }
        
        message = f"{method} {endpoint} | Status: {status_code} | Time: {log_data['response_time_ms']}ms | IP: {log_data['ip_address']}"
        
        if status_code >= 400:
            loggers['api'].error(message)
        elif status_code >= 300:
            loggers['api'].warning(message)
        else:
            loggers['api'].info(message)
            
    except Exception as e:
        loggers['system'].error(f"Erro ao registrar requisição API: {e}")

def log_performance_metric(metric_name: str, value: float, unit: str = 'ms', 
                          context: Optional[Dict[str, Any]] = None):
    """Log de métrica de performance"""
    try:
        log_data = {
            'timestamp': datetime.now().isoformat(),
            'metric': metric_name,
            'value': value,
            'unit': unit,
            'context': context or {}
        }
        
        message = f"Metric: {metric_name} | Value: {value}{unit}"
        if context:
            message += f" | Context: {json.dumps(context)}"
            
        loggers['performance'].info(message)
        
    except Exception as e:
        loggers['system'].error(f"Erro ao registrar métrica: {e}")

def performance_monitor(metric_name: str):
    """Decorator para monitorar performance de funções"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = datetime.now()
            try:
                result = func(*args, **kwargs)
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                log_performance_metric(
                    f"{func.__name__}_{metric_name}",
                    duration * 1000,
                    'ms',
                    {'function': func.__name__, 'success': True}
                )
                
                return result
            except Exception as e:
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                log_performance_metric(
                    f"{func.__name__}_{metric_name}_error",
                    duration * 1000,
                    'ms',
                    {'function': func.__name__, 'success': False, 'error': str(e)}
                )
                raise
                
        return wrapper
    return decorator

def get_log_stats() -> Dict[str, Any]:
    """Retorna estatísticas dos logs"""
    try:
        stats = {
            'log_files': {},
            'total_entries': 0,
            'last_updated': datetime.now().isoformat()
        }
        
        log_files = ['system.log', 'user_actions.log', 'api.log', 'performance.log']
        
        for log_file in log_files:
            file_path = f"{LOG_DIR}/{log_file}"
            if os.path.exists(file_path):
                file_stats = os.stat(file_path)
                with open(file_path, 'r', encoding='utf-8') as f:
                    line_count = sum(1 for line in f)
                
                stats['log_files'][log_file] = {
                    'size_bytes': file_stats.st_size,
                    'size_mb': round(file_stats.st_size / 1024 / 1024, 2),
                    'line_count': line_count,
                    'last_modified': datetime.fromtimestamp(file_stats.st_mtime).isoformat()
                }
                
                stats['total_entries'] += line_count
            else:
                stats['log_files'][log_file] = {
                    'exists': False
                }
        
        return stats
        
    except Exception as e:
        loggers['system'].error(f"Erro ao obter estatísticas de logs: {e}")
        return {'error': str(e)}

def search_logs(query: str, log_type: str = 'all', limit: int = 100) -> List[Dict[str, Any]]:
    """Busca nos logs por termo específico"""
    try:
        results = []
        log_files = []
        
        if log_type == 'all':
            log_files = ['system.log', 'user_actions.log', 'api.log', 'performance.log']
        else:
            log_files = [f"{log_type}.log"]
        
        for log_file in log_files:
            file_path = f"{LOG_DIR}/{log_file}"
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    
                for i, line in enumerate(reversed(lines)):
                    if len(results) >= limit:
                        break
                        
                    if query.lower() in line.lower():
                        results.append({
                            'file': log_file,
                            'line_number': len(lines) - i,
                            'content': line.strip(),
                            'timestamp': line.split(' - ')[0] if ' - ' in line else ''
                        })
        
        # Ordenar por timestamp (mais recentes primeiro)
        results.sort(key=lambda x: x['timestamp'], reverse=True)
        return results[:limit]
        
    except Exception as e:
        loggers['system'].error(f"Erro ao buscar logs: {e}")
        return [{'error': str(e)}]

# Log de inicialização
log_system_event("Sistema de logging avançado inicializado", "INFO", {
    'log_directory': LOG_DIR,
    'loggers_configured': list(loggers.keys())
})

print("✅ Sistema de logging avançado configurado")
print(f"📁 Logs salvos em: {LOG_DIR}/")
print(f"🔍 Loggers disponíveis: {', '.join(loggers.keys())}")