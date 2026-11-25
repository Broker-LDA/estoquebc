from sqlalchemy import select
from . import db
from .models import Balance, Movement, Product, CountLine, StockCount, utcnow

ZONES = ('LOJA', 'ARMAZENADO')
KINDS = ('entrada', 'transferencia', 'venda', 'perda', 'bonificacao', 'devolucao')


def error(message):
    raise ValueError(message)


def positive_integer(value, label='Quantidade'):
    try:
        number = int(value)
        if str(number) != str(value).strip() or number < 1 or number > 1_000_000:
            raise ValueError
        return number
    except (TypeError, ValueError):
        error(f'{label} deve ser um inteiro entre 1 e 1.000.000.')


def nonnegative_integer(value):
    try:
        number = int(value)
        if str(number) != str(value).strip() or number < 0 or number > 1_000_000:
            raise ValueError
        return number
    except (TypeError, ValueError):
        error('A contagem deve ser um inteiro entre 0 e 1.000.000.')


def lock_balances(product_id):
    # Bloqueia sempre as duas linhas na mesma ordem, inclusive na transferência.
    rows = db.session.execute(select(Balance).where(Balance.product_id == product_id)
                              .order_by(Balance.zone).with_for_update()).scalars().all()
    balances = {row.zone: row for row in rows}
    if set(balances) != set(ZONES):
        error('Produto sem saldos inicializados. Contate o administrador.')
    return balances


def move(product_id, actor_id, kind, quantity, source, destination, reason, reference='', *, customer_id=None, sale_id=None, lot_code='', expires_on=None, commit=True):
    if kind not in KINDS:
        error('Tipo de movimentação inválido.')
    quantity = positive_integer(quantity)
    reason = (reason or '').strip()
    reference = (reference or '').strip()
    if len(reason) < 5 or len(reason) > 300 or len(reference) > 100:
        error('Informe um motivo de 5 a 300 caracteres e uma referência de até 100.')
    if source not in (*ZONES, '') or destination not in (*ZONES, ''):
        error('Local de estoque inválido.')
    expected = {
        'entrada': (False, True), 'transferencia': (True, True),
        'venda': (True, False), 'perda': (True, False), 'bonificacao': (True, False),
        'devolucao': (False, True),
    }[kind]
    if (bool(source), bool(destination)) != expected or (source and destination and source == destination):
        error('Origem e destino incompatíveis com a operação.')
    if kind == 'venda' and source != 'LOJA':
        error('Vendas saem da loja; transfira do armazenado antes de vender.')
    product = db.session.execute(select(Product).where(Product.id == product_id)
                                 .with_for_update()).scalar_one_or_none()
    if not product or not product.active:
        error('Produto indisponível.')
    if kind == 'venda' and (not customer_id or not sale_id):
        error('Use Venda direta e selecione um cliente cadastrado.')
    balances = lock_balances(product_id)
    if source and balances[source].quantity < quantity:
        error(f'Saldo insuficiente em {source.lower()}.')
    allocate_lots(product_id, source, destination, quantity, lot_code, expires_on)
    if source:
        balances[source].quantity -= quantity
        balances[source].version += 1
    if destination:
        balances[destination].quantity += quantity
        balances[destination].version += 1
    db.session.add(Movement(product_id=product_id, sku_snapshot=product.sku,
                            name_snapshot=product.name, actor_id=actor_id, kind=kind, customer_id=customer_id, sale_id=sale_id,
                            quantity=quantity, source=source or None,
                            destination=destination or None, reason=reason,
                            reference=reference or None))
    if commit:
        db.session.commit()


def start_count(actor_id):
    products = db.session.execute(select(Product).where(Product.active.is_(True)).order_by(Product.id)).scalars().all()
    if not products:
        error('Cadastre produtos antes de abrir uma conferência.')
    pending = db.session.execute(select(StockCount).where(StockCount.status.in_(('rascunho', 'enviada')))).first()
    if pending:
        error('Já há uma conferência em andamento.')
    count = StockCount(created_by=actor_id)
    db.session.add(count)
    db.session.flush()
    for product in products:
        balances = lock_balances(product.id)
        for zone in ZONES:
            db.session.add(CountLine(count_id=count.id, product_id=product.id,
                                     zone=zone, expected=balances[zone].quantity,
                                     expected_version=balances[zone].version))
    db.session.commit()
    return count


def save_line(count_id, line_id, counted, note):
    count = db.session.execute(select(StockCount).where(StockCount.id == count_id)
                               .with_for_update()).scalar_one_or_none()
    if not count or count.status != 'rascunho':
        error('Conferência indisponível.')
    line = db.session.execute(select(CountLine).where(CountLine.id == line_id,
                          CountLine.count_id == count_id).with_for_update()).scalar_one_or_none()
    if not line:
        error('Linha ou conferência indisponível.')
    line.counted = nonnegative_integer(counted)
    line.note = (note or '').strip()[:300]
    line.revision += 1
    db.session.commit()


