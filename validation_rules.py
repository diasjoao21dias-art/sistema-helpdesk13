#!/usr/bin/env python3
"""
Regras de Validação - Sistema Olivion
Validações robustas para prevenir dados inválidos
"""

import re
from datetime import datetime
from typing import Dict, List, Tuple, Optional

class ValidationRules:
    """Conjunto de regras de validação para dados críticos"""
    
    @staticmethod
    def validate_user_data(username: str, password: str, role: str, setor: str = None) -> Tuple[bool, List[str]]:
        """Valida dados de usuário com regras de segurança"""
        errors = []
        
        # Validar username
        if not username or len(username.strip()) < 3:
            errors.append("Username deve ter pelo menos 3 caracteres")
        elif len(username) > 50:
            errors.append("Username não pode ter mais de 50 caracteres")
        elif not re.match(r'^[a-zA-Z0-9_-]+$', username):
            errors.append("Username só pode conter letras, números, _ e -")
        
        # Validar password
        if password:  # Só validar se senha foi fornecida
            if len(password) < 6:
                errors.append("Senha deve ter pelo menos 6 caracteres")
            elif len(password) > 128:
                errors.append("Senha não pode ter mais de 128 caracteres")
            elif not re.search(r'[A-Za-z]', password):
                errors.append("Senha deve conter pelo menos uma letra")
            elif not re.search(r'[0-9]', password):
                errors.append("Senha deve conter pelo menos um número")
        
        # Validar role
        valid_roles = ["admin", "operador", "usuario"]
        if role not in valid_roles:
            errors.append(f"Papel deve ser um de: {', '.join(valid_roles)}")
        
        # Validar setor se necessário
        if role == "operador" and not setor:
            errors.append("Operadores devem ter um setor definido")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_chamado_data(titulo: str, descricao: str, setor: str, 
                            prioridade: str = "media", usuario_id: int = None) -> Tuple[bool, List[str]]:
        """Valida dados de chamado com regras de negócio"""
        errors = []
        
        # Validar título
        if not titulo or len(titulo.strip()) < 5:
            errors.append("Título deve ter pelo menos 5 caracteres")
        elif len(titulo) > 200:
            errors.append("Título não pode ter mais de 200 caracteres")
        
        # Validar descrição
        if not descricao or len(descricao.strip()) < 10:
            errors.append("Descrição deve ter pelo menos 10 caracteres")
        elif len(descricao) > 2000:
            errors.append("Descrição não pode ter mais de 2000 caracteres")
        
        # Validar setor
        valid_setores = ["T.I", "Manutenção", "CCIH / SESMT / Manutenção de Ar condicionado", "Telefonia e outros serviços"]
        if setor not in valid_setores:
            errors.append(f"Setor deve ser um de: {', '.join(valid_setores)}")
        
        # Validar prioridade
        valid_prioridades = ["baixa", "media", "alta", "urgente"]
        if prioridade not in valid_prioridades:
            errors.append(f"Prioridade deve ser um de: {', '.join(valid_prioridades)}")
        
        # Validar usuário
        if usuario_id is not None and usuario_id <= 0:
            errors.append("ID de usuário inválido")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def sanitize_input(data: str, max_length: int = 1000) -> str:
        """Sanitiza entrada removendo caracteres perigosos"""
        if not data:
            return ""
        
        # Remover caracteres de controle
        sanitized = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', str(data))
        
        # Truncar se necessário
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
        
        # Remover espaços extras
        sanitized = re.sub(r'\s+', ' ', sanitized.strip())
        
        return sanitized
    
    @staticmethod
    def validate_file_upload(filename: str, file_size: int) -> Tuple[bool, List[str]]:
        """Valida upload de arquivo"""
        errors = []
        
        if not filename:
            errors.append("Nome do arquivo não pode estar vazio")
            return False, errors
        
        # Validar extensão
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
        if '.' not in filename:
            errors.append("Arquivo deve ter uma extensão")
        else:
            ext = filename.rsplit('.', 1)[1].lower()
            if ext not in allowed_extensions:
                errors.append(f"Extensões permitidas: {', '.join(allowed_extensions)}")
        
        # Validar tamanho (5MB máximo)
        max_size = 5 * 1024 * 1024
        if file_size > max_size:
            errors.append(f"Arquivo muito grande. Máximo: {max_size/1024/1024:.1f}MB")
        
        # Validar nome seguro
        if not re.match(r'^[a-zA-Z0-9._-]+$', filename):
            errors.append("Nome do arquivo contém caracteres inválidos")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_search_params(query: str, filters: Dict) -> Tuple[bool, List[str]]:
        """Valida parâmetros de busca para prevenir ataques"""
        errors = []
        
        # Validar query de busca
        if query and len(query) > 100:
            errors.append("Termo de busca muito longo")
        
        # Verificar caracteres suspeitos
        if query and re.search(r'[<>"\';]', query):
            errors.append("Termo de busca contém caracteres inválidos")
        
        # Validar filtros
        if filters:
            for key, value in filters.items():
                if not isinstance(key, str) or len(key) > 50:
                    errors.append(f"Chave de filtro inválida: {key}")
                
                if value and isinstance(value, str) and len(value) > 100:
                    errors.append(f"Valor de filtro muito longo: {key}")
        
        return len(errors) == 0, errors

# Instância global para uso na aplicação
validator = ValidationRules()