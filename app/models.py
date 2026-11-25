from datetime import datetime, timezone
from flask_login import UserMixin
from sqlalchemy import CheckConstraint, Index, UniqueConstraint, text
from werkzeug.security import check_password_hash, generate_password_hash
from . import db


def utcnow():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, unique=True)
    name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(12), nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    auth_version = db.Column(db.Integer, nullable=False, default=1)
    email = db.Column(db.String(254), unique=True)
    pending_email = db.Column(db.String(254))
    email_verified = db.Column(db.Boolean, nullable=False, default=False)
    avatar = db.Column(db.String(40), nullable=False, default='avatar-1')
    must_change_password = db.Column(db.Boolean, nullable=False, default=False)
    temporary_until = db.Column(db.DateTime(timezone=True))
    failed_attempts = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    __table_args__ = (CheckConstraint("role IN ('admin', 'lojista', 'assistente')", name='ck_user_role'),)

    def get_id(self):
        return f'{self.id}:{self.auth_version}'

    @property
    def is_active(self):
        return self.active

    def set_password(self, password):
        if len(password) < 12 or len(password) > 128:
            raise ValueError('A senha deve ter entre 12 e 128 caracteres.')
        self.password_hash = generate_password_hash(password, method='scrypt')
        self.auth_version += 1

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(40), nullable=False, unique=True)
    barcode = db.Column(db.String(40), unique=True)
    name = db.Column(db.String(180), nullable=False)
    category = db.Column(db.String(20), nullable=False)
    unit = db.Column(db.String(20), nullable=False, default='UN')
    # Uma embalagem do tipo INVENTARIO pode representar várias unidades soltas.
    # Esse fator informa a quantidade na venda; não altera automaticamente estoque.
    sale_multiple = db.Column(db.Integer, nullable=False, default=1)
    min_store = db.Column(db.Integer, nullable=False, default=0)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    __table_args__ = (CheckConstraint("category IN ('MIX','INVENTARIO','SAZONAIS','ACESSORIOS')", name='ck_product_category'),
                      CheckConstraint('sale_multiple > 0'), CheckConstraint('min_store >= 0'))


class Balance(db.Model):
    __tablename__ = 'balances'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    zone = db.Column(db.String(12), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    version = db.Column(db.Integer, nullable=False, default=0)
    product = db.relationship('Product')
    __table_args__ = (UniqueConstraint('product_id', 'zone'),
                      CheckConstraint("zone IN ('LOJA','ARMAZENADO')"),
                      CheckConstraint('quantity >= 0'))


class Movement(db.Model):
    __tablename__ = 'movements'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    sku_snapshot = db.Column(db.String(40), nullable=False)
    name_snapshot = db.Column(db.String(180), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    sale_id = db.Column(db.String(36))
    customer = db.relationship('Customer')
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    kind = db.Column(db.String(20), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    source = db.Column(db.String(12))
    destination = db.Column(db.String(12))
    reason = db.Column(db.String(300), nullable=False)
    reference = db.Column(db.String(100))
    occurred_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    product = db.relationship('Product')
    actor = db.relationship('User')
    __table_args__ = (CheckConstraint('quantity > 0'),)


class StockCount(db.Model):
    __tablename__ = 'stock_counts'
    id = db.Column(db.Integer, primary_key=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    status = db.Column(db.String(20), nullable=False, default='rascunho')
    opened_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    submitted_at = db.Column(db.DateTime(timezone=True))
    approved_at = db.Column(db.DateTime(timezone=True))
    notes = db.Column(db.String(300))
    lines = db.relationship('CountLine', back_populates='count', order_by='CountLine.id')
    __table_args__ = (Index('uq_one_open_count', text('(1)'), unique=True,
                            postgresql_where=text("status IN ('rascunho','enviada')"),
                            sqlite_where=text("status IN ('rascunho','enviada')")),)


class CountLine(db.Model):
    __tablename__ = 'count_lines'
    id = db.Column(db.Integer, primary_key=True)
    count_id = db.Column(db.Integer, db.ForeignKey('stock_counts.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    zone = db.Column(db.String(12), nullable=False)
    expected = db.Column(db.Integer, nullable=False)
    expected_version = db.Column(db.Integer, nullable=False, default=0)
    counted = db.Column(db.Integer)
    note = db.Column(db.String(300))
    revision = db.Column(db.Integer, nullable=False, default=0)
    count = db.relationship('StockCount', back_populates='lines')
    product = db.relationship('Product')
    __table_args__ = (UniqueConstraint('count_id', 'product_id', 'zone'),
                      CheckConstraint('expected >= 0'), CheckConstraint('counted >= 0'))


class Customer(db.Model):
    __tablename__ = 'customers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    document = db.Column(db.String(30), unique=True)
    phone = db.Column(db.String(40))
    active = db.Column(db.Boolean, nullable=False, default=True)


class Lot(db.Model):
    __tablename__ = 'lots'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    code = db.Column(db.String(80), nullable=False)
    expires_on = db.Column(db.Date)
    zone = db.Column(db.String(12), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    product = db.relationship('Product')
    __table_args__ = (CheckConstraint('quantity >= 0'),)


class Receipt(db.Model):
    __tablename__ = 'receipts'
    id = db.Column(db.Integer, primary_key=True)
    document_key = db.Column(db.String(80), unique=True, nullable=False)
    imported_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    payload = db.Column(db.JSON, nullable=False)
    confirmed_at = db.Column(db.DateTime(timezone=True))


class DirectSale(db.Model):
    __tablename__ = 'direct_sales'
    id = db.Column(db.String(36), primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)


class LotChange(db.Model):
    __tablename__ = 'lot_changes'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    reviewed_at = db.Column(db.DateTime(timezone=True))
    status = db.Column(db.String(20), nullable=False, default='pendente')
    reason = db.Column(db.String(300), nullable=False)
    before = db.Column(db.JSON, nullable=False)
    after = db.Column(db.JSON, nullable=False)
    versions = db.Column(db.JSON, nullable=False)
    product = db.relationship('Product')
    actor = db.relationship('User', foreign_keys=[actor_id])
    reviewer = db.relationship('User', foreign_keys=[reviewer_id])


class SupplierProduct(db.Model):
    __tablename__ = 'supplier_products'
    id = db.Column(db.Integer, primary_key=True)
    supplier_code = db.Column(db.String(80), unique=True, nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)


class AccountToken(db.Model):
    __tablename__ = 'account_tokens'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    digest = db.Column(db.String(64), unique=True, nullable=False)
    purpose = db.Column(db.String(20), nullable=False)
    value = db.Column(db.String(254))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    used = db.Column(db.Boolean, nullable=False, default=False)


class AccountAudit(db.Model):
    __tablename__ = 'account_audit'
    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)


class AuthThrottle(db.Model):
    __tablename__ = 'auth_throttles'
    key = db.Column(db.String(64), primary_key=True)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    started_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
