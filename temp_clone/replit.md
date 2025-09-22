# Sistema HelpDesk 13 - Olivion

## Visão Geral
Sistema de gestão de chamados/tickets instalado com sucesso a partir do repositório GitHub: https://github.com/diasjoao21dias-art/sistema-helpdesk13.git

### Status Atual
- ✅ **Sistema funcionando** na porta 5000
- ✅ **Base de dados SQLite** inicializada e limpa
- ✅ **Todas as dependências Python** instaladas
- ✅ **Sistema de licenciamento** ativo
- ✅ **Workflow configurado** e rodando automaticamente
- ✅ **Scripts LIMPAR_BANCO.py e USAR.py executados** com sucesso

## Informações de Acesso

### Como Acessar
- **URL**: https://[seu-repl-name].replit.app
- **Porta local**: 5000
- **Login padrão**: admin
- **Senha padrão**: admin

⚠️ **IMPORTANTE**: Altere a senha após o primeiro login!

## Funcionalidades Principais

### ✅ Gestão de Chamados/Tickets
- Abertura de chamados por usuários
- Atribuição por setores (T.I, Manutenção, CCIH, Telefonia)
- Controle de status e urgência
- Upload de imagens (até 3 por chamado)
- Histórico completo
- Campo para ramal e CDC

### ✅ Sistema de Usuários
- 3 níveis: Admin, Operador, Usuário
- Controle por setores
- Autenticação segura
- Sistema de permissões avançado

### ✅ Relatórios Avançados
- Gráficos e estatísticas
- Exportação PDF e Excel
- Filtros por período, setor, status
- Análise de performance

### ✅ Sistema de Licenças Comercial
- Licenciamento por hardware
- Controle de 30 dias
- 3 tipos de licença
- Ativação remota

## Configuração do Projeto

### Arquivos Principais
- `app.py` - Aplicação principal Flask
- `USAR.py` - Script de inicialização
- `models.py` - Modelos do banco de dados
- `config.py` - Configurações
- `requirements.txt` - Dependências Python

### Módulos de Segurança
- `backup_manager.py` - Gerenciamento de backups
- `database_safety.py` - Segurança do banco
- `activity_logger.py` - Log de atividades
- `license_manager.py` - Sistema de licenças

### Estrutura de Pastas
- `static/uploads/` → Imagens dos chamados
- `static/relatorios/` → Relatórios gerados
- `templates/` → Interfaces do usuário
- `instance/sistema_os.db` → Banco de dados SQLite
- `backups/` → Backups automáticos

## Configurações de Segurança

### Primeiro Acesso
1. Faça login com admin/admin
2. Vá em Admin > Usuários
3. Altere a senha do admin
4. Crie operadores e usuários

### Gerenciar Setores
- T.I → Problemas técnicos
- Manutenção → Manutenção predial
- CCIH / SESMT → Segurança do trabalho
- Telefonia → Telecomunicações

## Modificações Recentes
- **22/09/2025**: Nova instalação do projeto sistema-helpdesk13
  - Projeto clonado do GitHub: https://github.com/diasjoao21dias-art/sistema-helpdesk13.git
  - Dependências Python instaladas via packager_tool (Flask, SQLAlchemy, SocketIO, etc.)
  - Script LIMPAR_BANCO.py executado (banco limpo para nova máquina)
  - Script USAR.py executado (sistema iniciado)
  - Sistema configurado para Replit (porta 5000)
  - Workflow "Sistema HelpDesk" criado e funcionando
  - Banco de dados SQLite inicializado automaticamente

## Logs e Monitoramento
- Sistema de logs integrado e funcionando
- Monitoramento em tempo real via SocketIO
- Backup automático configurado
- Auditoria de ações de usuários
- Workflow: "Sistema Helpdesk" rodando na porta 5000

## Próximos Passos Recomendados
1. ✅ Alterar senha padrão do admin
2. ✅ Configurar usuários e operadores
3. ✅ Testar funcionalidades principais
4. ✅ Configurar setores conforme necessidade
5. ✅ Revisar sistema de licenciamento

## Comandos Úteis
- **Iniciar**: O sistema inicia automaticamente via workflow
- **Reiniciar**: Use o botão de restart do workflow no Replit
- **Logs**: Disponíveis no painel de logs do Replit

---
*Sistema Olivion v2.0 - Instalado em 22/09/2025*

## Preferências do Usuário
- **Idioma**: Português Brasileiro
- **Ambiente**: Replit com SQLite
- **Porta**: 5000 (padrão Replit)