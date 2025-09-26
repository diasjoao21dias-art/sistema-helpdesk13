from flask import Flask, render_template, request, redirect, url_for, session, send_file, abort, flash
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
from sqlalchemy import text
from sqlalchemy.orm import joinedload, selectinload
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from datetime import datetime, timedelta
import pytz
import io, os, shutil
import psutil
import json
import sqlite3

# Configure Brasília timezone (GMT-3)
BRAZIL_TZ = pytz.timezone('America/Sao_Paulo')

def now_brazil():
    """Return current datetime in Brazil timezone (GMT-3)"""
    return datetime.now(BRAZIL_TZ).replace(tzinfo=None)
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import uuid

# SISTEMAS DE LICENCIAMENTO REATIVADOS
try:
    from backup_manager import BackupManager
    from database_safety import DatabaseSafety  
    from activity_logger import activity_logger, log_login, log_logout, log_admin_action, log_system_event
    from license_manager import license_manager, is_licensed, get_license_status, check_feature_access
    from license_generator import license_generator, create_standard_license, create_premium_license
    backup_manager = BackupManager("sistema_os.db")
    db_safety = DatabaseSafety("sistema_os.db")
    print("✅ Configurações de segurança aplicadas")
    print("✅ Sistemas de segurança carregados")
    print("🔐 Sistema de licenciamento ativo")
except ImportError as e:
    print(f"⚠️ Sistemas de segurança não carregados: {e}")
    backup_manager = None
    db_safety = None
    activity_logger = None
    license_manager = None
    
    # Funções de fallback se não conseguir carregar
    def is_licensed():
        return True

    def get_license_status():
        return {'licensed': True}

    def check_feature_access(feature):
        return True
    
    def log_login(user_id, username, ip_address=None, user_agent=None, session_id=None):
        pass
    
    def log_logout(user_id, username, ip_address=None, session_id=None):
        pass
    
    def log_admin_action(user_id, username, action_description, details=None):
        pass
    
    def log_system_event(event_type, description, details=None):
        pass

APP_NAME = "Sistemas Olivium"

SETOR_CHOICES = ["T.I", "Manutenção", "CCIH / SESMT / Manutenção de Ar condicionado", "Telefonia e outros serviços"]

# Internal value mapping for sector consolidation
SETOR_INTERNAL_VALUES = {
    "T.I": "ti",
    "Manutenção": "manutencao", 
    "CCIH / SESMT / Manutenção de Ar condicionado": "ccih_sesmt_arcondicionado",
    "Telefonia e outros serviços": "telefonia_outros"
}

# File upload configuration
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_uploaded_file(file):
    """Save uploaded file with secure name and return filename"""
    if file and file.filename and allowed_file(file.filename):
        # Create unique filename to prevent conflicts
        filename_parts = file.filename.rsplit('.', 1)
        if len(filename_parts) > 1:
            ext = filename_parts[1].lower()
        else:
            ext = 'unknown'
        filename = f"{uuid.uuid4()}.{ext}"
        file.save(os.path.join(UPLOAD_FOLDER, filename))
        return filename
    return None

# Carregar variáveis do arquivo .env se existir
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv não instalado, continuar sem ele

app = Flask(__name__)
import secrets
app.secret_key = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(32))
# Configuração de banco de dados SQLite

# CONFIGURAÇÃO OTIMIZADA DE SQLITE PARA PRODUÇÃO
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///sistema_os.db"
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
    'connect_args': {
        'timeout': 10,
        'check_same_thread': False,  # Permite múltiplas threads
    },
    'pool_timeout': 20,
    'pool_size': 10,
    'max_overflow': 20,
}
print("🗄️ Usando SQLite para desenvolvimento...")

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Performance optimization: Configure cache headers for static files
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 31536000  # 1 year cache for static assets
app.config["REPORT_DIR"] = os.path.join("static", "relatorios")
os.makedirs(app.config["REPORT_DIR"], exist_ok=True)

# Ensure uploads directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Sistema de usuários online
online_users = set()
user_sessions = {}

# Add datetime functions to Jinja2
@app.template_global()
def now():
    return now_brazil()

# Add JSON filter to Jinja2
@app.template_filter('fromjson')
def fromjson_filter(value):
    import json
    try:
        return json.loads(value) if value else []
    except:
        return []

db = SQLAlchemy(app)

# Configuração SocketIO para produção
import os
redis_url = os.getenv('REDIS_URL')

if redis_url:
    # Produção com Redis para múltiplos workers
    socketio = SocketIO(app, 
                       cors_allowed_origins="*",
                       logger=True, 
                       engineio_logger=False,
                       async_mode='eventlet',
                       message_queue=redis_url,
                       ping_timeout=60,
                       ping_interval=25)
    print("✅ SocketIO configurado para múltiplos workers com Redis")
else:
    # Desenvolvimento/produção single-worker
    try:
        import eventlet
        socketio = SocketIO(app, 
                           cors_allowed_origins="*", 
                           logger=True, 
                           engineio_logger=False,
                           async_mode='eventlet',
                           ping_timeout=60,
                           ping_interval=25)
        print("⚠️ SocketIO single-worker com eventlet (use Redis para múltiplos workers)")
    except ImportError:
        socketio = SocketIO(app, 
                           cors_allowed_origins="*", 
                           logger=True, 
                           engineio_logger=False,
                           async_mode='threading',
                           ping_timeout=60,
                           ping_interval=25)
        print("⚠️ SocketIO single-worker com threading")

# Performance optimization: Add cache headers for static files
@app.after_request
def add_cache_headers(response):
    # Add cache headers for static assets to improve loading performance
    if request.endpoint == 'static':
        # Cache static files for 1 year
        response.cache_control.max_age = 31536000
        response.cache_control.public = True
    elif request.path.endswith(('.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.ico', '.woff', '.woff2', '.ttf')):
        # Cache other assets for 1 month
        response.cache_control.max_age = 2592000
        response.cache_control.public = True
    else:
        # No cache for dynamic pages (but allow reasonable cache for performance)
        response.cache_control.max_age = 0
        response.cache_control.no_cache = True
        response.cache_control.must_revalidate = True
    return response

def bootstrap():
    # cria tabelas e admin/admin se não existir
    db.create_all()
    
    # Adicionar coluna ramal se não existir
    try:
        db.session.execute(text('ALTER TABLE chamado ADD COLUMN ramal VARCHAR(20)'))
        db.session.commit()
        print("✅ Coluna 'ramal' adicionada na tabela 'chamado'")
    except Exception as e:
        if "duplicate column name" in str(e) or "already exists" in str(e):
            print("✅ Coluna 'ramal' já existe na tabela 'chamado'")
        else:
            print(f"⚠️ Erro ao adicionar coluna 'ramal': {e}")
        db.session.rollback()
    
    if not User.query.filter_by(username="admin").first():
        u = User(username="admin", role="admin", setor=None)
        u.set_password("admin")
        db.session.add(u)
        db.session.commit()


# -------------------- MODELOS --------------------

# New models for advanced admin functionality
class Sector(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=now_brazil)

# Many-to-many relationship table for users and sectors
user_sectors = db.Table('user_sectors',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('sector_id', db.Integer, db.ForeignKey('sector.id'), primary_key=True)
)
    
# Sistema de roles simplificado usando string

class SystemSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(100), unique=True, nullable=False)
    setting_value = db.Column(db.Text, nullable=True)
    setting_type = db.Column(db.String(20), default='string')  # string, int, bool, json
    description = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=now_brazil)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin, operador, usuario
    setor = db.Column(db.String(50), nullable=True)  # legacy single sector - DEPRECATED
    # Sistema de roles simplificado usando campo string
    # New many-to-many relationship with sectors
    sectors = db.relationship('Sector', secondary=user_sectors, backref='users', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
        
    def has_permission(self, permission):
        """Check if user has specific permission"""
        if self.role == 'admin':  # Admin always has all permissions
            return True
            
        # Check custom roles from Role table FIRST (they take precedence)
        custom_role = Role.query.filter_by(name=self.role, active=True).first()
        if custom_role:
            return custom_role.has_permission(permission)
            
        # Check basic built-in roles
        if self.role == 'operador':
            # Operators can view and update tickets
            return permission in ['view_tickets', 'update_tickets', 'create_tickets', 'view_sector', 'edit_sector', 'close_tickets', 'view_reports', 'edit_tickets', 'delete_tickets']
        elif self.role == 'usuario':
            # Users can only view and create their own tickets
            return permission in ['view_own_tickets', 'create_tickets', 'view_own']
        
        # Fallback to legacy role-based permissions for unknown roles
        legacy_permissions = {
            'admin': ['view_all', 'edit_all', 'delete_all', 'manage_users', 'manage_sectors', 'manage_roles', 'view_reports', 'manage_settings', 'close_tickets', 'create_tickets', 'admin_access', 'edit_tickets', 'delete_tickets'],
            'operador': ['view_sector', 'edit_sector', 'close_tickets', 'create_tickets', 'view_reports', 'edit_tickets', 'delete_tickets'],
            'usuario': ['create_tickets', 'view_own']
        }
        
        role_perms = legacy_permissions.get(self.role, [])
        return permission in role_perms
        
    def is_admin(self):
        """Check if user is admin (built-in admin or custom role with admin permissions)"""
        if self.role == 'admin':
            return True
        return self.has_permission('admin_access')
        
    def is_operator_like(self):
        """Check if user has operator-like permissions (built-in operador or custom role with operator permissions)"""
        if self.role == 'operador':
            return True
        return self.has_permission('view_sector') or self.has_permission('edit_sector')
        
    def can_access_sector(self, sector_name):
        """Check if user can access tickets from a specific sector"""
        if self.is_admin():
            return True
        if self.is_operator_like():
            return self.has_sector_access(sector_name)
        return False
        
    def get_sectors(self):
        """Get all sectors user has access to"""
        if self.role == 'admin':  # Admin sees all sectors
            return Sector.query.filter_by(active=True).all()
        elif self.sectors:
            return [s for s in self.sectors if s.active]
        elif self.setor:  # Legacy single sector
            sector = Sector.query.filter_by(name=self.setor, active=True).first()
            return [sector] if sector else []
        return []
    
    def get_sector_names(self):
        """Get list of sector names user has access to"""
        return [s.name for s in self.get_sectors()]
    
    def has_sector_access(self, sector_name):
        """Check if user has access to a specific sector"""
        if self.role == 'admin':
            return True
        return sector_name in self.get_sector_names()
    
    def assign_sectors(self, sector_ids):
        """Assign multiple sectors to user"""
        # Clear existing sectors
        self.sectors.clear()
        # Add new sectors
        if sector_ids:
            sectors = Sector.query.filter(Sector.id.in_(sector_ids)).all()
            self.sectors.extend(sectors)
        # Update legacy setor field for backward compatibility
        if self.sectors:
            self.setor = self.sectors[0].name
        else:
            self.setor = None

class Chamado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="Aberto")  # Aberto, Em Andamento, Fechado
    criado_em = db.Column(db.DateTime, default=now_brazil)  # horário de Brasília (GMT-3)
    fechado_em = db.Column(db.DateTime, nullable=True)
    resolucao = db.Column(db.Text, nullable=True)
    setor = db.Column(db.String(50), nullable=True)
    usuario_setor = db.Column(db.String(50), nullable=True)  # setor do usuário que abriu o chamado
    urgencia = db.Column(db.String(20), nullable=True)  # Urgente, Não Urgente (apenas quando fechado)
    ramal = db.Column(db.String(20), nullable=True)  # número do ramal do usuário
    cdc = db.Column(db.String(50), nullable=True)  # Campo para CDC (Centro de Custo)
    
    # Image attachments
    imagem1 = db.Column(db.String(255), nullable=True)  # Path to first image
    imagem2 = db.Column(db.String(255), nullable=True)  # Path to second image
    imagem3 = db.Column(db.String(255), nullable=True)  # Path to third image

    usuario_id = db.Column(db.Integer, db.ForeignKey("user.id"))        # quem abriu
    usuario = db.relationship("User", foreign_keys=[usuario_id])

    fechado_por_id = db.Column(db.Integer, db.ForeignKey("user.id"))    # quem fechou
    fechado_por = db.relationship("User", foreign_keys=[fechado_por_id])
    
    def get_images(self):
        """Return list of image paths that exist"""
        images = []
        for img_field in [self.imagem1, self.imagem2, self.imagem3]:
            if img_field:
                images.append(img_field)
        return images

class Role(db.Model):
    """Role model for advanced permissions system"""
    __tablename__ = 'role'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    permissions = db.Column(db.Text, nullable=True)  # JSON string
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=now_brazil)
    updated_at = db.Column(db.DateTime, default=now_brazil, onupdate=now_brazil)
    
    def __repr__(self):
        return f'<Role {self.name}: {self.display_name}>'
    
    def get_permissions(self):
        """Return list of permissions"""
        import json
        try:
            return json.loads(self.permissions) if self.permissions else []
        except:
            return []
    
    def has_permission(self, permission):
        """Check if role has specific permission"""
        perms = self.get_permissions()
        return permission in perms

# -------------------- HELPERS DE AUTENTICAÇÃO --------------------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        # Verificar licença primeiro (REATIVADO COMO ANTES)
        if license_manager:
            license_status = get_license_status()
            if not license_status['licensed']:
                if license_status.get('status') == 'expired':
                    return render_template("license/expired.html", 
                                         app_name=APP_NAME, 
                                         license_status=license_status)
                else:
                    return redirect(url_for("license_activation"))
        
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

