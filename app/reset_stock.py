"""Reset auditado dos saldos para homologação, executado somente pelo terminal."""
from uuid import uuid4
import click
from sqlalchemy import select
from . import db
from .models import User, Balance, Lot, Movement, StockCount, Product


def register_reset_command(app):
    @app.cli.command('reset-stock')
    @click.option('--admin', prompt='Login do administrador')
    @click.option('--dry-run', is_flag=True, help='Mostra totais sem alterar saldos.')
    @click.option('--cancel-open-counts', is_flag=True, help='Cancela conferências abertas, preservando suas linhas.')
    def reset_stock(admin, dry_run, cancel_open_counts):
        """Zera loja, armazenado e lotes; mantém catálogo e histórico. Pare o Flask antes."""
        password = click.prompt('Senha do administrador', hide_input=True)
        user = db.session.scalar(select(User).where(User.username == admin.strip().lower()))
        if not user or not user.active or user.role != 'admin' or not user.check_password(password):
            db.session.rollback()
            raise click.ClickException('Credenciais administrativas inválidas.')
        try:
            # A operação é exclusiva. A autenticação é revalidada após os locks.
            if db.engine.dialect.name == 'postgresql':
                from sqlalchemy import text
                db.session.execute(text('SET LOCAL lock_timeout = \'5s\''))
                db.session.execute(text('LOCK TABLE users, stock_counts, products, balances, lots, movements IN EXCLUSIVE MODE'))
            db.session.refresh(user)
            if not user.active or user.role != 'admin' or not user.check_password(password):
                raise click.ClickException('Acesso administrativo alterado. Tente novamente.')
            counts = db.session.scalars(select(StockCount).where(StockCount.status.in_(('rascunho','enviada')))
                                        .order_by(StockCount.id).with_for_update()).all()
            balances = db.session.scalars(select(Balance).order_by(Balance.product_id, Balance.zone)
                                          .with_for_update()).all()
            lots = db.session.scalars(select(Lot).order_by(Lot.product_id, Lot.zone, Lot.id).with_for_update()).all()
            totals = {zone: sum(b.quantity for b in balances if b.zone == zone) for zone in ('LOJA','ARMAZENADO')}
            click.echo(f'Loja: {totals["LOJA"]} unidades. Armazenado: {totals["ARMAZENADO"]} unidades.')
            click.echo(f'Conferências abertas: {len(counts)}. Catálogo, usuários, clientes e documentos serão preservados.')
            if dry_run:
                click.echo('SIMULAÇÃO: nenhum saldo alterado.')
                return
            if counts and not cancel_open_counts:
                raise click.ClickException('Há conferências abertas. Finalize-as ou repita com --cancel-open-counts para cancelá-las.')
            # Confere a integridade antes de zerar, evitando esconder divergências internas.
            lot_totals = {}
            for lot in lots:
                key = (lot.product_id, lot.zone)
                lot_totals[key] = lot_totals.get(key, 0) + lot.quantity
            balance_totals = {(b.product_id,b.zone):b.quantity for b in balances}
            if any(lot_totals.get(key,0) != balance_totals.get(key,0) for key in set(lot_totals)|set(balance_totals)):
                raise click.ClickException('Lotes e saldos estão divergentes. Corrija a conciliação antes de zerar.')
            if click.prompt('Digite ZERAR para confirmar', default='', show_default=False) != 'ZERAR':
                raise click.ClickException('Operação cancelada; nenhum saldo alterado.')
            reference = 'RESET-TESTE-' + str(uuid4())
            for count in counts:
                count.status = 'cancelada'
                count.notes = f'Cancelada no reset de testes por {user.username}. {reference}'
            products = {p.id:p for p in db.session.scalars(select(Product))}
            changes = 0
            for balance in balances:
                if balance.quantity:
                    p = products[balance.product_id]
                    db.session.add(Movement(product_id=p.id, sku_snapshot=p.sku, name_snapshot=p.name,
                        actor_id=user.id, kind='ajuste_teste', quantity=balance.quantity,
                        source=balance.zone, destination=None,
                        reason='Zeragem de saldo para iniciar testes de homologação.', reference=reference))
                    changes += 1
                    balance.quantity = 0
                    balance.version += 1
            for lot in lots:
                lot.quantity = 0
            db.session.commit()
            click.echo(f'Estoque zerado. {changes} ajustes registrados. Referência: {reference}')
            click.echo('Notas já confirmadas permanecem bloqueadas contra duplicidade. Reposição é um acumulado histórico e não é apagada.')
        except click.ClickException:
            raise
        except Exception as exc:
            # Não imprime DSN/senhas em falhas de banco.
            raise click.ClickException('Não foi possível zerar; transação desfeita. Verifique se o sistema está parado e o banco atualizado.') from exc
        finally:
            db.session.rollback()
