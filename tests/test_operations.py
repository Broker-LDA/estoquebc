from test_workflows import setup
from datetime import date,timedelta
import pytest
from sqlalchemy import select
from app import db
from app.models import Product,Balance,Customer,Lot,Movement,Receipt
from app.services import move,direct_sale,start_count


def test_accessory_atomic_sale_and_lots(setup):
    app,admin,staff,pid=setup
    with app.app_context():
        c=Customer(name='Cliente',active=True);p=Product(sku='BOLSA1',name='Bolsa',category='ACESSORIOS')
        db.session.add_all([c,p]);db.session.flush()
        for z in ('LOJA','ARMAZENADO'):db.session.add(Balance(product_id=p.id,zone=z,quantity=0))
        db.session.commit()
        move(pid,staff,'entrada',5,'','ARMAZENADO','Recebimento teste',expires_on=date.today()+timedelta(days=5),lot_code='L1')
        move(pid,staff,'transferencia',5,'ARMAZENADO','LOJA','Reposição loja')
        move(p.id,staff,'entrada',3,'','LOJA','Entrada bolsa')
        with pytest.raises(ValueError,match='Acessórios'):direct_sale(staff,c.id,[(p.id,1)],'Venda isolada')
        db.session.rollback()
        with pytest.raises(ValueError,match='insuficiente'):direct_sale(staff,c.id,[(pid,1),(p.id,4)],'Venda sem saldo')
        db.session.rollback()
        assert db.session.scalar(select(Balance.quantity).where(Balance.product_id==pid,Balance.zone=='LOJA'))==5
        token='a'*36;direct_sale(staff,c.id,[(pid,1),(p.id,1)],'Venda completa',token=token)
        with pytest.raises(ValueError,match='já foi'):direct_sale(staff,c.id,[(pid,1)],'Reenvio venda',token=token)
        db.session.rollback()
        assert sum(l.quantity for l in db.session.scalars(select(Lot).where(Lot.product_id==pid)))==4
        move(pid,staff,'bonificacao',1,'LOJA','','Degustação comercial')
        assert db.session.scalar(select(Movement.quantity).where(Movement.kind=='bonificacao'))==1


def test_batch_count_conflict_and_pdf(setup):
    app,admin,staff,pid=setup;app.config['WTF_CSRF_ENABLED']=False
    c=app.test_client();c.post('/login',data={'username':'admin','password':'senhaseguradeadministrador'})
    with app.app_context():
        count=start_count(staff);cid=count.id;ids=[l.id for l in count.lines]
    payload={'lines':[{'id':lid,'counted':i+2,'previous':None} for i,lid in enumerate(ids)]}
    assert c.post(f'/conferencias/{cid}/salvar-lote',json=payload).status_code==200
    assert c.post(f'/conferencias/{cid}/salvar-lote',json=payload).status_code==409
    assert b'value="2"' in c.get(f'/conferencias/{cid}').data
    r=c.get('/movimentacoes.pdf');assert r.status_code==200 and r.data.startswith(b'%PDF')
    for path in ['/','/clientes','/vendas-diretas','/lotes','/recebimentos','/produtos/novo']:assert c.get(path).status_code==200


def test_receipt_duplicate(setup):
    app,admin,staff,pid=setup;app.config['WTF_CSRF_ENABLED']=False
    c=app.test_client();c.post('/login',data={'username':'admin','password':'senhaseguradeadministrador'})
    with app.app_context():
        r=Receipt(document_key='nota-teste',imported_by=admin,payload=[{'name':'Trufa','supplier_code':'X','quantity':8}]);db.session.add(r);db.session.commit();rid=r.id
    data={'product_0':pid,'quantity_0':8,'expiry_0':'2027-01-01','lot_0':'LT'}
    c.post(f'/recebimentos/{rid}',data=data);c.post(f'/recebimentos/{rid}',data=data)
    with app.app_context():
        assert db.session.scalar(select(Balance.quantity).where(Balance.product_id==pid,Balance.zone=='ARMAZENADO'))==8
        assert db.session.scalar(select(Lot.expires_on).where(Lot.product_id==pid))==date(2027,1,1)