def roles_required(*roles):
    def deco(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            u = db.session.get(User, session["user_id"])
            if not u or u.role not in roles:
                return abort(403)
            return f(*args, **kwargs)
        return wrapper
    return deco

def permission_required(*permissions):
    """Decorator to check specific permissions instead of roles"""
    def deco(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            u = db.session.get(User, session["user_id"])
            if not u:
                return abort(403)
            
            # Check if user has ANY of the required permissions
            has_permission = False
            for permission in permissions:
                if u.has_permission(permission):
                    has_permission = True
                    break
                    
            if not has_permission:
                return abort(403)
            return f(*args, **kwargs)
        return wrapper
    return deco

def current_user():
    if "user_id" in session:
        try:
            user = db.session.get(User, session["user_id"])
            if user:
                # Refresh user sectors in session for immediate effect
                session['user_sectors'] = user.get_sector_names()
                session['user_role'] = user.role
                return user
        except Exception as e:
            print(f"Error getting current user: {e}")
            # Try with basic columns only
            try:
                with db.engine.connect() as conn:
                    # Fallback query compatível com SQLite
                    result = conn.execute(text('SELECT id, username, password_hash, role FROM user WHERE id = :user_id'), {"user_id": session["user_id"]})
                    row = result.fetchone()
                    if row:
                        user = User()
                        user.id = row[0]
                        user.username = row[1] 
                        user.password_hash = row[2]
                        user.role = row[3]
                        return user
            except Exception as e2:
                print(f"Error with fallback query: {e2}")
    return None

# -------------------- CRIA DB E USUÁRIOS PADRÃO --------------------

def ensure_columns():
    # garante colunas 'setor' em user e chamado (SQLite) e novas colunas para admin menu
    try:
        import sqlite3
        db_path = os.path.join(app.root_path, "sistema_os.db")
        if not os.path.exists(db_path):
            db_path = "sistema_os.db"
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        # WAL mode uma vez apenas (persiste no arquivo)
        try:
            cur.execute("PRAGMA journal_mode=WAL")
            print("✅ WAL mode configurado (persiste)")
        except Exception as pragma_e:
            print(f"⚠️ Erro ao configurar WAL: {pragma_e}")
        
        def has_col(table, col):
            cur.execute(f'PRAGMA table_info({table})')
            return any(r[1] == col for r in cur.fetchall())
        
        # Legacy columns
        if not has_col("user", "setor"):
            cur.execute("ALTER TABLE user ADD COLUMN setor VARCHAR(50)")
        if not has_col("chamado", "setor"):
            cur.execute("ALTER TABLE chamado ADD COLUMN setor VARCHAR(50)")
        if not has_col("chamado", "usuario_setor"):
            cur.execute("ALTER TABLE chamado ADD COLUMN usuario_setor VARCHAR(50)")
        if not has_col("chamado", "urgencia"):
            cur.execute("ALTER TABLE chamado ADD COLUMN urgencia VARCHAR(20)")
            
        # New columns for admin menu functionality
        if not has_col("user", "role_id"):
            cur.execute("ALTER TABLE user ADD COLUMN role_id INTEGER")
        if not has_col("user", "active"):
            cur.execute("ALTER TABLE user ADD COLUMN active BOOLEAN DEFAULT 1")
        if not has_col("user", "created_at"):
            cur.execute("ALTER TABLE user ADD COLUMN created_at DATETIME")
            
        conn.commit()
        conn.close()
    except Exception as e:
        print("Aviso: não consegui garantir colunas de setor:", e)

def configure_sqlite_pragmas():
    """Configurar PRAGMAs SQLite para produção via eventos SQLAlchemy"""
    from sqlalchemy import event
    
    @event.listens_for(db.engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        try:
            cursor = dbapi_connection.cursor()
            # WAL mode para melhor concorrência
            cursor.execute("PRAGMA journal_mode=WAL")
            # Timeout para operações bloqueadas - crítico para concorrência
            cursor.execute("PRAGMA busy_timeout=5000")
            # Cache de páginas em memória
            cursor.execute("PRAGMA cache_size=10000")
            # Armazenar arquivos temporários em memória
            cursor.execute("PRAGMA temp_store=memory")
            # Memory-mapped I/O para arquivos grandes
            cursor.execute("PRAGMA mmap_size=268435456")  # 256MB
            # Sincronização normal (balanço performance/segurança)
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()
            print("✅ PRAGMAs SQLite aplicados via SQLAlchemy")
        except Exception as e:
            print(f"⚠️ Erro ao configurar PRAGMAs SQLite: {e}")

def initialize_system():
    """Initialize database tables, default data, and migrate existing data"""
    with app.app_context():
        # Configure SQLite PRAGMAs first
        configure_sqlite_pragmas()
        # First create basic tables
        db.create_all()
        # Then ensure columns exist with migration
        ensure_columns()
        
        # Create default users with simple approach first
        def ensure_user(username, role, pwd):
            try:
                # Check if user exists using raw SQL to avoid ORM issues
                with db.engine.begin() as conn:
                    result = conn.execute(text("SELECT COUNT(*) FROM user WHERE username = :username"), {"username": username})
                    count = result.scalar()
                    
                    if count == 0:
                        # Create user with basic columns
                        conn.execute(text("INSERT INTO user (username, password_hash, role) VALUES (:username, :password_hash, :role)"), 
                                   {"username": username, "password_hash": generate_password_hash(pwd), "role": role})
                        print(f"Created user {username}")
                    else:
                        print(f"User {username} already exists")
                        
            except Exception as e:
                print(f"Error creating user {username}: {e}")
        
        ensure_user("admin", "admin", "admin")
        ensure_user("operador", "operador", "operador")
        ensure_user("usuario", "usuario", "usuario")
        
        print("Basic users created successfully")
        
        # Initialize custom roles
        try:
            # Create semigerente role if it doesn't exist
            semigerente = Role.query.filter_by(name='semigerente').first()
            if not semigerente:
                semigerente = Role(
                    name='semigerente',
                    display_name='Semi Gerente',
                    description='Acesso completo a todas as funcionalidades',
                    active=True,
                    permissions='view_all,edit_all,delete_all,manage_users,manage_sectors,view_reports,manage_settings,close_tickets,create_tickets,admin_access,edit_tickets,delete_tickets,view_tickets,update_tickets,view_sector,edit_sector'
                )
                db.session.add(semigerente)
                print("🔐 Papel 'semigerente' criado com todas as permissões")
            
            # Create semioperador role if it doesn't exist  
            semioperador = Role.query.filter_by(name='semioperador').first()
            if not semioperador:
                semioperador = Role(
                    name='semioperador',
                    display_name='Semi Operador',
                    description='Acesso somente a relatórios para visualização',
                    active=True,
                    permissions='view_reports,view_tickets,view_sector'
                )
                db.session.add(semioperador)
                print("🔐 Papel 'semioperador' criado com permissões de relatórios")
                
            db.session.commit()
            print("Custom roles initialized successfully")
            
        except Exception as e:
            print(f"❌ Erro ao criar papéis customizados: {e}")
            db.session.rollback()

# Initialize system on import (disabled - using manual DB init)
# initialize_system()

@app.route("/admin/init-system")
@login_required
def admin_init_system():
    """Manual initialization of custom roles (admin only)"""
    u = current_user()
    if not u.is_admin():
        abort(403)
    
    try:
        initialize_system()
        flash("Sistema inicializado com sucesso! Papéis customizados criados.", "success")
    except Exception as e:
        flash(f"Erro na inicialização: {e}", "danger")
    
    return redirect(url_for("index"))

# -------------------- ROTAS DE AUTENTICAÇÃO --------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            # Check if user is active (disabled - column doesn't exist in current schema)
            # This check was causing SQL errors and reducing performance
            # Future: Add 'active' column if user activation/deactivation is needed
            pass
            
            session["user_id"] = user.id
            
            # Rastrear usuário online
            online_users.add(user.id)
            user_sessions[user.id] = {
                'login_time': datetime.now(),
                'last_activity': datetime.now(),
                'username': user.username
            }
            
            # Log da atividade
            if activity_logger:
                log_login(user.id, user.username)
            
            return redirect(url_for("index"))
        flash("Usuário ou senha incorretos.", "danger")
    return render_template("login.html", app_name=APP_NAME)

@app.route("/logout")
@login_required
def logout():
    # Rastrear saída do usuário
    user_id = session.get("user_id")
    if user_id:
        # Remover usuário da lista de online
        online_users.discard(user_id)
        if user_id in user_sessions:
            username = user_sessions[user_id].get('username', 'Usuário')
            del user_sessions[user_id]
            # Log da atividade
            if activity_logger:
                log_logout(user_id, username)
    
    session.clear()
    return redirect(url_for("login"))

# -------------------- ROTAS PRINCIPAIS --------------------
@app.route("/")
@login_required
def index():
    u = current_user()
    
    # Se não conseguiu obter usuário atual, redirecionar para login
    if not u or not hasattr(u, 'role'):
        session.clear()
        return redirect(url_for("login"))
    
    # Paginação inteligente - Admin pode ver todos, mas de forma eficiente
    page = request.args.get('page', 1, type=int)
    per_page = int(request.args.get('per_page', 50))  # 50 por página é um bom equilíbrio
    
    # Permitir até 200 por página para admins que querem ver mais
    if per_page > 200:
        per_page = 200
    
    # Get sort parameter from URL (default: desc for newest first - mais útil)
    sort_order = request.args.get('sort', 'desc')
    
    # Determine sort order (desc = mais recentes primeiro é melhor para admins)
    if sort_order == 'desc':
        order_by_clause = Chamado.criado_em.desc()
        next_sort = 'asc'
        sort_label = 'Recentes Primeiro'
        sort_icon = 'bi bi-arrow-down'
    else:
        order_by_clause = Chamado.criado_em.asc()
        next_sort = 'desc'
        sort_label = 'Antigos Primeiro'
        sort_icon = 'bi bi-arrow-up'
    
    # Optimize database queries with eager loading to prevent N+1 problems
    base_query = Chamado.query.options(
        joinedload(Chamado.usuario),
        joinedload(Chamado.fechado_por)
    )
    
    # Aplicar filtros baseados no usuário
    if u.is_admin():
        # Admin sees all tickets - mas paginado para performance
        query = base_query.order_by(order_by_clause)
    elif u.has_permission('view_all'):
        # Users with view_all permission (like semigerente) see all tickets
        query = base_query.order_by(order_by_clause)
    elif u.is_operator_like():
        # Operators and operator-like roles see tickets from their assigned sectors only
        user_sector_names = u.get_sector_names()
        if user_sector_names:
            query = base_query.filter(Chamado.setor.in_(user_sector_names)).order_by(order_by_clause)
        else:
            query = base_query.filter(Chamado.id == -1)  # Query that returns no results
    else:
        # Regular users see only their own tickets
        query = base_query.filter_by(usuario_id=u.id).order_by(order_by_clause)
    
    # Executar paginação
    pagination = query.paginate(
        page=page, 
        per_page=per_page, 
        error_out=False,
        max_per_page=200
    )
    
    chamados = pagination.items
    
    # Estatísticas rápidas para o dashboard (só para admin)
    stats = None
    if u.is_admin() or u.has_permission('view_all'):
        try:
            # Usar índices criados para consultas rápidas
            total = Chamado.query.count()
            abertos = Chamado.query.filter_by(status='Aberto').count()
            fechados = Chamado.query.filter_by(status='Fechado').count()
            em_andamento = Chamado.query.filter_by(status='Em Andamento').count()
            
            stats = {
                'total': total,
                'abertos': abertos,
                'fechados': fechados,
                'em_andamento': em_andamento
            }
        except Exception as e:
            print(f"Erro ao calcular estatísticas: {e}")
            stats = None
    
    return render_template("index.html", 
                         app_name=APP_NAME, 
                         user=u, 
                         chamados=chamados,
                         pagination=pagination,
                         stats=stats,
                         sort_order=sort_order,
                         next_sort=next_sort,
                         sort_label=sort_label,
                         sort_icon=sort_icon,
                         per_page=per_page)

# -------------------- USUÁRIOS (ADMIN) --------------------
@app.route("/usuarios")
@login_required
@roles_required("admin")
def usuarios_list():
    users = User.query.order_by(User.username).all()
    return render_template("usuarios_list.html", app_name=APP_NAME, user=current_user(), users=users)

@app.route("/usuarios/novo", methods=["GET","POST"])
@login_required
@roles_required("admin")
def usuarios_novo():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        role = request.form["role"]
        if not username or not password:
            flash("Preencha usuário e senha.", "warning")
            return redirect(url_for("usuarios_novo"))
        if User.query.filter_by(username=username).first():
            flash("Usuário já existe.", "danger")
            return redirect(url_for("usuarios_novo"))
        
        u = User(username=username, role=role)
        u.set_password(password)
        db.session.add(u)
        
        # Handle sector assignment
        sector_ids = request.form.getlist('sector_ids')
        legacy_setor = request.form.get('setor')
        
        if sector_ids:
            sector_ids = [int(id) for id in sector_ids if id.isdigit()]
            u.assign_sectors(sector_ids)
        elif legacy_setor:
            sector = Sector.query.filter_by(name=legacy_setor).first()
            if sector:
                u.assign_sectors([sector.id])
            else:
                u.setor = legacy_setor
        
        # Validate operator sector assignment
        if role == 'operador' and not u.get_sectors():
            flash("Operadores devem ter pelo menos um setor atribuído.", "warning")
            # Buscar setores para o template
            try:
                sectors = Sector.query.filter_by(active=True).order_by(Sector.display_name).all()
            except:
                sectors = []
            return render_template("usuarios_form.html", app_name=APP_NAME, user=current_user(), u=None, sectors=sectors)
        
        db.session.commit()
        flash("Usuário criado.", "success")
        return redirect(url_for("usuarios_list"))
    
    # Buscar setores para o template
    try:
        sectors = Sector.query.filter_by(active=True).order_by(Sector.display_name).all()
    except:
        sectors = []
    return render_template("usuarios_form.html", app_name=APP_NAME, user=current_user(), u=None, sectors=sectors)

@app.route("/usuarios/editar/<int:user_id>", methods=["GET","POST"])
@login_required
@roles_required("admin")
def usuarios_editar(user_id):
    u = db.session.get(User, user_id) or abort(404)
    if request.method == "POST":
        u.username = request.form["username"].strip()
        new_pwd = request.form.get("password","").strip()
        u.role = request.form["role"]
        
        # Handle both legacy single sector and new multi-sector assignment
        sector_ids = request.form.getlist('sector_ids')
        legacy_setor = request.form.get('setor')
        
        if sector_ids:
            # New multi-sector system
            sector_ids = [int(id) for id in sector_ids if id.isdigit()]
            u.assign_sectors(sector_ids)
        elif legacy_setor:
            # Legacy single sector system - find sector by name and assign
            sector = Sector.query.filter_by(name=legacy_setor).first()
            if sector:
                u.assign_sectors([sector.id])
            else:
                u.setor = legacy_setor  # Fallback for backward compatibility
        else:
            # Clear sectors
            u.assign_sectors([])
        
        # Validate operator sector assignment
        if u.is_operator_like() and not u.is_admin() and not u.get_sectors():
            flash("Operadores devem ter pelo menos um setor atribuído.", "warning")
            # Buscar setores para o template
            try:
                sectors = Sector.query.filter_by(active=True).order_by(Sector.display_name).all()
            except:
                sectors = []
            return render_template("usuarios_form.html", app_name=APP_NAME, user=current_user(), u=u, sectors=sectors)
        
        if new_pwd:
            u.set_password(new_pwd)
        
        # Force session refresh for currently logged in user
        if u.id == session.get('user_id'):
            session['user_sectors'] = u.get_sector_names()
            session['user_role'] = u.role
        
        db.session.commit()
        flash("Usuário atualizado.", "success")
        return redirect(url_for("usuarios_list"))
    
    # Buscar setores para o template
    try:
        sectors = Sector.query.filter_by(active=True).order_by(Sector.display_name).all()
    except:
        sectors = []
    return render_template("usuarios_form.html", app_name=APP_NAME, user=current_user(), u=u, sectors=sectors)

@app.route("/usuarios/excluir/<int:user_id>")
@login_required
@roles_required("admin")
def usuarios_excluir(user_id):
    if user_id == session.get("user_id"):
        flash("Você não pode excluir a si mesmo.", "warning")
        return redirect(url_for("usuarios_list"))
    u = db.session.get(User, user_id) or abort(404)
    db.session.delete(u)
    db.session.commit()
    flash("Usuário excluído.", "success")
    return redirect(url_for("usuarios_list"))

# -------------------- CHAMADOS --------------------
@app.route("/chamados/novo", methods=["GET","POST"])
@login_required
def chamados_novo():
    u = current_user()
    if request.method == "POST":
        titulo = request.form["titulo"].strip()
        descricao = request.form["descricao"].strip()
        if not titulo or not descricao:
            flash("Informe título e descrição.", "warning")
            return redirect(url_for("chamados_novo"))
        usuario_setor = request.form.get('usuario_setor')
        if not usuario_setor:
            flash("Informe seu setor.", "warning")
            return redirect(url_for("chamados_novo"))
        ramal = request.form.get('ramal', '').strip()
        cdc = request.form.get('cdc', '').strip()
        
        # Validação CDC para setor COMPRAS
        setor_selecionado = request.form.get('setor', '').strip()
        if setor_selecionado and ('COMPRAS' in setor_selecionado.upper() or 'COMPRA' in setor_selecionado.upper()):
            if not cdc:
                flash("Para o setor COMPRAS é obrigatório informar o CDC. Caso não tenha na sua OS, a mesma será invalidada.", "error")
                return redirect(url_for("chamados_novo"))
        
        c = Chamado(titulo=titulo, descricao=descricao, usuario_id=u.id, status="Aberto", setor=request.form.get('setor'), usuario_setor=usuario_setor, ramal=ramal, cdc=cdc)
        
        # Handle image uploads
        for i in range(1, 4):  # imagem1, imagem2, imagem3
            file = request.files.get(f'imagem{i}')
            if file:
                filename = save_uploaded_file(file)
                if filename:
                    setattr(c, f'imagem{i}', filename)
        
        db.session.add(c)
        db.session.commit()
        # Emit WebSocket event for new ticket
        emit_ticket_update(ticket_to_dict(c), 'created')
        flash("Chamado criado.", "success")
        return redirect(url_for("index"))
    
    # Get dynamic sectors for the form
    try:
        sectors = Sector.query.filter_by(active=True).order_by(Sector.display_name).all()
    except:
        # Fallback to default sectors if table doesn't exist yet
        sectors = [
            {'name': 'ti', 'display_name': 'T.I'},
            {'name': 'manutencao', 'display_name': 'Manutenção'},
            {'name': 'ccih', 'display_name': 'CCIH / SESMT / Manutenção de Ar condicionado'},
            {'name': 'telefonia', 'display_name': 'Telefonia e outros serviços'}
        ]
    
    return render_template("chamado_form.html", app_name=APP_NAME, user=u, chamado=None, sectors=sectors)

@app.route("/chamados/editar/<int:cid>", methods=["GET","POST"])
@login_required
def chamados_editar(cid):
    u = current_user()
    c = db.session.get(Chamado, cid) or abort(404)
    # permissões atualizadas: apenas admin pode editar
    if not u.is_admin():
        abort(403)
    if request.method == "POST":
        old_status = c.status
        c.titulo = request.form["titulo"].strip()
        c.descricao = request.form["descricao"].strip()
        c.status = request.form.get("status", c.status)
        # Update sector if provided
        setor = request.form.get("setor")
        if setor:
            c.setor = setor
        
        # Update CDC field
        cdc = request.form.get('cdc', '').strip()
        c.cdc = cdc
        
        # Validação CDC para setor COMPRAS na edição
        if c.setor and ('COMPRAS' in c.setor.upper() or 'COMPRA' in c.setor.upper()):
            if not cdc:
                flash("Para o setor COMPRAS é obrigatório informar o CDC. Caso não tenha na sua OS, a mesma será invalidada.", "error")
                # Get dynamic sectors for the form in case of error
                try:
                    sectors = Sector.query.filter_by(active=True).order_by(Sector.display_name).all()
                except:
                    sectors = [
                        {'name': 'ti', 'display_name': 'T.I'},
                        {'name': 'manutencao', 'display_name': 'Manutenção'},
                        {'name': 'ccih', 'display_name': 'CCIH / SESMT / Manutenção de Ar condicionado'},
                        {'name': 'telefonia', 'display_name': 'Telefonia e outros serviços'}
                    ]
                return render_template("chamado_form.html", app_name=APP_NAME, user=u, chamado=c, sectors=sectors)
        
        # Handle image uploads and removals
        for i in range(1, 4):  # imagem1, imagem2, imagem3
            # Check if user wants to remove existing image
            if request.form.get(f'remover_imagem{i}'):
                old_image = getattr(c, f'imagem{i}')
                if old_image:
                    # Delete file from filesystem
                    try:
                        os.remove(os.path.join(UPLOAD_FOLDER, old_image))
                    except:
                        pass  # File might not exist
                setattr(c, f'imagem{i}', None)
            
            # Handle new image upload
            file = request.files.get(f'imagem{i}')
            if file:
                filename = save_uploaded_file(file)
                if filename:
                    # Remove old image if replacing
                    old_image = getattr(c, f'imagem{i}')
                    if old_image:
                        try:
                            os.remove(os.path.join(UPLOAD_FOLDER, old_image))
                        except:
                            pass
                    setattr(c, f'imagem{i}', filename)
        
        db.session.commit()
        # Emit WebSocket event for ticket update
        event_type = 'status_changed' if old_status != c.status else 'updated'
        emit_ticket_update(ticket_to_dict(c), event_type)
        flash("Chamado atualizado.", "success")
        return redirect(url_for("index"))
    
    # Get dynamic sectors for the form
    try:
        sectors = Sector.query.filter_by(active=True).order_by(Sector.display_name).all()
    except:
        # Fallback to default sectors if table doesn't exist yet
        sectors = [
            {'name': 'ti', 'display_name': 'T.I'},
            {'name': 'manutencao', 'display_name': 'Manutenção'},
            {'name': 'ccih', 'display_name': 'CCIH / SESMT / Manutenção de Ar condicionado'},
            {'name': 'telefonia', 'display_name': 'Telefonia e outros serviços'}
        ]
    
    return render_template("chamado_form.html", app_name=APP_NAME, user=u, chamado=c, sectors=sectors)

@app.route("/chamados/fechar/<int:cid>", methods=["GET","POST"])
@login_required
def chamados_fechar(cid):
    u = current_user()
    c = db.session.get(Chamado, cid) or abort(404)
    # admin/operador podem fechar, operador apenas do seu setor
    if not (u.is_admin() or u.is_operator_like()):
        abort(403)
    if u.is_operator_like() and not u.is_admin() and c.setor and not u.can_access_sector(c.setor):
        abort(403)
    if request.method == "POST":
        urgencia = request.form.get("urgencia")
        if not urgencia or urgencia not in ["Urgente", "Não Urgente"]:
            flash("É obrigatório selecionar a classificação de urgência.", "error")
            return render_template("chamado_fechar.html", app_name=APP_NAME, user=u, chamado=c)
        
        c.status = "Fechado"
        c.fechado_em = now_brazil()
        c.resolucao = request.form["resolucao"].strip()
        c.urgencia = urgencia
        c.fechado_por_id = u.id
        db.session.commit()
        # Emit WebSocket event for ticket closure
        emit_ticket_update(ticket_to_dict(c), 'closed')
        flash("Chamado fechado.", "success")
        return redirect(url_for("index"))
    return render_template("chamado_fechar.html", app_name=APP_NAME, user=u, chamado=c)

@app.route("/chamados/excluir/<int:cid>")
@login_required
def chamados_excluir(cid):
    u = current_user()
    c = db.session.get(Chamado, cid) or abort(404)
    # apenas admin pode excluir
    if not u.is_admin():
        abort(403)
    db.session.delete(c)
    db.session.commit()
    flash("Chamado excluído.", "success")
    return redirect(url_for("index"))

# -------------------- VIEW TICKET --------------------
@app.route("/chamados/view/<int:cid>")
@login_required
def chamados_view(cid):
    u = current_user()
    c = db.session.get(Chamado, cid) or abort(404)
    
    # Permissões: admin vê tudo, operador vê do seu setor, usuário vê apenas os seus
    if not u.is_admin() and not u.has_permission('view_all'):
        if u.is_operator_like() and c.setor and not u.can_access_sector(c.setor):
            abort(403)
        elif not u.is_operator_like() and c.usuario_id != u.id:
            abort(403)
    
    return render_template("chamado_view.html", app_name=APP_NAME, user=u, chamado=c)

# -------------------- ADMIN UTIL --------------------
@app.route("/admin/backup")
@login_required
@roles_required("admin")
def admin_backup():
    # envia o arquivo sqlite para download
    db_path = os.path.join(app.root_path, "sistema_os.db")
    if not os.path.exists(db_path):
        # também pode estar relativo
        db_path = "sistema_os.db"
    if not os.path.exists(db_path):
        flash("Banco de dados não encontrado.", "danger")
        return redirect(url_for("index"))
    return send_file(db_path, as_attachment=True, download_name="sistema_os_backup.sqlite")

# -------------------- DATABASE MANAGEMENT --------------------
@app.route("/admin/database/export")
@login_required
@roles_required("admin")
def admin_database_export():
    """Exportar banco de dados principal"""
    try:
        # Criar backup antes da exportação
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        db_path = "sistema_os.db"
        if not os.path.exists(db_path):
            flash("Banco de dados não encontrado.", "danger")
            return redirect(url_for("admin_settings"))
        
        # Nome do arquivo com timestamp
        download_name = f"sistema_os_export_{timestamp}.db"
        
        return send_file(db_path, as_attachment=True, download_name=download_name, mimetype='application/x-sqlite3')
    except Exception as e:
        flash(f"Erro ao exportar banco de dados: {str(e)}", "danger")
        return redirect(url_for("admin_settings"))

@app.route("/admin/database/import", methods=["POST"])
@login_required
@roles_required("admin")
def admin_database_import():
    """Importar banco de dados"""
    try:
        # Verificar se arquivo foi enviado
        if 'database_file' not in request.files:
            flash("Nenhum arquivo selecionado.", "danger")
            return redirect(url_for("admin_settings"))
        
        file = request.files['database_file']
        if file.filename == '':
            flash("Nenhum arquivo selecionado.", "danger")
            return redirect(url_for("admin_settings"))
        
        # Verificar confirmação
        if not request.form.get('confirm_import'):
            flash("É necessário confirmar a importação.", "danger")
            return redirect(url_for("admin_settings"))
        
        # Verificar extensão do arquivo
        allowed_extensions = {'.db', '.sqlite', '.sqlite3'}
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in allowed_extensions:
            flash("Tipo de arquivo não permitido. Use apenas .db, .sqlite ou .sqlite3", "danger")
            return redirect(url_for("admin_settings"))
        
        # Criar backup do banco atual antes da importação
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"backup_before_import_{timestamp}.db"
        
        import shutil
        if os.path.exists("sistema_os.db"):
            shutil.copy2("sistema_os.db", backup_path)
            print(f"Backup criado: {backup_path}")
        
        # Salvar arquivo temporário
        temp_path = f"temp_import_{timestamp}.db"
        file.save(temp_path)
        
        # Validar se é um banco SQLite válido
        import sqlite3
        try:
            test_conn = sqlite3.connect(temp_path)
            test_conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            test_conn.close()
        except sqlite3.Error as e:
            os.remove(temp_path)
            flash(f"Arquivo não é um banco SQLite válido: {str(e)}", "danger")
            return redirect(url_for("admin_settings"))
        
        # Fechar conexões do SQLAlchemy
        db.session.close()
        db.engine.dispose()
        
        # Substituir banco atual
        if os.path.exists("sistema_os.db"):
            os.remove("sistema_os.db")
        
        shutil.move(temp_path, "sistema_os.db")
        
        # Recriar conexão
        from sqlalchemy import create_engine
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sistema_os.db'
        db.engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
        
        flash(f"Banco de dados importado com sucesso! Backup salvo como: {backup_path}", "success")
        
        # Redirecionar para login pois pode ter mudado usuários
        session.clear()
        return redirect(url_for("login"))
        
    except Exception as e:
        # Tentar restaurar backup se algo deu errado
        try:
            if 'backup_path' in locals() and os.path.exists(backup_path):
                if os.path.exists("sistema_os.db"):
                    os.remove("sistema_os.db")
                shutil.move(backup_path, "sistema_os.db")
                flash(f"Erro na importação, banco restaurado: {str(e)}", "danger")
            else:
                flash(f"Erro crítico na importação: {str(e)}", "danger")
        except:
            flash(f"Erro crítico na importação e falha na restauração: {str(e)}", "danger")
        
        return redirect(url_for("admin_settings"))

# -------------------- MONITORING SYSTEM --------------------
@app.route("/admin/monitoring")
@login_required
@roles_required("admin")
def admin_monitoring():
    """Página principal de monitoramento do sistema"""
    try:
        # Status geral do sistema
        system_status = get_system_status()
        
        # Performance do sistema
        performance = get_system_performance()
        
        # Estatísticas do banco
        db_stats = get_database_stats()
        
        # Usuários online
        online_count = len(online_users)
        
        # Atividades recentes
        recent_activities = []
        if activity_logger:
            recent_activities = activity_logger.get_recent_activities(20)
        
        return render_template("admin/monitoring.html",
                             app_name=APP_NAME,
                             user=current_user(),
                             system_status=system_status,
                             performance=performance,
                             db_stats=db_stats,
                             online_users=online_count,
                             recent_activities=recent_activities)
    except Exception as e:
        flash(f"Erro ao carregar monitoramento: {str(e)}", "danger")
        return redirect(url_for("admin_dashboard"))

@app.route("/admin/monitoring/data")
@login_required
@roles_required("admin")
def admin_monitoring_data():
    """API para dados de monitoramento em tempo real"""
    try:
        # Atividades recentes
        recent_activities = []
        if activity_logger:
            recent_activities = activity_logger.get_recent_activities(10)
        
        data = {
            'online_users': len(online_users),
            'recent_activities': recent_activities,
            'timestamp': datetime.now().strftime('%H:%M:%S')
        }
        
        return json.dumps(data)
    except Exception as e:
        return json.dumps({'error': str(e)})

def get_system_status():
    """Obter status geral do sistema"""
    status = {
        'overall_status': 'Operacional',
        'overall_status_color': 'success',
        'overall_icon': 'check-circle',
        'db_status': 'Conectado',
        'db_status_color': 'success',
        'backup_status': 'Ativo',
        'backup_status_color': 'success',
        'last_backup': 'Hoje'
    }
    
    try:
        # Verificar conexão do banco
        result = db.session.execute(text("SELECT 1")).fetchone()
        if not result:
            status['db_status'] = 'Erro'
            status['db_status_color'] = 'danger'
            status['overall_status'] = 'Atenção'
            status['overall_status_color'] = 'warning'
    except:
        status['db_status'] = 'Erro'
        status['db_status_color'] = 'danger'
        status['overall_status'] = 'Crítico'
        status['overall_status_color'] = 'danger'
        status['overall_icon'] = 'exclamation-triangle'
    
    # Verificar último backup
    try:
        import glob
        backup_files = glob.glob("backups/*.db")
        if backup_files:
            latest_backup = max(backup_files, key=os.path.getctime)
            backup_time = datetime.fromtimestamp(os.path.getctime(latest_backup))
            hours_ago = (datetime.now() - backup_time).total_seconds() / 3600
            
            if hours_ago < 24:
                status['last_backup'] = f"{int(hours_ago)}h atrás"
            else:
                status['last_backup'] = backup_time.strftime('%d/%m')
                if hours_ago > 48:  # Mais de 2 dias
                    status['backup_status'] = 'Atrasado'
                    status['backup_status_color'] = 'warning'
        else:
            status['backup_status'] = 'Sem backup'
            status['backup_status_color'] = 'danger'
    except:
        status['backup_status'] = 'Erro'
        status['backup_status_color'] = 'danger'
    
    return status

def get_system_performance():
    """Obter métricas de performance do sistema"""
    performance = {
        'cpu_percent': 0,
        'cpu_color': 'success',
        'memory_percent': 0,
        'memory_color': 'success',
        'disk_percent': 0,
        'disk_color': 'success'
    }
    
    try:
        # CPU
        cpu = psutil.cpu_percent(interval=1)
        performance['cpu_percent'] = round(cpu, 1)
        if cpu > 80:
            performance['cpu_color'] = 'danger'
        elif cpu > 60:
            performance['cpu_color'] = 'warning'
        
        # Memória
        memory = psutil.virtual_memory()
        performance['memory_percent'] = round(memory.percent, 1)
        if memory.percent > 80:
            performance['memory_color'] = 'danger'
        elif memory.percent > 60:
            performance['memory_color'] = 'warning'
        
        # Disco
        disk = psutil.disk_usage('/')
        performance['disk_percent'] = round(disk.percent, 1)
        if disk.percent > 90:
            performance['disk_color'] = 'danger'
        elif disk.percent > 80:
            performance['disk_color'] = 'warning'
            
    except Exception as e:
        print(f"Erro ao obter performance: {e}")
    
    return performance

def get_database_stats():
    """Obter estatísticas do banco de dados"""
    stats = {
        'total_records': 0,
        'db_size': '0 MB',
        'active_tickets': 0,
        'total_users': 0
    }
    
    try:
        # Total de registros
        tables = ['user', 'chamado', 'system_activity']
        total = 0
        for table in tables:
            try:
                result = db.session.execute(text(f"SELECT COUNT(*) FROM {table}")).fetchone()
                if result:
                    total += result[0]
            except:
                pass
        stats['total_records'] = total
        
        # Tamanho do banco
        if os.path.exists("sistema_os.db"):
            size_bytes = os.path.getsize("sistema_os.db")
            size_mb = round(size_bytes / (1024 * 1024), 2)
            stats['db_size'] = f"{size_mb} MB"
        
        # Chamados ativos
        result = db.session.execute(text("SELECT COUNT(*) FROM chamado WHERE status != 'fechado'")).fetchone()
        if result:
            stats['active_tickets'] = result[0]
        
        # Total de usuários
        result = db.session.execute(text("SELECT COUNT(*) FROM user")).fetchone()
        if result:
            stats['total_users'] = result[0]
            
    except Exception as e:
        print(f"Erro ao obter estatísticas do banco: {e}")
    
    return stats

@app.route("/admin/logs")
@login_required
@roles_required("admin")
def admin_logs():
    """Página de logs de atividades"""
    try:
        # Paginação
        page = request.args.get('page', 1, type=int)
        per_page = 50
        
        # Filtros
        action_filter = request.args.get('action', '')
        user_filter = request.args.get('user', '')
        date_filter = request.args.get('date', '')
        
        # Obter logs com filtros
        logs = []
        total_logs = 0
        
        if activity_logger:
            # Implementar filtros na consulta
            conn = sqlite3.connect("sistema_os.db")
            cursor = conn.cursor()
            
            query = "SELECT * FROM system_activity WHERE 1=1"
            params = []
            
            if action_filter:
                query += " AND action_type LIKE ?"
                params.append(f'%{action_filter}%')
            
            if user_filter:
                query += " AND username LIKE ?"
                params.append(f'%{user_filter}%')
            
            if date_filter:
                query += " AND DATE(timestamp) = ?"
                params.append(date_filter)
            
            # Contar total
            count_query = query.replace("SELECT *", "SELECT COUNT(*)")
            cursor.execute(count_query, params)
            total_logs = cursor.fetchone()[0]
            
            # Buscar logs paginados
            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([per_page, (page - 1) * per_page])
            
            cursor.execute(query, params)
            raw_logs = cursor.fetchall()
            
            # Formatar logs
            for log in raw_logs:
                logs.append({
                    'id': log[0],
                    'timestamp': activity_logger.format_timestamp(log[1]),
                    'user': log[3] or 'Sistema',
                    'action': log[4],
                    'description': log[5],
                    'details': log[6],
                    'ip': log[7],
                    'color': activity_logger.get_action_color(log[4])
                })
            
            conn.close()
        
        # Estatísticas rápidas
        stats = activity_logger.get_activity_stats() if activity_logger else {}
        
        return render_template("admin/logs.html",
                             app_name=APP_NAME,
                             user=current_user(),
                             logs=logs,
                             total_logs=total_logs,
                             page=page,
                             per_page=per_page,
                             action_filter=action_filter,
                             user_filter=user_filter,
                             date_filter=date_filter,
                             stats=stats)
    
    except Exception as e:
        flash(f"Erro ao carregar logs: {str(e)}", "danger")
        return redirect(url_for("admin_dashboard"))

@app.route("/admin/maintenance", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def admin_maintenance():
    """Página de manutenção do sistema"""
    if request.method == "POST":
        action = request.form.get("action")
        
        try:
            if action == "optimize_db":
                # Otimizar banco de dados
                db.session.execute(text("VACUUM;"))
                db.session.execute(text("REINDEX;"))
                db.session.commit()
                
                if activity_logger:
                    log_admin_action(current_user().id, current_user().username, 
                                   "Otimização do banco de dados")
                
                flash("Banco de dados otimizado com sucesso!", "success")
                
            elif action == "cleanup_logs":
                # Limpar logs antigos
                if activity_logger:
                    days = int(request.form.get("days", 30))
                    deleted = activity_logger.cleanup_old_activities(days)
                    
                    log_admin_action(current_user().id, current_user().username, 
                                   f"Limpeza de logs - {deleted} registros removidos")
                    
                    flash(f"Removidos {deleted} logs antigos (mais de {days} dias)!", "success")
                
            elif action == "cleanup_reports":
                # Limpar relatórios antigos
                import glob
                report_files = glob.glob(os.path.join(app.config["REPORT_DIR"], "*.png"))
                report_files.extend(glob.glob(os.path.join(app.config["REPORT_DIR"], "*.pdf")))
                
                removed_count = 0
                for file in report_files:
                    try:
                        os.remove(file)
                        removed_count += 1
                    except:
                        pass
                
                if activity_logger:
                    log_admin_action(current_user().id, current_user().username, 
                                   f"Limpeza de relatórios - {removed_count} arquivos removidos")
                
                flash(f"Removidos {removed_count} arquivos de relatórios!", "success")
                
            elif action == "backup_db":
                # Criar backup manual
                if backup_manager:
                    backup_path = backup_manager.create_backup()
                    
                    if activity_logger:
                        log_admin_action(current_user().id, current_user().username, 
                                       f"Backup manual criado: {backup_path}")
                    
                    flash(f"Backup criado: {backup_path}", "success")
                else:
                    flash("Sistema de backup não disponível!", "warning")
                    
        except Exception as e:
            flash(f"Erro na operação: {str(e)}", "danger")
        
        return redirect(url_for("admin_maintenance"))
    
    # Obter informações do sistema
    try:
        # Informações do banco
        db_size = os.path.getsize("sistema_os.db") / (1024 * 1024) if os.path.exists("sistema_os.db") else 0
        
        # Informações de logs
        log_count = 0
        if activity_logger:
            conn = sqlite3.connect("sistema_os.db")
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT COUNT(*) FROM system_activity")
                log_count = cursor.fetchone()[0]
            except:
                pass
            conn.close()
        
        # Informações de backups
        backup_info = []
        if os.path.exists("backups"):
            import glob
            backup_files = glob.glob("backups/*.db")
            for backup in sorted(backup_files, key=os.path.getctime, reverse=True)[:5]:
                backup_info.append({
                    'name': os.path.basename(backup),
                    'size': f"{os.path.getsize(backup) / (1024 * 1024):.2f} MB",
                    'date': datetime.fromtimestamp(os.path.getctime(backup)).strftime('%d/%m/%Y %H:%M')
                })
        
        # Informações de relatórios
        report_count = 0
        report_size = 0
        if os.path.exists(app.config["REPORT_DIR"]):
            import glob
            report_files = glob.glob(os.path.join(app.config["REPORT_DIR"], "*"))
            report_count = len(report_files)
            for file in report_files:
                try:
                    report_size += os.path.getsize(file)
                except:
                    pass
            report_size = report_size / (1024 * 1024)  # MB
        
        system_info = {
            'db_size': f"{db_size:.2f} MB",
            'log_count': log_count,
            'backup_count': len(backup_info),
            'report_count': report_count,
            'report_size': f"{report_size:.2f} MB",
            'backup_info': backup_info
        }
        
    except Exception as e:
        system_info = {'error': str(e)}
    
    # Obter informações da licença
    license_status = None
    if license_manager:
        license_status = get_license_status()
    
    return render_template("admin/maintenance.html",
                         app_name=APP_NAME,
                         user=current_user(),
                         system_info=system_info,
                         license_status=license_status)

@app.route("/admin/audit")
@login_required
@roles_required("admin")
def admin_audit():
    """Página de auditoria e segurança"""
    try:
        # Estatísticas de segurança
        security_stats = {}
        
        if activity_logger:
            conn = sqlite3.connect("sistema_os.db")
            cursor = conn.cursor()
            
            # Logins nas últimas 24h
            yesterday = datetime.now() - timedelta(days=1)
            cursor.execute("""
                SELECT COUNT(*) FROM system_activity 
                WHERE action_type = 'LOGIN' AND timestamp > ?
            """, (yesterday.strftime('%Y-%m-%d %H:%M:%S'),))
            security_stats['logins_24h'] = cursor.fetchone()[0]
            
            # Tentativas de login falharam (seria necessário implementar)
            security_stats['failed_logins'] = 0
            
            # Ações administrativas
            cursor.execute("""
                SELECT COUNT(*) FROM system_activity 
                WHERE action_type = 'ADMIN' AND timestamp > ?
            """, (yesterday.strftime('%Y-%m-%d %H:%M:%S'),))
            security_stats['admin_actions'] = cursor.fetchone()[0]
            
            # Usuários únicos ativos
            cursor.execute("""
                SELECT COUNT(DISTINCT user_id) FROM system_activity 
                WHERE timestamp > ?
            """, (yesterday.strftime('%Y-%m-%d %H:%M:%S'),))
            security_stats['active_users'] = cursor.fetchone()[0]
            
            # Ações por tipo nas últimas 24h
            cursor.execute("""
                SELECT action_type, COUNT(*) FROM system_activity 
                WHERE timestamp > ?
                GROUP BY action_type
                ORDER BY COUNT(*) DESC
            """, (yesterday.strftime('%Y-%m-%d %H:%M:%S'),))
            
            security_stats['actions_by_type'] = dict(cursor.fetchall())
            
            # IPs únicos nas últimas 24h
            cursor.execute("""
                SELECT COUNT(DISTINCT ip_address) FROM system_activity 
                WHERE timestamp > ? AND ip_address IS NOT NULL
            """, (yesterday.strftime('%Y-%m-%d %H:%M:%S'),))
            security_stats['unique_ips'] = cursor.fetchone()[0]
            
            conn.close()
        
        # Informações de usuários
        user_stats = {}
        try:
            result = db.session.execute(text("SELECT COUNT(*) FROM user")).fetchone()
            user_stats['total_users'] = result[0] if result else 0
            
            result = db.session.execute(text("SELECT COUNT(*) FROM user WHERE role = 'admin'")).fetchone()
            user_stats['admin_users'] = result[0] if result else 0
            
            # Usuários ativos (simplified - treating all users as active for performance)
            # The 'active' column doesn't exist in current schema, so all users are considered active
            user_stats['active_users'] = user_stats['total_users']
                
        except Exception as e:
            user_stats = {'error': str(e)}
        
        return render_template("admin/audit.html",
                             app_name=APP_NAME,
                             user=current_user(),
                             security_stats=security_stats,
                             user_stats=user_stats)
    
    except Exception as e:
        flash(f"Erro ao carregar auditoria: {str(e)}", "danger")
        return redirect(url_for("admin_dashboard"))

# -------------------- LICENSE MANAGEMENT --------------------
@app.route("/license")
@app.route("/license/activation")
def license_activation():
    """Página de ativação de licença - REATIVADA"""
    if not license_manager:
        flash("Sistema de licenciamento não disponível", "error")
        return redirect(url_for("login"))
    
    license_status = get_license_status()
    machine_id = license_manager.machine_id if license_manager else "N/A"
    
    return render_template("license/activation.html",
                         app_name=APP_NAME,
                         license_status=license_status,
                         machine_id=machine_id)

@app.route("/license/activate", methods=["POST"])
def license_activate():
    """Processar ativação de licença"""
    if not license_manager:
        flash("Sistema de licenciamento não disponível", "error")
        return redirect(url_for("license_activation"))
    
    license_key = request.form.get("license_key", "").strip().upper()
    customer_name = request.form.get("customer_name", "").strip()
    customer_email = request.form.get("customer_email", "").strip()
    
    if not all([license_key, customer_name, customer_email]):
        flash("Todos os campos são obrigatórios", "error")
        return redirect(url_for("license_activation"))
    
    # Tentar ativar licença
    success, message = license_manager.activate_license(license_key, customer_name, customer_email)
    
    if success:
        if activity_logger:
            log_admin_action(0, "Sistema", f"Licença ativada para {customer_name}")
        flash(message, "success")
        return redirect(url_for("license_activation"))
    else:
        flash(message, "error")
        return redirect(url_for("license_activation"))

@app.route("/license/renew", methods=["POST"])
def license_renew():
    """Renovar licença existente"""
    if not license_manager:
        flash("Sistema de licenciamento não disponível", "error")
        return redirect(url_for("license_activation"))
    
    license_key = request.form.get("license_key", "").strip()
    
    if not license_key:
        flash("Chave de licença é obrigatória", "error")
        return redirect(url_for("license_activation"))
    
    # Tentar renovar licença
    success, message = license_manager.renew_license(license_key)
    
    if success:
        if activity_logger:
            log_admin_action(0, "Sistema", "Licença renovada")
        flash(message, "success")
    else:
        flash(message, "error")
    
    return redirect(url_for("license_activation"))

@app.route("/license/status")
def license_status():
    """API para verificar status da licença"""
    if not license_manager:
        return json.dumps({"licensed": False, "error": "Sistema não disponível"})
    
    status = get_license_status()
    return json.dumps(status)

@app.route("/admin/license")
@login_required
@roles_required("admin")
def admin_license():
    """Painel administrativo de licenças"""
    if not license_manager:
        flash("Sistema de licenciamento não disponível", "error")
        return redirect(url_for("admin_dashboard"))
    
    license_info = license_manager.get_license_info()
    
    # Verificar recursos disponíveis
    features_status = {}
    if license_info['licensed'] and 'features' in license_info:
        features = license_info['features']
        features_status = {
            'max_users': features.get('max_users', 10),
            'max_tickets': features.get('max_tickets', 100),
            'premium_reports': features.get('premium_reports', False),
            'api_access': features.get('api_access', False),
            'white_label': features.get('white_label', False)
        }
    
    # Obter licenças disponíveis e vendidas
    available_licenses = license_generator.get_available_licenses()
    sold_licenses = license_generator.get_sold_licenses()
    
    return render_template("admin/license_management.html",
                         app_name=APP_NAME,
                         user=current_user(),
                         license_info=license_info,
                         features_status=features_status,
                         available_licenses=available_licenses,
                         sold_licenses=sold_licenses)

@app.route("/admin/license/generate", methods=["POST"])
@login_required
@roles_required("admin")
def admin_license_generate():
    """Gerar nova chave de licença"""
    if not license_generator:
        flash("Sistema de geração não disponível", "error")
        return redirect(url_for("admin_license"))
    
    license_type = request.form.get("license_type", "standard")
    customer_name = request.form.get("customer_name", "").strip()
    customer_email = request.form.get("customer_email", "").strip()
    notes = request.form.get("notes", "").strip()
    
    # Definir preço baseado no tipo
    prices = {
        'basic': 100.0,
        'standard': 200.0,
        'premium': 500.0,
        'enterprise': 1000.0
    }
    
    price = prices.get(license_type, 200.0)
    
    result = license_generator.create_license(
        license_type=license_type,
        customer_name=customer_name if customer_name else None,
        customer_email=customer_email if customer_email else None,
        price=price,
        notes=notes if notes else None
    )
    
    if result['success']:
        if activity_logger:
            log_admin_action(
                session.get("user_id", 0),
                session.get("username", "Sistema"),
                f"Chave gerada: {result['license_key']} - Tipo: {license_type}"
            )
        flash(f"Chave de licença gerada: {result['license_key']}", "success")
    else:
        flash(result['message'], "error")
    
    return redirect(url_for("admin_license"))

@app.route("/admin/license/bulk", methods=["POST"])
@login_required
@roles_required("admin")
def admin_license_bulk():
    """Gerar licenças em lote"""
    if not license_generator:
        flash("Sistema de geração não disponível", "error")
        return redirect(url_for("admin_license"))
    
    try:
        count = int(request.form.get("count", 10))
        license_type = request.form.get("license_type", "standard")
        
        if count > 100:
            flash("Máximo 100 licenças por vez", "error")
            return redirect(url_for("admin_license"))
        
        created_keys = license_generator.bulk_create_licenses(count, license_type)
        
        if activity_logger:
            log_admin_action(
                session.get("user_id", 0),
                session.get("username", "Sistema"),
                f"Geradas {len(created_keys)} chaves em lote - Tipo: {license_type}"
            )
        
        flash(f"{len(created_keys)} chaves de licença geradas com sucesso!", "success")
        
    except ValueError:
        flash("Quantidade inválida", "error")
    except Exception as e:
        flash(f"Erro ao gerar licenças: {str(e)}", "error")
    
    return redirect(url_for("admin_license"))

@app.route("/admin/sistema", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def admin_sistema():
    if request.method == "POST":
        # Handle configuration updates
        action = request.form.get("action")
        
        if action == "optimize_db":
            # Optimize database
            try:
                db.session.execute(text("VACUUM;"))
                db.session.commit()
                flash("Banco de dados otimizado com sucesso!", "success")
            except Exception as e:
                flash(f"Erro ao otimizar banco: {str(e)}", "danger")
        
        elif action == "clear_logs":
            # Clear old reports from static folder
            try:
                import glob
                report_files = glob.glob(os.path.join(app.config["REPORT_DIR"], "*.png"))
                report_files.extend(glob.glob(os.path.join(app.config["REPORT_DIR"], "*.pdf")))
                removed_count = 0
                for file in report_files:
                    try:
                        os.remove(file)
                        removed_count += 1
                    except:
                        pass
                flash(f"Removidos {removed_count} arquivos de relatórios antigos!", "success")
            except Exception as e:
                flash(f"Erro ao limpar arquivos: {str(e)}", "danger")
        
        return redirect(url_for("admin_sistema"))
    
    # Get system statistics
    stats = {}
    try:
        # Database stats
        result = db.session.execute(text("SELECT COUNT(*) FROM chamado")).fetchone()
        stats['total_chamados'] = result[0] if result else 0
        
        result = db.session.execute(text("SELECT COUNT(*) FROM user")).fetchone()
        stats['total_usuarios'] = result[0] if result else 0
        
        result = db.session.execute(text("SELECT COUNT(*) FROM chamado WHERE status = 'aberto'")).fetchone()
        stats['chamados_abertos'] = result[0] if result else 0
        
        # Database file size
        db_size = os.path.getsize("sistema_os.db") / (1024 * 1024)  # MB
        stats['db_size'] = f"{db_size:.2f} MB"
        
        # Report files count
        import glob
        report_files = len(glob.glob(os.path.join(app.config["REPORT_DIR"], "*")))
        stats['report_files'] = report_files
        
    except Exception as e:
        stats['error'] = str(e)
    
    return render_template("admin_sistema.html", stats=stats, app_name=APP_NAME, user=current_user())

# -------------------- RELATÓRIOS --------------------
@app.route("/relatorios", methods=["GET","POST"])
@login_required
@permission_required("view_reports")
def relatorios():
    u = current_user()
    # filtros
    data_ini = request.values.get("data_ini","")
    data_fim = request.values.get("data_fim","")
    status = request.values.get("status","")
    setor = request.values.get("setor","")
    responsavel = request.values.get("responsavel","")
    aberto_por = request.values.get("aberto_por","")
    urgencia = request.values.get("urgencia","")

    # Optimize query with eager loading to prevent N+1 problems
    q = Chamado.query.options(
        joinedload(Chamado.usuario),
        joinedload(Chamado.fechado_por)
    )
    if setor:
        # Suporte a dados legados: filtrar tanto por name interno quanto display_name
        # para garantir compatibilidade com dados antigos
        try:
            sector_obj = Sector.query.filter(
                (Sector.name == setor) | (Sector.display_name == setor)
            ).first()
            
            if sector_obj:
                # Filtrar por ambos os valores possíveis para máxima compatibilidade
                q = q.filter(
                    (Chamado.setor == sector_obj.name) | 
                    (Chamado.setor == sector_obj.display_name)
                )
            else:
                # Fallback: filtrar pelo valor exato selecionado
                q = q.filter(Chamado.setor == setor)
        except:
            # Em caso de erro, usar filtro simples
            q = q.filter(Chamado.setor == setor)
    if u.is_operator_like() and not u.is_admin():
        user_sectors = u.get_sectors()
        if user_sectors:
            # Incluir compatibilidade com dados legados: tanto name quanto display_name
            allowed_sector_values = []
            for sector in user_sectors:
                allowed_sector_values.append(sector.name)
                allowed_sector_values.append(sector.display_name)
            # Remover duplicados
            allowed_sector_values = list(set(allowed_sector_values))
            q = q.filter(Chamado.setor.in_(allowed_sector_values))
        else:
            # Operator with no sectors sees no tickets
            q = q.filter(False)
    if data_ini:
        try:
            di = datetime.strptime(data_ini, "%Y-%m-%d")
            q = q.filter(Chamado.criado_em >= di)
        except:
            pass
    if data_fim:
        try:
            df = datetime.strptime(data_fim, "%Y-%m-%d")
            df = df.replace(hour=23, minute=59, second=59)
            q = q.filter(Chamado.criado_em <= df)
        except:
            pass
    if status:
        q = q.filter(Chamado.status == status)
    if responsavel and responsavel.isdigit():
        q = q.filter(Chamado.fechado_por_id == int(responsavel))
    if aberto_por and aberto_por.isdigit():
        q = q.filter(Chamado.usuario_id == int(aberto_por))
    if urgencia:
        q = q.filter(Chamado.urgencia == urgencia)

    chamados = q.order_by(Chamado.criado_em.asc()).all()

    # dataframe
    rows = []
    for c in chamados:
        duracao_h = None
        if c.fechado_em:
            duracao_h = (c.fechado_em - c.criado_em).total_seconds()/3600.0
        rows.append({
            "ID": c.id,
            "Título": c.titulo,
            "Status": c.status,
            "Criado em": c.criado_em,
            "Fechado em": c.fechado_em,
            "Duração(h)": duracao_h,
            "Aberto por": c.usuario.username if c.usuario else "",
            "Fechado por": c.fechado_por.username if c.fechado_por else "",
            "Setor": (c.setor or '—'),
            "Setor do Solicitante": (c.usuario_setor or '—')
        })
    df = pd.DataFrame(rows)

    # gerar gráficos (salvos como PNG na pasta static/relatorios)
    chart_files = []
    if not df.empty:
        # OS por mês
        df["Mes"] = pd.to_datetime(df["Criado em"]).dt.to_period("M").astype(str)
        qty_by_month = df.groupby("Mes")["ID"].count().sort_index()

        fig1 = plt.figure()
        qty_by_month.plot(kind="bar")
        plt.title("Quantidade de OS por mês")
        plt.xlabel("Mês")
        plt.ylabel("Qtd de OS")
        file1 = os.path.join(app.config["REPORT_DIR"], f"{uuid4_hex()}_qtd_mes.png")
        fig1.savefig(file1, bbox_inches="tight")
        plt.close(fig1)
        chart_files.append(file1)

        # Médias por mês (fechadas)
        df_closed = df.dropna(subset=["Fechado em"]).copy()
        if not df_closed.empty:
            df_closed["MesFech"] = pd.to_datetime(df_closed["Fechado em"]).dt.to_period("M").astype(str)
            mean_by_month = df_closed.groupby("MesFech")["Duração(h)"].mean().sort_index()
            fig2 = plt.figure()
            mean_by_month.plot(kind="line", marker="o")
            plt.title("Tempo médio de atendimento (h) por mês")
            plt.xlabel("Mês")
            plt.ylabel("Média (h)")
            file2 = os.path.join(app.config["REPORT_DIR"], f"{uuid4_hex()}_media_mes.png")
            fig2.savefig(file2, bbox_inches="tight")
            plt.close(fig2)
            chart_files.append(file2)

        # Distribuição por status
        by_status = df["Status"].value_counts()
        fig3 = plt.figure()
        by_status.plot(kind="pie", autopct="%1.1f%%")
        plt.title("Distribuição por status")
        plt.ylabel("")
        file3 = os.path.join(app.config["REPORT_DIR"], f"{uuid4_hex()}_status.png")
        fig3.savefig(file3, bbox_inches="tight")
        plt.close(fig3)
        chart_files.append(file3)

        # OS por operador (fechou) - contagem
        if not df_closed.empty:
            by_op_count = df_closed["Fechado por"].value_counts()
            fig5 = plt.figure()
            by_op_count.plot(kind="bar")
            plt.title("OS fechadas por operador")
            plt.xlabel("Operador")
            plt.ylabel("Qtd")
            file5 = os.path.join(app.config["REPORT_DIR"], f"{uuid4_hex()}_qtd_operador.png")
            fig5.savefig(file5, bbox_inches="tight")
            plt.close(fig5)
            chart_files.append(file5)

            # Tempo total por operador
            by_op_hours = df_closed.groupby("Fechado por")["Duração(h)"].sum().sort_values(ascending=False)
            fig4 = plt.figure()
            by_op_hours.plot(kind="bar")
            plt.title("Tempo total por operador (h)")
            plt.xlabel("Operador")
            plt.ylabel("Horas")
            file4 = os.path.join(app.config["REPORT_DIR"], f"{uuid4_hex()}_tempo_operador.png")
            fig4.savefig(file4, bbox_inches="tight")
            plt.close(fig4)
            chart_files.append(file4)

            # Top 5 OS mais demoradas
            top5 = df_closed.sort_values("Duração(h)", ascending=False).head(5).set_index("ID")["Duração(h)"]
            if not top5.empty:
                fig6 = plt.figure()
                top5.plot(kind="bar")
                plt.title("Top 5 OS mais demoradas (h)")
                plt.xlabel("OS")
                plt.ylabel("Horas")
                file6 = os.path.join(app.config["REPORT_DIR"], f"{uuid4_hex()}_top5.png")
                fig6.savefig(file6, bbox_inches="tight")
                plt.close(fig6)
                chart_files.append(file6)

    # listar operadores e usuários para filtros
    operadores = User.query.filter(User.role.in_(["operador","admin"])).order_by(User.username).all()
    usuarios = User.query.filter(User.role.in_(["usuario","operador","admin"])).order_by(User.username).all()
    
    # Buscar setores dinamicamente da tabela Sector
    try:
        setores_db = Sector.query.filter_by(active=True).order_by(Sector.display_name).all()
        setores = [{'name': sector.name, 'display_name': sector.display_name} for sector in setores_db]
    except:
        # Fallback para setores padrão se a tabela não existir
        setores = [
            {'name': 'T.I', 'display_name': 'T.I'},
            {'name': 'Manutenção', 'display_name': 'Manutenção'},
            {'name': 'CCIH / SESMT / Manutenção de Ar condicionado', 'display_name': 'CCIH / SESMT / Manutenção de Ar condicionado'},
            {'name': 'Telefonia e outros serviços', 'display_name': 'Telefonia e outros serviços'}
        ]

    # KPIs
    total_abertas = int((df["Status"] == "Aberto").sum()) if not df.empty else 0
    total_fechadas = int((df["Status"] == "Fechado").sum()) if not df.empty else 0
    media_h = round(float(df["Duração(h)"].dropna().mean()), 2) if not df.empty and df["Duração(h)"].notna().any() else 0.0
    mediana_h = round(float(df["Duração(h)"].dropna().median()), 2) if not df.empty and df["Duração(h)"].notna().any() else 0.0
    taxa_fechamento = round((total_fechadas / (len(df) if not df.empty else 1)) * 100, 1) if not df.empty else 0.0
    total_horas = round(float(df["Duração(h)"].dropna().sum()), 2) if not df.empty else 0.0

    return render_template(
        "relatorios.html",
        app_name=APP_NAME,
        user=u,
        chamados=chamados,
        data_ini=data_ini, data_fim=data_fim, status=status, responsavel=responsavel, aberto_por=aberto_por,
        setor=setor, urgencia=urgencia,
        operadores=operadores, usuarios=usuarios, setores=setores,
        chart_files=[f.replace("\\","/") for f in chart_files],
        total_abertas=total_abertas, total_fechadas=total_fechadas, media_h=media_h,
        mediana_h=mediana_h, taxa_fechamento=taxa_fechamento, total_horas=total_horas
    )

# Exportações com filtros atuais
def _filtered_dataframe(params):
    data_ini = params.get("data_ini","")
    data_fim = params.get("data_fim","")
    status = params.get("status","")
    responsavel = params.get("responsavel","")
    aberto_por = params.get("aberto_por","")
    setor = params.get("setor","")
    urgencia = params.get("urgencia","")
    
    # Get current user and apply sector restrictions
    u = current_user()
    q = Chamado.query
    
    # Apply operator sector restrictions FIRST
    if u.is_operator_like() and not u.is_admin() and not u.has_permission('view_all'):
        user_sector_names = u.get_sector_names()
        if user_sector_names:
            q = q.filter(Chamado.setor.in_(user_sector_names))
        else:
            # Operator with no sectors sees no tickets
            q = q.filter(False)
    
    # Then apply additional filters
    if setor:
        q = q.filter(Chamado.setor == setor)
    if data_ini:
        try:
            di = datetime.strptime(data_ini, "%Y-%m-%d")
            q = q.filter(Chamado.criado_em >= di)
        except:
            pass
    if data_fim:
        try:
            df_ = datetime.strptime(data_fim, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            q = q.filter(Chamado.criado_em <= df_)
        except:
            pass
    if status:
        q = q.filter(Chamado.status == status)
    if responsavel and str(responsavel).isdigit():
        q = q.filter(Chamado.fechado_por_id == int(responsavel))
    if aberto_por and str(aberto_por).isdigit():
        q = q.filter(Chamado.usuario_id == int(aberto_por))
    if urgencia:
        q = q.filter(Chamado.urgencia == urgencia)

    chamados = q.order_by(Chamado.criado_em.asc()).all()
    rows = []
    for c in chamados:
        duracao_h = None
        if c.fechado_em:
            duracao_h = round((c.fechado_em - c.criado_em).total_seconds()/3600.0, 2)
        rows.append([
            c.id,
            c.criado_em,
            c.usuario.username if c.usuario else "",
            c.setor or '—',
            getattr(c, 'ramal', '') or "",
            c.descricao,
            c.status,
            c.fechado_em if c.fechado_em else "",
            c.fechado_por.username if c.fechado_por else "",
            duracao_h,
            getattr(c, 'cdc', '') or ""
        ])
    df = pd.DataFrame(rows, columns=["ID","Abertura","Aberto por","Setor","Ramal","Descrição","Status","Fechamento","Fechado por","Duração(h)","CDC"])
    
    # Handle NaT values for Excel export compatibility
    df['Abertura'] = pd.to_datetime(df['Abertura'])
    df['Fechamento'] = pd.to_datetime(df['Fechamento'], errors='coerce')
    
    return df

@app.route("/export_xlsx")
@login_required
@permission_required("view_reports")
def export_xlsx():
    df = _filtered_dataframe(request.args)
    output = io.BytesIO()
    
    # Create Excel with professional formatting
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Relatório de OS", startrow=4)
        
        workbook = writer.book
        worksheet = writer.sheets['Relatório de OS']
        
        # Header format
        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'fg_color': '#2E86AB',
            'font_color': 'white',
            'border': 1
        })
        
        # Description text wrap formats (for alternating rows)
        wrap_format = workbook.add_format({
            'text_wrap': True,
            'valign': 'top',
            'border': 1
        })
        
        wrap_alt_format = workbook.add_format({
            'text_wrap': True,
            'valign': 'top',
            'border': 1,
            'bg_color': '#F8F9FA'
        })
        
        # Title format
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 16,
            'align': 'center',
            'valign': 'vcenter'
        })
        
        # Date format
        date_format = workbook.add_format({
            'num_format': 'dd/mm/yyyy hh:mm',
            'border': 1
        })
        
        # Date format with alternating background
        date_alt_format = workbook.add_format({
            'num_format': 'dd/mm/yyyy hh:mm',
            'bg_color': '#F8F9FA',
            'border': 1
        })
        
        # Alternating row format
        alt_row_format = workbook.add_format({
            'bg_color': '#F8F9FA',
            'border': 1
        })
        
        # Add title (cover all columns - now 11 columns A to K)
        worksheet.merge_range('A1:K2', 'Sistemas Olivium - Relatório de OS', title_format)
        worksheet.write('A3', f'Gerado em: {now_brazil().strftime("%d/%m/%Y %H:%M")}')
        
        # Format headers
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(4, col_num, value, header_format)
        
        # Format data rows with proper date handling
        for row_num in range(len(df)):
            for col_num, col_name in enumerate(df.columns):
                value = df.iloc[row_num, col_num]
                
                # Handle date columns specifically
                if col_name in ['Abertura', 'Fechamento'] and pd.notna(value):
                    format_to_use = date_format if row_num % 2 == 0 else date_alt_format
                    worksheet.write_datetime(row_num + 5, col_num, value, format_to_use)
                elif value is None or pd.isna(value):
                    # Write empty string for None/NaN values
                    format_to_use = alt_row_format if row_num % 2 == 1 else None
                    worksheet.write(row_num + 5, col_num, "", format_to_use)
                else:
                    # Regular data with special handling for description column
                    if col_name == 'Descrição':
                        # Apply text wrap to description column with alternating backgrounds
                        format_to_use = wrap_format if row_num % 2 == 0 else wrap_alt_format  
                        worksheet.write(row_num + 5, col_num, value, format_to_use)
                    else:
                        format_to_use = alt_row_format if row_num % 2 == 1 else None
                        worksheet.write(row_num + 5, col_num, value, format_to_use)
        
        # Set proper column widths matching the new column order
        worksheet.set_column('A:A', 8)   # ID column - narrow
        worksheet.set_column('B:B', 20)  # Abertura - wider for date/time
        worksheet.set_column('C:C', 15)  # Aberto por column
        worksheet.set_column('D:D', 20)  # Setor column
        worksheet.set_column('E:E', 10)  # Ramal column - narrow
        worksheet.set_column('F:F', 50)  # Descrição column - wider for long descriptions
        worksheet.set_column('G:G', 15)  # Status column
        worksheet.set_column('H:H', 20)  # Fechamento - wider for date/time
        worksheet.set_column('I:I', 15)  # Fechado por column
        worksheet.set_column('J:J', 12)  # Duração(h) column
        worksheet.set_column('K:K', 10)  # CDC column
    
    output.seek(0)
    return send_file(output, as_attachment=True, download_name=f"relatorio_os_{now_brazil().strftime('%Y%m%d_%H%M')}.xlsx", 
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route("/relatorios/export/csv")
@login_required
@permission_required("view_reports")
def export_csv():
    df = _filtered_dataframe(request.args)
    output = io.StringIO()
    df.to_csv(output, index=False)
    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode("utf-8-sig")), as_attachment=True, 
                     download_name="relatorio_os.csv", mimetype="text/csv")

@app.route("/export_pdf")
@login_required
@permission_required("view_reports")
def export_pdf():
    df = _filtered_dataframe(request.args)
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=A4)
    width, height = A4
    
    # Title and header
    y = height - 80
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(width/2, y, "Sistemas Olivium")
    y -= 25
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width/2, y, "Relatório de Ordens de Serviço")
    y -= 20
    c.setFont("Helvetica", 10)
    c.drawCentredString(width/2, y, f"Gerado em: {now_brazil().strftime('%d/%m/%Y %H:%M')}")
    y -= 30
    
    # Draw header line
    c.setStrokeColorRGB(0.2, 0.5, 0.7)
    c.setLineWidth(2)
    c.line(50, y, width-50, y)
    y -= 20
    
    # Table headers
    c.setFont("Helvetica-Bold", 8)
    headers = ["ID", "Descrição", "Status", "Setor", "Set.Solic", "Abertura", "Fechamento", "Dur.(h)", "Aberto por", "Ramal"]
    x_positions = [50, 80, 140, 180, 210, 240, 280, 310, 350, 390]
    
    for i, header in enumerate(headers):
        c.drawString(x_positions[i], y, header)
    y -= 5
    c.line(50, y, width-50, y)
    y -= 15
    
    # Table data
    c.setFont("Helvetica", 7)
    row_color = True
    
    for _, row in df.iterrows():
        if y < 100:
            c.showPage()
            y = height - 50
            # Redraw headers on new page
            c.setFont("Helvetica-Bold", 8)
            for i, header in enumerate(headers):
                c.drawString(x_positions[i], y, header)
            y -= 5
            c.line(50, y, width-50, y)
            y -= 15
            c.setFont("Helvetica", 7)
        
        # Alternate row background
        if row_color:
            c.setFillColorRGB(0.97, 0.97, 0.97)
            c.rect(50, y-10, width-100, 12, fill=1, stroke=0)
        
        c.setFillColorRGB(0, 0, 0)  # Reset to black for text
        
        # Handle optional columns safely
        setor_solicitante = ""
        if "Setor do Solicitante" in df.columns and pd.notna(row["Setor do Solicitante"]) and row["Setor do Solicitante"] != '—':
            setor_solicitante = str(row["Setor do Solicitante"])[:8]
        
        data = [
            str(row["ID"]),
            str(row["Descrição"])[:15],
            str(row["Status"]),
            str(row["Setor"])[:6] if row["Setor"] != '—' else "",
            setor_solicitante,
            row["Abertura"].strftime("%d/%m") if pd.notna(row["Abertura"]) else "",
            row["Fechamento"].strftime("%d/%m") if pd.notna(row["Fechamento"]) else "",
            f'{row["Duração(h)"]:.1f}' if pd.notna(row["Duração(h)"]) else "",
            str(row["Aberto por"])[:8] if row["Aberto por"] else "",
            str(row["Ramal"]) if row["Ramal"] else ""
        ]
        
        for i, value in enumerate(data):
            c.drawString(x_positions[i], y, value)
        
        y -= 12
        row_color = not row_color
    
    # Footer
    c.setFont("Helvetica", 8)
    c.drawCentredString(width/2, 30, f"Total de registros: {len(df)}")
    
    c.save()
    packet.seek(0)
    return send_file(packet, as_attachment=True, download_name=f"relatorio_os_{now_brazil().strftime('%Y%m%d_%H%M')}.pdf", 
                     mimetype="application/pdf")

