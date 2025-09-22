import os
from pathlib import Path
import secrets

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / 'instance'
INSTANCE_DIR.mkdir(exist_ok=True)

# Generate secure SECRET_KEY if not provided via environment
DEFAULT_SECRET_KEY = 'c932d1d52814ca0d71451877069fc3130400f33b51cdf34722fe197ea61fb0e5'
SECRET_KEY = os.environ.get('SECRET_KEY', DEFAULT_SECRET_KEY)

# Use consistent database path (sistema_os.db in root directory)
DB_PATH = BASE_DIR / 'sistema_os.db'
SQLALCHEMY_DATABASE_URI = f"sqlite:///{DB_PATH.as_posix()}"
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Security configurations
WTF_CSRF_ENABLED = True
WTF_CSRF_TIME_LIMIT = 3600  # 1 hour
SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

# Performance configurations
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}

# Cache configuration
CACHE_TYPE = 'SimpleCache'
CACHE_DEFAULT_TIMEOUT = 300
