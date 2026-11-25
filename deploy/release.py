"""Aguarda PostgreSQL e aplica migrações uma vez por vez antes de iniciar workers."""
import os
import sys
import time

from flask_migrate import upgrade
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app import create_app, db

LOCK_ID = 7210261125


def migrate(app, timeout=120):
    deadline = time.monotonic() + timeout
    with app.app_context():
        if db.engine.dialect.name != 'postgresql':
            raise RuntimeError('O comando de produção requer PostgreSQL.')
        connection = None
        while connection is None:
            try:
                connection = db.engine.connect()
            except OperationalError:
                if time.monotonic() >= deadline:
                    raise RuntimeError('PostgreSQL indisponível. Confira o host interno e as credenciais.') from None
                time.sleep(2)
        locked = False
        try:
            # Lock de sessão: permanece ativo enquanto Alembic usa outra conexão.
            while not locked:
                locked = connection.scalar(text('SELECT pg_try_advisory_lock(:key)'), {'key': LOCK_ID})
                connection.commit()
                if not locked:
                    if time.monotonic() >= deadline:
                        raise RuntimeError('Outra implantação ainda está aplicando migrações.')
                    time.sleep(2)
            print('PostgreSQL disponível. Aplicando migrações pendentes...', flush=True)
            upgrade()
            print('Migrações concluídas. Nenhum catálogo ou usuário foi criado automaticamente.', flush=True)
        finally:
            try:
                if locked:
                    connection.execute(text('SELECT pg_advisory_unlock(:key)'), {'key': LOCK_ID})
                    connection.commit()
            finally:
                connection.close()


if __name__ == '__main__':
    try:
        migrate(create_app(), timeout=int(os.getenv('DATABASE_STARTUP_TIMEOUT', '120')))
    except RuntimeError as error:
        # Mensagens de validação definidas acima não contêm valores de segredos.
        print(f'Inicialização interrompida: {error}', file=sys.stderr)
        sys.exit(1)
    except Exception as error:
        # Evita colocar URL do banco ou segredos nos logs de implantação.
        print(f'Inicialização interrompida ({type(error).__name__}). Confira as variáveis, '
              'a disponibilidade do PostgreSQL e a revisão das migrações.', file=sys.stderr)
        sys.exit(1)
