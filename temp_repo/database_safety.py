#!/usr/bin/env python3
"""
Sistema de Segurança de Banco de Dados - Sistema Olivion
Transações seguras, validações e monitoramento
"""

import sqlite3
import functools
import logging
from datetime import datetime
from contextlib import contextmanager

class DatabaseSafety:
    """Gerenciador de segurança para operações de banco de dados"""
    
    def __init__(self, db_path):
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        
        # Configurar SQLite para máxima segurança
        self._configure_safety_settings()
    
    def _configure_safety_settings(self):
        """Configura SQLite para máxima segurança e integridade"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Configurações críticas de segurança
            cursor.execute("PRAGMA foreign_keys = ON")           # Integridade referencial
            cursor.execute("PRAGMA journal_mode = WAL")          # Write-Ahead Logging
            cursor.execute("PRAGMA synchronous = FULL")          # Máxima durabilidade
            cursor.execute("PRAGMA temp_store = MEMORY")         # Temp em memória
            cursor.execute("PRAGMA cache_size = 10000")          # Cache maior
            cursor.execute("PRAGMA mmap_size = 268435456")       # 256MB mmap
            
            conn.commit()
            conn.close()
            
            self.logger.info("✅ Configurações de segurança aplicadas")
            
        except Exception as e:
            self.logger.error(f"❌ Erro ao configurar segurança: {e}")
    
    @contextmanager
    def safe_transaction(self):
        """Context manager para transações seguras"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        
        try:
            conn.execute("BEGIN IMMEDIATE")  # Lock imediato
            yield conn
            conn.commit()
            self.logger.debug("✅ Transação commitada com sucesso")
            
        except Exception as e:
            conn.rollback()
            self.logger.error(f"❌ Transação revertida: {e}")
            raise
        finally:
            conn.close()
    
    def safe_operation(func):
        """Decorator para operações seguras com transação automática"""
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                with self.safe_transaction() as conn:
                    return func(self, conn, *args, **kwargs)
            except Exception as e:
                self.logger.error(f"❌ Operação {func.__name__} falhou: {e}")
                raise
        return wrapper
    
    def check_database_integrity(self):
        """Verifica integridade completa do banco de dados"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Verificar integridade estrutural
            cursor.execute("PRAGMA integrity_check")
            integrity_result = cursor.fetchone()[0]
            
            # Verificar foreign keys
            cursor.execute("PRAGMA foreign_key_check")
            fk_violations = cursor.fetchall()
            
            # Verificar estatísticas das tabelas
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            stats = {}
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                stats[table] = cursor.fetchone()[0]
            
            conn.close()
            
            report = {
                'integrity': integrity_result,
                'foreign_key_violations': len(fk_violations),
                'table_stats': stats,
                'timestamp': datetime.now().isoformat()
            }
            
            if integrity_result == "ok" and len(fk_violations) == 0:
                self.logger.info("✅ Banco de dados íntegro")
                return True, report
            else:
                self.logger.warning(f"⚠️ Problemas detectados: {fk_violations}")
                return False, report
                
        except Exception as e:
            self.logger.error(f"❌ Erro ao verificar integridade: {e}")
            return False, {'error': str(e)}
    
    def create_audit_log_table(self):
        """Cria tabela de auditoria para rastreamento de mudanças"""
        try:
            with self.safe_transaction() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS audit_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        table_name TEXT NOT NULL,
                        operation TEXT NOT NULL,
                        record_id TEXT,
                        old_values TEXT,
                        new_values TEXT,
                        user_id INTEGER,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        ip_address TEXT
                    )
                """)
                
                # Índice para consultas rápidas
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp 
                    ON audit_log(timestamp DESC)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_audit_log_table_operation 
                    ON audit_log(table_name, operation)
                """)
                
            self.logger.info("✅ Tabela de auditoria criada")
            
        except Exception as e:
            self.logger.error(f"❌ Erro ao criar tabela de auditoria: {e}")
    
    def log_database_operation(self, table_name, operation, record_id=None, 
                             old_values=None, new_values=None, user_id=None, ip_address=None):
        """Registra operação no log de auditoria"""
        try:
            with self.safe_transaction() as conn:
                conn.execute("""
                    INSERT INTO audit_log 
                    (table_name, operation, record_id, old_values, new_values, user_id, ip_address)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (table_name, operation, record_id, old_values, new_values, user_id, ip_address))
                
        except Exception as e:
            self.logger.error(f"❌ Erro ao registrar auditoria: {e}")
    
    def get_database_statistics(self):
        """Retorna estatísticas detalhadas do banco de dados"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Tamanho do banco
            cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
            db_size = cursor.fetchone()[0]
            
            # Número de páginas livres
            cursor.execute("PRAGMA freelist_count")
            free_pages = cursor.fetchone()[0]
            
            # Estatísticas por tabela
            table_stats = {}
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            
            for (table_name,) in cursor.fetchall():
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                row_count = cursor.fetchone()[0]
                
                table_stats[table_name] = {
                    'row_count': row_count
                }
            
            conn.close()
            
            return {
                'database_size_bytes': db_size,
                'database_size_mb': round(db_size / 1024 / 1024, 2),
                'free_pages': free_pages,
                'table_statistics': table_stats,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"❌ Erro ao obter estatísticas: {e}")
            return {'error': str(e)}

# Instância global para uso na aplicação
database_safety = DatabaseSafety("sistema_os.db")