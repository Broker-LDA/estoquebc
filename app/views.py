import csv
import io
from datetime import timedelta, timezone, date
from functools import wraps
from flask import (Blueprint, Response, abort, current_app, flash, redirect,
                   render_template, request, url_for)
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from . import db
from .models import Balance, CountLine, Movement, Product, StockCount, User, Lot, utcnow
from .permissions import managers
from .services import ZONES, approve_count, move, positive_integer, save_line, start_count, submit_count

bp = Blueprint('main', __name__)


def admin_only(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.role != 'admin':
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def finish(action, success, fallback):
    try:
        result = action()
        flash(success, 'success')
        return result or redirect(fallback)
    except (ValueError, IntegrityError) as exc:
        db.session.rollback()
        message = str(exc) if isinstance(exc, ValueError) else 'Registro conflitante. Recarregue a página e tente novamente.'
        flash(message, 'error')
        return redirect(fallback)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')
        user = db.session.execute(select(User).where(User.username == username).with_for_update()).scalar_one_or_none()
        now = utcnow()
        locked = user and user.locked_until and user.locked_until.replace(tzinfo=timezone.utc) > now
        expired = user and user.must_change_password and user.temporary_until and user.temporary_until.replace(tzinfo=timezone.utc) <= now
        if user and user.active and not locked and not expired and user.check_password(password):
            user.failed_attempts = 0
            user.locked_until = None
            db.session.commit()
            login_user(user, remember=False, fresh=True)
            return redirect(url_for('account.profile' if user.must_change_password else 'main.dashboard'))
        if user and user.active and not locked:
            user.failed_attempts += 1
            if user.failed_attempts >= 5:
                user.failed_attempts = 0
                user.locked_until = now + timedelta(minutes=15)
            db.session.commit()
        flash('Credenciais inválidas ou conta temporariamente bloqueada.', 'error')
    return render_template('login.html')


@bp.post('/logout')
@login_required
def logout():
    logout_user()
    flash('Sessão encerrada.', 'success')
    return redirect(url_for('main.login'))


@bp.get('/')
@login_required
def dashboard():
    products = db.session.execute(select(Product).where(Product.active.is_(True)).order_by(Product.name)).scalars().all()
    balances = db.session.execute(select(Balance)).scalars().all()
    by_id = {(b.product_id, b.zone): b.quantity for b in balances}
    store = sum(by_id.get((p.id, 'LOJA'), 0) for p in products)
    stored = sum(by_id.get((p.id, 'ARMAZENADO'), 0) for p in products)
    today=utcnow().astimezone(timezone(timedelta(hours=-3))).date()
    low = db.session.scalars(select(Lot).join(Product).where(Product.active.is_(True), Lot.quantity > 0,
        Lot.expires_on <= today + timedelta(days=current_app.config['EXPIRY_ALERT_DAYS']))
        .order_by(Lot.expires_on, Product.name)).all()
    alert_products={}
    for lot in low:
        alert_products.setdefault(lot.product_id,{'product':lot.product,'lots':[]})['lots'].append(lot)
    received = db.session.scalar(select(func.coalesce(func.sum(Movement.quantity),0)).where(Movement.kind=='entrada'))
    unknown = db.session.scalar(select(func.coalesce(func.sum(Lot.quantity),0)).where(Lot.expires_on.is_(None)))
    latest = db.session.execute(select(Movement).order_by(Movement.id.desc()).limit(8)).scalars().all()
    approved = db.session.execute(select(StockCount).where(StockCount.status == 'aprovada')
                                  .order_by(StockCount.id.desc()).limit(1)).scalar_one_or_none()
    pending = db.session.execute(select(StockCount).where(StockCount.status.in_(('rascunho','enviada')))
                                 .order_by(StockCount.id.desc()).limit(1)).scalar_one_or_none()
    due = not approved or (utcnow() - approved.approved_at.replace(tzinfo=timezone.utc)).days >= current_app.config['COUNT_INTERVAL_DAYS']
    return render_template('dashboard.html', products=products, store=store, stored=stored,
                           low=low, alert_products=alert_products.values(), received=received, unknown=unknown, today=today, latest=latest, approved=approved, pending=pending, due=due)


@bp.get('/produtos')
@login_required
def products():
    q = request.args.get('q', '').strip()[:80]
    category = request.args.get('category', '')
    query = select(Product).where(Product.active.is_(True))
    if q:
        query = query.where(or_(Product.name.ilike(f'%{q}%'), Product.sku.ilike(f'%{q}%'), Product.barcode.ilike(f'%{q}%')))
    if category in ('MIX', 'INVENTARIO', 'SAZONAIS', 'ACESSORIOS'):
        query = query.where(Product.category == category)
    pagination = db.paginate(query.order_by(Product.name), page=max(1,request.args.get('page',1,type=int) or 1), per_page=10, error_out=False)
    items = pagination.items
    balances = {(b.product_id,b.zone): b.quantity for b in db.session.execute(select(Balance)).scalars()}
    return render_template('products.html', items=items, balances=balances, q=q, category=category, pagination=pagination)


@bp.route('/produtos/novo', methods=['GET', 'POST'])
@login_required
def new_product():
    if request.method == 'POST':
        return finish(lambda: persist_product(None), 'Produto cadastrado.', url_for('main.new_product'))
    return render_template('product_form.html', product=None)


@bp.route('/produtos/<int:product_id>/editar', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    product = db.get_or_404(Product, product_id)
    if request.method == 'POST':
        return finish(lambda: persist_product(product), 'Produto atualizado.', request.path)
    return render_template('product_form.html', product=product)


def persist_product(product):
    sku = request.form.get('sku', '').strip().upper()
    barcode = request.form.get('barcode', '').strip() or None
    name = request.form.get('name', '').strip()
    category = request.form.get('category', '')
    unit = request.form.get('unit', 'UN').strip().upper()
    if not (1 <= len(sku) <= 40 and 2 <= len(name) <= 180 and len(unit) <= 20 and unit):
        raise ValueError('Confira código, descrição e unidade.')
    if barcode and (len(barcode) > 40 or not barcode.isdigit()):
        raise ValueError('Código de barras deve conter apenas números.')
    if category not in ('MIX', 'INVENTARIO', 'SAZONAIS', 'ACESSORIOS'):
        raise ValueError('Selecione uma linha válida.')
    multiple = positive_integer(request.form.get('sale_multiple', '1'), 'Fator de venda')
    minimum = int(request.form.get('min_store', '0'))
    if minimum < 0 or minimum > 1_000_000:
        raise ValueError('Estoque mínimo inválido.')
    if product is None:
        product = Product()
        db.session.add(product)
    product.sku, product.barcode, product.name = sku, barcode, name
    product.category, product.unit = category, unit
    product.sale_multiple, product.min_store = multiple, minimum
    db.session.flush()
    for zone in ZONES:
        existing = db.session.execute(select(Balance).where(Balance.product_id == product.id, Balance.zone == zone)).scalar_one_or_none()
        if existing is None:
            db.session.add(Balance(product_id=product.id, zone=zone, quantity=0))
    db.session.commit()
    return redirect(url_for('main.products'))


@bp.post('/produtos/<int:product_id>/arquivar')
@login_required
def archive_product(product_id):
    def action():
        product = db.session.execute(select(Product).where(Product.id == product_id)
                                     .with_for_update()).scalar_one_or_none()
        if product is None:
            abort(404)
        balances = db.session.execute(select(Balance).where(Balance.product_id == product_id).with_for_update()).scalars().all()
        if any(b.quantity for b in balances):
            raise ValueError('Zere os saldos com movimentações justificadas antes de arquivar.')
        pending = db.session.execute(select(CountLine).join(StockCount).where(CountLine.product_id == product_id,
                          StockCount.status.in_(('rascunho','enviada')))).first()
        if pending:
            raise ValueError('Produto incluído em conferência aberta.')
        product.active = False
        db.session.commit()
    return finish(action, 'Produto arquivado sem apagar o histórico.', url_for('main.products'))


@bp.route('/movimentar', methods=['GET', 'POST'])
@login_required
def movement_form():
    if request.method == 'POST':
        def action():
            if request.form.get('kind') == 'venda':
                raise ValueError('Registre as vendas na tela Venda direta com cliente e itens.')
            if request.form.get('kind') in ('entrada','devolucao'):
                p = db.session.get(Product, int(request.form.get('product_id',0)))
                if p and p.category != 'ACESSORIOS' and not request.form.get('expires_on'):
                    raise ValueError('Informe a validade do item alimentício na entrada.')
            move(int(request.form.get('product_id', 0)), current_user.id,
                 request.form.get('kind', ''), request.form.get('quantity', ''),
                 request.form.get('source',''), request.form.get('destination',''),
                 request.form.get('reason',''), request.form.get('reference',''),
                 lot_code=request.form.get('lot_code',''),
                 expires_on=date.fromisoformat(request.form['expires_on']) if request.form.get('expires_on') else None)
            return redirect(url_for('main.movements'))
        return finish(action, 'Movimentação registrada.', url_for('main.movement_form'))
    items = db.session.execute(select(Product).where(Product.active.is_(True)).order_by(Product.name)).scalars().all()
    selected = request.args.get('product_id', type=int)
    return render_template('movement_form.html', items=items, selected=selected)


@bp.get('/movimentacoes')
@login_required
def movements():
    entries = db.session.execute(select(Movement).order_by(Movement.id.desc()).limit(250)).scalars().all()
    return render_template('movements.html', entries=entries)


@bp.get('/movimentacoes.csv')
@login_required
def export_movements():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['id', 'data_utc', 'sku', 'produto', 'operador', 'tipo', 'quantidade', 'origem', 'destino', 'motivo', 'referencia', 'cliente', 'venda'])
    def safe(value):
        s = str(value or '')
        return "'" + s if s.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')) else s
    for m in db.session.execute(select(Movement).order_by(Movement.id)).scalars():
        writer.writerow([m.id, m.occurred_at.isoformat(), safe(m.sku_snapshot), safe(m.name_snapshot),
                         safe(m.actor.name), m.kind, m.quantity, m.source, m.destination, safe(m.reason), safe(m.reference), safe(m.customer.name if m.customer else ''), m.sale_id])
    return Response('\ufeff' + output.getvalue(), mimetype='text/csv; charset=utf-8',
                    headers={'Content-Disposition':'attachment; filename=movimentacoes.csv'})


@bp.get('/conferencias')
@login_required
def counts():
    entries = db.session.execute(select(StockCount).order_by(StockCount.id.desc()).limit(50)).scalars().all()
    return render_template('counts.html', entries=entries)


@bp.post('/conferencias/abrir')
@login_required
def new_count():
    return finish(lambda: redirect(url_for('main.count_detail', count_id=start_count(current_user.id).id)),
                  'Conferência aberta.', url_for('main.counts'))


@bp.get('/conferencias/<int:count_id>')
@login_required
def count_detail(count_id):
    count = db.get_or_404(StockCount, count_id)
    grouped={}
    for line in sorted(count.lines,key=lambda l:(l.product.name,l.product_id)):
        grouped.setdefault(line.product_id,{'product':line.product,'lines':{}})['lines'][line.zone]=line
    return render_template('count_detail.html', count=count, grouped=grouped.values())


@bp.post('/conferencias/<int:count_id>/linha/<int:line_id>')
@login_required
def count_line(count_id, line_id):
    return finish(lambda: save_line(count_id, line_id, request.form.get('counted'), request.form.get('note')),
                  'Contagem salva.', url_for('main.count_detail', count_id=count_id))


@bp.post('/conferencias/<int:count_id>/enviar')
@login_required
def count_submit(count_id):
    return finish(lambda: submit_count(count_id), 'Conferência enviada para aprovação.',
                  url_for('main.count_detail', count_id=count_id))


@bp.post('/conferencias/<int:count_id>/aprovar')
@managers
def count_approve(count_id):
    return finish(lambda: approve_count(count_id, current_user.id), 'Conferência aprovada e saldos reconciliados.',
                  url_for('main.count_detail', count_id=count_id))


@bp.post('/conferencias/<int:count_id>/cancelar')
@managers
def count_cancel(count_id):
    def action():
        count = db.session.execute(select(StockCount).where(StockCount.id == count_id).with_for_update()).scalar_one_or_none()
        if not count or count.status not in ('rascunho','enviada'):
            raise ValueError('Não é possível cancelar esta conferência.')
        count.status = 'cancelada'
        db.session.commit()
    return finish(action, 'Conferência cancelada.', url_for('main.counts'))


@bp.get('/usuarios')
@admin_only
def users():
    items = db.session.execute(select(User).order_by(User.name)).scalars().all()
    from .models import AccountAudit
    audits=db.session.scalars(select(AccountAudit).order_by(AccountAudit.id.desc()).limit(50)).all()
    return render_template('users.html', items=items, audits=audits, names={u.id:u.name for u in items})


@bp.route('/usuarios/novo', methods=['GET', 'POST'])
@admin_only
def new_user():
    if request.method == 'POST':
        return finish(lambda: persist_user(None), 'Usuário criado.', request.path)
    return render_template('user_form.html', user=None)


@bp.route('/usuarios/<int:user_id>/editar', methods=['GET', 'POST'])
@admin_only
def edit_user(user_id):
    user = db.get_or_404(User, user_id)
    if request.method == 'POST':
        return finish(lambda: persist_user(user), 'Usuário atualizado.', request.path)
    return render_template('user_form.html', user=user)


def persist_user(user):
    username = request.form.get('username','').strip().lower()
    name = request.form.get('name','').strip()
    role = request.form.get('role','')
    password = request.form.get('password','')
    if len(username) < 3 or len(username) > 80 or not all(c.isalnum() or c in '._-' for c in username):
        raise ValueError('Login deve conter 3 a 80 caracteres (letras, números, ponto, hífen ou sublinhado).')
    if not (2 <= len(name) <= 120) or role not in ('admin','lojista','assistente'):
        raise ValueError('Confira nome e perfil.')
    if user is None:
        user = User(active=True, auth_version=0)
        db.session.add(user)
        if not password:
            raise ValueError('Informe a senha inicial.')
    elif user.id == current_user.id and role != 'admin':
        raise ValueError('Você não pode remover seu próprio acesso administrativo.')
    elif user.role == 'admin' and role != 'admin':
        admins = db.session.scalar(select(func.count(User.id)).where(User.role == 'admin', User.active.is_(True)))
        if admins <= 1:
            raise ValueError('Mantenha ao menos um administrador ativo.')
    if user.role and user.role != role: user.auth_version += 1
    user.username, user.name, user.role = username, name, role
    address=request.form.get('email','').strip().lower()
    if address and address!=user.email:
        from .account import email_address
        user.pending_email=email_address(address)
    if password:
        user.set_password(password)
    db.session.commit()
    return redirect(url_for('main.users'))


@bp.post('/usuarios/<int:user_id>/alternar')
@admin_only
def toggle_user(user_id):
    def action():
        user = db.get_or_404(User, user_id)
        if user.id == current_user.id:
            raise ValueError('Não é possível desativar sua própria conta.')
        if user.active and user.role == 'admin':
            admins = db.session.scalar(select(func.count(User.id)).where(User.role == 'admin', User.active.is_(True)))
            if admins <= 1:
                raise ValueError('Mantenha ao menos um administrador ativo.')
        user.active = not user.active
        user.auth_version += 1
        db.session.commit()
    return finish(action, 'Acesso atualizado.', url_for('main.users'))
