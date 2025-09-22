#!/usr/bin/env python3
"""
Sistema de Backup Automático - Sistema Olivion
Proteção contra perda de dados com backups programados
"""

import os
import sqlite3
import shutil
import datetime
import logging
import threading
import time
from pathlib import Path

class BackupManager:
    """Gerenciador de backups automáticos do banco de dados"""
    
    def __init__(self, db_path, backup_dir="backups"):
        self.db_path = db_path
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
        
        # Configurar logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - BACKUP - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('backup.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def create_backup(self, backup_type="manual"):
        """Cria backup do banco de dados"""
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"sistema_os_backup_{backup_type}_{timestamp}.db"
            backup_path = self.backup_dir / backup_name
            
            # Backup seguro usando SQLite VACUUM INTO
            conn = sqlite3.connect(self.db_path)
            conn.execute(f"VACUUM INTO '{backup_path}'")
            conn.close()
            
            # Verificar integridade do backup
            if self._verify_backup(backup_path):
                self.logger.info(f"✅ Backup criado com sucesso: {backup_name}")
                return backup_path
            else:
                self.logger.error(f"❌ Backup corrompido removido: {backup_name}")
                backup_path.unlink()
                return None
                
        except Exception as e:
            self.logger.error(f"❌ Erro ao criar backup: {e}")
            return None
    
    def _verify_backup(self, backup_path):
        """Verifica integridade do backup"""
        try:
            conn = sqlite3.connect(backup_path)
            # Testar algumas consultas básicas
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM user")
            user_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM chamado") 
            chamado_count = cursor.fetchone()[0]
            conn.close()
            
            return user_count >= 0 and chamado_count >= 0
        except:
            return False
    
    def cleanup_old_backups(self, keep_days=30):
        """Remove backups antigos para economizar espaço"""
        try:
            cutoff_date = datetime.datetime.now() - datetime.timedelta(days=keep_days)
            
            for backup_file in self.backup_dir.glob("sistema_os_backup_*.db"):
                if backup_file.stat().st_mtime < cutoff_date.timestamp():
                    backup_file.unlink()
                    self.logger.info(f"🗑️ Backup antigo removido: {backup_file.name}")
                    
        except Exception as e:
            self.logger.error(f"❌ Erro na limpeza de backups: {e}")
    
    def restore_backup(self, backup_path):
        """Restaura banco de dados de um backup"""
        try:
            if not Path(backup_path).exists():
                self.logger.error(f"❌ Arquivo de backup não encontrado: {backup_path}")
                return False
            
            # Verificar integridade antes de restaurar
            if not self._verify_backup(backup_path):
                self.logger.error(f"❌ Backup corrompido: {backup_path}")
                return False
            
            # Criar backup do estado atual
            current_backup = self.create_backup("pre_restore")
            
            # Restaurar
            shutil.copy2(backup_path, self.db_path)
            self.logger.info(f"✅ Banco restaurado de: {backup_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Erro ao restaurar backup: {e}")
            return False
    
    def list_backups(self):
        """Lista todos os backups disponíveis"""
        backups = []
        for backup_file in sorted(self.backup_dir.glob("sistema_os_backup_*.db")):
            stat = backup_file.stat()
            backups.append({
                'name': backup_file.name,
                'path': str(backup_file),
                'size': f"{stat.st_size / 1024:.1f} KB",
                'created': datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            })
        return backups
    
    def start_automatic_backups(self, interval_hours=6):
        """Inicia backups automáticos em thread separada"""
        def backup_worker():
            while True:
                self.create_backup("auto")
                self.cleanup_old_backups()
                time.sleep(interval_hours * 3600)  # Converter horas para segundos
        
        thread = threading.Thread(target=backup_worker, daemon=True)
        thread.start()
        self.logger.info(f"🕐 Backups automáticos iniciados (a cada {interval_hours}h)")

if __name__ == "__main__":
    # Teste do sistema de backup
    backup_manager = BackupManager("sistema_os.db")
    
    print("🔄 Criando backup manual...")
    backup_path = backup_manager.create_backup()
    
    print("\n📋 Backups disponíveis:")
    for backup in backup_manager.list_backups():
        print(f"  - {backup['name']} ({backup['size']}) - {backup['created']}")