import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / 'instance'
INSTANCE_DIR.mkdir(exist_ok=True)

SECRET_KEY = os.environ.get('SECRET_KEY', 'change-this-secret-key')
SQLALCHEMY_DATABASE_URI = f"sqlite:///{(INSTANCE_DIR / 'app.db').as_posix()}"
SQLALCHEMY_TRACK_MODIFICATIONS = False
