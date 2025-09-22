# metrics_dashboard.py - Dashboard de métricas avançadas

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import sqlite3
import json
from collections import defaultdict, Counter

class MetricsDashboard:
    """Sistema de métricas avançadas para o HelpDesk"""
    
    def __init__(self, db_path: str = "sistema_os.db"):
        self.db_path = db_path
        
    def _get_db_connection(self):
        """Conexão com o banco de dados"""
        return sqlite3.connect(self.db_path)
    
    def get_system_health(self) -> Dict[str, Any]:
        """Métricas de saúde do sistema"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            # Contadores básicos
            cursor.execute("SELECT COUNT(*) FROM user WHERE active = 1")
            active_users = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM chamado")
            total_chamados = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM system_activity WHERE timestamp >= datetime('now', '-24 hours')")
            activities_24h = cursor.fetchone()[0]
            
            # Status dos chamados
            cursor.execute("""
                SELECT status, COUNT(*) 
                FROM chamado 
                GROUP BY status
            """)
            status_counts = dict(cursor.fetchall())
            
            # Chamados por urgência
            cursor.execute("""
                SELECT urgencia, COUNT(*) 
                FROM chamado 
                GROUP BY urgencia
            """)
            urgencia_counts = dict(cursor.fetchall())
            
            # Chamados recentes (últimas 24h)
            cursor.execute("""
                SELECT COUNT(*) 
                FROM chamado 
                WHERE criado_em >= datetime('now', '-24 hours')
            """)
            chamados_24h = cursor.fetchone()[0]
            
            # Chamados resolvidos nas últimas 24h
            cursor.execute("""
                SELECT COUNT(*) 
                FROM chamado 
                WHERE fechado_em >= datetime('now', '-24 hours') 
                AND status IN ('Resolvido', 'Fechado')
            """)
            resolvidos_24h = cursor.fetchone()[0]
            
            # Taxa de resolução
            taxa_resolucao = (resolvidos_24h / max(chamados_24h, 1)) * 100 if chamados_24h > 0 else 0
            
            conn.close()
            
            health_status = 'healthy'
            if chamados_24h > 20:  # Muitos chamados
                health_status = 'warning'
            if taxa_resolucao < 50:  # Taxa baixa de resolução
                health_status = 'critical'
                
            return {
                'status': health_status,
                'active_users': active_users,
                'total_chamados': total_chamados,
                'activities_24h': activities_24h,
                'chamados_24h': chamados_24h,
                'resolvidos_24h': resolvidos_24h,
                'taxa_resolucao': round(taxa_resolucao, 2),
                'status_distribution': status_counts,
                'urgencia_distribution': urgencia_counts,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def get_performance_metrics(self, days: int = 7) -> Dict[str, Any]:
        """Métricas de performance dos últimos X dias"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            # Chamados por dia
            cursor.execute("""
                SELECT DATE(criado_em) as dia, COUNT(*) as total
                FROM chamado 
                WHERE criado_em >= ?
                GROUP BY DATE(criado_em)
                ORDER BY dia
            """, (start_date,))
            
            chamados_por_dia = {
                row[0]: row[1] for row in cursor.fetchall()
            }
            
            # Tempo médio de resolução por setor
            cursor.execute("""
                SELECT setor, 
                       AVG(julianday(fechado_em) - julianday(criado_em)) * 24 as horas_media
                FROM chamado 
                WHERE fechado_em IS NOT NULL 
                AND criado_em >= ?
                GROUP BY setor
            """, (start_date,))
            
            tempo_resolucao_setor = {
                row[0]: round(row[1], 2) for row in cursor.fetchall()
            }
            
            # Chamados por usuário (top 10)
            cursor.execute("""
                SELECT u.username, COUNT(c.id) as total_chamados
                FROM chamado c
                JOIN user u ON c.usuario_id = u.id
                WHERE c.criado_em >= ?
                GROUP BY u.username
                ORDER BY total_chamados DESC
                LIMIT 10
            """, (start_date,))
            
            top_usuarios = {
                row[0]: row[1] for row in cursor.fetchall()
            }
            
            # Distribuição por hora do dia
            cursor.execute("""
                SELECT strftime('%H', criado_em) as hora, COUNT(*) as total
                FROM chamado 
                WHERE criado_em >= ?
                GROUP BY strftime('%H', criado_em)
                ORDER BY hora
            """, (start_date,))
            
            chamados_por_hora = {
                f"{row[0]}:00": row[1] for row in cursor.fetchall()
            }
            
            # Eficiência por setor
            cursor.execute("""
                SELECT setor,
                       COUNT(*) as total,
                       SUM(CASE WHEN status IN ('Resolvido', 'Fechado') THEN 1 ELSE 0 END) as resolvidos
                FROM chamado 
                WHERE criado_em >= ?
                GROUP BY setor
            """, (start_date,))
            
            eficiencia_setor = {}
            for row in cursor.fetchall():
                setor, total, resolvidos = row
                eficiencia = (resolvidos / total * 100) if total > 0 else 0
                eficiencia_setor[setor] = {
                    'total': total,
                    'resolvidos': resolvidos,
                    'eficiencia_pct': round(eficiencia, 2)
                }
            
            conn.close()
            
            return {
                'period_days': days,
                'chamados_por_dia': chamados_por_dia,
                'tempo_resolucao_setor': tempo_resolucao_setor,
                'top_usuarios': top_usuarios,
                'chamados_por_hora': chamados_por_hora,
                'eficiencia_setor': eficiencia_setor,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def get_user_metrics(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Métricas específicas de usuário"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            if user_id:
                # Métricas para usuário específico
                cursor.execute("""
                    SELECT username, role, setor, created_at
                    FROM user WHERE id = ?
                """, (user_id,))
                user_info = cursor.fetchone()
                
                if not user_info:
                    return {'error': 'Usuário não encontrado'}
                
                # Chamados criados pelo usuário
                cursor.execute("""
                    SELECT COUNT(*) FROM chamado WHERE usuario_id = ?
                """, (user_id,))
                chamados_criados = cursor.fetchone()[0]
                
                # Chamados fechados pelo usuário (se for operador/admin)
                cursor.execute("""
                    SELECT COUNT(*) FROM chamado WHERE fechado_por_id = ?
                """, (user_id,))
                chamados_fechados = cursor.fetchone()[0]
                
                # Atividades recentes
                cursor.execute("""
                    SELECT action_type, COUNT(*) 
                    FROM system_activity 
                    WHERE user_id = ? 
                    AND timestamp >= datetime('now', '-7 days')
                    GROUP BY action_type
                    ORDER BY COUNT(*) DESC
                    LIMIT 10
                """, (user_id,))
                
                atividades = dict(cursor.fetchall())
                
                return {
                    'user_info': {
                        'username': user_info[0],
                        'role': user_info[1], 
                        'setor': user_info[2],
                        'created_at': user_info[3]
                    },
                    'chamados_criados': chamados_criados,
                    'chamados_fechados': chamados_fechados,
                    'atividades_recentes': atividades,
                    'timestamp': datetime.now().isoformat()
                }
            else:
                # Métricas gerais de usuários
                cursor.execute("""
                    SELECT role, COUNT(*) FROM user WHERE active = 1 GROUP BY role
                """)
                usuarios_por_role = dict(cursor.fetchall())
                
                cursor.execute("""
                    SELECT setor, COUNT(*) FROM user 
                    WHERE active = 1 AND setor != '' 
                    GROUP BY setor
                """)
                usuarios_por_setor = dict(cursor.fetchall())
                
                # Usuários mais ativos (por chamados criados)
                cursor.execute("""
                    SELECT u.username, COUNT(c.id) as total
                    FROM user u
                    LEFT JOIN chamado c ON u.id = c.usuario_id
                    WHERE u.active = 1
                    GROUP BY u.username
                    ORDER BY total DESC
                    LIMIT 10
                """)
                usuarios_ativos = {row[0]: row[1] for row in cursor.fetchall()}
                
                return {
                    'usuarios_por_role': usuarios_por_role,
                    'usuarios_por_setor': usuarios_por_setor,
                    'usuarios_mais_ativos': usuarios_ativos,
                    'timestamp': datetime.now().isoformat()
                }
                
            conn.close()
            
        except Exception as e:
            return {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def get_trend_analysis(self, metric: str = 'chamados', days: int = 30) -> Dict[str, Any]:
        """Análise de tendências"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            if metric == 'chamados':
                # Tendência de chamados
                cursor.execute("""
                    SELECT DATE(criado_em) as dia, 
                           COUNT(*) as total,
                           SUM(CASE WHEN urgencia = 'Crítica' THEN 1 ELSE 0 END) as criticos,
                           SUM(CASE WHEN urgencia = 'Alta' THEN 1 ELSE 0 END) as altos
                    FROM chamado 
                    WHERE criado_em >= ?
                    GROUP BY DATE(criado_em)
                    ORDER BY dia
                """, (start_date,))
                
                data = cursor.fetchall()
                trend_data = []
                
                for row in data:
                    trend_data.append({
                        'date': row[0],
                        'total': row[1],
                        'criticos': row[2],
                        'altos': row[3]
                    })
                
                # Calcular tendência (regressão linear simples)
                if len(trend_data) >= 2:
                    values = [item['total'] for item in trend_data]
                    n = len(values)
                    
                    # Média móvel de 7 dias
                    moving_avg = []
                    for i in range(len(values)):
                        start_idx = max(0, i - 6)
                        avg = sum(values[start_idx:i+1]) / (i - start_idx + 1)
                        moving_avg.append(round(avg, 2))
                    
                    # Tendência (diferença entre últimos e primeiros valores)
                    trend = 'stable'
                    if len(values) >= 7:
                        recent_avg = sum(values[-7:]) / 7
                        earlier_avg = sum(values[:7]) / 7
                        
                        if recent_avg > earlier_avg * 1.1:
                            trend = 'increasing'
                        elif recent_avg < earlier_avg * 0.9:
                            trend = 'decreasing'
                    
                    return {
                        'metric': metric,
                        'period_days': days,
                        'trend_direction': trend,
                        'data_points': trend_data,
                        'moving_average': moving_avg,
                        'summary': {
                            'total_period': sum(values),
                            'daily_average': round(sum(values) / len(values), 2),
                            'peak_day': max(trend_data, key=lambda x: x['total']),
                            'min_day': min(trend_data, key=lambda x: x['total'])
                        },
                        'timestamp': datetime.now().isoformat()
                    }
                
            conn.close()
            
            return {
                'metric': metric,
                'error': 'Dados insuficientes para análise de tendência',
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'metric': metric,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def generate_alerts(self) -> List[Dict[str, Any]]:
        """Gera alertas automáticos baseados nas métricas"""
        alerts = []
        
        try:
            health = self.get_system_health()
            performance = self.get_performance_metrics(7)
            
            # Alert: Muitos chamados abertos
            if health['status_distribution'].get('Aberto', 0) > 10:
                alerts.append({
                    'type': 'warning',
                    'title': 'Muitos chamados abertos',
                    'message': f"Existem {health['status_distribution']['Aberto']} chamados em aberto",
                    'severity': 'medium',
                    'timestamp': datetime.now().isoformat()
                })
            
            # Alert: Taxa de resolução baixa
            if health['taxa_resolucao'] < 70:
                alerts.append({
                    'type': 'warning', 
                    'title': 'Taxa de resolução baixa',
                    'message': f"Taxa de resolução nas últimas 24h: {health['taxa_resolucao']}%",
                    'severity': 'high',
                    'timestamp': datetime.now().isoformat()
                })
            
            # Alert: Setor com tempo alto de resolução
            for setor, tempo in performance['tempo_resolucao_setor'].items():
                if tempo > 48:  # Mais de 48 horas
                    alerts.append({
                        'type': 'alert',
                        'title': f'Tempo alto de resolução - {setor}',
                        'message': f"Tempo médio de resolução: {tempo:.1f} horas",
                        'severity': 'medium',
                        'timestamp': datetime.now().isoformat()
                    })
            
            # Alert: Poucas atividades no sistema
            if health['activities_24h'] < 5:
                alerts.append({
                    'type': 'info',
                    'title': 'Baixa atividade no sistema',
                    'message': f"Apenas {health['activities_24h']} atividades nas últimas 24h",
                    'severity': 'low',
                    'timestamp': datetime.now().isoformat()
                })
                
        except Exception as e:
            alerts.append({
                'type': 'error',
                'title': 'Erro ao gerar alertas',
                'message': str(e),
                'severity': 'high',
                'timestamp': datetime.now().isoformat()
            })
        
        return alerts

# Instância global
metrics_dashboard = MetricsDashboard()

print("✅ Dashboard de métricas configurado")
print("📊 Métricas disponíveis: saúde, performance, usuários, tendências")
print("🚨 Sistema de alertas automáticos ativado")