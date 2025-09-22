#!/usr/bin/env python3
"""
Sistema de Replicação - Sistema Olivion
Sistema simples de alta disponibilidade e replicação de dados
"""

import os
import sqlite3
import shutil
import threading
import time
import logging
import json
from datetime import datetime, timedelta
from pathlib import Path

class ReplicationManager:
    """Gerenciador de replicação e alta disponibilidade"""
    
    def __init__(self, primary_db="sistema_os.db", replica_dir="replicas"):
        self.primary_db = primary_db
        self.replica_dir = Path(replica_dir)
        self.replica_dir.mkdir(exist_ok=True)
        
        self.replication_active = False
        self.replication_log = []
        
        # Configurações de replicação
        self.config = {
            'replication_interval_seconds': 300,  # 5 minutos
            'max_replicas': 3,                    # Máximo 3 réplicas
            'max_lag_seconds': 600,               # Máximo 10 min de atraso
            'verification_enabled': True          # Verificar integridade
        }
        
        # Configurar logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - REPLICATION - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def log_replication_event(self, event_type, status, details=None):
        """Registra evento de replicação"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'status': status,
            'details': details or {}
        }
        
        self.replication_log.append(log_entry)
        
        # Manter apenas últimos 1000 eventos
        if len(self.replication_log) > 1000:
            self.replication_log = self.replication_log[-1000:]
        
        self.logger.info(f"🔄 {event_type}: {status}")
    
    def get_database_checksum(self, db_path):
        """Calcula checksum do banco de dados"""
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Contar registros e calcular hash simples
            cursor.execute("SELECT COUNT(*) FROM user")
            user_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM chamado") 
            chamado_count = cursor.fetchone()[0]
            
            # Última modificação de chamados
            cursor.execute("SELECT MAX(criado_em) FROM chamado")
            last_update = cursor.fetchone()[0] or ""
            
            conn.close()
            
            # Checksum simples baseado em contadores e timestamp
            checksum = f"{user_count}:{chamado_count}:{last_update}"
            return checksum
            
        except Exception as e:
            self.logger.error(f"❌ Erro ao calcular checksum: {e}")
            return None
    
    def create_replica(self, replica_name=None):
        """Cria réplica do banco principal"""
        try:
            if not replica_name:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                replica_name = f"replica_{timestamp}.db"
            
            replica_path = self.replica_dir / replica_name
            
            # Verificar se banco principal existe
            if not Path(self.primary_db).exists():
                self.log_replication_event("Criar Réplica", "FALHA", {"reason": "Banco principal não encontrado"})
                return None
            
            # Criar cópia do banco principal
            shutil.copy2(self.primary_db, replica_path)
            
            # Verificar integridade da réplica
            if self.config['verification_enabled']:
                primary_checksum = self.get_database_checksum(self.primary_db)
                replica_checksum = self.get_database_checksum(replica_path)
                
                if primary_checksum != replica_checksum:
                    replica_path.unlink()  # Remover réplica inválida
                    self.log_replication_event("Criar Réplica", "FALHA", {
                        "reason": "Checksum inválido",
                        "primary": primary_checksum,
                        "replica": replica_checksum
                    })
                    return None
            
            # Adicionar metadados da réplica
            metadata = {
                'created_at': datetime.now().isoformat(),
                'primary_db': self.primary_db,
                'primary_checksum': self.get_database_checksum(self.primary_db),
                'replica_size': replica_path.stat().st_size
            }
            
            metadata_path = replica_path.with_suffix('.meta.json')
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            self.log_replication_event("Criar Réplica", "SUCESSO", {
                "replica_name": replica_name,
                "size_bytes": replica_path.stat().st_size
            })
            
            return replica_path
            
        except Exception as e:
            self.log_replication_event("Criar Réplica", "ERRO", {"error": str(e)})
            return None
    
    def update_replicas(self):
        """Atualiza todas as réplicas existentes"""
        try:
            replicas = list(self.replica_dir.glob("replica_*.db"))
            
            if not replicas:
                self.log_replication_event("Atualizar Réplicas", "NADA_PARA_FAZER", {"reason": "Nenhuma réplica encontrada"})
                return True
            
            primary_checksum = self.get_database_checksum(self.primary_db)
            if not primary_checksum:
                self.log_replication_event("Atualizar Réplicas", "FALHA", {"reason": "Erro no banco principal"})
                return False
            
            updated_count = 0
            failed_count = 0
            
            for replica_path in replicas:
                try:
                    # Verificar se réplica precisa ser atualizada
                    replica_checksum = self.get_database_checksum(replica_path)
                    
                    if replica_checksum == primary_checksum:
                        continue  # Réplica já está atualizada
                    
                    # Atualizar réplica
                    shutil.copy2(self.primary_db, replica_path)
                    
                    # Verificar atualização
                    new_checksum = self.get_database_checksum(replica_path)
                    if new_checksum == primary_checksum:
                        # Atualizar metadados
                        metadata_path = replica_path.with_suffix('.meta.json')
                        if metadata_path.exists():
                            with open(metadata_path, 'r') as f:
                                metadata = json.load(f)
                            
                            metadata['last_updated'] = datetime.now().isoformat()
                            metadata['primary_checksum'] = primary_checksum
                            
                            with open(metadata_path, 'w') as f:
                                json.dump(metadata, f, indent=2)
                        
                        updated_count += 1
                    else:
                        failed_count += 1
                        
                except Exception as e:
                    self.logger.error(f"❌ Erro ao atualizar réplica {replica_path.name}: {e}")
                    failed_count += 1
            
            if failed_count == 0:
                self.log_replication_event("Atualizar Réplicas", "SUCESSO", {
                    "atualizadas": updated_count,
                    "total": len(replicas)
                })
                return True
            else:
                self.log_replication_event("Atualizar Réplicas", "PARCIAL", {
                    "atualizadas": updated_count,
                    "falharam": failed_count,
                    "total": len(replicas)
                })
                return False
                
        except Exception as e:
            self.log_replication_event("Atualizar Réplicas", "ERRO", {"error": str(e)})
            return False
    
    def cleanup_old_replicas(self, max_age_hours=24):
        """Remove réplicas antigas"""
        try:
            cutoff_time = time.time() - (max_age_hours * 3600)
            replicas = list(self.replica_dir.glob("replica_*.db"))
            
            # Manter pelo menos 1 réplica
            if len(replicas) <= 1:
                return True
            
            # Ordenar por data de modificação (mais recente primeiro)
            replicas.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            removed_count = 0
            
            # Manter as N réplicas mais recentes e remover antigas
            for replica in replicas[self.config['max_replicas']:]:
                try:
                    replica.unlink()
                    # Remover metadados também
                    metadata_path = replica.with_suffix('.meta.json')
                    if metadata_path.exists():
                        metadata_path.unlink()
                    
                    removed_count += 1
                    
                except Exception as e:
                    self.logger.error(f"❌ Erro ao remover réplica {replica.name}: {e}")
            
            # Remover réplicas muito antigas
            for replica in replicas[:self.config['max_replicas']]:
                if replica.stat().st_mtime < cutoff_time:
                    try:
                        replica.unlink()
                        metadata_path = replica.with_suffix('.meta.json')
                        if metadata_path.exists():
                            metadata_path.unlink()
                        
                        removed_count += 1
                        
                    except Exception as e:
                        self.logger.error(f"❌ Erro ao remover réplica antiga {replica.name}: {e}")
            
            if removed_count > 0:
                self.log_replication_event("Limpeza de Réplicas", "SUCESSO", {
                    "removidas": removed_count,
                    "max_age_hours": max_age_hours
                })
            else:
                self.log_replication_event("Limpeza de Réplicas", "NADA_PARA_FAZER")
            
            return True
            
        except Exception as e:
            self.log_replication_event("Limpeza de Réplicas", "ERRO", {"error": str(e)})
            return False
    
    def verify_replica_integrity(self, replica_path):
        """Verifica integridade de uma réplica"""
        try:
            primary_checksum = self.get_database_checksum(self.primary_db)
            replica_checksum = self.get_database_checksum(replica_path)
            
            is_valid = primary_checksum == replica_checksum
            
            return {
                'valid': is_valid,
                'primary_checksum': primary_checksum,
                'replica_checksum': replica_checksum,
                'replica_path': str(replica_path)
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': str(e),
                'replica_path': str(replica_path)
            }
    
    def get_replication_status(self):
        """Retorna status do sistema de replicação"""
        try:
            replicas = list(self.replica_dir.glob("replica_*.db"))
            
            status = {
                'replication_active': self.replication_active,
                'primary_db': self.primary_db,
                'primary_exists': Path(self.primary_db).exists(),
                'replica_count': len(replicas),
                'replicas': []
            }
            
            # Informações de cada réplica
            for replica in replicas:
                replica_info = {
                    'name': replica.name,
                    'size_mb': round(replica.stat().st_size / 1024 / 1024, 2),
                    'modified': datetime.fromtimestamp(replica.stat().st_mtime).isoformat(),
                    'valid': None
                }
                
                # Verificar integridade se solicitado
                if self.config['verification_enabled']:
                    integrity = self.verify_replica_integrity(replica)
                    replica_info['valid'] = integrity['valid']
                
                status['replicas'].append(replica_info)
            
            # Estatísticas de replicação
            recent_events = [
                event for event in self.replication_log
                if datetime.fromisoformat(event['timestamp']) > datetime.now() - timedelta(hours=24)
            ]
            
            status['recent_activity'] = {
                'last_24h_events': len(recent_events),
                'successful_replications': len([e for e in recent_events if e['status'] == 'SUCESSO']),
                'failed_replications': len([e for e in recent_events if e['status'] in ['FALHA', 'ERRO']])
            }
            
            return status
            
        except Exception as e:
            return {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def run_replication_cycle(self):
        """Executa um ciclo completo de replicação"""
        try:
            self.logger.info("🔄 Iniciando ciclo de replicação...")
            
            # 1. Verificar se há réplicas
            replicas = list(self.replica_dir.glob("replica_*.db"))
            
            if len(replicas) == 0:
                # Criar primeira réplica
                self.create_replica()
            else:
                # Atualizar réplicas existentes
                self.update_replicas()
            
            # 2. Limpeza de réplicas antigas
            self.cleanup_old_replicas()
            
            # 3. Criar nova réplica se necessário
            current_replicas = list(self.replica_dir.glob("replica_*.db"))
            if len(current_replicas) < self.config['max_replicas']:
                self.create_replica()
            
            self.log_replication_event("Ciclo de Replicação", "SUCESSO", {
                "replicas_atuais": len(current_replicas)
            })
            
            return True
            
        except Exception as e:
            self.log_replication_event("Ciclo de Replicação", "ERRO", {"error": str(e)})
            return False
    
    def start_automatic_replication(self):
        """Inicia replicação automática"""
        self.replication_active = True
        
        def replication_worker():
            while self.replication_active:
                self.run_replication_cycle()
                time.sleep(self.config['replication_interval_seconds'])
        
        thread = threading.Thread(target=replication_worker, daemon=True)
        thread.start()
        
        self.log_replication_event("Sistema de Replicação", "INICIADO", {
            "interval_seconds": self.config['replication_interval_seconds']
        })
    
    def stop_automatic_replication(self):
        """Para replicação automática"""
        self.replication_active = False
        self.log_replication_event("Sistema de Replicação", "PARADO")

if __name__ == "__main__":
    # Teste do sistema de replicação
    replication = ReplicationManager()
    
    print("🔄 Executando teste de replicação...")
    success = replication.run_replication_cycle()
    
    if success:
        status = replication.get_replication_status()
        print(f"✅ Replicação executada com sucesso")
        print(f"📊 Réplicas ativas: {status['replica_count']}")
        print(f"💾 Banco principal: {status['primary_db']} ({'OK' if status['primary_exists'] else 'ERRO'})")
    else:
        print("❌ Falha na replicação")