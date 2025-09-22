#!/usr/bin/env python3
"""
Sistema de Manutenção Automatizada - Sistema Olivion
Automação de tarefas de manutenção preventiva
"""

import os
import sqlite3
import threading
import time
import logging
import schedule
from datetime import datetime, timedelta
from pathlib import Path

# Importar nossos sistemas
try:
    from backup_manager import BackupManager
    from database_safety import DatabaseSafety
    from cloud_backup_manager import CloudBackupManager
    from monitoring_system import MonitoringSystem
except ImportError as e:
    print(f"⚠️ Alguns sistemas não disponíveis: {e}")

class MaintenanceScheduler:
    """Agendador de manutenção preventiva automatizada"""
    
    def __init__(self, db_path="sistema_os.db"):
        self.db_path = db_path
        self.maintenance_active = False
        self.maintenance_log = []
        
        # Inicializar sistemas
        try:
            self.backup_manager = BackupManager(db_path)
            self.db_safety = DatabaseSafety(db_path)
            self.cloud_backup = CloudBackupManager(db_path)
            self.monitoring = MonitoringSystem(db_path)
        except:
            # Fallback se sistemas não estiverem disponíveis
            self.backup_manager = None
            self.db_safety = None
            self.cloud_backup = None
            self.monitoring = None
        
        # Configurar logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - MAINTENANCE - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('maintenance.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def log_maintenance_task(self, task_name, status, details=None):
        """Registra tarefa de manutenção"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'task': task_name,
            'status': status,
            'details': details or {}
        }
        
        self.maintenance_log.append(log_entry)
        
        # Manter apenas últimos 1000 logs
        if len(self.maintenance_log) > 1000:
            self.maintenance_log = self.maintenance_log[-1000:]
        
        # Log
        self.logger.info(f"🔧 {task_name}: {status}")
    
    def verify_database_integrity(self):
        """Tarefa: Verificar integridade do banco de dados"""
        try:
            self.logger.info("🔍 Iniciando verificação de integridade...")
            
            if self.db_safety:
                is_healthy, report = self.db_safety.check_database_integrity()
                
                if is_healthy:
                    self.log_maintenance_task(
                        "Verificação de Integridade",
                        "SUCESSO",
                        {"integrity": "OK", "report": report}
                    )
                    return True
                else:
                    self.log_maintenance_task(
                        "Verificação de Integridade",
                        "FALHA",
                        {"integrity": "PROBLEMAS", "report": report}
                    )
                    return False
            else:
                # Verificação manual básica
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("PRAGMA integrity_check")
                result = cursor.fetchone()[0]
                conn.close()
                
                if result == "ok":
                    self.log_maintenance_task("Verificação de Integridade", "SUCESSO")
                    return True
                else:
                    self.log_maintenance_task("Verificação de Integridade", "FALHA", {"result": result})
                    return False
                    
        except Exception as e:
            self.log_maintenance_task("Verificação de Integridade", "ERRO", {"error": str(e)})
            return False
    
    def create_maintenance_backup(self):
        """Tarefa: Criar backup de manutenção"""
        try:
            self.logger.info("💾 Criando backup de manutenção...")
            
            if self.backup_manager:
                backup_path = self.backup_manager.create_backup("maintenance")
                
                if backup_path:
                    self.log_maintenance_task(
                        "Backup de Manutenção",
                        "SUCESSO",
                        {"backup_path": str(backup_path)}
                    )
                    return True
                else:
                    self.log_maintenance_task("Backup de Manutenção", "FALHA")
                    return False
            else:
                # Backup manual básico
                backup_dir = Path("maintenance_backups")
                backup_dir.mkdir(exist_ok=True)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = backup_dir / f"maintenance_backup_{timestamp}.db"
                
                import shutil
                shutil.copy2(self.db_path, backup_path)
                
                self.log_maintenance_task("Backup de Manutenção", "SUCESSO", {"backup_path": str(backup_path)})
                return True
                
        except Exception as e:
            self.log_maintenance_task("Backup de Manutenção", "ERRO", {"error": str(e)})
            return False
    
    def cleanup_audit_logs(self, days_to_keep=90):
        """Tarefa: Limpar logs de auditoria antigos"""
        try:
            self.logger.info(f"🧹 Limpando logs de auditoria (>{days_to_keep} dias)...")
            
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Verificar se tabela de auditoria existe
            cursor.execute("""
                SELECT COUNT(*) FROM sqlite_master 
                WHERE type='table' AND name='audit_log'
            """)
            
            if cursor.fetchone()[0] == 0:
                conn.close()
                self.log_maintenance_task("Limpeza de Auditoria", "PULADO", {"reason": "Tabela não existe"})
                return True
            
            # Contar logs antigos
            cursor.execute("""
                SELECT COUNT(*) FROM audit_log 
                WHERE timestamp < ?
            """, (cutoff_date.isoformat(),))
            
            old_logs_count = cursor.fetchone()[0]
            
            if old_logs_count > 0:
                # Remover logs antigos
                cursor.execute("""
                    DELETE FROM audit_log 
                    WHERE timestamp < ?
                """, (cutoff_date.isoformat(),))
                
                conn.commit()
                
                self.log_maintenance_task(
                    "Limpeza de Auditoria",
                    "SUCESSO",
                    {"logs_removidos": old_logs_count, "dias_mantidos": days_to_keep}
                )
            else:
                self.log_maintenance_task("Limpeza de Auditoria", "NADA_PARA_FAZER")
            
            conn.close()
            return True
            
        except Exception as e:
            self.log_maintenance_task("Limpeza de Auditoria", "ERRO", {"error": str(e)})
            return False
    
    def optimize_database(self):
        """Tarefa: Otimizar banco de dados"""
        try:
            self.logger.info("⚡ Otimizando banco de dados...")
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Tamanho antes da otimização
            cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
            size_before = cursor.fetchone()[0]
            
            # Executar otimizações
            cursor.execute("VACUUM")  # Recompactar banco
            cursor.execute("ANALYZE") # Atualizar estatísticas
            cursor.execute("REINDEX") # Reconstruir índices
            
            # Tamanho após otimização
            cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
            size_after = cursor.fetchone()[0]
            
            conn.close()
            
            space_saved = size_before - size_after
            space_saved_mb = space_saved / 1024 / 1024
            
            self.log_maintenance_task(
                "Otimização do Banco",
                "SUCESSO",
                {
                    "tamanho_antes_mb": round(size_before / 1024 / 1024, 2),
                    "tamanho_depois_mb": round(size_after / 1024 / 1024, 2),
                    "espaco_liberado_mb": round(space_saved_mb, 2)
                }
            )
            
            return True
            
        except Exception as e:
            self.log_maintenance_task("Otimização do Banco", "ERRO", {"error": str(e)})
            return False
    
    def cleanup_old_uploads(self, days_to_keep=365):
        """Tarefa: Limpar uploads antigos órfãos"""
        try:
            self.logger.info(f"🗂️ Limpando uploads antigos (>{days_to_keep} dias)...")
            
            uploads_dir = Path("static/uploads")
            if not uploads_dir.exists():
                self.log_maintenance_task("Limpeza de Uploads", "PULADO", {"reason": "Diretório não existe"})
                return True
            
            # Obter lista de arquivos em uso
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT imagem_filename FROM chamado WHERE imagem_filename IS NOT NULL")
            files_in_use = {row[0] for row in cursor.fetchall()}
            conn.close()
            
            # Verificar arquivos órfãos antigos
            cutoff_time = time.time() - (days_to_keep * 24 * 60 * 60)
            files_removed = 0
            space_freed = 0
            
            for file_path in uploads_dir.iterdir():
                if file_path.is_file():
                    # Verificar se arquivo está órfão e antigo
                    if (file_path.name not in files_in_use and 
                        file_path.stat().st_mtime < cutoff_time):
                        
                        file_size = file_path.stat().st_size
                        file_path.unlink()
                        files_removed += 1
                        space_freed += file_size
            
            space_freed_mb = space_freed / 1024 / 1024
            
            self.log_maintenance_task(
                "Limpeza de Uploads",
                "SUCESSO" if files_removed > 0 else "NADA_PARA_FAZER",
                {
                    "arquivos_removidos": files_removed,
                    "espaco_liberado_mb": round(space_freed_mb, 2),
                    "dias_mantidos": days_to_keep
                }
            )
            
            return True
            
        except Exception as e:
            self.log_maintenance_task("Limpeza de Uploads", "ERRO", {"error": str(e)})
            return False
    
    def generate_maintenance_report(self):
        """Tarefa: Gerar relatório de manutenção"""
        try:
            self.logger.info("📊 Gerando relatório de manutenção...")
            
            # Estatísticas do banco
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM user")
            user_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM chamado")
            chamado_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM chamado WHERE status = 'aberto'")
            open_chamados = cursor.fetchone()[0]
            
            cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
            db_size = cursor.fetchone()[0]
            
            conn.close()
            
            # Estatísticas de manutenção (última semana)
            week_ago = datetime.now() - timedelta(days=7)
            recent_tasks = [
                task for task in self.maintenance_log
                if datetime.fromisoformat(task['timestamp']) > week_ago
            ]
            
            task_summary = {}
            for task in recent_tasks:
                task_name = task['task']
                status = task['status']
                
                if task_name not in task_summary:
                    task_summary[task_name] = {'SUCESSO': 0, 'FALHA': 0, 'ERRO': 0, 'PULADO': 0, 'NADA_PARA_FAZER': 0}
                
                task_summary[task_name][status] = task_summary[task_name].get(status, 0) + 1
            
            report = {
                'timestamp': datetime.now().isoformat(),
                'sistema': {
                    'usuarios_totais': user_count,
                    'chamados_totais': chamado_count,
                    'chamados_abertos': open_chamados,
                    'tamanho_banco_mb': round(db_size / 1024 / 1024, 2)
                },
                'manutencao_ultima_semana': {
                    'total_tarefas': len(recent_tasks),
                    'resumo_por_tarefa': task_summary
                }
            }
            
            # Salvar relatório
            report_dir = Path("maintenance_reports")
            report_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_path = report_dir / f"maintenance_report_{timestamp}.json"
            
            import json
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2)
            
            self.log_maintenance_task(
                "Relatório de Manutenção",
                "SUCESSO",
                {"report_path": str(report_path), "tarefas_semana": len(recent_tasks)}
            )
            
            return True
            
        except Exception as e:
            self.log_maintenance_task("Relatório de Manutenção", "ERRO", {"error": str(e)})
            return False
    
    def run_daily_maintenance(self):
        """Executa manutenção diária"""
        self.logger.info("🌅 Iniciando manutenção diária...")
        
        tasks = [
            self.verify_database_integrity,
            self.create_maintenance_backup,
            self.optimize_database
        ]
        
        results = []
        for task in tasks:
            results.append(task())
        
        success_rate = sum(results) / len(results) * 100
        self.logger.info(f"✅ Manutenção diária concluída: {success_rate:.1f}% sucesso")
        
        return success_rate > 80
    
    def run_weekly_maintenance(self):
        """Executa manutenção semanal"""
        self.logger.info("📅 Iniciando manutenção semanal...")
        
        tasks = [
            self.verify_database_integrity,
            self.create_maintenance_backup,
            lambda: self.cleanup_audit_logs(90),  # 90 dias
            self.optimize_database,
            lambda: self.cleanup_old_uploads(365), # 1 ano
            self.generate_maintenance_report
        ]
        
        results = []
        for task in tasks:
            results.append(task())
        
        success_rate = sum(results) / len(results) * 100
        self.logger.info(f"✅ Manutenção semanal concluída: {success_rate:.1f}% sucesso")
        
        return success_rate > 75
    
    def run_monthly_maintenance(self):
        """Executa manutenção mensal"""
        self.logger.info("📆 Iniciando manutenção mensal...")
        
        tasks = [
            self.verify_database_integrity,
            self.create_maintenance_backup,
            lambda: self.cleanup_audit_logs(60),   # 60 dias
            self.optimize_database,
            lambda: self.cleanup_old_uploads(180), # 6 meses
            self.generate_maintenance_report
        ]
        
        results = []
        for task in tasks:
            results.append(task())
        
        success_rate = sum(results) / len(results) * 100
        self.logger.info(f"✅ Manutenção mensal concluída: {success_rate:.1f}% sucesso")
        
        return success_rate > 75
    
    def setup_maintenance_schedule(self):
        """Configura agendamento de manutenção"""
        # Manutenção diária às 02:00
        schedule.every().day.at("02:00").do(self.run_daily_maintenance)
        
        # Manutenção semanal aos domingos às 03:00
        schedule.every().sunday.at("03:00").do(self.run_weekly_maintenance)
        
        # Manutenção mensal no primeiro dia do mês às 04:00
        schedule.every().day.at("04:00").do(self._check_monthly_maintenance)
        
        self.logger.info("📋 Agendamento de manutenção configurado")
    
    def _check_monthly_maintenance(self):
        """Verifica se deve executar manutenção mensal"""
        if datetime.now().day == 1:  # Primeiro dia do mês
            self.run_monthly_maintenance()
    
    def start_scheduler(self):
        """Inicia agendador de manutenção"""
        self.maintenance_active = True
        self.setup_maintenance_schedule()
        
        def scheduler_worker():
            while self.maintenance_active:
                schedule.run_pending()
                time.sleep(60)  # Verificar a cada minuto
        
        thread = threading.Thread(target=scheduler_worker, daemon=True)
        thread.start()
        
        self.logger.info("⏰ Agendador de manutenção iniciado")
    
    def stop_scheduler(self):
        """Para agendador de manutenção"""
        self.maintenance_active = False
        schedule.clear()
        self.logger.info("🛑 Agendador de manutenção parado")
    
    def get_maintenance_status(self):
        """Retorna status da manutenção"""
        recent_tasks = self.maintenance_log[-10:] if self.maintenance_log else []
        
        return {
            'scheduler_active': self.maintenance_active,
            'total_tasks_executed': len(self.maintenance_log),
            'recent_tasks': recent_tasks,
            'next_scheduled': {
                'daily': "02:00",
                'weekly': "Domingo 03:00", 
                'monthly': "Primeiro dia do mês 04:00"
            }
        }

if __name__ == "__main__":
    # Teste do sistema de manutenção
    scheduler = MaintenanceScheduler()
    
    print("🔧 Executando manutenção de teste...")
    success = scheduler.run_daily_maintenance()
    
    if success:
        print("✅ Manutenção executada com sucesso")
        status = scheduler.get_maintenance_status()
        print(f"📊 Total de tarefas: {status['total_tasks_executed']}")
    else:
        print("❌ Falha na manutenção")