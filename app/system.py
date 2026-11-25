"""Instalação pública do PWA e prontidão sem exposição de informações internas."""
from functools import lru_cache
from pathlib import Path

from alembic.script import ScriptDirectory
from flask import Blueprint, jsonify, render_template
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from . import db

system = Blueprint('system', __name__)


@lru_cache(maxsize=1)
def schema_head():
    return ScriptDirectory(str(Path(__file__).resolve().parent.parent / 'migrations')).get_current_head()


@system.get('/healthz')
def health():
    # Não acessa contas, saldos ou contatos; resposta genérica também nas falhas.
    try:
        with db.engine.connect() as connection:
            revision = connection.scalar(text('SELECT version_num FROM alembic_version'))
        if revision == schema_head():
            return jsonify(status='ok')
    except SQLAlchemyError:
        pass
    return jsonify(status='unavailable'), 503


@system.get('/instalar')
def install():
    return render_template('install.html')