def submit_count(count_id):
    count = db.session.execute(select(StockCount).where(StockCount.id == count_id)
                               .with_for_update()).scalar_one_or_none()
    if not count or count.status != 'rascunho':
        error('Conferência indisponível para envio.')
    if any(line.counted is None for line in count.lines):
        error('Preencha as duas áreas de todos os produtos; informe 0 quando não houver unidades.')
    count.status = 'enviada'
    count.submitted_at = utcnow()
    db.session.commit()


def approve_count(count_id, actor_id):
    count = db.session.execute(select(StockCount).where(StockCount.id == count_id)
                               .with_for_update()).scalar_one_or_none()
    if not count or count.status != 'enviada':
        error('Conferência indisponível para aprovação.')
    # Rejeita resultado antigo, sem apagar o histórico de contagem para auditoria.
    for line in sorted(count.lines, key=lambda row: (row.product_id, row.zone)):
        balance = db.session.execute(select(Balance).where(Balance.product_id == line.product_id,
                                   Balance.zone == line.zone).with_for_update()).scalar_one()
        if balance.quantity != line.expected or balance.version != line.expected_version:
            error(f'Saldo alterado desde a abertura: {line.product.sku} / {line.zone}. Cancele esta contagem e abra outra.')
        diff = line.counted - line.expected
        if diff:
            allocate_lots(line.product_id, line.zone if diff < 0 else '', line.zone if diff > 0 else '', abs(diff), 'Ajuste de inventário', None)
            balance.quantity = line.counted
            balance.version += 1
            db.session.add(Movement(product_id=line.product_id, sku_snapshot=line.product.sku,
                                    name_snapshot=line.product.name, actor_id=actor_id,
                                    kind='ajuste_contagem', quantity=abs(diff),
                                    source=line.zone if diff < 0 else None,
                                    destination=line.zone if diff > 0 else None,
                                    reason=(f'Conferência #{count.id}: {line.note or "diferença apurada"}')[:300],
                                    reference=f'CONTAGEM-{count.id}'))
    count.status = 'aprovada'
    count.approved_by = actor_id
    count.approved_at = utcnow()
    db.session.commit()


def allocate_lots(product_id, source, destination, quantity, code='', expiry=None):
    """Mantém lotes e saldos agregados juntos; saídas por validade mais próxima."""
    from .models import Lot
    if not source:
        db.session.add(Lot(product_id=product_id, zone=destination, quantity=quantity,
                           code=(code or 'Não identificado')[:80], expires_on=expiry))
        return
    rows = db.session.execute(select(Lot).where(Lot.product_id == product_id, Lot.zone == source,
                            Lot.quantity > 0).order_by(Lot.expires_on.asc().nullslast(), Lot.id)
                            .with_for_update()).scalars().all()
    if sum(row.quantity for row in rows) < quantity:
        error('Lotes não conciliados com saldo. Contate o administrador.')
    remaining = quantity
    for row in rows:
        take = min(remaining, row.quantity)
        if take:
            row.quantity -= take
            if destination:
                db.session.add(Lot(product_id=product_id, zone=destination, quantity=take,
                                   code=row.code, expires_on=row.expires_on))
            remaining -= take
        if not remaining:
            break


def direct_sale(actor_id, customer_id, lines, reason, reference='', token=None):
    from .models import Customer, Movement, DirectSale
    from uuid import uuid4
    customer = db.session.get(Customer, customer_id)
    if not customer or not customer.active:
        error('Selecione um cliente ativo.')
    if not lines or len(lines) > 200:
        error('Informe de 1 a 200 itens na venda.')
    combined = {}
    for pid, qty in lines:
        combined[int(pid)] = combined.get(int(pid), 0) + positive_integer(qty)
    products = db.session.execute(select(Product).where(Product.id.in_(combined))
                                 .order_by(Product.id).with_for_update()).scalars().all()
    if len(products) != len(combined) or any(not p.active for p in products):
        error('Produto indisponível.')
    if any(p.category == 'ACESSORIOS' for p in products) and not any(p.category != 'ACESSORIOS' for p in products):
        error('Acessórios exigem pelo menos um produto não acessório na mesma venda.')
    sale_id = token or str(uuid4())
    if db.session.scalar(select(Movement.id).where(Movement.sale_id == sale_id)):
        error('Esta venda já foi registrada.')
    db.session.add(DirectSale(id=sale_id, customer_id=customer.id, actor_id=actor_id))
    db.session.flush()
    for p in products:
        move(p.id, actor_id, 'venda', combined[p.id], 'LOJA', '', reason, reference,
             customer_id=customer.id, sale_id=sale_id, commit=False)
    db.session.commit()
