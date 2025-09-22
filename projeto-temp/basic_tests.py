# basic_tests.py - Testes automatizados básicos para o Sistema HelpDesk

import os
import sys
import sqlite3
import requests
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

class HelpDeskTester:
    """Classe para executar testes automatizados do Sistema HelpDesk"""
    
    def __init__(self, base_url: str = "http://localhost:5000", db_path: str = "sistema_os.db"):
        self.base_url = base_url
        self.db_path = db_path
        self.test_results = []
        self.session = requests.Session()
        
    def log_test(self, test_name: str, success: bool, message: str = "", details: Optional[Dict] = None):
        """Registra resultado de um teste"""
        result = {
            'test_name': test_name,
            'success': success,
            'message': message,
            'details': details or {},
            'timestamp': datetime.now().isoformat()
        }
        self.test_results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {test_name}: {message}")
    
    def test_database_connectivity(self) -> bool:
        """Testa conectividade com o banco de dados"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Verificar se as tabelas existem
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            required_tables = ['user', 'chamado', 'system_activity', 'system_license']
            missing_tables = [table for table in required_tables if table not in tables]
            
            if missing_tables:
                self.log_test("database_connectivity", False, 
                             f"Tabelas faltando: {missing_tables}")
                return False
            
            # Verificar dados básicos
            cursor.execute("SELECT COUNT(*) FROM user")
            user_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM chamado")
            chamado_count = cursor.fetchone()[0]
            
            conn.close()
            
            self.log_test("database_connectivity", True, 
                         f"Banco OK - {user_count} usuários, {chamado_count} chamados")
            return True
            
        except Exception as e:
            self.log_test("database_connectivity", False, str(e))
            return False
    
    def test_server_connectivity(self) -> bool:
        """Testa se o servidor está respondendo"""
        try:
            response = self.session.get(f"{self.base_url}/", timeout=10)
            
            if response.status_code in [200, 302]:  # 302 = redirect to login
                self.log_test("server_connectivity", True, 
                             f"Servidor respondendo - Status: {response.status_code}")
                return True
            else:
                self.log_test("server_connectivity", False, 
                             f"Status inesperado: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("server_connectivity", False, str(e))
            return False
    
    def test_login_page(self) -> bool:
        """Testa se a página de login carrega corretamente"""
        try:
            response = self.session.get(f"{self.base_url}/login", timeout=10)
            
            if response.status_code == 200:
                content = response.text
                
                # Verificar se elementos importantes estão presentes
                required_elements = ['username', 'password', 'login', 'form']
                missing_elements = [elem for elem in required_elements 
                                  if elem.lower() not in content.lower()]
                
                if missing_elements:
                    self.log_test("login_page", False, 
                                 f"Elementos faltando: {missing_elements}")
                    return False
                
                self.log_test("login_page", True, "Página de login carregando corretamente")
                return True
            else:
                self.log_test("login_page", False, f"Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("login_page", False, str(e))
            return False
    
    def test_api_endpoints(self) -> bool:
        """Testa endpoints da API REST"""
        try:
            # Teste endpoint de health (público)
            response = self.session.get(f"{self.base_url}/api/v1/health", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'success' in data and 'data' in data:
                    health_data = data['data']
                    if 'status' in health_data and health_data['status'] == 'healthy':
                        self.log_test("api_health_endpoint", True, 
                                     "Endpoint /api/v1/health funcionando")
                        
                        # Teste endpoint de stats (requer autenticação)
                        headers = {'X-API-Key': 'helpdesk_demo_api_key_2025'}
                        stats_response = self.session.get(f"{self.base_url}/api/v1/stats", headers=headers, timeout=10)
                        if stats_response.status_code == 200:
                            self.log_test("api_stats_endpoint", True, 
                                         "Endpoint /api/v1/stats funcionando")
                            return True
                        else:
                            self.log_test("api_stats_endpoint", False, 
                                         f"Stats endpoint status: {stats_response.status_code}")
                            return False
                    else:
                        self.log_test("api_health_endpoint", False, 
                                     "Health status não é 'healthy'")
                        return False
                else:
                    self.log_test("api_health_endpoint", False, 
                                 "Estrutura de resposta inválida")
                    return False
            else:
                self.log_test("api_health_endpoint", False, 
                             f"Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("api_endpoints", False, str(e))
            return False
    
    def test_static_files(self) -> bool:
        """Testa se arquivos estáticos estão acessíveis"""
        try:
            static_files = [
                '/static/css/style.css',
                '/static/js/form-validation.js',
                '/static/sw.js'
            ]
            
            successful_files = 0
            
            for file_path in static_files:
                try:
                    response = self.session.get(f"{self.base_url}{file_path}", timeout=5)
                    if response.status_code == 200:
                        successful_files += 1
                except:
                    pass
            
            if successful_files >= len(static_files) * 0.7:  # Pelo menos 70% dos arquivos
                self.log_test("static_files", True, 
                             f"{successful_files}/{len(static_files)} arquivos acessíveis")
                return True
            else:
                self.log_test("static_files", False, 
                             f"Apenas {successful_files}/{len(static_files)} arquivos acessíveis")
                return False
                
        except Exception as e:
            self.log_test("static_files", False, str(e))
            return False
    
    def test_performance_basic(self) -> bool:
        """Testa performance básica do sistema"""
        try:
            # Medir tempo de resposta da página principal
            start_time = time.time()
            response = self.session.get(f"{self.base_url}/", timeout=15)
            end_time = time.time()
            
            response_time = (end_time - start_time) * 1000  # em ms
            
            if response_time < 5000:  # Menos de 5 segundos
                self.log_test("performance_basic", True, 
                             f"Tempo de resposta: {response_time:.0f}ms")
                return True
            else:
                self.log_test("performance_basic", False, 
                             f"Tempo de resposta muito alto: {response_time:.0f}ms")
                return False
                
        except Exception as e:
            self.log_test("performance_basic", False, str(e))
            return False
    
    def test_data_integrity(self) -> bool:
        """Testa integridade dos dados no banco"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Verificar se o usuário admin existe
            cursor.execute("SELECT id, username, role FROM user WHERE username = 'admin'")
            admin_user = cursor.fetchone()
            
            if not admin_user:
                self.log_test("data_integrity", False, "Usuário admin não encontrado")
                return False
            
            # Verificar se há chamados de demonstração
            cursor.execute("SELECT COUNT(*) FROM chamado")
            chamado_count = cursor.fetchone()[0]
            
            if chamado_count == 0:
                self.log_test("data_integrity", False, "Nenhum chamado encontrado")
                return False
            
            # Verificar integridade referencial
            cursor.execute("""
                SELECT COUNT(*) FROM chamado c 
                LEFT JOIN user u ON c.usuario_id = u.id 
                WHERE u.id IS NULL
            """)
            orphaned_chamados = cursor.fetchone()[0]
            
            if orphaned_chamados > 0:
                self.log_test("data_integrity", False, 
                             f"{orphaned_chamados} chamados órfãos encontrados")
                return False
            
            conn.close()
            
            self.log_test("data_integrity", True, 
                         f"Dados íntegros - Admin OK, {chamado_count} chamados")
            return True
            
        except Exception as e:
            self.log_test("data_integrity", False, str(e))
            return False
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Executa todos os testes"""
        print("🧪 Iniciando testes automatizados do Sistema HelpDesk...")
        print("=" * 60)
        
        tests = [
            self.test_database_connectivity,
            self.test_server_connectivity,
            self.test_login_page,
            self.test_api_endpoints,
            self.test_static_files,
            self.test_performance_basic,
            self.test_data_integrity
        ]
        
        passed_tests = 0
        total_tests = len(tests)
        
        for test in tests:
            try:
                if test():
                    passed_tests += 1
            except Exception as e:
                self.log_test(test.__name__, False, f"Erro inesperado: {e}")
        
        print("=" * 60)
        print(f"📊 RESULTADO DOS TESTES:")
        print(f"✅ Aprovados: {passed_tests}/{total_tests}")
        print(f"❌ Falharam: {total_tests - passed_tests}/{total_tests}")
        print(f"📈 Taxa de sucesso: {(passed_tests/total_tests)*100:.1f}%")
        
        # Determinar status geral
        if passed_tests == total_tests:
            overall_status = "SUCCESS"
        elif passed_tests >= total_tests * 0.8:  # 80% ou mais
            overall_status = "WARNING"
        else:
            overall_status = "CRITICAL"
        
        return {
            'overall_status': overall_status,
            'passed_tests': passed_tests,
            'total_tests': total_tests,
            'success_rate': (passed_tests/total_tests)*100,
            'test_results': self.test_results,
            'timestamp': datetime.now().isoformat()
        }

def run_tests():
    """Função principal para executar os testes"""
    tester = HelpDeskTester()
    return tester.run_all_tests()

if __name__ == "__main__":
    # Aguardar um pouco para o servidor inicializar
    print("⏳ Aguardando sistema inicializar...")
    time.sleep(3)
    
    result = run_tests()
    
    # Exit code baseado no resultado
    if result['overall_status'] == 'SUCCESS':
        sys.exit(0)
    elif result['overall_status'] == 'WARNING':
        sys.exit(1)
    else:
        sys.exit(2)