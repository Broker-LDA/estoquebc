"""Perfis, aprovação de lotes, vínculos de NF e segurança de contas."""
from alembic import op
import sqlalchemy as sa
revision='f20b20261124'
down_revision='f10b20261124'
branch_labels=None
depends_on=None


def upgrade():
    bind=op.get_bind()
    checks=sa.inspect(bind).get_check_constraints('users')
    with op.batch_alter_table('users',naming_convention={'ck':'ck_%(table_name)s_%(column_0_name)s'}) as b:
        for c in checks:
            if 'role' in c['sqltext']: b.drop_constraint(c['name'] or 'ck_users_',type_='check')
        b.create_check_constraint('ck_user_role',"role IN ('admin','lojista','assistente')")
        b.add_column(sa.Column('email',sa.String(254)))
        b.add_column(sa.Column('pending_email',sa.String(254)))
        b.add_column(sa.Column('email_verified',sa.Boolean,nullable=False,server_default=sa.false()))
        b.add_column(sa.Column('avatar',sa.String(40),nullable=False,server_default='avatar-1'))
        b.add_column(sa.Column('must_change_password',sa.Boolean,nullable=False,server_default=sa.false()))
        b.add_column(sa.Column('temporary_until',sa.DateTime(timezone=True)))
        b.create_unique_constraint('uq_user_email',['email'])
    with op.batch_alter_table('count_lines', table_args=(sa.CheckConstraint('expected >= 0',name='ck_count_expected'),sa.CheckConstraint('counted >= 0',name='ck_count_counted')) if bind.dialect.name=='sqlite' else ()) as b:
        b.add_column(sa.Column('revision',sa.Integer,nullable=False,server_default='0'))
    op.create_table('lot_changes',sa.Column('id',sa.Integer,primary_key=True),sa.Column('product_id',sa.Integer,sa.ForeignKey('products.id'),nullable=False),sa.Column('actor_id',sa.Integer,sa.ForeignKey('users.id'),nullable=False),sa.Column('reviewer_id',sa.Integer,sa.ForeignKey('users.id')),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('reviewed_at',sa.DateTime(timezone=True)),sa.Column('status',sa.String(20),nullable=False),sa.Column('reason',sa.String(300),nullable=False),sa.Column('before',sa.JSON,nullable=False),sa.Column('after',sa.JSON,nullable=False),sa.Column('versions',sa.JSON,nullable=False))
    op.create_table('supplier_products',sa.Column('id',sa.Integer,primary_key=True),sa.Column('supplier_code',sa.String(80),nullable=False,unique=True),sa.Column('product_id',sa.Integer,sa.ForeignKey('products.id'),nullable=False))
    op.create_table('account_tokens',sa.Column('id',sa.Integer,primary_key=True),sa.Column('user_id',sa.Integer,sa.ForeignKey('users.id'),nullable=False),sa.Column('digest',sa.String(64),nullable=False,unique=True),sa.Column('purpose',sa.String(20),nullable=False),sa.Column('value',sa.String(254)),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),sa.Column('used',sa.Boolean,nullable=False))
    op.create_table('auth_throttles',sa.Column('key',sa.String(64),primary_key=True),sa.Column('attempts',sa.Integer,nullable=False),sa.Column('started_at',sa.DateTime(timezone=True),nullable=False))
    op.create_table('account_audit',sa.Column('id',sa.Integer,primary_key=True),sa.Column('actor_id',sa.Integer,sa.ForeignKey('users.id'),nullable=False),sa.Column('user_id',sa.Integer,sa.ForeignKey('users.id'),nullable=False),sa.Column('action',sa.String(120),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))


def downgrade():
    raise RuntimeError('Restaure backup para reverter esta atualização operacional.')
