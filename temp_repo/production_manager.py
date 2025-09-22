#!/usr/bin/env python3
"""
Gerenciador de Produção - Sistema Olivion
Sistema integrado para preparação e gerenciamento de produção
"""

import os
import logging
from datetime import datetime
from pathlib import Path

# Importar todos os sistemas
try:
    from postgresql_migration import PostgreSQLMigrator
    from cloud_backup_manager import CloudBackupManager
    from monitoring_system import MonitoringSystem
    from maintenance_scheduler import MaintenanceScheduler
    from backup_manager import BackupManager
    from database_safety import DatabaseSafety
except ImportError as e:
    print(f"⚠️ Alguns sistemas não disponíveis: {e}")

class ProductionManager:
    """Gerenciador integrado para ambiente de produção"""
    
    def __init__(self, db_path="sistema_os.db"):
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        
        # Inicializar todos os sistemas
        self.migrator = PostgreSQLMigrator(db_path) if 'PostgreSQLMigrator' in locals() else None
        self.cloud_backup = CloudBackupManager(db_path) if 'CloudBackupManager' in locals() else None
        self.monitoring = MonitoringSystem(db_path) if 'MonitoringSystem' in locals() else None
        self.scheduler = MaintenanceScheduler(db_path) if 'MaintenanceScheduler' in locals() else None
        self.backup_manager = BackupManager(db_path) if 'BackupManager' in locals() else None
        self.db_safety = DatabaseSafety(db_path) if 'DatabaseSafety' in locals() else None
        
        # Configurar logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - PRODUCTION - %(levelname)s - %(message)s'
        )
    
    def check_production_readiness(self):
        """Verifica se sistema está pronto para produção"""
        self.logger.info("🔍 Verificando prontidão para produção...")
        
        checks = {
            'database_integrity': False,
            'backup_system': False,
            'monitoring_system': False,
            'maintenance_scheduler': False,
            'security_settings': False
        }
        
        issues = []
        
        # 1. Verificar integridade do banco
        try:
            if self.db_safety:
                is_healthy, _ = self.db_safety.check_database_integrity()
                checks['database_integrity'] = is_healthy
                if not is_healthy:
                    issues.append("Problemas de integridade no banco de dados")
        except Exception as e:
            issues.append(f"Erro na verificação de integridade: {e}")
        
        # 2. Verificar sistema de backup
        try:
            if self.backup_manager:
                backup_path = self.backup_manager.create_backup("readiness_check")
                checks['backup_system'] = backup_path is not None
                if not backup_path:
                    issues.append("Sistema de backup não funcional")
        except Exception as e:
            issues.append(f"Erro no sistema de backup: {e}")
        
        # 3. Verificar monitoramento
        try:
            if self.monitoring:
                cycle_data = self.monitoring.perform_monitoring_cycle()
                checks['monitoring_system'] = cycle_data is not None
                if not cycle_data:
                    issues.append("Sistema de monitoramento não funcional")
        except Exception as e:
            issues.append(f"Erro no sistema de monitoramento: {e}")
        
        # 4. Verificar scheduler de manutenção
        try:
            if self.scheduler:
                status = self.scheduler.get_maintenance_status()
                checks['maintenance_scheduler'] = status is not None
                if not status:
                    issues.append("Agendador de manutenção não funcional")
        except Exception as e:
            issues.append(f"Erro no agendador de manutenção: {e}")
        
        # 5. Verificar configurações de segurança
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("PRAGMA foreign_keys")
            fk_enabled = cursor.fetchone()[0]
            
            cursor.execute("PRAGMA journal_mode")
            journal_mode = cursor.fetchone()[0]
            
            cursor.execute("PRAGMA synchronous")
            sync_mode = cursor.fetchone()[0]
            
            conn.close()
            
            # Verificar configurações seguras
            secure_config = (fk_enabled == 1 and 
                           journal_mode == 'wal' and 
                           sync_mode >= 2)
            
            checks['security_settings'] = secure_config
            if not secure_config:
                issues.append(f"Configurações inseguras: FK={fk_enabled}, WAL={journal_mode}, SYNC={sync_mode}")
        
        except Exception as e:
            issues.append(f"Erro na verificação de segurança: {e}")
        
        # Calcular score de prontidão
        readiness_score = sum(checks.values()) / len(checks) * 100
        
        result = {
            'ready_for_production': readiness_score >= 80,
            'readiness_score': round(readiness_score, 1),
            'checks_passed': checks,
            'issues': issues,
            'timestamp': datetime.now().isoformat()
        }
        
        if result['ready_for_production']:
            self.logger.info(f"✅ Sistema PRONTO para produção (Score: {readiness_score}%)")
        else:
            self.logger.warning(f"⚠️ Sistema NÃO pronto para produção (Score: {readiness_score}%)")
            for issue in issues:
                self.logger.warning(f"  - {issue}")
        
        return result
    
    def prepare_for_production(self):
        """Prepara sistema para ambiente de produção"""
        self.logger.info("🚀 Preparando sistema para produção...")
        
        preparation_steps = []
        
        # 1. Criar backup pré-produção
        try:
            if self.backup_manager:
                backup_path = self.backup_manager.create_backup("pre_production")
                if backup_path:
                    preparation_steps.append(("Backup pré-produção", "SUCESSO", str(backup_path)))
                else:
                    preparation_steps.append(("Backup pré-produção", "FALHA", "Não foi possível criar backup"))
        except Exception as e:
            preparation_steps.append(("Backup pré-produção", "ERRO", str(e)))
        
        # 2. Configurar sistemas de segurança
        try:
            if self.db_safety:
                # Aplicar configurações de segurança
                import sqlite3
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute("PRAGMA foreign_keys = ON")
                cursor.execute("PRAGMA journal_mode = WAL")
                cursor.execute("PRAGMA synchronous = FULL")
                cursor.execute("PRAGMA temp_store = MEMORY")
                cursor.execute("PRAGMA cache_size = 10000")
                
                conn.close()
                preparation_steps.append(("Configurações de segurança", "SUCESSO", "Aplicadas"))
        except Exception as e:
            preparation_steps.append(("Configurações de segurança", "ERRO", str(e)))
        
        # 3. Iniciar monitoramento
        try:
            if self.monitoring and not self.monitoring.monitoring_active:
                self.monitoring.start_monitoring()
                preparation_steps.append(("Monitoramento 24/7", "SUCESSO", "Iniciado"))
        except Exception as e:
            preparation_steps.append(("Monitoramento 24/7", "ERRO", str(e)))
        
        # 4. Configurar manutenção automática
        try:
            if self.scheduler and not self.scheduler.maintenance_active:
                self.scheduler.start_scheduler()
                preparation_steps.append(("Manutenção automática", "SUCESSO", "Agendada"))
        except Exception as e:
            preparation_steps.append(("Manutenção automática", "ERRO", str(e)))
        
        # 5. Configurar backups na nuvem
        try:
            if self.cloud_backup:
                self.cloud_backup.start_automatic_backups(interval_hours=6)
                preparation_steps.append(("Backup na nuvem", "SUCESSO", "Ativo a cada 6h"))
        except Exception as e:
            preparation_steps.append(("Backup na nuvem", "ERRO", str(e)))
        
        # Verificar resultados
        successful_steps = sum(1 for step in preparation_steps if step[1] == "SUCESSO")
        total_steps = len(preparation_steps)
        success_rate = successful_steps / total_steps * 100
        
        result = {
            'preparation_successful': success_rate >= 80,
            'success_rate': round(success_rate, 1),
            'steps_completed': preparation_steps,
            'timestamp': datetime.now().isoformat()
        }
        
        if result['preparation_successful']:
            self.logger.info(f"✅ Preparação concluída com sucesso ({success_rate}%)")
        else:
            self.logger.warning(f"⚠️ Preparação incompleta ({success_rate}%)")
        
        return result
    
    def migrate_to_postgresql(self):
        """Migra para PostgreSQL se disponível"""
        try:
            if not self.migrator:
                return {
                    'migration_successful': False,
                    'reason': 'Sistema de migração não disponível',
                    'timestamp': datetime.now().isoformat()
                }
            
            self.logger.info("📦 Iniciando migração para PostgreSQL...")
            
            # Verificar disponibilidade PostgreSQL
            available, missing = self.migrator.check_postgresql_availability()
            
            if not available:
                return {
                    'migration_successful': False,
                    'reason': f'PostgreSQL não configurado. Variáveis ausentes: {missing}',
                    'timestamp': datetime.now().isoformat()
                }
            
            # Executar migração
            success = self.migrator.full_migration()
            
            result = {
                'migration_successful': success,
                'reason': 'Migração concluída' if success else 'Falha na migração',
                'timestamp': datetime.now().isoformat()
            }
            
            if success:
                self.logger.info("✅ Migração PostgreSQL concluída")
            else:
                self.logger.error("❌ Falha na migração PostgreSQL")
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Erro na migração: {e}")
            return {
                'migration_successful': False,
                'reason': f'Erro: {e}',
                'timestamp': datetime.now().isoformat()
            }
    
    def get_production_status(self):
        """Retorna status completo do sistema de produção"""
        try:
            status = {
                'timestamp': datetime.now().isoformat(),
                'systems': {}
            }
            
            # Status de cada sistema
            if self.monitoring:
                summary = self.monitoring.get_monitoring_summary(1)  # Última hora
                status['systems']['monitoring'] = {
                    'active': self.monitoring.monitoring_active,
                    'last_check': summary.get('last_check'),
                    'alerts': summary.get('alerts', {})
                }
            
            if self.scheduler:
                maint_status = self.scheduler.get_maintenance_status()
                status['systems']['maintenance'] = {
                    'active': maint_status.get('scheduler_active', False),
                    'tasks_executed': maint_status.get('total_tasks_executed', 0),
                    'next_scheduled': maint_status.get('next_scheduled', {})
                }
            
            if self.cloud_backup:
                backup_stats = self.cloud_backup.get_backup_statistics()
                status['systems']['cloud_backup'] = {
                    'active': True,
                    'statistics': backup_stats
                }
            
            # Verificação de prontidão
            readiness = self.check_production_readiness()
            status['readiness'] = readiness
            
            return status
            
        except Exception as e:
            self.logger.error(f"❌ Erro ao obter status: {e}")
            return {
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }

if __name__ == "__main__":
    # Teste do gerenciador de produção
    manager = ProductionManager()
    
    print("🔍 Verificando prontidão para produção...")
    readiness = manager.check_production_readiness()
    
    print(f"📊 Score de prontidão: {readiness['readiness_score']}%")
    print(f"✅ Pronto para produção: {'SIM' if readiness['ready_for_production'] else 'NÃO'}")
    
    if readiness['issues']:
        print("⚠️ Problemas encontrados:")
        for issue in readiness['issues']:
            print(f"  - {issue}")
    
    if readiness['ready_for_production']:
        print("\n🚀 Preparando para produção...")
        preparation = manager.prepare_for_production()
        print(f"✅ Preparação: {preparation['success_rate']}% concluída")