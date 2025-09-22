#!/usr/bin/env python3
"""
Gerador de Chaves de Licença - Sistema Olivion
Cria chaves de licença válidas para venda aos clientes
"""

import secrets
import string
import hashlib
import json
from datetime import datetime, timedelta
import sqlite3
from typing import Dict, List, Optional

class LicenseGenerator:
    def __init__(self, db_path: str = "sistema_os.db"):
        self.db_path = db_path
        self.setup_license_store()
    
    def setup_license_store(self):
        """Criar tabela para armazenar chaves geradas"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS license_store (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    license_key TEXT UNIQUE NOT NULL,
                    customer_name TEXT,
                    customer_email TEXT,
                    license_type TEXT DEFAULT 'standard',
                    max_users INTEGER DEFAULT 50,
                    max_tickets INTEGER DEFAULT 1000,
                    features TEXT DEFAULT '{}',
                    price DECIMAL(10,2),
                    currency TEXT DEFAULT 'BRL',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    sold_at DATETIME,
                    activated_at DATETIME,
                    status TEXT DEFAULT 'available',
                    notes TEXT
                )
            ''')
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Erro ao criar tabela de chaves: {e}")
    
    def generate_license_key(self, prefix: str = "OLIVION") -> str:
        """Gerar chave de licença única"""
        # Formato: OLIVION-XXXX-XXXX-XXXX-XXXX
        segments = []
        
        for i in range(4):
            # Gerar segmento de 4 caracteres alfanuméricos
            segment = ''.join(secrets.choice(string.ascii_uppercase + string.digits) 
                            for _ in range(4))
            segments.append(segment)
        
        license_key = f"{prefix}-{'-'.join(segments)}"
        
        # Verificar se já existe
        if self._key_exists(license_key):
            return self.generate_license_key(prefix)  # Recursão para gerar nova
        
        return license_key
    
    def _key_exists(self, license_key: str) -> bool:
        """Verificar se chave já existe"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT id FROM license_store WHERE license_key = ?", (license_key,))
            exists = cursor.fetchone() is not None
            
            conn.close()
            return exists
            
        except:
            return False
    
    def create_license(self, 
                      license_type: str = "standard",
                      customer_name: str = None,
                      customer_email: str = None,
                      price: float = 200.0,
                      max_users: int = 50,
                      max_tickets: int = 1000,
                      notes: str = None) -> Dict:
        """Criar nova licença para venda"""
        
        license_key = self.generate_license_key()
        
        # Definir recursos baseado no tipo
        features = self._get_features_by_type(license_type)
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO license_store 
                (license_key, customer_name, customer_email, license_type, 
                 max_users, max_tickets, features, price, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                license_key,
                customer_name,
                customer_email,
                license_type,
                max_users,
                max_tickets,
                json.dumps(features),
                price,
                notes
            ))
            
            conn.commit()
            conn.close()
            
            return {
                'success': True,
                'license_key': license_key,
                'type': license_type,
                'price': price,
                'features': features,
                'message': f'Licença {license_key} criada com sucesso!'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Erro ao criar licença: {str(e)}'
            }
    
    def _get_features_by_type(self, license_type: str) -> Dict:
        """Obter recursos baseado no tipo de licença"""
        features_map = {
            'basic': {
                'max_users': 10,
                'max_tickets': 500,
                'premium_reports': False,
                'api_access': False,
                'white_label': False,
                'cloud_backup': False,
                'priority_support': False
            },
            'standard': {
                'max_users': 50,
                'max_tickets': 1000,
                'premium_reports': True,
                'api_access': True,
                'white_label': False,
                'cloud_backup': True,
                'priority_support': False
            },
            'premium': {
                'max_users': 100,
                'max_tickets': 5000,
                'premium_reports': True,
                'api_access': True,
                'white_label': True,
                'cloud_backup': True,
                'priority_support': True
            },
            'enterprise': {
                'max_users': 500,
                'max_tickets': 25000,
                'premium_reports': True,
                'api_access': True,
                'white_label': True,
                'cloud_backup': True,
                'priority_support': True,
                'custom_branding': True,
                'dedicated_support': True
            }
        }
        
        return features_map.get(license_type, features_map['standard'])
    
    def mark_as_sold(self, license_key: str, customer_name: str, customer_email: str) -> bool:
        """Marcar licença como vendida"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE license_store 
                SET customer_name = ?, customer_email = ?, 
                    sold_at = CURRENT_TIMESTAMP, status = 'sold'
                WHERE license_key = ?
            ''', (customer_name, customer_email, license_key))
            
            success = cursor.rowcount > 0
            conn.commit()
            conn.close()
            
            return success
            
        except Exception as e:
            print(f"Erro ao marcar como vendida: {e}")
            return False
    
    def get_available_licenses(self) -> List[Dict]:
        """Obter licenças disponíveis para venda"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT license_key, license_type, price, max_users, max_tickets, 
                       created_at, features, notes
                FROM license_store 
                WHERE status = 'available'
                ORDER BY created_at DESC
            ''')
            
            licenses = []
            for row in cursor.fetchall():
                license_key, license_type, price, max_users, max_tickets, created_at, features_str, notes = row
                
                licenses.append({
                    'license_key': license_key,
                    'type': license_type,
                    'price': price,
                    'max_users': max_users,
                    'max_tickets': max_tickets,
                    'created_at': created_at,
                    'features': json.loads(features_str) if features_str else {},
                    'notes': notes
                })
            
            conn.close()
            return licenses
            
        except Exception as e:
            print(f"Erro ao obter licenças: {e}")
            return []
    
    def get_sold_licenses(self) -> List[Dict]:
        """Obter licenças vendidas"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT license_key, customer_name, customer_email, license_type, 
                       price, sold_at, activated_at, status
                FROM license_store 
                WHERE status IN ('sold', 'activated')
                ORDER BY sold_at DESC
            ''')
            
            licenses = []
            for row in cursor.fetchall():
                license_key, customer_name, customer_email, license_type, price, sold_at, activated_at, status = row
                
                licenses.append({
                    'license_key': license_key,
                    'customer_name': customer_name,
                    'customer_email': customer_email,
                    'type': license_type,
                    'price': price,
                    'sold_at': sold_at,
                    'activated_at': activated_at,
                    'status': status
                })
            
            conn.close()
            return licenses
            
        except Exception as e:
            print(f"Erro ao obter licenças vendidas: {e}")
            return []
    
    def bulk_create_licenses(self, count: int = 10, license_type: str = "standard") -> List[str]:
        """Criar várias licenças em lote"""
        created_keys = []
        
        for _ in range(count):
            result = self.create_license(license_type=license_type)
            if result['success']:
                created_keys.append(result['license_key'])
        
        return created_keys
    
    def get_license_info(self, license_key: str) -> Optional[Dict]:
        """Obter informações de uma licença específica"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT license_key, customer_name, customer_email, license_type,
                       max_users, max_tickets, features, price, created_at, 
                       sold_at, activated_at, status, notes
                FROM license_store 
                WHERE license_key = ?
            ''', (license_key,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                license_key, customer_name, customer_email, license_type, max_users, max_tickets, features_str, price, created_at, sold_at, activated_at, status, notes = row
                
                return {
                    'license_key': license_key,
                    'customer_name': customer_name,
                    'customer_email': customer_email,
                    'type': license_type,
                    'max_users': max_users,
                    'max_tickets': max_tickets,
                    'features': json.loads(features_str) if features_str else {},
                    'price': price,
                    'created_at': created_at,
                    'sold_at': sold_at,
                    'activated_at': activated_at,
                    'status': status,
                    'notes': notes
                }
            
            return None
            
        except Exception as e:
            print(f"Erro ao obter info da licença: {e}")
            return None

# Instância global do gerador
license_generator = LicenseGenerator()

def create_standard_license(customer_name: str = None, customer_email: str = None) -> str:
    """Função helper para criar licença padrão"""
    result = license_generator.create_license(
        license_type="standard",
        customer_name=customer_name,
        customer_email=customer_email,
        price=200.0
    )
    
    if result['success']:
        return result['license_key']
    else:
        raise Exception(result['message'])

def create_premium_license(customer_name: str = None, customer_email: str = None) -> str:
    """Função helper para criar licença premium"""
    result = license_generator.create_license(
        license_type="premium",
        customer_name=customer_name,
        customer_email=customer_email,
        price=500.0,
        max_users=100,
        max_tickets=5000
    )
    
    if result['success']:
        return result['license_key']
    else:
        raise Exception(result['message'])