# util
def uuid4_hex():
    return uuid.uuid4().hex

# -------------------- WEBSOCKET HELPERS --------------------
def emit_ticket_update(ticket_data, event_type):
    """Emits ticket updates to clients with proper sector filtering"""
    # For now, emit to all clients - client-side filtering should handle sector restrictions
    # In a production environment, you'd want to track user sessions and filter server-side
    socketio.emit('ticket_update', {
        'event_type': event_type,
        'ticket': ticket_data
    }, namespace='/')
    
    # TODO: Implement server-side session tracking for sector-based filtering
    # This would require storing user sector info in socket sessions

def ticket_to_dict(chamado):
    """Convert a ticket object to dictionary for JSON emission"""
    return {
        'id': chamado.id,
        'titulo': chamado.titulo,
        'descricao': chamado.descricao,
        'status': chamado.status,
        'criado_em': chamado.criado_em.strftime('%Y-%m-%d %H:%M:%S') if chamado.criado_em else None,
        'fechado_em': chamado.fechado_em.strftime('%Y-%m-%d %H:%M:%S') if chamado.fechado_em else None,
        'setor': chamado.setor,
        'usuario_setor': chamado.usuario_setor,
        'usuario': chamado.usuario.username if chamado.usuario else None,
        'fechado_por': chamado.fechado_por.username if chamado.fechado_por else None
    }

