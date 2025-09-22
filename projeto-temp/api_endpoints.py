# api_endpoints.py - Endpoints REST para integração externa/mobile

from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from datetime import datetime
import json
from typing import Dict, List, Any, Optional
from api_security import enhanced_api_auth, api_rate_limit

def create_api_routes(app: Flask, db: SQLAlchemy) -> None:
    """Cria endpoints REST para o sistema"""
    
    def api_key_required(f):
        """Decorator para validar API key ou sessão ativa"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask import session, request, jsonify
            
            # Verificar API key no header
            api_key = request.headers.get('X-API-Key')
            if api_key == 'helpdesk_demo_api_key_2025':  # API key para demonstração
                return f(*args, **kwargs)
            
            # Verificar se usuário tem sessão ativa e é admin/operador
            if 'user_id' in session:
                try:
                    # Import dentro do contexto para evitar problemas
                    from models import User
                    user = User.query.get(session['user_id'])
                    if user and (user.is_admin or user.is_operator_like):
                        return f(*args, **kwargs)
                except:
                    pass
            
            # Não autorizado
            return jsonify({
                'success': False,
                'error': 'API key ou autorização necessária',
                'timestamp': datetime.now().isoformat()
            }), 401
            
        return decorated_function
    
    def json_response(data: Any, status_code: int = 200) -> tuple:
        """Padroniza resposta JSON"""
        return jsonify({
            'success': status_code < 400,
            'data': data,
            'timestamp': datetime.now().isoformat()
        }), status_code
    
    @app.route('/api/v1/health', methods=['GET'])
    def api_health() -> tuple:
        """Endpoint de saúde da API"""
        return json_response({
            'status': 'healthy',
            'version': '1.0.0',
            'database': 'connected'
        })
    
    @app.route('/api/v1/stats', methods=['GET'])
    @api_key_required
    def api_stats() -> tuple:
        """Estatísticas básicas do sistema"""
        try:
            # Usar SQLite diretamente para máxima compatibilidade
            import sqlite3
            conn = sqlite3.connect('sistema_os.db')
            cursor = conn.cursor()
            
            try:
                # Contar usuários (sem coluna active que não existe)
                cursor.execute("SELECT COUNT(*) FROM user")
                total_users = cursor.fetchone()[0]
                
                # Contar total de chamados
                cursor.execute("SELECT COUNT(*) FROM chamado")
                total_chamados = cursor.fetchone()[0]
                
                # Chamados por status
                cursor.execute("SELECT status, COUNT(*) FROM chamado GROUP BY status")
                status_data = cursor.fetchall()
                status_counts = {status: count for status, count in status_data}
                
                # Chamados por setor
                cursor.execute("SELECT setor, COUNT(*) FROM chamado GROUP BY setor")
                setor_data = cursor.fetchall()
                setor_counts = {setor: count for setor, count in setor_data}
                
            finally:
                conn.close()
            
            return json_response({
                'total_users': total_users,
                'total_chamados': total_chamados,
                'chamados_por_status': status_counts,
                'chamados_por_setor': setor_counts
            })
            
        except Exception as e:
            return json_response({'error': str(e)}, 500)
    
    @app.route('/api/v1/chamados', methods=['GET'])
    @api_rate_limit
    @enhanced_api_auth('read')
    def api_list_chamados() -> tuple:
        """Lista todos os chamados"""
        try:
            from models import Chamado, User
            
            # Parâmetros de filtro
            status = request.args.get('status')
            setor = request.args.get('setor')
            limit = min(int(request.args.get('limit', 50)), 100)  # Max 100
            offset = int(request.args.get('offset', 0))
            
            # Query base
            query = Chamado.query
            
            # Aplicar filtros
            if status:
                query = query.filter(Chamado.status == status)
            if setor:
                query = query.filter(Chamado.setor == setor)
            
            # Paginação
            chamados = query.offset(offset).limit(limit).all()
            
            # Serializar resultados
            result = []
            for chamado in chamados:
                result.append({
                    'id': chamado.id,
                    'titulo': chamado.titulo,
                    'descricao': chamado.descricao,
                    'status': chamado.status,
                    'setor': chamado.setor,
                    'urgencia': chamado.urgencia,
                    'prioridade': chamado.prioridade,
                    'criado_em': chamado.criado_em.isoformat() if chamado.criado_em else None,
                    'fechado_em': chamado.fechado_em.isoformat() if chamado.fechado_em else None,
                    'ramal': chamado.ramal,
                    'cdc': chamado.cdc
                })
            
            return json_response({
                'chamados': result,
                'count': len(result),
                'offset': offset,
                'limit': limit
            })
            
        except Exception as e:
            return json_response({'error': str(e)}, 500)
    
    @app.route('/api/v1/chamados/<int:chamado_id>', methods=['GET'])
    @api_key_required
    def api_get_chamado(chamado_id: int) -> tuple:
        """Busca chamado específico"""
        try:
            from models import Chamado, User
            
            chamado = Chamado.query.get(chamado_id)
            if not chamado:
                return json_response({'error': 'Chamado não encontrado'}, 404)
            
            # Buscar informações do usuário
            usuario = User.query.get(chamado.usuario_id) if chamado.usuario_id else None
            fechado_por = User.query.get(chamado.fechado_por_id) if chamado.fechado_por_id else None
            
            result = {
                'id': chamado.id,
                'titulo': chamado.titulo,
                'descricao': chamado.descricao,
                'status': chamado.status,
                'setor': chamado.setor,
                'urgencia': chamado.urgencia,
                'prioridade': chamado.prioridade,
                'criado_em': chamado.criado_em.isoformat() if chamado.criado_em else None,
                'fechado_em': chamado.fechado_em.isoformat() if chamado.fechado_em else None,
                'resolucao': chamado.resolucao,
                'ramal': chamado.ramal,
                'cdc': chamado.cdc,
                'usuario': usuario.username if usuario else None,
                'fechado_por': fechado_por.username if fechado_por else None,
                'imagens': [chamado.imagem1, chamado.imagem2, chamado.imagem3]
            }
            
            return json_response(result)
            
        except Exception as e:
            return json_response({'error': str(e)}, 500)
    
    @app.route('/api/v1/chamados', methods=['POST'])
    @api_rate_limit
    @enhanced_api_auth('write')
    def api_create_chamado() -> tuple:
        """Cria novo chamado via API"""
        try:
            from models import Chamado
            
            data = request.get_json()
            if not data:
                return json_response({'error': 'Dados JSON obrigatórios'}, 400)
            
            # Validar campos obrigatórios
            required_fields = ['titulo', 'descricao', 'setor']
            for field in required_fields:
                if not data.get(field):
                    return json_response({'error': f'Campo {field} é obrigatório'}, 400)
            
            # Criar novo chamado
            chamado = Chamado()
            chamado.titulo = data['titulo']
            chamado.descricao = data['descricao'] 
            chamado.setor = data['setor']
            chamado.urgencia = data.get('urgencia', 'Normal')
            chamado.prioridade = data.get('prioridade', 'Normal')
            chamado.status = data.get('status', 'Aberto')
            chamado.ramal = data.get('ramal', '')
            chamado.cdc = data.get('cdc', '')
            chamado.usuario_id = data.get('usuario_id', 1)
            chamado.criado_em = datetime.now()
            
            db.session.add(chamado)
            db.session.commit()
            
            return json_response({
                'message': 'Chamado criado com sucesso',
                'chamado_id': chamado.id
            }, 201)
            
        except Exception as e:
            db.session.rollback()
            return json_response({'error': str(e)}, 500)
    
    @app.route('/api/v1/chamados/<int:chamado_id>/status', methods=['PUT'])
    @api_rate_limit
    @enhanced_api_auth('write')
    def api_update_chamado_status(chamado_id: int) -> tuple:
        """Atualiza status de um chamado"""
        try:
            from models import Chamado
            
            data = request.get_json()
            if not data or 'status' not in data:
                return json_response({'error': 'Status é obrigatório'}, 400)
            
            chamado = Chamado.query.get(chamado_id)
            if not chamado:
                return json_response({'error': 'Chamado não encontrado'}, 404)
            
            # Atualizar status
            old_status = chamado.status
            chamado.status = data['status']
            
            # Se fechando, definir data
            if data['status'] in ['Fechado', 'Resolvido']:
                chamado.fechado_em = datetime.now()
                if data.get('resolucao'):
                    chamado.resolucao = data['resolucao']
            
            db.session.commit()
            
            return json_response({
                'message': f'Status alterado de {old_status} para {data["status"]}',
                'chamado_id': chamado_id
            })
            
        except Exception as e:
            db.session.rollback()
            return json_response({'error': str(e)}, 500)
    
    @app.route('/api/v1/usuarios', methods=['GET'])
    @api_key_required
    def api_list_usuarios() -> tuple:
        """Lista usuários do sistema"""
        try:
            from models import User
            
            limit = min(int(request.args.get('limit', 20)), 50)  # Max 50
            offset = int(request.args.get('offset', 0))
            
            usuarios = User.query.filter(User.active == True).offset(offset).limit(limit).all()
            
            result = []
            for user in usuarios:
                result.append({
                    'id': user.id,
                    'username': user.username,
                    'role': user.role,
                    'setor': user.setor,
                    'created_at': user.created_at.isoformat() if user.created_at else None
                })
            
            return json_response({
                'usuarios': result,
                'count': len(result),
                'offset': offset,
                'limit': limit
            })
            
        except Exception as e:
            return json_response({'error': str(e)}, 500)
    
    @app.route('/api/v1/setores', methods=['GET'])
    def api_list_setores() -> tuple:
        """Lista setores disponíveis"""
        from app import SETOR_CHOICES
        return json_response({
            'setores': SETOR_CHOICES
        })
    
    print("✅ Endpoints REST configurados:")
    print("   GET  /api/v1/health")
    print("   GET  /api/v1/stats") 
    print("   GET  /api/v1/chamados")
    print("   POST /api/v1/chamados")
    print("   GET  /api/v1/chamados/<id>")
    print("   PUT  /api/v1/chamados/<id>/status")
    print("   GET  /api/v1/usuarios")
    print("   GET  /api/v1/setores")