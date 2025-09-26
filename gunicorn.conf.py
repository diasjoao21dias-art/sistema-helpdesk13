# Configuração Gunicorn para produção
import multiprocessing
import os

# Configurações básicas
bind = "0.0.0.0:5000"

# Worker processes - ajustado para SocketIO
redis_url = os.getenv('REDIS_URL')
if redis_url:
    # Com Redis - múltiplos workers
    workers = min(4, multiprocessing.cpu_count())
    print("🔧 Usando múltiplos workers com Redis")
else:
    # Sem Redis - single worker para SocketIO
    workers = 1
    print("⚠️ Usando single worker (configure REDIS_URL para múltiplos workers)")

worker_class = "eventlet"  # Para suporte SocketIO
worker_connections = 1000

# Configurações de timeout
timeout = 120
keepalive = 2
max_requests = 1000
max_requests_jitter = 100

# Configurações de memória
worker_tmp_dir = "/dev/shm"
preload_app = True

# Logs
loglevel = "info"
accesslog = "-"
errorlog = "-"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Configurações de segurança
limit_request_line = 8190
limit_request_fields = 100
limit_request_field_size = 8190

# Graceful restart
graceful_timeout = 30
worker_tmp_dir = "/dev/shm"

# Performance
sendfile = True

def when_ready(server):
    server.log.info("Sistema Helpdesk pronto para produção!")

def worker_int(worker):
    worker.log.info("Worker recebeu INT ou QUIT signal")

def pre_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)