# -------------------- ADMIN MENU SYSTEM --------------------

@app.route("/admin")
@login_required
@roles_required("admin")
def admin_dashboard():
    """Admin dashboard with system overview"""
    # Get system statistics
    total_users = User.query.filter_by(active=True).count() if hasattr(User, 'active') else User.query.count()
    total_tickets = Chamado.query.count()
    open_tickets = Chamado.query.filter_by(status='Aberto').count()
    closed_tickets = Chamado.query.filter_by(status='Fechado').count()
    urgent_tickets = Chamado.query.filter_by(urgencia='Urgente').count() if hasattr(Chamado, 'urgencia') else 0
    
    # Recent activity (last 7 days)
    seven_days_ago = now_brazil() - pd.Timedelta(days=7)
    recent_tickets = Chamado.query.filter(Chamado.criado_em >= seven_days_ago).count()
    
    stats = {
        'total_users': total_users,
        'total_tickets': total_tickets,
        'open_tickets': open_tickets,
        'closed_tickets': closed_tickets,
        'urgent_tickets': urgent_tickets,
        'recent_tickets': recent_tickets
    }
    
    return render_template("admin/dashboard.html", app_name=APP_NAME, user=current_user(), stats=stats)

# -------------------- ADMIN SECTOR MANAGEMENT --------------------

