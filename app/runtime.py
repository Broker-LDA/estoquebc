"""Valida a configuração antes de aceitar tráfego de produção."""
import os
from urllib.parse import urlsplit

from sqlalchemy.engine import make_url


def configure_runtime(app):
    production = app.config['APP_ENV'] == 'production'
    url = make_url(app.config['SQLALCHEMY_DATABASE_URI'])
    if url.get_backend_name() == 'postgresql':
        # Cada worker tem seu próprio pool. Limites pequenos preservam a VPS compartilhada.
        app.config.setdefault('SQLALCHEMY_ENGINE_OPTIONS', {
            'pool_pre_ping': True,
            'pool_recycle': 1800,
            'pool_size': 3,
            'max_overflow': 2,
            'pool_timeout': 30,
            'connect_args': {'connect_timeout': 10, 'application_name': 'estoque-bc'},
        })
    if not production:
        return

    if url.get_backend_name() != 'postgresql' or url.drivername != 'postgresql+psycopg':
        raise RuntimeError('Produção exige DATABASE_URL com postgresql+psycopg://.')
    if not app.config['SESSION_COOKIE_SECURE']:
        raise RuntimeError('Produção exige COOKIE_SECURE=true e acesso HTTPS.')
    if app.debug or os.getenv('FLASK_DEBUG', '').lower() in ('1', 'true', 'yes'):
        raise RuntimeError('Desative FLASK_DEBUG em produção.')
    secret = app.config['SECRET_KEY'].lower()
    if any(value in secret for value in ('gere-uma-chave', 'troque-esta', 'change-me', 'substitua_por')):
        raise RuntimeError('Substitua a SECRET_KEY de exemplo por uma chave aleatória.')

    public = urlsplit(app.config['PUBLIC_BASE_URL'])
    if (public.scheme != 'https' or not public.hostname or public.username or public.password
            or public.path not in ('', '/') or public.query or public.fragment):
        raise RuntimeError('PUBLIC_BASE_URL deve ser a origem HTTPS, sem caminho ou credenciais.')
    if public.hostname in ('localhost', '127.0.0.1') or 'seudominio' in public.hostname:
        raise RuntimeError('Informe o domínio real em PUBLIC_BASE_URL.')

    hosts = app.config.get('TRUSTED_HOSTS') or [public.hostname]
    if public.hostname not in hosts or any('/' in host or '*' in host for host in hosts):
        raise RuntimeError('TRUSTED_HOSTS deve incluir o domínio público, sem protocolo ou curingas.')
    app.config['TRUSTED_HOSTS'] = hosts
    app.config['PREFERRED_URL_SCHEME'] = 'https'
