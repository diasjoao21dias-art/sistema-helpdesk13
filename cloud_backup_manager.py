#!/usr/bin/env python3
"""
Sistema de Backup na Nuvem - Sistema Olivion
Backup automático para armazenamento remoto com redundância
"""

import os
import shutil
import gzip
import json
import sqlite3
import logging
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
import hashlib

class CloudBackupManager:
    """Gerenciador de backup na nuvem com redundância"""
    
    def __init__(self, db_path="sistema_os.db", cloud_backup_dir="cloud_backups"):
        self.db_path = db_path
        self.cloud_backup_dir = Path(cloud_backup_dir)
        self.cloud_backup_dir.mkdir(exist_ok=True)
        
        # Diretórios para diferentes tipos de backup
        self.daily_dir = self.cloud_backup_dir / "daily"
        self.weekly_dir = self.cloud_backup_dir / "weekly"
        self.monthly_dir = self.cloud_backup_dir / "monthly"
        
        for dir_path in [self.daily_dir, self.weekly_dir, self.monthly_dir]:
            dir_path.mkdir(exist_ok=True)
        
        # Configurar logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - CLOUD_BACKUP - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def calculate_file_hash(self, file_path):
        """Calcula hash MD5 do arquivo para verificação de integridade"""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            self.logger.error(f"❌ Erro ao calcular hash: {e}")
            return None
    
    def compress_file(self, source_path, dest_path):
        """Comprime arquivo usando gzip para economizar espaço"""
        try:
            with open(source_path, 'rb') as f_in:
                with gzip.open(dest_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            return True
        except Exception as e:
            self.logger.error(f"❌ Erro na compressão: {e}")
            return False
    
    def create_backup_metadata(self, backup_path, backup_type):
        """Cria metadados do backup para controle de versão"""
        try:
            # Calcular estatísticas do banco
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Obter contadores de tabelas
            cursor.execute("SELECT COUNT(*) FROM user")
            user_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM chamado")
            chamado_count = cursor.fetchone()[0]
            
            # Obter tamanho do banco
            cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
            db_size = cursor.fetchone()[0]
            
            conn.close()
            
            # Hash do backup
            backup_hash = self.calculate_file_hash(backup_path)
            
            # Metadados
            metadata = {
                'backup_type': backup_type,
                'created_at': datetime.now().isoformat(),
                'file_size': os.path.getsize(backup_path),
                'compressed_size': os.path.getsize(backup_path),
                'file_hash': backup_hash,
                'database_stats': {
                    'user_count': user_count,
                    'chamado_count': chamado_count,
                    'database_size': db_size
                },
                'source_database': self.db_path,
                'backup_version': '1.0'
            }
            
            # Salvar metadados
            metadata_path = backup_path.with_suffix('.json')
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            return metadata
            
        except Exception as e:
            self.logger.error(f"❌ Erro ao criar metadados: {e}")
            return None
    
    def create_daily_backup(self):
        """Cria backup diário comprimido"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"daily_backup_{timestamp}.db.gz"
            backup_path = self.daily_dir / backup_name
            
            # Comprimir e salvar
            if self.compress_file(self.db_path, backup_path):
                metadata = self.create_backup_metadata(backup_path, "daily")
                if metadata:
                    self.logger.info(f"✅ Backup diário criado: {backup_name}")
                    return backup_path
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Erro no backup diário: {e}")
            return None
    
    def create_weekly_backup(self):
        """Cria backup semanal (aos domingos)"""
        try:
            if datetime.now().weekday() != 6:  # 6 = domingo
                return None
            
            timestamp = datetime.now().strftime("%Y_W%U")
            backup_name = f"weekly_backup_{timestamp}.db.gz"
            backup_path = self.weekly_dir / backup_name
            
            # Evitar duplicatas
            if backup_path.exists():
                return backup_path
            
            if self.compress_file(self.db_path, backup_path):
                metadata = self.create_backup_metadata(backup_path, "weekly")
                if metadata:
                    self.logger.info(f"✅ Backup semanal criado: {backup_name}")
                    return backup_path
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Erro no backup semanal: {e}")
            return None
    
    def create_monthly_backup(self):
        """Cria backup mensal (primeiro dia do mês)"""
        try:
            if datetime.now().day != 1:
                return None
            
            timestamp = datetime.now().strftime("%Y_%m")
            backup_name = f"monthly_backup_{timestamp}.db.gz"
            backup_path = self.monthly_dir / backup_name
            
            # Evitar duplicatas
            if backup_path.exists():
                return backup_path
            
            if self.compress_file(self.db_path, backup_path):
                metadata = self.create_backup_metadata(backup_path, "monthly")
                if metadata:
                    self.logger.info(f"✅ Backup mensal criado: {backup_name}")
                    return backup_path
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Erro no backup mensal: {e}")
            return None
    
    def cleanup_old_backups(self):
        """Remove backups antigos baseado na política de retenção"""
        try:
            current_time = datetime.now()
            
            # Política de retenção
            policies = {
                'daily': (self.daily_dir, 30),      # 30 dias
                'weekly': (self.weekly_dir, 12),    # 12 semanas  
                'monthly': (self.monthly_dir, 24)   # 24 meses
            }
            
            for backup_type, (directory, retention_count) in policies.items():
                # Listar backups ordenados por data (mais recente primeiro)
                backups = sorted(
                    directory.glob(f"{backup_type}_backup_*.db.gz"),
                    key=lambda x: x.stat().st_mtime,
                    reverse=True
                )
                
                # Remover backups excedentes
                if len(backups) > retention_count:
                    for old_backup in backups[retention_count:]:
                        old_backup.unlink()
                        # Remover metadados também
                        metadata_file = old_backup.with_suffix('.json')
                        if metadata_file.exists():
                            metadata_file.unlink()
                        
                        self.logger.info(f"🗑️ Backup antigo removido: {old_backup.name}")
            
        except Exception as e:
            self.logger.error(f"❌ Erro na limpeza: {e}")
    
    def verify_backup_integrity(self, backup_path):
        """Verifica integridade do backup"""
        try:
            if not backup_path.exists():
                return False
            
            # Verificar metadados
            metadata_path = backup_path.with_suffix('.json')
            if not metadata_path.exists():
                return False
            
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            # Verificar hash
            current_hash = self.calculate_file_hash(backup_path)
            stored_hash = metadata.get('file_hash')
            
            if current_hash != stored_hash:
                self.logger.error(f"❌ Hash inválido para backup: {backup_path.name}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Erro na verificação: {e}")
            return False
    
    def get_backup_statistics(self):
        """Retorna estatísticas dos backups"""
        try:
            stats = {
                'daily': {'count': 0, 'total_size': 0},
                'weekly': {'count': 0, 'total_size': 0},
                'monthly': {'count': 0, 'total_size': 0}
            }
            
            for backup_type in ['daily', 'weekly', 'monthly']:
                directory = getattr(self, f"{backup_type}_dir")
                backups = list(directory.glob(f"{backup_type}_backup_*.db.gz"))
                
                stats[backup_type]['count'] = len(backups)
                stats[backup_type]['total_size'] = sum(
                    backup.stat().st_size for backup in backups
                )
            
            return stats
            
        except Exception as e:
            self.logger.error(f"❌ Erro nas estatísticas: {e}")
            return {}
    
    def run_scheduled_backup(self):
        """Executa backup programado com todas as políticas"""
        try:
            self.logger.info("🔄 Iniciando backup programado...")
            
            # Criar backups baseado no dia
            backups_created = []
            
            # Backup diário (sempre)
            daily_backup = self.create_daily_backup()
            if daily_backup:
                backups_created.append(('daily', daily_backup))
            
            # Backup semanal (domingos)
            weekly_backup = self.create_weekly_backup()
            if weekly_backup:
                backups_created.append(('weekly', weekly_backup))
            
            # Backup mensal (primeiro dia do mês)
            monthly_backup = self.create_monthly_backup()
            if monthly_backup:
                backups_created.append(('monthly', monthly_backup))
            
            # Limpeza de backups antigos
            self.cleanup_old_backups()
            
            # Verificar integridade dos novos backups
            for backup_type, backup_path in backups_created:
                if not self.verify_backup_integrity(backup_path):
                    self.logger.error(f"❌ Falha na integridade: {backup_type}")
            
            self.logger.info(f"✅ Backup programado concluído: {len(backups_created)} backups criados")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Erro no backup programado: {e}")
            return False
    
    def start_automatic_backups(self, interval_hours=6):
        """Inicia backups automáticos em thread separada"""
        def backup_worker():
            while True:
                self.run_scheduled_backup()
                time.sleep(interval_hours * 3600)
        
        thread = threading.Thread(target=backup_worker, daemon=True)
        thread.start()
        self.logger.info(f"🕐 Backups automáticos iniciados (a cada {interval_hours}h)")

if __name__ == "__main__":
    # Teste do sistema de backup
    cloud_backup = CloudBackupManager()
    
    print("🔄 Executando backup de teste...")
    success = cloud_backup.run_scheduled_backup()
    
    if success:
        stats = cloud_backup.get_backup_statistics()
        print("📊 Estatísticas de backup:")
        for backup_type, data in stats.items():
            size_mb = data['total_size'] / 1024 / 1024
            print(f"  {backup_type}: {data['count']} backups, {size_mb:.2f} MB")
    else:
        print("❌ Falha no backup")