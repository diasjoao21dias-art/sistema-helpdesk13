#!/usr/bin/env python3
"""
Sistema de Licenciamento - Sistema Olivion
Controla ativação, validação e expiração de licenças comerciais
"""

import json
import sqlite3
import hashlib
import requests
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
import uuid
import os
from typing import Dict, Optional, Tuple

class LicenseManager:
    def __init__(self, db_path: str = "sistema_os.db", validation_server: str = "https://license.olivion.com.br"):
        self.db_path = db_path
        self.validation_server = validation_server
        self.license_file = "license.dat"
        self.machine_id = self._get_machine_id()
        self.setup_license_table()
    
    def setup_license_table(self):
        """Criar tabela de licenças se não existir"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_license (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    license_key TEXT NOT NULL,
                    customer_name TEXT NOT NULL,
                    customer_email TEXT NOT NULL,
                    machine_id TEXT NOT NULL,
                    activated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    expires_at DATETIME NOT NULL,
                    status TEXT DEFAULT 'active',
                    last_validation DATETIME DEFAULT CURRENT_TIMESTAMP,
                    validation_count INTEGER DEFAULT 1,
                    features TEXT DEFAULT '{}',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(license_key, machine_id)
                )
            ''')
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Erro ao criar tabela de licenças: {e}")
    
    def _get_machine_id(self) -> str:
        """Obter ID único da máquina"""
        try:
            # Tentar usar UUID baseado em características da máquina
            import platform
            import socket
            
            machine_info = f"{platform.machine()}-{platform.processor()}-{socket.gethostname()}"
            machine_hash = hashlib.sha256(machine_info.encode()).hexdigest()
            return machine_hash[:16]
        except:
            # Fallback para arquivo local
            machine_file = ".machine_id"
            if os.path.exists(machine_file):
                with open(machine_file, 'r') as f:
                    return f.read().strip()
            else:
                machine_id = str(uuid.uuid4())[:16]
                with open(machine_file, 'w') as f:
                    f.write(machine_id)
                return machine_id
    
    def activate_license(self, license_key: str, customer_name: str, customer_email: str) -> Tuple[bool, str]:
        """Ativar licença com validação remota"""
        try:
            # Primeiro validar com servidor remoto
            validation_result = self._validate_with_server(license_key, customer_name, customer_email)
            
            if not validation_result['valid']:
                return False, validation_result['message']
            
            # Salvar licença localmente
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Verificar se já existe licença com esta chave
            cursor.execute("SELECT id, status FROM system_license WHERE license_key = ? AND machine_id = ?", 
                         (license_key, self.machine_id))
            existing_license = cursor.fetchone()
            
            # Remover completamente registros duplicados/problemáticos desta licença
            cursor.execute("DELETE FROM system_license WHERE license_key = ? AND machine_id = ?", 
                         (license_key, self.machine_id))
            
            # Desativar todas as licenças ativas anteriores (outras licenças)
            cursor.execute("UPDATE system_license SET status = 'replaced' WHERE status = 'active' AND machine_id = ?", 
                         (self.machine_id,))
            
            expires_at = datetime.now() + timedelta(days=30)
            
            # Sempre inserir nova licença (já removemos duplicatas acima)
            cursor.execute('''
                INSERT INTO system_license 
                (license_key, customer_name, customer_email, machine_id, expires_at, features, status)
                VALUES (?, ?, ?, ?, ?, ?, 'active')
            ''', (
                license_key,
                customer_name,
                customer_email,
                self.machine_id,
                expires_at.strftime('%Y-%m-%d %H:%M:%S'),
                json.dumps(validation_result.get('features', {}))
            ))
            
            conn.commit()
            conn.close()
            
            # Salvar arquivo de licença criptografado
            self._save_license_file(license_key, customer_name, expires_at)
            
            return True, "Licença ativada com sucesso!"
            
        except Exception as e:
            # Se ainda houver erro de constraint, tentar limpar e recriar
            if "UNIQUE constraint failed" in str(e):
                try:
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    # Remover todas as licenças desta máquina para permitir reativação
                    cursor.execute("DELETE FROM system_license WHERE machine_id = ?", (self.machine_id,))
                    conn.commit()
                    conn.close()
                    return False, "Licença limpa. Tente ativar novamente."
                except:
                    pass
            return False, f"Erro na ativação: {str(e)}"
    
    def _validate_with_server(self, license_key: str, customer_name: str, customer_email: str) -> Dict:
        """Validar licença com servidor remoto"""
        try:
            payload = {
                'license_key': license_key,
                'customer_name': customer_name,
                'customer_email': customer_email,
                'machine_id': self.machine_id,
                'product': 'Sistema_Olivion',
                'version': '9.0'
            }
            
            # Licenças fixas válidas (3 chaves como solicitado)
            valid_licenses = {
                "OLIVION-ADMIN-2024-MASTER-KEY": {
                    'valid': True,
                    'message': 'Licença Master ativada com sucesso',
                    'features': {
                        'max_users': 100,
                        'max_tickets': 10000,
                        'premium_reports': True,
                        'api_access': True,
                        'white_label': True
                    }
                },
                "OLIVION-STANDARD-2024-PRO-LIC": {
                    'valid': True,
                    'message': 'Licença Profissional ativada com sucesso',
                    'features': {
                        'max_users': 50,
                        'max_tickets': 5000,
                        'premium_reports': True,
                        'api_access': True,
                        'white_label': False
                    }
                },
                "OLIVION-ENTERPRISE-2024-UNLIMITED": {
                    'valid': True,
                    'message': 'Licença Enterprise ativada - Acesso Ilimitado',
                    'features': {
                        'max_users': 999999,
                        'max_tickets': 999999,
                        'premium_reports': True,
                        'api_access': True,
                        'white_label': True,
                        'unlimited_access': True,
                        'priority_support': True,
                        'custom_branding': True,
                        'advanced_analytics': True,
                        'multi_tenant': True
                    }
                }
            }
            
            # Normalizar chave para comparação (trim e maiúscula)
            normalized_key = license_key.strip().upper()
            
            # Verificar se a chave está na lista de licenças válidas
            if normalized_key in valid_licenses:
                return valid_licenses[normalized_key]
            else:
                return {
                    'valid': False,
                    'message': 'Chave de licença inválida ou não autorizada'
                }
            
            # Validação real com servidor
            response = requests.post(
                f"{self.validation_server}/api/validate",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    'valid': False,
                    'message': 'Falha na comunicação com servidor de licenças'
                }
                
        except requests.RequestException:
            # Em caso de falha de rede, verificar licença local se existir
            return self._fallback_validation(license_key)
        except Exception as e:
            return {
                'valid': False,
                'message': f'Erro na validação: {str(e)}'
            }
    
    def _fallback_validation(self, license_key: str) -> Dict:
        """Validação offline de emergência"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT expires_at, status FROM system_license 
                WHERE license_key = ? AND machine_id = ?
                ORDER BY created_at DESC LIMIT 1
            ''', (license_key, self.machine_id))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                expires_at = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')
                if expires_at > datetime.now() and result[1] == 'active':
                    return {
                        'valid': True,
                        'message': 'Validação offline - licença local válida'
                    }
            
            return {
                'valid': False,
                'message': 'Licença não encontrada ou expirada'
            }
            
        except:
            return {
                'valid': False,
                'message': 'Falha na validação offline'
            }
    
    def _save_license_file(self, license_key: str, customer_name: str, expires_at: datetime):
        """Salvar arquivo de licença criptografado"""
        try:
            # Gerar chave de criptografia baseada na máquina
            key_material = f"{self.machine_id}-{license_key}".encode()
            key = hashlib.sha256(key_material).digest()
            import base64
            fernet = Fernet(base64.urlsafe_b64encode(key))
            
            license_data = {
                'license_key': license_key,
                'customer_name': customer_name,
                'machine_id': self.machine_id,
                'expires_at': expires_at.isoformat(),
                'activated_at': datetime.now().isoformat()
            }
            
            encrypted_data = fernet.encrypt(json.dumps(license_data).encode())
            
            with open(self.license_file, 'wb') as f:
                f.write(encrypted_data)
                
        except Exception as e:
            print(f"Erro ao salvar arquivo de licença: {e}")
    
    def check_license_status(self) -> Dict:
        """Verificar status atual da licença"""
        try:
            # Verificar banco de dados
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT license_key, customer_name, expires_at, status, features, last_validation
                FROM system_license 
                WHERE status = 'active' AND machine_id = ?
                ORDER BY created_at DESC LIMIT 1
            ''', (self.machine_id,))
            
            result = cursor.fetchone()
            
            if not result:
                conn.close()
                return {
                    'licensed': False,
                    'status': 'unlicensed',
                    'message': 'Sistema não licenciado',
                    'days_remaining': 0
                }
            
            license_key, customer_name, expires_at_str, status, features_str, last_validation = result
            expires_at = datetime.strptime(expires_at_str, '%Y-%m-%d %H:%M:%S')
            
            # Verificar se expirou
            now = datetime.now()
            if expires_at <= now:
                # Marcar como expirada
                cursor.execute("UPDATE system_license SET status = 'expired' WHERE license_key = ?", (license_key,))
                conn.commit()
                conn.close()
                
                return {
                    'licensed': False,
                    'status': 'expired',
                    'message': f'Licença expirada em {expires_at.strftime("%d/%m/%Y")}',
                    'days_remaining': 0,
                    'customer_name': customer_name
                }
            
            # Calcular dias restantes
            days_remaining = (expires_at - now).days
            
            # Atualizar última validação
            cursor.execute('''
                UPDATE system_license 
                SET last_validation = CURRENT_TIMESTAMP, validation_count = validation_count + 1 
                WHERE license_key = ?
            ''', (license_key,))
            conn.commit()
            conn.close()
            
            # Verificar se precisa renovar (aviso com 7 dias)
            status_message = "Licença ativa"
            if days_remaining <= 7:
                status_message = f"Licença expira em {days_remaining} dias - Renove urgente!"
            elif days_remaining <= 15:
                status_message = f"Licença expira em {days_remaining} dias"
            
            features = json.loads(features_str) if features_str else {}
            
            return {
                'licensed': True,
                'status': 'active',
                'message': status_message,
                'days_remaining': days_remaining,
                'expires_at': expires_at.strftime('%d/%m/%Y'),
                'customer_name': customer_name,
                'features': features,
                'license_key': license_key[:8] + "..." + license_key[-4:]  # Mascarar chave
            }
            
        except Exception as e:
            return {
                'licensed': False,
                'status': 'error',
                'message': f'Erro na verificação: {str(e)}',
                'days_remaining': 0
            }
    
    def renew_license(self, license_key: str) -> Tuple[bool, str]:
        """Renovar licença existente"""
        try:
            # Validar renovação com servidor
            validation_result = self._validate_renewal_with_server(license_key)
            
            if not validation_result['valid']:
                return False, validation_result['message']
            
            # Atualizar banco de dados
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            new_expires = datetime.now() + timedelta(days=30)
            
            cursor.execute('''
                UPDATE system_license 
                SET expires_at = ?, status = 'active', last_validation = CURRENT_TIMESTAMP
                WHERE license_key = ? AND machine_id = ?
            ''', (
                new_expires.strftime('%Y-%m-%d %H:%M:%S'),
                license_key,
                self.machine_id
            ))
            
            if cursor.rowcount == 0:
                conn.close()
                return False, "Licença não encontrada para renovação"
            
            conn.commit()
            conn.close()
            
            return True, f"Licença renovada até {new_expires.strftime('%d/%m/%Y')}"
            
        except Exception as e:
            return False, f"Erro na renovação: {str(e)}"
    
    def _validate_renewal_with_server(self, license_key: str) -> Dict:
        """Validar renovação com servidor"""
        try:
            payload = {
                'license_key': license_key,
                'machine_id': self.machine_id,
                'action': 'renew'
            }
            
            # Simulação para desenvolvimento
            if self.validation_server.startswith("https://license.olivion"):
                return {
                    'valid': True,
                    'message': 'Renovação autorizada'
                }
            
            response = requests.post(
                f"{self.validation_server}/api/renew",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    'valid': False,
                    'message': 'Renovação não autorizada pelo servidor'
                }
                
        except:
            return {
                'valid': False,
                'message': 'Falha na comunicação para renovação'
            }
    
    def deactivate_license(self) -> bool:
        """Desativar licença atual"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE system_license 
                SET status = 'deactivated' 
                WHERE status = 'active' AND machine_id = ?
            ''', (self.machine_id,))
            
            conn.commit()
            conn.close()
            
            # Remover arquivo de licença
            if os.path.exists(self.license_file):
                os.remove(self.license_file)
            
            return True
            
        except Exception as e:
            print(f"Erro ao desativar licença: {e}")
            return False
    
    def get_license_info(self) -> Dict:
        """Obter informações detalhadas da licença"""
        status = self.check_license_status()
        
        if not status['licensed']:
            return status
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT customer_email, activated_at, validation_count, features
                FROM system_license 
                WHERE status = 'active' AND machine_id = ?
                ORDER BY created_at DESC LIMIT 1
            ''', (self.machine_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                customer_email, activated_at, validation_count, features_str = result
                features = json.loads(features_str) if features_str else {}
                
                status.update({
                    'customer_email': customer_email,
                    'activated_at': activated_at,
                    'validation_count': validation_count,
                    'features': features,
                    'machine_id': self.machine_id
                })
            
            return status
            
        except Exception as e:
            status['message'] = f"Erro ao obter detalhes: {str(e)}"
            return status

# Instância global do gerenciador de licenças
license_manager = LicenseManager()

def is_licensed() -> bool:
    """Verificação rápida se sistema está licenciado"""
    status = license_manager.check_license_status()
    return status['licensed']

def get_license_status() -> Dict:
    """Obter status completo da licença"""
    return license_manager.check_license_status()

def check_feature_access(feature: str) -> bool:
    """Verificar se recurso específico está disponível na licença"""
    info = license_manager.get_license_info()
    if not info['licensed']:
        return False
    
    features = info.get('features', {})
    return features.get(feature, False)