#!/usr/bin/env python3
"""
Sistema de Log de Atividades - Sistema Olivion
Registra todas as atividades importantes do sistema para auditoria
"""

import sqlite3
import json
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from flask import request, session
import os
import sys

class ColoredFormatter(logging.Formatter):
    """Formatador colorido para logs no console"""
    
    # Cores ANSI
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'       # Reset
    }
    
    def format(self, record):
        # Adicionar cor para o nível de log
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname_color = self.COLORS[levelname]
        else:
            record.levelname_color = ''
        record.reset = self.COLORS['RESET']
        
        return super().format(record)

class ActivityLogger:
    def __init__(self, db_path: str = "sistema_os.db"):
        self.db_path = db_path
        self.setup_logging()
        self.create_activity_table()
    
    def setup_logging(self):
        """Configurar logging estruturado com rotação e formatação colorida"""
        # Formatter with colors for console
        console_formatter = ColoredFormatter(
            '%(asctime)s - %(levelname_color)s%(levelname)s%(reset)s - %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Formatter for file (no colors)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Create logs directory first
        os.makedirs('logs', exist_ok=True)
        
        # Rotating file handler (max 10MB, keep 5 backups)
        file_handler = RotatingFileHandler(
            'logs/activity.log', 
            maxBytes=10*1024*1024, 
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(file_formatter)
        
        # Console handler with colors
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(console_formatter)
        
        # Configure logger
        self.logger = logging.getLogger('ActivityLogger')
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()  # Clear any existing handlers
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        # Prevent propagation to root logger
        self.logger.propagate = False
    
    def create_activity_table(self):
        """Criar tabela de atividades se não existir"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_activity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    user_id INTEGER,
                    username TEXT,
                    action_type TEXT NOT NULL,
                    action_description TEXT NOT NULL,
                    details TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    session_id TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Criar índices para melhor performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_activity_timestamp ON system_activity(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_activity_user ON system_activity(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_activity_type ON system_activity(action_type)')
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            self.logger.error(f"Erro ao criar tabela de atividades: {e}")
    
    def debug(self, message: str, **kwargs):
        """Log mensagem de debug"""
        self.logger.debug(message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log mensagem de informação"""
        self.logger.info(message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log mensagem de aviso"""
        self.logger.warning(message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log mensagem de erro"""
        self.logger.error(message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log mensagem crítica"""
        self.logger.critical(message, **kwargs)
    
    def log_activity(self, action_type: str, action_description: str, 
                    user_id: Optional[int] = None, username: Optional[str] = None,
                    details: Optional[Dict] = None):
        """Registrar uma atividade do sistema"""
        try:
            # Obter informações da requisição atual se disponível
            ip_address = self.get_client_ip()
            user_agent = self.get_user_agent()
            session_id = self.get_session_id()
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO system_activity 
                (user_id, username, action_type, action_description, details, 
                 ip_address, user_agent, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                username,
                action_type,
                action_description,
                json.dumps(details) if details else None,
                ip_address,
                user_agent,
                session_id
            ))
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"Atividade registrada: {action_type} - {action_description} - Usuário: {username}")
            
        except Exception as e:
            self.logger.error(f"Erro ao registrar atividade: {e}")
    
    def get_client_ip(self) -> str:
        """Obter IP do cliente"""
        try:
            if request:
                return request.environ.get('HTTP_X_FORWARDED_FOR', 
                                         request.environ.get('REMOTE_ADDR', 'unknown'))
            return 'system'
        except:
            return 'system'
    
    def get_user_agent(self) -> str:
        """Obter User Agent do cliente"""
        try:
            if request:
                return request.environ.get('HTTP_USER_AGENT', 'unknown')[:500]
            return 'system'
        except:
            return 'system'
    
    def get_session_id(self) -> str:
        """Obter ID da sessão"""
        try:
            if session:
                return str(session.get('_id', 'no_session'))[:50]
            return 'no_session'
        except:
            return 'no_session'
    
    def get_recent_activities(self, limit: int = 50) -> List[Dict]:
        """Obter atividades recentes"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT timestamp, username, action_type, action_description, 
                       details, ip_address
                FROM system_activity 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (limit,))
            
            activities = []
            for row in cursor.fetchall():
                timestamp, username, action_type, description, details, ip = row
                
                # Determinar cor do tipo de ação
                type_color = self.get_action_color(action_type)
                
                activities.append({
                    'timestamp': self.format_timestamp(timestamp),
                    'user': username or 'Sistema',
                    'action': action_type,
                    'details': description,
                    'ip': ip or 'N/A',
                    'type_color': type_color
                })
            
            conn.close()
            return activities
            
        except Exception as e:
            self.logger.error(f"Erro ao obter atividades recentes: {e}")
            return []
    
    def get_action_color(self, action_type: str) -> str:
        """Determinar cor para tipo de ação"""
        color_map = {
            'LOGIN': 'success',
            'LOGOUT': 'secondary',
            'CREATE': 'primary',
            'UPDATE': 'warning',
            'DELETE': 'danger',
            'ADMIN': 'info',
            'SYSTEM': 'dark',
            'ERROR': 'danger',
            'SECURITY': 'warning'
        }
        return color_map.get(action_type.upper(), 'secondary')
    
    def format_timestamp(self, timestamp_str: str) -> str:
        """Formatar timestamp para exibição"""
        try:
            dt = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
            return dt.strftime('%d/%m %H:%M')
        except:
            return timestamp_str
    
    def get_activity_stats(self) -> Dict:
        """Obter estatísticas de atividades"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Atividades das últimas 24 horas
            yesterday = datetime.now() - timedelta(days=1)
            cursor.execute('''
                SELECT COUNT(*) FROM system_activity 
                WHERE timestamp > ?
            ''', (yesterday.strftime('%Y-%m-%d %H:%M:%S'),))
            
            last_24h = cursor.fetchone()[0]
            
            # Total de atividades
            cursor.execute('SELECT COUNT(*) FROM system_activity')
            total = cursor.fetchone()[0]
            
            # Atividades por tipo nas últimas 24h
            cursor.execute('''
                SELECT action_type, COUNT(*) 
                FROM system_activity 
                WHERE timestamp > ?
                GROUP BY action_type
                ORDER BY COUNT(*) DESC
            ''', (yesterday.strftime('%Y-%m-%d %H:%M:%S'),))
            
            by_type = dict(cursor.fetchall())
            
            conn.close()
            
            return {
                'last_24h': last_24h,
                'total': total,
                'by_type': by_type
            }
            
        except Exception as e:
            self.logger.error(f"Erro ao obter estatísticas: {e}")
            return {'last_24h': 0, 'total': 0, 'by_type': {}}
    
    def cleanup_old_activities(self, days_to_keep: int = 90):
        """Limpar atividades antigas para manter performance"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM system_activity 
                WHERE timestamp < ?
            ''', (cutoff_date.strftime('%Y-%m-%d %H:%M:%S'),))
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            self.logger.info(f"Limpeza de atividades: {deleted_count} registros removidos")
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"Erro na limpeza de atividades: {e}")
            return 0

# Instância global do logger (path padrão, pode ser sobrescrito via init_app)
activity_logger = ActivityLogger(db_path="instance/sistema_os.db")

def create_module_logger(module_name: str, log_level=logging.INFO) -> logging.Logger:
    """
    Criar logger específico para módulo com formatação consistente
    
    Args:
        module_name: Nome do módulo (ex: 'Authentication', 'Backup', 'Reports')
        log_level: Nível de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Returns:
        Logger configurado para o módulo
    """
    # Formatador colorido para console
    console_formatter = ColoredFormatter(
        f'%(asctime)s - %(levelname_color)s%(levelname)s%(reset)s - {module_name} - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Formatador para arquivo
    file_formatter = logging.Formatter(
        f'%(asctime)s - %(levelname)s - {module_name} - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Criar diretório de logs
    os.makedirs('logs', exist_ok=True)
    
    # Handler para arquivo com rotação
    log_filename = f'logs/{module_name.lower().replace(" ", "_")}.log'
    file_handler = RotatingFileHandler(
        log_filename,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
    
    # Handler para console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(console_formatter)
    
    # Configurar logger
    logger = logging.getLogger(module_name)
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.propagate = False
    
    return logger

# Funções de conveniência para uso fácil
def log_login(user_id: int, username: str):
    """Registrar login de usuário"""
    activity_logger.log_activity('LOGIN', f'Usuário {username} fez login', user_id, username)

def log_logout(user_id: int, username: str):
    """Registrar logout de usuário"""
    activity_logger.log_activity('LOGOUT', f'Usuário {username} fez logout', user_id, username)

def log_ticket_create(user_id: int, username: str, ticket_id: int, title: str):
    """Registrar criação de chamado"""
    activity_logger.log_activity('CREATE', f'Criou chamado #{ticket_id}: {title}', 
                                user_id, username, {'ticket_id': ticket_id, 'title': title})

def log_admin_action(user_id: int, username: str, action: str, details: Dict = None):
    """Registrar ação administrativa"""
    activity_logger.log_activity('ADMIN', action, user_id, username, details)

def log_system_event(event: str, details: Dict = None):
    """Registrar evento do sistema"""
    activity_logger.log_activity('SYSTEM', event, details=details)

def log_security_event(event: str, details: Dict = None):
    """Registrar evento de segurança"""
    activity_logger.log_activity('SECURITY', event, details=details)