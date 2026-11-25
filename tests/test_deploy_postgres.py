"""Integração opcional: roda no CI com PostgreSQL 16 exclusivo e sem dados reais."""
import os

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app import create_app, db
from app.models import Product, Balance, User
from deploy.release import LOCK_ID, migrate


def test_postgres_release_is_repeatable_and_serialized():
    url = os.getenv('TEST_POSTGRES_URL')
    if not url:
        pytest.skip('Defina TEST_POSTGRES_URL apontando para banco exclusivo terminado em _ci ou _test.')
    assert make_url(url).database.endswith(('_ci', '_test')), 'Use somente um banco dedicado de testes.'
    app = create_app({'TESTING': True, 'SECRET_KEY': 'test-' + 'z' * 64, 'APP_ENV': 'production',
                      'PUBLIC_BASE_URL': 'https://estoquebc.ldalogistica.com.br',
                      'TRUSTED_HOSTS': ['estoquebc.ldalogistica.com.br'],
                      'SESSION_COOKIE_SECURE': True, 'SQLALCHEMY_DATABASE_URI': url})
    migrate(app, timeout=30)
    with app.app_context():
        assert db.session.scalar(text('SELECT rolsuper FROM pg_roles WHERE rolname = current_user')) is False
        assert User.query.count() == 0  # O release não inventa contas ou senhas.
        product = Product(sku='RELEASE-CI', name='Teste de preservação', category='MIX')
        db.session.add(product)
        db.session.flush()
        db.session.add(Balance(product_id=product.id, zone='ARMAZENADO', quantity=42))
        db.session.commit()
    migrate(app, timeout=30)
    with app.app_context():
        assert Balance.query.one().quantity == 42
        with db.engine.connect() as other:
            other.execute(text('SELECT pg_advisory_lock(:key)'), {'key': LOCK_ID})
            other.commit()
            try:
                with pytest.raises(RuntimeError, match='Outra implantação'):
                    migrate(app, timeout=0)
            finally:
                other.execute(text('SELECT pg_advisory_unlock(:key)'), {'key': LOCK_ID})
                other.commit()
    client = app.test_client()
    assert client.get('/healthz', base_url='https://estoquebc.ldalogistica.com.br').json == {'status': 'ok'}
