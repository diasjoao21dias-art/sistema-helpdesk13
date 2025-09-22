#!/usr/bin/env python3
"""
API de Licenciamento Remoto - Sistema Olivion
Permite controle remoto de licenças via internet
"""

import json
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional
import os

class CloudLicenseAPI:
    def __init__(self, api_base_url: str = None):
        # URL do seu servidor de licenças (pode ser este mesmo sistema publicado)
        self.api_base_url = api_base_url or os.environ.get('LICENSE_SERVER_URL', 'https://your-replit-app.replit.app')
        self.timeout = 10
        
    def validate_license_online(self, license_key: str, machine_id: str) -> Dict:
        """Validar licença com servidor remoto"""
        try:
            url = f"{self.api_base_url}/api/license/validate"
            payload = {
                'license_key': license_key,
                'machine_id': machine_id,
                'timestamp': datetime.now().isoformat(),
                'product': 'Sistema_Olivion'
            }
            
            response = requests.post(url, json=payload, timeout=self.timeout)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 403:
                return {
                    'valid': False,
                    'reason': 'license_blocked',
                    'message': 'Licença bloqueada remotamente'
                }
            elif response.status_code == 404:
                return {
                    'valid': False,
                    'reason': 'license_not_found',
                    'message': 'Licença não encontrada'
                }
            else:
                return {
                    'valid': False,
                    'reason': 'server_error',
                    'message': f'Erro do servidor: {response.status_code}'
                }
                
        except requests.ConnectionError:
            return {
                'valid': False,
                'reason': 'no_connection',
                'message': 'Sem conexão com servidor de licenças'
            }
        except requests.Timeout:
            return {
                'valid': False,
                'reason': 'timeout',
                'message': 'Timeout na validação remota'
            }
        except Exception as e:
            return {
                'valid': False,
                'reason': 'error',
                'message': f'Erro na validação: {str(e)}'
            }
    
    def block_license_remote(self, license_key: str, reason: str = "Administrative block") -> Dict:
        """Bloquear licença remotamente"""
        try:
            url = f"{self.api_base_url}/api/license/block"
            payload = {
                'license_key': license_key,
                'reason': reason,
                'blocked_at': datetime.now().isoformat(),
                'admin_action': True
            }
            
            response = requests.post(url, json=payload, timeout=self.timeout)
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'message': 'Licença bloqueada com sucesso'
                }
            else:
                return {
                    'success': False,
                    'message': f'Erro ao bloquear: {response.status_code}'
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f'Erro na comunicação: {str(e)}'
            }
    
    def unblock_license_remote(self, license_key: str) -> Dict:
        """Desbloquear licença remotamente"""
        try:
            url = f"{self.api_base_url}/api/license/unblock"
            payload = {
                'license_key': license_key,
                'unblocked_at': datetime.now().isoformat(),
                'admin_action': True
            }
            
            response = requests.post(url, json=payload, timeout=self.timeout)
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'message': 'Licença desbloqueada com sucesso'
                }
            else:
                return {
                    'success': False,
                    'message': f'Erro ao desbloquear: {response.status_code}'
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f'Erro na comunicação: {str(e)}'
            }
    
    def get_license_status_remote(self, license_key: str) -> Dict:
        """Obter status da licença no servidor remoto"""
        try:
            url = f"{self.api_base_url}/api/license/status"
            params = {'license_key': license_key}
            
            response = requests.get(url, params=params, timeout=self.timeout)
            
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    'found': False,
                    'message': 'Licença não encontrada no servidor'
                }
                
        except Exception as e:
            return {
                'found': False,
                'message': f'Erro na consulta: {str(e)}'
            }

# Instância global da API
cloud_api = CloudLicenseAPI()

def check_internet_connection() -> bool:
    """Verificar se há conexão com internet"""
    try:
        response = requests.get('https://www.google.com', timeout=5)
        return response.status_code == 200
    except:
        return False

def force_online_validation(license_key: str, machine_id: str) -> Dict:
    """Forçar validação online - usado para controle remoto"""
    if not check_internet_connection():
        return {
            'valid': False,
            'reason': 'no_internet',
            'message': 'Sem conexão com internet - validação obrigatória falhou'
        }
    
    return cloud_api.validate_license_online(license_key, machine_id)