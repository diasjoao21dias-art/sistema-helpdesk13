#!/usr/bin/env python3
"""
SCRIPT PARA LIMPAR BANCO DE DADOS - USAR EM NOVA MÁQUINA
Sistema Olivion - Preparar banco para nova instalação
"""

import sqlite3
import os
from datetime import datetime

def limpar_banco():
    """
    Remove dados antigos do banco SQLite para uso em nova máquina
    """
    db_path = "sistema_os.db"
    
    if not os.path.exists(db_path):
        print("❌ Arquivo sistema_os.db não encontrado!")
        print("   Execute este script na pasta TesteProgram")
        return False
    
    try:
        # Conectar ao banco
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("🧹 Limpando banco de dados para nova máquina...")
        
        # 1. LIMPAR SISTEMA DE LICENÇAS (principal problema)
        print("   → Removendo licenças antigas...")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='system_license'")
        if cursor.fetchone():
            cursor.execute("DELETE FROM system_license")
            print("     ✅ Licenças removidas")
        else:
            print("     ⚪ Tabela system_license não existe")
        
        # 2. LIMPAR CHAMADOS DE TESTE (se tabela existir)
        print("   → Verificando chamados de teste...")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chamado'")
        if cursor.fetchone():
            cursor.execute("DELETE FROM chamado")
            print("     ✅ Chamados removidos")
        else:
            print("     ⚪ Tabela chamado não existe")
        
        # 3. LIMPAR LOGS DE ATIVIDADE (se tabelas existirem)
        print("   → Removendo logs antigos...")
        for table in ['audit_log', 'system_activity']:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
            if cursor.fetchone():
                cursor.execute(f"DELETE FROM {table}")
                print(f"     ✅ {table} limpa")
            else:
                print(f"     ⚪ Tabela {table} não existe")
        
        # 4. MANTER APENAS O ADMIN PADRÃO (se tabela user existir)
        print("   → Mantendo apenas usuário admin...")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user'")
        if cursor.fetchone():
            cursor.execute("DELETE FROM user WHERE username != 'admin'")
            print("     ✅ Usuários extras removidos")
        else:
            print("     ⚪ Tabela user não existe")
        
        # 5. RESETAR CONFIGURAÇÕES DO SISTEMA
        print("   → Resetando configurações...")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='license_store'")
        if cursor.fetchone():
            cursor.execute("DELETE FROM license_store")
            print("     ✅ Configurações resetadas")
        else:
            print("     ⚪ Tabela license_store não existe")
        
        # 6. GARANTIR PAPÉIS PADRÃO (CRITICAL - Para sistema de papéis funcionar)
        print("   → Verificando papéis padrão do sistema...")
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='role'")
        if cursor.fetchone():
            # Verificar se existem papéis padrão, se não criar
            papeis_padrao = [
                ('admin', 'Administrador', 'Acesso total ao sistema', '["manage_users", "manage_sectors", "manage_roles", "view_all", "edit_all", "delete_all", "close_tickets", "create_tickets", "view_reports", "manage_settings"]'),
                ('operador', 'Operador', 'Operador de setor', '["view_sector", "edit_sector", "close_tickets", "create_tickets", "view_reports"]'),
                ('usuario', 'Usuário', 'Usuário básico', '["view_own", "create_tickets"]')
            ]
            
            for name, display_name, description, permissions in papeis_padrao:
                cursor.execute("SELECT COUNT(*) FROM role WHERE name = ?", (name,))
                if cursor.fetchone()[0] == 0:
                    cursor.execute("""
                        INSERT INTO role (name, display_name, description, permissions, active, created_at, updated_at) 
                        VALUES (?, ?, ?, ?, 1, datetime('now'), datetime('now'))
                    """, (name, display_name, description, permissions))
                    print(f"     ✅ Papel '{display_name}' criado")
                else:
                    print(f"     ⚪ Papel '{display_name}' já existe")
        else:
            print("     ⚪ Tabela role não existe - execute o sistema primeiro para criar tabelas")
        
        # Confirmar mudanças
        conn.commit()
        
        # Mostrar estatísticas
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user'")
        if cursor.fetchone():
            cursor.execute("SELECT COUNT(*) FROM user")
            users = cursor.fetchone()[0]
        else:
            users = 0
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='system_license'")
        if cursor.fetchone():
            cursor.execute("SELECT COUNT(*) FROM system_license")
            licenses = cursor.fetchone()[0]
        else:
            licenses = 0
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chamado'")
        if cursor.fetchone():
            cursor.execute("SELECT COUNT(*) FROM chamado")
            tickets = cursor.fetchone()[0]
        else:
            tickets = 0
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='role'")
        if cursor.fetchone():
            cursor.execute("SELECT COUNT(*) FROM role")
            roles = cursor.fetchone()[0]
        else:
            roles = 0
        
        conn.close()
        
        print("\n✅ BANCO LIMPO COM SUCESSO!")
        print(f"   👥 Usuários: {users} (admin mantido)")
        print(f"   🔐 Licenças: {licenses} (limpas)")
        print(f"   📋 Chamados: {tickets} (limpas)")
        print(f"   👔 Papéis: {roles} (padrão garantidos)")
        print("\n🎯 Agora execute: python USAR.py")
        print("   Login: admin / admin")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao limpar banco: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("    LIMPEZA DE BANCO - SISTEMA OLIVION")
    print("=" * 60)
    print("⚠️  Este script vai REMOVER:")
    print("   - Todas as licenças antigas")
    print("   - Todos os chamados de teste") 
    print("   - Todos os logs antigos")
    print("   - Usuários extras (mantém admin)")
    print("   ✅ MANTÉM: Papéis/grupos e suas permissões")
    print("=" * 60)
    print("🔄 Executando limpeza automaticamente...")
    
    if limpar_banco():
        print("\n🚀 Sistema pronto para usar na sua máquina!")
    else:
        print("\n💡 Verifique se está na pasta correta (TesteProgram)")