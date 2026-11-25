from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app, db
from app.models import Balance, Movement, Product, StockCount, User, Customer
from app.services import approve_count, move, save_line, start_count, submit_count, direct_sale


@pytest.fixture
def setup(tmp_path):
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': f'sqlite:///{tmp_path}/test.db',
                      'SECRET_KEY': 's'*64, 'SESSION_COOKIE_SECURE': False})
    with app.app_context():
        db.create_all()
        admin = User(username='admin', name='Admin', role='admin', active=True, auth_version=0)
        admin.set_password('senhaseguradeadministrador')
        staff = User(username='loja', name='Loja', role='lojista', active=True, auth_version=0)
        staff.set_password('senhaseguradolojista')
        db.session.add_all([admin, staff]); db.session.flush()
        product = Product(sku='12345', barcode='7891823934442', name='TRUFA ALPINO 25G', category='INVENTARIO')
        db.session.add(product); db.session.flush()
        db.session.add_all([Balance(product_id=product.id, zone='LOJA', quantity=0),
                            Balance(product_id=product.id, zone='ARMAZENADO', quantity=0)])
        db.session.commit()
        ids = (admin.id, staff.id, product.id)
    yield (app, *ids)


def test_stock_operations_and_audit(setup):
    app, admin_id, staff_id, product_id = setup
    with app.app_context():
        move(product_id, staff_id, 'entrada', 20, '', 'ARMAZENADO', 'Recebimento da nota 42')
        move(product_id, staff_id, 'transferencia', 8, 'ARMAZENADO', 'LOJA', 'Reposição da vitrine')
        customer=Customer(name='Cliente direto',active=True);db.session.add(customer);db.session.commit()
        direct_sale(staff_id,customer.id,[(product_id,3)],'Venda do cupom 123')
        assert {b.zone: b.quantity for b in Balance.query.all()} == {'LOJA': 5, 'ARMAZENADO': 12}
        with pytest.raises(ValueError, match='insuficiente'):
            direct_sale(staff_id,customer.id,[(product_id,6)],'Venda além do saldo')
        db.session.rollback()
        assert Movement.query.count() == 3
        with pytest.raises(ValueError, match='Vendas saem'):
            move(product_id, staff_id, 'venda', 1, 'ARMAZENADO', '', 'Venda impossível')
        db.session.rollback()


def test_count_requires_completion_and_records_adjustments(setup):
    app, admin_id, staff_id, product_id = setup
    with app.app_context():
        count = start_count(staff_id)
        lines = {line.zone: line for line in count.lines}
        save_line(count.id, lines['LOJA'].id, 5, 'Cinco na vitrine')
        with pytest.raises(ValueError, match='Preencha'):
            submit_count(count.id)
        db.session.rollback()
        save_line(count.id, lines['ARMAZENADO'].id, 12, 'Doze na reserva')
        submit_count(count.id)
        approve_count(count.id, admin_id)
        assert db.session.get(StockCount, count.id).status == 'aprovada'
        assert {b.zone: b.quantity for b in Balance.query.all()} == {'LOJA': 5, 'ARMAZENADO': 12}
        assert Movement.query.filter_by(kind='ajuste_contagem').count() == 2


def test_stale_count_rejected_even_if_balance_returns_to_original(setup):
    app, admin_id, staff_id, product_id = setup
    with app.app_context():
        count = start_count(staff_id)
        for line in count.lines:
            save_line(count.id, line.id, 0, '')
        submit_count(count.id)
        move(product_id, staff_id, 'entrada', 1, '', 'LOJA', 'Nova entrada externa')
        move(product_id, staff_id, 'perda', 1, 'LOJA', '', 'Produto vencido depois')
        with pytest.raises(ValueError, match='Saldo alterado'):
            approve_count(count.id, admin_id)
        db.session.rollback()
        assert db.session.get(StockCount, count.id).status == 'enviada'


def test_auth_roles_csrf_and_disabling_session(setup):
    app, admin_id, staff_id, product_id = setup
    client = app.test_client()
    assert client.get('/usuarios').status_code == 302
    assert client.post('/login', data={'username': 'loja', 'password': 'senhaseguradolojista'}).status_code == 400
    response = client.get('/login')
    from html.parser import HTMLParser
    class TokenParser(HTMLParser):
        token = None
        def handle_starttag(self, tag, attrs):
            if tag == 'input' and dict(attrs).get('name') == 'csrf_token':
                self.token = dict(attrs).get('value')
    parser = TokenParser(); parser.feed(response.get_data(as_text=True))
    assert parser.token
    response = client.post('/login', data={'username': 'loja', 'password': 'senhaseguradolojista', 'csrf_token': parser.token})
    assert response.status_code == 302
    assert client.get('/').status_code == 200
    assert client.get('/usuarios').status_code == 403
    with app.app_context():
        user = db.session.get(User, staff_id); user.active = False; user.auth_version += 1; db.session.commit()
    assert client.get('/').status_code == 302