@app.route("/admin/sectors")
@login_required
@roles_required("admin")
def admin_sectors():
    """Manage sectors"""
    sectors = Sector.query.filter_by(active=True).order_by(Sector.display_name).all()
    return render_template("admin/sectors.html", app_name=APP_NAME, user=current_user(), sectors=sectors)

@app.route("/admin/sectors/new", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def admin_sectors_new():
    """Create new sector"""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        display_name = request.form.get("display_name", "").strip()
        description = request.form.get("description", "").strip()
        
        if not name or not display_name:
            flash("Nome interno e nome de exibição são obrigatórios.", "danger")
            return render_template("admin/sector_form.html", app_name=APP_NAME, user=current_user())
        
        # Check if there's an existing sector with the same name (active or inactive)
        existing_sector = Sector.query.filter_by(name=name).first()
        
        if existing_sector:
            if existing_sector.active:
                flash("Já existe um setor ativo com este nome interno.", "danger")
                return render_template("admin/sector_form.html", app_name=APP_NAME, user=current_user())
            else:
                # Reactivate the inactive sector
                existing_sector.active = True
                existing_sector.display_name = display_name
                existing_sector.description = description
                db.session.commit()
                flash("Setor reativado com sucesso.", "success")
        else:
            # Create new sector
            sector = Sector(name=name, display_name=display_name, description=description)
            db.session.add(sector)
            db.session.commit()
            flash("Setor criado com sucesso.", "success")
        return redirect(url_for("admin_sectors"))
    
    return render_template("admin/sector_form.html", app_name=APP_NAME, user=current_user(), sector=None)

@app.route("/admin/sectors/edit/<int:sector_id>", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def admin_sectors_edit(sector_id):
    """Edit sector"""
    sector = Sector.query.get_or_404(sector_id)
    
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        display_name = request.form.get("display_name", "").strip()
        description = request.form.get("description", "").strip()
        
        if not name or not display_name:
            flash("Nome interno e nome de exibição são obrigatórios.", "danger")
            return render_template("admin/sector_form.html", app_name=APP_NAME, user=current_user(), sector=sector)
        
        # Check for duplicate names (excluding current sector, only among active sectors)
        existing = Sector.query.filter(Sector.name == name, Sector.id != sector_id, Sector.active == True).first()
        if existing:
            flash("Já existe outro setor com este nome interno.", "danger")
            return render_template("admin/sector_form.html", app_name=APP_NAME, user=current_user(), sector=sector)
        
        sector.name = name
        sector.display_name = display_name
        sector.description = description
        db.session.commit()
        flash("Setor atualizado com sucesso.", "success")
        return redirect(url_for("admin_sectors"))
    
    return render_template("admin/sector_form.html", app_name=APP_NAME, user=current_user(), sector=sector)

@app.route("/admin/sectors/delete/<int:sector_id>", methods=["POST"])
@login_required
@roles_required("admin")
def admin_sectors_delete(sector_id):
    """Delete sector"""
    sector = Sector.query.get_or_404(sector_id)
    
    # Check if sector is being used
    tickets_count = Chamado.query.filter_by(setor=sector.name).count()
    users_count = User.query.filter_by(setor=sector.name).count()
    
    if tickets_count > 0 or users_count > 0:
        flash(f"Não é possível excluir o setor. Ele está sendo usado por {tickets_count} chamados e {users_count} usuários.", "danger")
        return redirect(url_for("admin_sectors"))
    
    sector.active = False  # Soft delete
    db.session.commit()
    flash("Setor removido com sucesso.", "success")
    return redirect(url_for("admin_sectors"))

# -------------------- ADMIN USER MANAGEMENT --------------------

@app.route("/admin/users")
@login_required
@roles_required("admin")
def admin_users():
    """Advanced user management"""
    users = User.query.order_by(User.username).all()
    roles = Role.query.filter_by(active=True).order_by(Role.display_name).all()  # Custom roles system enabled
    sectors = Sector.query.filter_by(active=True).order_by(Sector.display_name).all()
    return render_template("admin/users.html", app_name=APP_NAME, user=current_user(), users=users, roles=roles, sectors=sectors)

@app.route("/admin/users/new", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def admin_users_new():
    """Create new user with advanced settings"""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "")
        # role_id = request.form.get("role_id", type=int)  # Removed for PostgreSQL compatibility
        sector_ids = request.form.getlist("sector_ids")
        
        if not username or not password:
            flash("Usuário e senha são obrigatórios.", "danger")
            return redirect(url_for("admin_users_new"))
        
        if User.query.filter_by(username=username).first():
            flash("Usuário já existe.", "danger")
            return redirect(url_for("admin_users_new"))
        
        user = User(username=username, role=role)
        user.set_password(password)
        
        # Set new role system if available
        # Legacy role_id system removed for PostgreSQL compatibility
        if hasattr(user, 'active'):
            user.active = True
        if hasattr(user, 'created_at'):
            user.created_at = now_brazil()
        
        db.session.add(user)
        db.session.commit()
        
        # Assign sectors using the new method
        if sector_ids:
            sector_ids = [int(id) for id in sector_ids if id.isdigit()]
            user.assign_sectors(sector_ids)
            db.session.commit()
        
        # Validate operator sector assignment
        if role == 'operador' and not user.get_sectors():
            flash("Operadores devem ter pelo menos um setor atribuído.", "warning")
            # roles = Role.query.filter_by(active=True).order_by(Role.display_name).all()  # Removed for PostgreSQL compatibility
            roles = []  # Using simple string role system
            sectors = Sector.query.filter_by(active=True).order_by(Sector.display_name).all()
            return render_template("admin/user_form.html", app_name=APP_NAME, user=current_user(), u=user, roles=roles, sectors=sectors)
        
        flash("Usuário criado com sucesso.", "success")
        return redirect(url_for("admin_users"))
    
    roles = Role.query.filter_by(active=True).order_by(Role.display_name).all()  # Custom roles system enabled
    sectors = Sector.query.filter_by(active=True).order_by(Sector.display_name).all()
    return render_template("admin/user_form.html", app_name=APP_NAME, user=current_user(), u=None, roles=roles, sectors=sectors)

@app.route("/admin/users/edit/<int:uid>", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def admin_users_editar(uid):
    """Edit user with advanced settings"""
    u = db.session.get(User, uid) or abort(404)
    
    if request.method == "POST":
        u.username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "")
        # role_id = request.form.get("role_id", type=int)  # Removed for PostgreSQL compatibility
        sector_ids = request.form.getlist("sector_ids")
        
        if not u.username:
            flash("Usuário é obrigatório.", "danger")
            return redirect(url_for("admin_users_editar", uid=uid))
        
        # Check for username conflicts (excluding current user)
        existing = User.query.filter(User.username == u.username, User.id != uid).first()
        if existing:
            flash("Já existe outro usuário com este nome.", "danger")
            return redirect(url_for("admin_users_editar", uid=uid))
        
        u.role = role
        
        # Set new role system if available
        if hasattr(u, 'role_id') and role_id:
            u.role_id = role_id
        
        # Assign sectors using the new method
        if sector_ids:
            sector_ids = [int(id) for id in sector_ids if id.isdigit()]
            u.assign_sectors(sector_ids)
        else:
            u.assign_sectors([])  # Clear all sectors
        
        # Validate operator sector assignment
        if role == 'operador' and not u.get_sectors():
            flash("Operadores devem ter pelo menos um setor atribuído.", "warning")
            # roles = Role.query.filter_by(active=True).order_by(Role.display_name).all()  # Removed for PostgreSQL compatibility
            roles = []  # Using simple string role system
            sectors = Sector.query.filter_by(active=True).order_by(Sector.display_name).all()
            return render_template("admin/user_form.html", app_name=APP_NAME, user=current_user(), u=u, roles=roles, sectors=sectors)
        
        if password:
            u.set_password(password)
        
        # Force session refresh for currently logged in user
        if u.id == session.get('user_id'):
            session['user_sectors'] = u.get_sector_names()
            session['user_role'] = u.role
        
        db.session.commit()
        flash("Usuário atualizado com sucesso.", "success")
        return redirect(url_for("admin_users"))
    
    roles = Role.query.filter_by(active=True).order_by(Role.display_name).all()  # Custom roles system enabled
    sectors = Sector.query.filter_by(active=True).order_by(Sector.display_name).all()
    return render_template("admin/user_form.html", app_name=APP_NAME, user=current_user(), u=u, roles=roles, sectors=sectors)

# -------------------- ADMIN ROLES & PERMISSIONS --------------------

@app.route("/admin/roles")
@login_required
@roles_required("admin")
def admin_roles():
    """Manage roles and permissions"""
    
    roles = Role.query.filter_by(active=True).order_by(Role.display_name).all()
    
    # Calculate user count for each role
    roles_with_counts = []
    for role in roles:
        user_count = User.query.filter_by(role=role.name).count()
        roles_with_counts.append({
            'role': role,
            'user_count': user_count
        })
    
    return render_template("admin/roles.html", app_name=APP_NAME, user=current_user(), roles_with_counts=roles_with_counts)

@app.route("/admin/roles/new", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def admin_roles_new():
    """Create new role"""
    
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        display_name = request.form.get("display_name", "").strip()
        description = request.form.get("description", "").strip()
        permissions = request.form.getlist("permissions")
        
        if not name or not display_name:
            flash("Nome e nome de exibição são obrigatórios.", "danger")
            return render_template("admin/role_form.html", app_name=APP_NAME, user=current_user())
        
        # Check if there's an existing role with the same name (active or inactive)
        existing_role = Role.query.filter_by(name=name).first()
        
        if existing_role:
            if existing_role.active:
                flash("Já existe um papel ativo com este nome.", "danger")
                return render_template("admin/role_form.html", app_name=APP_NAME, user=current_user())
            else:
                # Reactivate the inactive role
                import json
                existing_role.active = True
                existing_role.display_name = display_name
                existing_role.description = description
                existing_role.permissions = json.dumps(permissions)
                db.session.commit()
                flash("Papel reativado com sucesso.", "success")
                return redirect(url_for("admin_roles"))
        else:
            # Create new role
            import json
            role = Role(
                name=name, 
                display_name=display_name, 
                description=description, 
                permissions=json.dumps(permissions)
            )
            db.session.add(role)
        db.session.commit()
        
        # Log activity
        if activity_logger:
            user = current_user()
            log_admin_action(
                user.id if user else 0,
                user.username if user else "Sistema",
                f"Papel '{display_name}' criado"
            )
        
        flash("Papel criado com sucesso.", "success")
        return redirect(url_for("admin_roles"))
    
    available_permissions = [
        {"id": "view_all", "name": "Ver todos os chamados"},
        {"id": "view_sector", "name": "Ver chamados do setor"},
        {"id": "view_own", "name": "Ver próprios chamados"},
        {"id": "edit_all", "name": "Editar todos os chamados"},
        {"id": "edit_sector", "name": "Editar chamados do setor"},
        {"id": "delete_all", "name": "Excluir qualquer chamado"},
        {"id": "close_tickets", "name": "Fechar chamados"},
        {"id": "create_tickets", "name": "Criar chamados"},
        {"id": "manage_users", "name": "Gerenciar usuários"},
        {"id": "manage_sectors", "name": "Gerenciar setores"},
        {"id": "manage_roles", "name": "Gerenciar papéis"},
        {"id": "view_reports", "name": "Visualizar relatórios"},
        {"id": "manage_settings", "name": "Gerenciar configurações"}
    ]
    
    return render_template("admin/role_form.html", app_name=APP_NAME, user=current_user(), role=None, available_permissions=available_permissions)

@app.route("/admin/roles/edit/<int:role_id>", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def admin_roles_edit(role_id):
    """Edit role"""
    
    role = Role.query.get_or_404(role_id)
    
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        display_name = request.form.get("display_name", "").strip()
        description = request.form.get("description", "").strip()
        permissions = request.form.getlist("permissions")
        
        if not name or not display_name:
            flash("Nome e nome de exibição são obrigatórios.", "danger")
            return redirect(url_for("admin_roles_edit", role_id=role_id))
        
        # Check for duplicate names (excluding current role)
        existing = Role.query.filter(Role.name == name, Role.id != role_id).first()
        if existing:
            flash("Já existe outro papel com este nome.", "danger")
            return redirect(url_for("admin_roles_edit", role_id=role_id))
        
        import json
        role.name = name
        role.display_name = display_name
        role.description = description
        role.permissions = json.dumps(permissions)
        role.updated_at = datetime.now()
        
        db.session.commit()
        
        # Log activity
        if activity_logger:
            user = current_user()
            log_admin_action(
                user.id if user else 0,
                user.username if user else "Sistema",
                f"Papel '{display_name}' editado"
            )
        
        flash("Papel atualizado com sucesso.", "success")
        return redirect(url_for("admin_roles"))
    
    available_permissions = [
        {"id": "view_all", "name": "Ver todos os chamados"},
        {"id": "view_sector", "name": "Ver chamados do setor"},
        {"id": "view_own", "name": "Ver próprios chamados"},
        {"id": "edit_all", "name": "Editar todos os chamados"},
        {"id": "edit_sector", "name": "Editar chamados do setor"},
        {"id": "delete_all", "name": "Excluir qualquer chamado"},
        {"id": "close_tickets", "name": "Fechar chamados"},
        {"id": "create_tickets", "name": "Criar chamados"},
        {"id": "manage_users", "name": "Gerenciar usuários"},
        {"id": "manage_sectors", "name": "Gerenciar setores"},
        {"id": "manage_roles", "name": "Gerenciar papéis"},
        {"id": "view_reports", "name": "Visualizar relatórios"},
        {"id": "manage_settings", "name": "Gerenciar configurações"}
    ]
    
    return render_template("admin/role_form.html", app_name=APP_NAME, user=current_user(), role=role, available_permissions=available_permissions)
    
    available_permissions = [
        {"id": "view_all", "name": "Ver todos os chamados"},
        {"id": "view_sector", "name": "Ver chamados do setor"},
        {"id": "view_own", "name": "Ver próprios chamados"},
        {"id": "edit_all", "name": "Editar todos os chamados"},
        {"id": "edit_sector", "name": "Editar chamados do setor"},
        {"id": "delete_all", "name": "Excluir qualquer chamado"},
        {"id": "close_tickets", "name": "Fechar chamados"},
        {"id": "create_tickets", "name": "Criar chamados"},
        {"id": "manage_users", "name": "Gerenciar usuários"},
        {"id": "manage_sectors", "name": "Gerenciar setores"},
        {"id": "manage_roles", "name": "Gerenciar papéis"},
        {"id": "view_reports", "name": "Visualizar relatórios"},
        {"id": "manage_settings", "name": "Gerenciar configurações"}
    ]
    
    return render_template("admin/role_form.html", app_name=APP_NAME, user=current_user(), role=role, available_permissions=available_permissions)

@app.route("/admin/roles/delete/<int:role_id>", methods=["POST"])
@login_required
@roles_required("admin")
def admin_roles_delete(role_id):
    """Delete role"""
    
    role = Role.query.get_or_404(role_id)
    
    # Check if role is being used by any users (using string comparison)
    users_count = User.query.filter_by(role=role.name).count()
    
    if users_count > 0:
        flash(f"Não é possível excluir o papel '{role.display_name}'. Ele está sendo usado por {users_count} usuário(s).", "danger")
        return redirect(url_for("admin_roles"))
    
    # Soft delete - just mark as inactive
    role.active = False
    db.session.commit()
    
    # Log activity
    if activity_logger:
        user = current_user()
        log_admin_action(
            user.id if user else 0,
            user.username if user else "Sistema",
            f"Papel '{role.display_name}' removido"
        )
    
    flash("Papel removido com sucesso.", "success")
    return redirect(url_for("admin_roles"))

# -------------------- ADMIN SETTINGS --------------------

@app.route("/admin/settings")
@login_required
@roles_required("admin")
def admin_settings():
    """System settings management"""
    settings = SystemSettings.query.order_by(SystemSettings.setting_key).all()
    settings_dict = {s.setting_key: s.setting_value for s in settings}
    return render_template("admin/settings.html", app_name=APP_NAME, user=current_user(), settings=settings_dict)

@app.route("/admin/settings/update", methods=["POST"])
@login_required
@roles_required("admin")
def admin_settings_update():
    """Update system settings"""
    for key, value in request.form.items():
        if key.startswith('setting_'):
            setting_key = key.replace('setting_', '')
            setting = SystemSettings.query.filter_by(setting_key=setting_key).first()
            if setting:
                setting.setting_value = value
                setting.updated_at = now_brazil()
            else:
                # Create new setting
                setting = SystemSettings(setting_key=setting_key, setting_value=value, updated_at=now_brazil())
                db.session.add(setting)
    
    db.session.commit()
    flash("Configurações atualizadas com sucesso.", "success")
    return redirect(url_for("admin_settings"))

# -------------------- ENHANCED UTILITIES --------------------

def get_system_setting(key, default=None):
    """Get system setting value"""
    setting = SystemSettings.query.filter_by(setting_key=key).first()
    return setting.setting_value if setting else default

# Update APP_NAME to be dynamic
def get_app_name():
    return get_system_setting("system_name", "Sistemas Olivium")

# -------------------- RUN --------------------
if __name__ == "__main__":
    print("🚀 Iniciando Sistema Olivion v2.0...")
    print("📊 Sistema de Gestão de Chamados")
    print("🌐 Servidor será iniciado em: http://localhost:5000")
    print("=" * 50)
    
    # Garantir que SQLite está inicializado
    with app.app_context():
        try:
            bootstrap()  # Criar tabelas e usuário admin
            print("✅ SQLite inicializado com sucesso!")
        except Exception as e:
            print(f"⚠️ Erro na inicialização: {e}")
    
    try:
        port = int(os.getenv("PORT", 5000))
        
        # Verificar se deve usar HTTPS para desenvolvimento local
        # Detectar se está rodando no Replit ou localmente
        is_replit = any([
            os.getenv("REPL_ID"),
            os.getenv("REPL_SLUG"), 
            os.getenv("REPLIT_DEPLOYMENT"),
            os.getenv("REPLIT_DB_URL"),
            "replit" in os.getcwd().lower()
        ])
        
        # Usar SSL apenas se for desenvolvimento local (não Replit) e variável específica
        use_ssl = (not is_replit and os.getenv("ENABLE_LOCAL_SSL") == "1")
        
        if use_ssl:
            try:
                print("🔒 HTTPS ativado para desenvolvimento local")
                print("⚠️  Aceite o certificado autoassinado no navegador")
                print("🌐 Acesse: https://localhost:5000")
                # Para HTTPS local, forçar threading mode para compatibilidade com SSL
                socketio.init_app(app, async_mode='threading')
                app.run(host="0.0.0.0", port=port, debug=False, ssl_context='adhoc', threaded=True)
            except Exception as e:
                print(f"⚠️  Não foi possível ativar HTTPS: {e}")
                print("🌐 Usando HTTP com SocketIO: http://localhost:5000")
                socketio.run(app, host="0.0.0.0", port=port, debug=False, use_reloader=False, log_output=True)
        else:
            # Para produção, Replit ou local sem SSL, usar SocketIO normal
            print("🌐 Usando HTTP com SocketIO")
            socketio.run(app, host="0.0.0.0", port=port, debug=False, use_reloader=False, log_output=True)
    except OSError as e:
        if "Address already in use" in str(e):
            print("❌ ERRO: Porta 5000 já está em uso!")
            print("💡 Solução: Feche outros programas que usam a porta 5000")
            print("   Ou mude a porta no arquivo app.py (linha final)")
        else:
            print(f"❌ ERRO: {e}")
        input("Pressione Enter para fechar...")

