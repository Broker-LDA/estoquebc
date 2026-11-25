"""Ponto inicial conservador para a VPS compartilhada; ajuste por métricas reais."""
import os

bind = f"0.0.0.0:{int(os.getenv('PORT', '8000'))}"
workers = int(os.getenv('WEB_CONCURRENCY', '2'))
threads = int(os.getenv('GUNICORN_THREADS', '2'))
worker_class = 'gthread'
timeout = 90
graceful_timeout = 30
keepalive = 5
max_requests = 1000
max_requests_jitter = 100
accesslog = '-'
errorlog = '-'
loglevel = 'info'
# Não registra query strings: links de recuperação contêm tokens de uso único.
access_log_format = '%(h)s %(t)s "%(m)s %(U)s %(H)s" %(s)s %(b)s %(L)s'
capture_output = True
# A interpretação dos cabeçalhos é feita por ProxyFix com um único proxy confiável.
forwarded_allow_ips = '127.0.0.1,::1'
