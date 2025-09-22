from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=False)  # Match database length
    role = db.Column(db.String(20), nullable=False, default='usuario')  # admin, operador, usuario
    setor = db.Column(db.String(50), nullable=True)  # Match database schema
    active = db.Column(db.Boolean, default=True, nullable=False)  # Match database schema
    created_at = db.Column(db.DateTime, default=datetime.now)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)
    
    def is_active(self) -> bool:
        return self.active
    
    def __repr__(self):
        return f'<User {self.username}>'

class Chamado(db.Model):
    __tablename__ = 'chamado'
    
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False, index=True)
    descricao = db.Column(db.Text, nullable=True)  # Match database schema
    status = db.Column(db.String(20), default='aberto', nullable=False, index=True)  # Match database default
    prioridade = db.Column(db.String(20), default='normal', nullable=False)  # Match database schema
    setor = db.Column(db.String(50), nullable=True, index=True)  # Match database schema
    usuario_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)  # Match database name
    criado_em = db.Column(db.DateTime, default=datetime.now, nullable=False)  # Match database name
    fechado_em = db.Column(db.DateTime, nullable=True)  # Match database name
    ramal = db.Column(db.String(20), nullable=True)  # Campo para número do ramal
    cdc = db.Column(db.String(50), nullable=True)  # Campo para CDC (Centro de Custo)
    
    # Additional fields for system functionality (can be added via migration)
    resolucao = db.Column(db.Text, nullable=True)  # Corrigido para corresponder ao esquema do banco
    assignee_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    closed_by_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)

    # Relationships with proper cascade settings
    usuario = db.relationship('User', foreign_keys=[usuario_id], backref=db.backref('chamados_criados', lazy='dynamic', cascade='all, delete-orphan'))
    assignee = db.relationship('User', foreign_keys=[assignee_id], backref=db.backref('chamados_assumidos', lazy='dynamic'))
    closed_by = db.relationship('User', foreign_keys=[closed_by_id], backref=db.backref('chamados_fechados', lazy='dynamic'))
    
    # Compatibility properties for existing code
    @property
    def creator_id(self):
        return self.usuario_id
        
    @property
    def created_at(self):
        return self.criado_em
        
    @property 
    def closed_at(self):
        return self.fechado_em
        
    @property
    def creator(self):
        return self.usuario
    
    def __repr__(self):
        return f'<Chamado {self.id}: {self.titulo}>'

class Role(db.Model):
    __tablename__ = 'role'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    permissions = db.Column(db.Text, nullable=True)  # JSON string
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f'<Role {self.name}: {self.display_name}>'
    
    def get_permissions(self):
        """Retorna lista de permissões"""
        import json
        try:
            return json.loads(self.permissions) if self.permissions else []
        except:
            return []
    
    def has_permission(self, permission):
        """Verifica se role tem permissão específica"""
        perms = self.get_permissions()
        return permission in perms

class Sector(db.Model):
    __tablename__ = 'sector'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    def __repr__(self):
        return f'<Sector {self.name}: {self.display_name}>'

class SystemSettings(db.Model):
    __tablename__ = 'system_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(100), unique=True, nullable=False)
    setting_value = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f'<SystemSettings {self.setting_key}: {self.setting_value}>'
