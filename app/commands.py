import csv
from pathlib import Path
import click
from flask import current_app
from flask.cli import with_appcontext
from sqlalchemy import select
from . import db
from .models import Balance, Product, User


def register_commands(app):
    from .reset_stock import register_reset_command
    register_reset_command(app)

    @app.cli.command('create-admin')
    @click.option('--username', prompt='Login', help='Login inicial do administrador')
    @click.option('--name', prompt='Nome', help='Nome exibido')
    @click.password_option(confirmation_prompt=True)
    @with_appcontext
    def create_admin(username, name, password):
        username = username.strip().lower()
        if not username or db.session.scalar(select(User.id).where(User.username == username)):
            raise click.ClickException('Login inválido ou já cadastrado.')
        user = User(username=username, name=name.strip(), role='admin', active=True, auth_version=0)
        try:
            user.set_password(password)
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
        db.session.add(user)
        db.session.commit()
        click.echo('Administrador criado.')

    @app.cli.command('import-catalog')
    @with_appcontext
    def import_catalog():
        """Importa somente catálogo extraído dos PDFs, sem aplicar saldos antigos."""
        path = Path(current_app.root_path).parent / 'data' / 'catalogo_referencia_2026-08-21.csv'
        created = 0
        with path.open(encoding='utf-8-sig', newline='') as file:
            for row in csv.DictReader(file):
                if db.session.scalar(select(Product.id).where(Product.sku == row['sku'])):
                    continue
                p = Product(sku=row['sku'], barcode=row['barcode'], name=row['name'],
                            category=row['category'], unit='UN', sale_multiple=1, active=True)
                db.session.add(p)
                db.session.flush()
                for zone in ('LOJA','ARMAZENADO'):
                    db.session.add(Balance(product_id=p.id, zone=zone, quantity=0))
                created += 1
        db.session.commit()
        click.echo(f'{created} produtos adicionados. Saldos em zero até a primeira conferência.')
