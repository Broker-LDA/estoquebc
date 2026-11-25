"""Clientes, lotes, recebimentos e novas categorias; preserva saldos existentes."""
from alembic import op
import sqlalchemy as sa
revision = 'f10b20261124'
down_revision = 'e20ec54d50fe'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    # PostgreSQL atribuiu nome automático ao CHECK original; localize pela expressão.
    checks = sa.inspect(bind).get_check_constraints('products')
    category_checks = [c for c in checks if 'category' in c['sqltext']]
    if bind.dialect.name == 'sqlite':
        with op.batch_alter_table('products', naming_convention={'ck': 'ck_%(table_name)s_%(column_0_name)s'}) as batch:
            for c in category_checks:
                batch.drop_constraint(c['name'] or 'ck_products_', type_='check')
            batch.create_check_constraint('ck_product_multiple', 'sale_multiple > 0')
            batch.create_check_constraint('ck_product_minimum', 'min_store >= 0')
            batch.create_check_constraint('ck_product_category', "category IN ('MIX','INVENTARIO','SAZONAIS','ACESSORIOS')")
    else:
        for c in category_checks:
            op.drop_constraint(c['name'], 'products', type_='check')
        op.create_check_constraint('ck_product_category', 'products', "category IN ('MIX','INVENTARIO','SAZONAIS','ACESSORIOS')")
    op.create_table('customers', sa.Column('id', sa.Integer, primary_key=True), sa.Column('name', sa.String(120), nullable=False),
                    sa.Column('document', sa.String(30), unique=True), sa.Column('phone', sa.String(40)),
                    sa.Column('active', sa.Boolean, nullable=False))
    op.create_table('direct_sales', sa.Column('id', sa.String(36), primary_key=True),
                    sa.Column('customer_id', sa.Integer, sa.ForeignKey('customers.id'), nullable=False),
                    sa.Column('actor_id', sa.Integer, sa.ForeignKey('users.id'), nullable=False),
                    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_table('lots', sa.Column('id', sa.Integer, primary_key=True),
                    sa.Column('product_id', sa.Integer, sa.ForeignKey('products.id'), nullable=False),
                    sa.Column('code', sa.String(80), nullable=False), sa.Column('expires_on', sa.Date),
                    sa.Column('zone', sa.String(12), nullable=False), sa.Column('quantity', sa.Integer, nullable=False),
                    sa.CheckConstraint('quantity >= 0'))
    op.create_table('receipts', sa.Column('id', sa.Integer, primary_key=True),
                    sa.Column('document_key', sa.String(80), nullable=False, unique=True),
                    sa.Column('imported_by', sa.Integer, sa.ForeignKey('users.id'), nullable=False),
                    sa.Column('payload', sa.JSON, nullable=False), sa.Column('confirmed_at', sa.DateTime(timezone=True)))
    with op.batch_alter_table('movements', table_args=(sa.CheckConstraint('quantity > 0', name='ck_movement_positive'),) if bind.dialect.name=='sqlite' else ()) as batch:
        batch.add_column(sa.Column('customer_id', sa.Integer))
        batch.add_column(sa.Column('sale_id', sa.String(36)))
        batch.create_foreign_key('fk_movement_customer', 'customers', ['customer_id'], ['id'])
    bind.execute(sa.text("INSERT INTO lots (product_id, code, zone, quantity) SELECT product_id, 'Saldo anterior - validade não informada', zone, quantity FROM balances WHERE quantity > 0"))


def downgrade():
    raise RuntimeError('Migração com dados operacionais: restaure backup para reverter com segurança.')
