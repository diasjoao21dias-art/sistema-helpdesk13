#!/usr/bin/env python3
"""
🚀 SISTEMA OLIVION - SQLite Funcionando
Execute este arquivo para usar o sistema
"""

import subprocess
import sys

print("=" * 50)
print("🚀 SISTEMA OLIVION - SQLITE")
print("=" * 50)
print("✅ SQLite sempre funcionando")
print("🌐 Sistema na porta 5000")  
print("👤 Login: admin")
print("🔐 Senha: admin")
print("=" * 50)
print()

try:
    subprocess.run([sys.executable, "app.py"])
except KeyboardInterrupt:
    print("\n✅ Sistema encerrado.")
except Exception as e:
    print(f"\n❌ Erro: {e}")
    input("Pressione Enter...")