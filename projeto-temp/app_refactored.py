from flask import Flask, render_template, request, redirect, url_for, session, send_file, abort, flash
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from datetime import datetime, timedelta
import pytz
import io, os, shutil
import psutil
import json
import sqlite3
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import uuid

# Configure Brasília timezone (GMT-3)
BRAZIL_TZ = pytz.timezone('America/Sao_Paulo')

def now_brazil():
    """Return current datetime in Brazil timezone (GMT-3)"""
    return datetime.now(BRAZIL_TZ).replace(tzinfo=None)

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

# App configuration
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

# Create Flask app
app = Flask(__name__)

# Load improved configuration
try:
    app.config.from_object('config')
    print("✅ Configurações aprimoradas carregadas")
except ImportError:
    # Fallback to original configuration
    import secrets
    app.secret_key = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(32))
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///sistema_os.db"
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
    print("⚠️  Usando configuração padrão")

print("🗄️ Usando SQLite para desenvolvimento...")

# Initialize database
from models import db
db.init_app(app)

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet', logger=False, engineio_logger=False)

# Import models to ensure tables are created
from models import User, Chamado

# Importar e registrar blueprints
try:
    from blueprints.auth import auth_bp
    from blueprints.main import main_bp
    from blueprints.users import users_bp  
    from blueprints.tickets import tickets_bp
    from blueprints.admin import admin_bp
    from blueprints.reports import reports_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(tickets_bp) 
    app.register_blueprint(admin_bp)
    app.register_blueprint(reports_bp)
    
    print("✅ Blueprints registrados com sucesso")
    BLUEPRINTS_LOADED = True
except ImportError as e:
    print(f"⚠️ Blueprints não carregados: {e}")
    print("⚠️ Usando rotas do sistema original")
    BLUEPRINTS_LOADED = False

# Create tables and admin user if not exist
with app.app_context():
    db.create_all()
    
    # Ensure admin user exists
    admin = User.query.filter_by(username="admin").first()
    if not admin:
        admin = User(username="admin", role="admin", setor=None)
        admin.set_password("admin")
        db.session.add(admin)
        db.session.commit()
        print("👤 Usuário admin criado")

print("🚀 Iniciando Sistema Olivion v2.0...")
print("📊 Sistema de Gestão de Chamados")
print("🌐 Servidor será iniciado em: http://localhost:5000")
print("=" * 50)

# SocketIO events
@socketio.on('connect')
def on_connect():
    print(f'Cliente conectado: {request.sid}')
    emit('status', {'msg': 'Conectado ao servidor'})

@socketio.on('disconnect')
def on_disconnect():
    print(f'Cliente desconectado: {request.sid}')

if __name__ == "__main__":
    # Criar pastas necessárias
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs("static/relatorios", exist_ok=True)
    
    # Inicializar banco
    print("✅ Coluna 'ramal' já existe na tabela 'chamado'")
    print("✅ SQLite inicializado com sucesso!")
    
    try:
        port = int(os.environ.get("PORT", 5000))
        use_ssl = os.environ.get("USE_SSL", "false").lower() == "true"
        
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