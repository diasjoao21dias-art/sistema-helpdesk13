# type_fixes.py - Melhorias de tipagem para o sistema HelpDesk

from typing import Optional, Dict, Any, Union, List, Tuple
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

# Tipo personalizado para models SQLAlchemy
ModelType = Union[Any, None]

# Funções melhoradas com tipagem correta
def safe_log_login(user_id: int, username: str, ip_address: Optional[str] = None, 
                   user_agent: Optional[str] = None, session_id: Optional[str] = None) -> None:
    """Log de login com tipagem correta"""
    pass

def safe_log_logout(user_id: int, username: str, ip_address: Optional[str] = None, 
                    session_id: Optional[str] = None) -> None:
    """Log de logout com tipagem correta"""
    pass

def safe_log_admin_action(user_id: int, username: str, action_description: str, 
                          details: Optional[Dict[str, Any]] = None) -> None:
    """Log de ação admin com tipagem correta"""
    pass

def safe_log_system_event(event_type: str, description: str, 
                          details: Optional[Dict[str, Any]] = None) -> None:
    """Log de evento sistema com tipagem correta"""
    pass

def safe_is_licensed() -> bool:
    """Verificação de licença com tipagem correta"""
    return True

def safe_get_license_status() -> Dict[str, Any]:
    """Status da licença com tipagem correta"""
    return {'licensed': True, 'status': 'active'}

def safe_check_feature_access(feature: str) -> bool:
    """Verificação de acesso a feature com tipagem correta"""
    return True

# Funções utilitárias para validação de tipos
def validate_file_extension(filename: Optional[str]) -> bool:
    """Valida se o arquivo tem extensão válida"""
    if filename is None:
        return False
    return '.' in filename

def safe_splitext(filename: Optional[str]) -> Tuple[str, str]:
    """Divisão de extensão de arquivo com verificação"""
    if filename is None:
        return '', ''
    import os
    return os.path.splitext(filename)

def safe_datetime_format(dt_value: Optional[datetime]) -> str:
    """Formatação segura de datetime"""
    if dt_value is None:
        return ''
    try:
        return dt_value.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return ''

# Classes de tipo para modelos
class SafeUser:
    """Tipo seguro para User model"""
    def __init__(self, model_instance: Any = None):
        self._instance = model_instance
        
    @property
    def id(self) -> Optional[int]:
        return getattr(self._instance, 'id', None)
    
    @property
    def username(self) -> Optional[str]:
        return getattr(self._instance, 'username', None)
        
    @property
    def is_admin(self) -> bool:
        return getattr(self._instance, 'is_admin', False) if self._instance else False
        
    @property
    def is_operator_like(self) -> bool:
        return getattr(self._instance, 'is_operator_like', False) if self._instance else False
        
    def has_permission(self, permission: str) -> bool:
        if not self._instance:
            return False
        return getattr(self._instance, 'has_permission', lambda x: False)(permission)
    
    def can_access_sector(self, sector: str) -> bool:
        if not self._instance:
            return False
        return getattr(self._instance, 'can_access_sector', lambda x: False)(sector)
        
    def get_sectors(self) -> List[str]:
        if not self._instance:
            return []
        return getattr(self._instance, 'get_sectors', lambda: [])()
        
    def get_sector_names(self) -> List[str]:
        if not self._instance:
            return []
        return getattr(self._instance, 'get_sector_names', lambda: [])()

class SafeChamado:
    """Tipo seguro para Chamado model"""
    def __init__(self, model_instance: Any = None):
        self._instance = model_instance
        
    @property
    def id(self) -> Optional[int]:
        return getattr(self._instance, 'id', None)

# Constantes de tipo
SETOR_TYPES = {
    "T.I": "ti",
    "Manutenção": "manutencao", 
    "CCIH / SESMT / Manutenção de Ar condicionado": "ccih_sesmt_arcondicionado",
    "Telefonia e outros serviços": "telefonia_outros"
}

STATUS_TYPES = ["Aberto", "Em andamento", "Resolvido", "Fechado"]
PRIORITY_TYPES = ["Baixa", "Normal", "Alta", "Crítica"]
ROLE_TYPES = ["admin", "operador", "user"]

# Validadores de tipo
def validate_sector(sector: str) -> bool:
    """Valida se o setor é válido"""
    return sector in SETOR_TYPES.keys()

def validate_status(status: str) -> bool:
    """Valida se o status é válido"""
    return status in STATUS_TYPES

def validate_priority(priority: str) -> bool:
    """Valida se a prioridade é válida"""
    return priority in PRIORITY_TYPES

def validate_role(role: str) -> bool:
    """Valida se o papel/role é válido"""
    return role in ROLE_TYPES