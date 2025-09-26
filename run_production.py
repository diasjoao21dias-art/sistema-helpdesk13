#!/usr/bin/env python3
"""
Script para iniciar o sistema em produção com Gunicorn
Configurado para suportar múltiplos workers e SocketIO
"""
import os
import sqlite3
from pathlib import Path

def setup_production_db():
    """Configura o banco SQLite para produção"""
    db_path = "sistema_os.db"
    
    if os.path.exists(db_path):
        print("🗄️ Configurando SQLite para produção...")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Habilitar WAL mode para melhor concorrência
        cursor.execute("PRAGMA journal_mode=WAL;")
        
        # Configurar timeout para writes
        cursor.execute("PRAGMA busy_timeout=5000;")
        
        # Otimizações de performance
        cursor.execute("PRAGMA cache_size=10000;")
        cursor.execute("PRAGMA temp_store=memory;")
        cursor.execute("PRAGMA mmap_size=268435456;")  # 256MB
        
        # Verificar índices existem
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%';")
        indices = cursor.fetchall()
        
        print(f"✅ Banco configurado com {len(indices)} índices otimizados")
        
        conn.close()
    else:
        print("⚠️ Banco de dados não encontrado. Execute a aplicação primeiro para criar.")

def main():
    """Função principal para produção"""
    print("🚀 Iniciando Sistema Helpdesk em modo PRODUÇÃO")
    print("=" * 50)
    
    # Configurar banco para produção
    setup_production_db()
    
    # Verificar se Gunicorn está disponível
    try:
        import gunicorn
        print(f"✅ Gunicorn {gunicorn.__version__} disponível")
    except ImportError:
        print("❌ Gunicorn não instalado. Instale com: pip install gunicorn[eventlet]")
        return
        
    # Verificar se eventlet está disponível (já está nas requirements.txt)
    try:
        import eventlet
        print(f"✅ Eventlet {eventlet.__version__} disponível")
    except ImportError:
        print("❌ Eventlet não disponível. Verifique requirements.txt")
        return
    
    print("\n🌐 Iniciando servidor com múltiplos workers...")
    print("📊 Configuração:")
    print("   - Workers: CPU cores * 2 + 1")
    print("   - Worker Class: eventlet (SocketIO)")  
    print("   - Porta: 5000")
    print("   - Timeout: 120s")
    print("   - Max Requests: 1000/worker")
    
    # Executar via gunicorn
    os.system("gunicorn --config gunicorn.conf.py app:app")

if __name__ == "__main__":
    main()