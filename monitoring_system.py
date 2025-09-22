#!/usr/bin/env python3
"""
Sistema de Monitoramento 24/7 - Sistema Olivion
Monitoramento avançado com alertas automáticos
"""

import os
import sqlite3
import psutil
import threading
import time
import logging
import json
from datetime import datetime, timedelta
from pathlib import Path

class MonitoringSystem:
    """Sistema de monitoramento 24/7 com alertas"""
    
    def __init__(self, db_path="sistema_os.db"):
        self.db_path = db_path
        self.monitoring_active = False
        self.alerts_log = []
        self.monitoring_data = []
        
        # Configurações de alertas
        self.alert_config = {
            'db_size_threshold_mb': 100,        # Alertar se banco > 100MB
            'db_response_time_ms': 1000,        # Alertar se query > 1s
            'cpu_threshold': 80,                # Alertar se CPU > 80%
            'memory_threshold': 80,             # Alertar se RAM > 80%
            'disk_threshold': 90,               # Alertar se disco > 90%
            'max_failed_connections': 5,       # Alertar após 5 falhas
            'check_interval_seconds': 60       # Verificar a cada 1 minuto
        }
        
        # Configurar logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - MONITORING - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('monitoring.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def check_database_health(self):
        """Verifica saúde do banco de dados"""
        try:
            start_time = time.time()
            
            # Conectar e testar
            conn = sqlite3.connect(self.db_path, timeout=5)
            cursor = conn.cursor()
            
            # Query de teste
            cursor.execute("SELECT COUNT(*) FROM user")
            user_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM chamado")
            chamado_count = cursor.fetchone()[0]
            
            # Verificar integridade
            cursor.execute("PRAGMA integrity_check")
            integrity = cursor.fetchone()[0]
            
            # Tamanho do banco
            cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
            db_size_bytes = cursor.fetchone()[0]
            db_size_mb = db_size_bytes / 1024 / 1024
            
            conn.close()
            
            # Tempo de resposta
            response_time_ms = (time.time() - start_time) * 1000
            
            # Dados de saúde
            health_data = {
                'timestamp': datetime.now().isoformat(),
                'status': 'healthy',
                'response_time_ms': round(response_time_ms, 2),
                'database_size_mb': round(db_size_mb, 2),
                'user_count': user_count,
                'chamado_count': chamado_count,
                'integrity': integrity,
                'warnings': []
            }
            
            # Verificar alertas
            if db_size_mb > self.alert_config['db_size_threshold_mb']:
                health_data['warnings'].append(f"Banco de dados grande: {db_size_mb:.1f}MB")
            
            if response_time_ms > self.alert_config['db_response_time_ms']:
                health_data['warnings'].append(f"Resposta lenta: {response_time_ms:.1f}ms")
            
            if integrity != "ok":
                health_data['status'] = 'critical'
                health_data['warnings'].append(f"Integridade comprometida: {integrity}")
            
            return health_data
            
        except Exception as e:
            return {
                'timestamp': datetime.now().isoformat(),
                'status': 'error',
                'error': str(e),
                'warnings': ['Falha na conexão com banco de dados']
            }
    
    def check_system_resources(self):
        """Verifica recursos do sistema"""
        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memória
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disco
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            
            # Processo atual
            process = psutil.Process()
            process_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            resource_data = {
                'timestamp': datetime.now().isoformat(),
                'cpu_percent': round(cpu_percent, 1),
                'memory_percent': round(memory_percent, 1),
                'disk_percent': round(disk_percent, 1),
                'process_memory_mb': round(process_memory, 1),
                'warnings': []
            }
            
            # Verificar alertas
            if cpu_percent > self.alert_config['cpu_threshold']:
                resource_data['warnings'].append(f"CPU alta: {cpu_percent}%")
            
            if memory_percent > self.alert_config['memory_threshold']:
                resource_data['warnings'].append(f"Memória alta: {memory_percent}%")
            
            if disk_percent > self.alert_config['disk_threshold']:
                resource_data['warnings'].append(f"Disco cheio: {disk_percent}%")
            
            return resource_data
            
        except Exception as e:
            return {
                'timestamp': datetime.now().isoformat(),
                'error': str(e),
                'warnings': ['Falha na coleta de recursos do sistema']
            }
    
    def check_application_health(self):
        """Verifica saúde da aplicação"""
        try:
            # Verificar arquivos críticos
            critical_files = [
                'app.py', 'models.py', 'sistema_os.db',
                'backup_manager.py', 'database_safety.py'
            ]
            
            missing_files = []
            for file_name in critical_files:
                if not Path(file_name).exists():
                    missing_files.append(file_name)
            
            # Verificar logs de erro recentes
            error_count = 0
            if Path('app.log').exists():
                try:
                    with open('app.log', 'r') as f:
                        recent_logs = f.readlines()[-100:]  # Últimas 100 linhas
                        error_count = sum(1 for line in recent_logs if 'ERROR' in line)
                except:
                    pass
            
            app_data = {
                'timestamp': datetime.now().isoformat(),
                'status': 'healthy',
                'missing_files': missing_files,
                'recent_errors': error_count,
                'warnings': []
            }
            
            if missing_files:
                app_data['status'] = 'warning'
                app_data['warnings'].append(f"Arquivos ausentes: {', '.join(missing_files)}")
            
            if error_count > 10:
                app_data['warnings'].append(f"Muitos erros recentes: {error_count}")
            
            return app_data
            
        except Exception as e:
            return {
                'timestamp': datetime.now().isoformat(),
                'status': 'error',
                'error': str(e),
                'warnings': ['Falha na verificação da aplicação']
            }
    
    def send_alert(self, alert_data):
        """Envia alerta (log + possível email)"""
        try:
            alert = {
                'timestamp': datetime.now().isoformat(),
                'type': alert_data.get('type', 'unknown'),
                'severity': alert_data.get('severity', 'warning'),
                'message': alert_data.get('message', ''),
                'details': alert_data.get('details', {})
            }
            
            # Adicionar ao log de alertas
            self.alerts_log.append(alert)
            
            # Manter apenas últimos 1000 alertas
            if len(self.alerts_log) > 1000:
                self.alerts_log = self.alerts_log[-1000:]
            
            # Log do alerta
            severity_level = {
                'info': logging.INFO,
                'warning': logging.WARNING,
                'critical': logging.ERROR
            }.get(alert['severity'], logging.WARNING)
            
            self.logger.log(severity_level, f"🚨 ALERTA {alert['type']}: {alert['message']}")
            
            # Email/SMS poderia ser implementado aqui
            # self.send_email_alert(alert)
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Erro ao enviar alerta: {e}")
            return False
    
    def perform_monitoring_cycle(self):
        """Executa um ciclo completo de monitoramento"""
        try:
            cycle_data = {
                'timestamp': datetime.now().isoformat(),
                'database': self.check_database_health(),
                'system': self.check_system_resources(),
                'application': self.check_application_health()
            }
            
            # Adicionar aos dados de monitoramento
            self.monitoring_data.append(cycle_data)
            
            # Manter apenas últimas 24 horas de dados (assumindo check a cada minuto)
            max_data_points = 24 * 60
            if len(self.monitoring_data) > max_data_points:
                self.monitoring_data = self.monitoring_data[-max_data_points:]
            
            # Verificar e enviar alertas
            all_warnings = []
            all_warnings.extend(cycle_data['database'].get('warnings', []))
            all_warnings.extend(cycle_data['system'].get('warnings', []))
            all_warnings.extend(cycle_data['application'].get('warnings', []))
            
            # Enviar alertas se necessário
            for warning in all_warnings:
                self.send_alert({
                    'type': 'system_warning',
                    'severity': 'warning',
                    'message': warning,
                    'details': cycle_data
                })
            
            # Verificar status crítico
            critical_status = [
                cycle_data['database'].get('status') == 'critical',
                cycle_data['database'].get('status') == 'error',
                cycle_data['application'].get('status') == 'error'
            ]
            
            if any(critical_status):
                self.send_alert({
                    'type': 'system_critical',
                    'severity': 'critical',
                    'message': 'Sistema em estado crítico',
                    'details': cycle_data
                })
            
            return cycle_data
            
        except Exception as e:
            self.logger.error(f"❌ Erro no ciclo de monitoramento: {e}")
            return None
    
    def get_monitoring_summary(self, hours=24):
        """Retorna resumo do monitoramento das últimas N horas"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            # Filtrar dados recentes
            recent_data = [
                data for data in self.monitoring_data
                if datetime.fromisoformat(data['timestamp']) > cutoff_time
            ]
            
            if not recent_data:
                return {'error': 'Nenhum dado de monitoramento disponível'}
            
            # Calcular estatísticas
            db_response_times = [d['database'].get('response_time_ms', 0) for d in recent_data]
            cpu_usage = [d['system'].get('cpu_percent', 0) for d in recent_data]
            memory_usage = [d['system'].get('memory_percent', 0) for d in recent_data]
            
            # Contar alertas
            recent_alerts = [
                alert for alert in self.alerts_log
                if datetime.fromisoformat(alert['timestamp']) > cutoff_time
            ]
            
            summary = {
                'period_hours': hours,
                'data_points': len(recent_data),
                'database_performance': {
                    'avg_response_time_ms': round(sum(db_response_times) / len(db_response_times), 2),
                    'max_response_time_ms': round(max(db_response_times), 2)
                },
                'system_performance': {
                    'avg_cpu_percent': round(sum(cpu_usage) / len(cpu_usage), 1),
                    'max_cpu_percent': round(max(cpu_usage), 1),
                    'avg_memory_percent': round(sum(memory_usage) / len(memory_usage), 1),
                    'max_memory_percent': round(max(memory_usage), 1)
                },
                'alerts': {
                    'total_alerts': len(recent_alerts),
                    'critical_alerts': len([a for a in recent_alerts if a['severity'] == 'critical']),
                    'warning_alerts': len([a for a in recent_alerts if a['severity'] == 'warning'])
                },
                'last_check': recent_data[-1]['timestamp'] if recent_data else None
            }
            
            return summary
            
        except Exception as e:
            self.logger.error(f"❌ Erro no resumo: {e}")
            return {'error': str(e)}
    
    def start_monitoring(self):
        """Inicia monitoramento contínuo"""
        self.monitoring_active = True
        
        def monitoring_worker():
            while self.monitoring_active:
                self.perform_monitoring_cycle()
                time.sleep(self.alert_config['check_interval_seconds'])
        
        thread = threading.Thread(target=monitoring_worker, daemon=True)
        thread.start()
        
        self.logger.info("🔍 Monitoramento 24/7 iniciado")
        self.send_alert({
            'type': 'system_info',
            'severity': 'info',
            'message': 'Sistema de monitoramento iniciado',
            'details': {'interval_seconds': self.alert_config['check_interval_seconds']}
        })
    
    def stop_monitoring(self):
        """Para monitoramento"""
        self.monitoring_active = False
        self.logger.info("🛑 Monitoramento parado")

if __name__ == "__main__":
    # Teste do sistema de monitoramento
    monitor = MonitoringSystem()
    
    print("🔍 Executando verificação de teste...")
    cycle_data = monitor.perform_monitoring_cycle()
    
    if cycle_data:
        print("📊 Status atual:")
        print(f"  Database: {cycle_data['database']['status']}")
        print(f"  System CPU: {cycle_data['system']['cpu_percent']}%")
        print(f"  System Memory: {cycle_data['system']['memory_percent']}%")
        print(f"  Response Time: {cycle_data['database']['response_time_ms']}ms")
    else:
        print("❌ Falha na verificação")