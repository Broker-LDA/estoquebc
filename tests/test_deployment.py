"""Verifica proteções de produção e recursos necessários à instalação do PWA."""
import io
import json

import pytest
from PIL import Image
from sqlalchemy import text

from app import create_app, db
from app.system import schema_head


def config(**changes):
    values = {'TESTING': True, 'SECRET_KEY': 'teste-aleatorio-' + 'a' * 64,
              'SQLALCHEMY_DATABASE_URI': 'postgresql+psycopg://test:example@127.0.0.1/estoque_ci',
              'APP_ENV': 'production', 'SESSION_COOKIE_SECURE': True,
              'PUBLIC_BASE_URL': 'https://estoquebc.ldalogistica.com.br',
              'TRUSTED_HOSTS': ['estoquebc.ldalogistica.com.br'], 'TRUST_PROXY': True}
    values.update(changes)
    return values


@pytest.mark.parametrize('changes,reason', [
    ({'SQLALCHEMY_DATABASE_URI': 'sqlite://'}, 'PostgreSQL|postgresql'),
    ({'SESSION_COOKIE_SECURE': False}, 'COOKIE_SECURE'),
    ({'DEBUG': True}, 'FLASK_DEBUG'),
    ({'SECRET_KEY': 'SUBSTITUA_POR_UMA_CHAVE_ALEATORIA_DE_EXEMPLO'}, 'SECRET_KEY'),
    ({'PUBLIC_BASE_URL': 'http://estoquebc.ldalogistica.com.br'}, 'HTTPS'),
    ({'PUBLIC_BASE_URL': 'https://estoquebc.ldalogistica.com.br/login'}, 'sem caminho'),
    ({'TRUSTED_HOSTS': ['outro.exemplo.com']}, 'TRUSTED_HOSTS'),
])
def test_production_rejects_unsafe_configuration(changes, reason):
    with pytest.raises(RuntimeError, match=reason):
        create_app(config(**changes))


def test_public_install_and_hosts_do_not_need_database():
    # Nenhum PostgreSQL está disponível neste endereço: recursos públicos devem funcionar mesmo assim.
    app = create_app(config())
    client = app.test_client()
    base = 'https://estoquebc.ldalogistica.com.br'
    assert client.get('/instalar', base_url=base).status_code == 200
    assert client.get('/sw.js', base_url=base).status_code == 200
    assert client.get('/instalar', base_url='https://intruso.example').status_code == 400
    assert client.get('/static/manifest.webmanifest', base_url=base).status_code == 200
    assert client.get('/produtos', base_url=base).status_code == 302


def test_manifest_icons_and_scope():
    app = create_app({'TESTING': True, 'SECRET_KEY': 's' * 64,
                      'SQLALCHEMY_DATABASE_URI': 'sqlite://', 'APP_ENV': 'development'})
    client = app.test_client()
    response = client.get('/static/manifest.webmanifest')
    assert 'manifest+json' in response.content_type
    manifest = json.loads(response.data)
    assert manifest['id'] == '/' and manifest['scope'] == '/' and manifest['start_url'] == '/'
    assert manifest['display'] == 'standalone'
    assert not manifest['prefer_related_applications']
    dimensions = set()
    for icon in manifest['icons']:
        resource = client.get(icon['src'])
        assert resource.status_code == 200
        dimensions.add(Image.open(io.BytesIO(resource.data)).size)
    assert {(192, 192), (512, 512)} <= dimensions
    html = client.get('/instalar').text
    assert 'apple-touch-icon' in html and 'pwa-install-button' in html


def test_readiness_reports_schema_without_sensitive_details():
    app = create_app({'TESTING': True, 'SECRET_KEY': 's' * 64,
                      'SQLALCHEMY_DATABASE_URI': 'sqlite://', 'APP_ENV': 'development'})
    client = app.test_client()
    assert client.get('/healthz').status_code == 503
    assert client.get('/healthz').json == {'status': 'unavailable'}
    with app.app_context():
        with db.engine.begin() as connection:
            connection.execute(text('CREATE TABLE alembic_version (version_num VARCHAR(32))'))
            connection.execute(text('INSERT INTO alembic_version VALUES (:revision)'), {'revision': schema_head()})
    assert client.get('/healthz').json == {'status': 'ok'}
