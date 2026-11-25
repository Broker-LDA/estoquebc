import re
from datetime import date
import pytest
from sqlalchemy import select
from test_workflows import setup
from app import db
from app.models import User,Customer,Product,Balance,Lot,LotChange,Receipt,AccountToken,DirectSale,Movement
from app.services import move,direct_sale,start_count,save_line,submit_count


def add_assistant(app):
    with app.app_context():
        u=User(username='assist',name='Assistente',role='assistente',active=True,auth_version=0)
        u.set_password('senha-do-assistente-123');db.session.add(u);db.session.commit();return u.id


def login(app,user='admin',password='senhaseguradeadministrador'):
    app.config['WTF_CSRF_ENABLED']=False;c=app.test_client()
    assert c.post('/login',data={'username':user,'password':password}).status_code==302
    return c


def test_assistant_server_permissions_and_manager_approval(setup):
    app,admin,staff,pid=setup;aid=add_assistant(app);c=login(app,'assist','senha-do-assistente-123')
    for path in ['/','/clientes','/produtos','/lotes','/movimentacoes','/perfil','/conferencias']:
        assert c.get(path).status_code==200,path
    for path in ['/usuarios','/usuarios/novo','/movimentar','/vendas-diretas','/recebimentos','/produtos/novo',f'/produtos/{pid}/editar']:
        assert c.get(path).status_code==403,path
    for path in ['/clientes','/movimentar','/vendas-diretas',f'/usuarios/{staff}/resetar-senha']:
        assert c.post(path,data={}).status_code==403,path
    with app.app_context():
        count=start_count(aid);cid=count.id
        for l in count.lines:save_line(cid,l.id,2,'Conferido')
        submit_count(cid)
    html=c.get(f'/conferencias/{cid}').text
    assert html.count('data-count-product ')==1
    assert c.post(f'/conferencias/{cid}/aprovar').status_code==403
    manager=login(app,'loja','senhaseguradolojista')
    assert manager.post(f'/conferencias/{cid}/aprovar').status_code==302
    with app.app_context():assert sum(b.quantity for b in Balance.query.all())==4


def test_lot_split_audited_pending_then_approval(setup):
    app,admin,staff,pid=setup;aid=add_assistant(app)
    with app.app_context():move(pid,staff,'entrada',20,'','ARMAZENADO','Recebimento de teste',lot_code='A',expires_on=date(2027,1,1))
    c=login(app,'assist','senha-do-assistente-123')
    html=c.get('/lotes').text;token=re.search('name="snapshot" value="([^"]+)"',html)[1]
    data={'snapshot':token,'code':['A','B'],'expiry':['2027-01-01','2027-02-01'],'store':['0','0'],'stored':['10','10'],'reason':'Divisão física dos lotes'}
    assert c.post(f'/lotes/{pid}/propor',data=data).status_code==302
    with app.app_context():
        change=LotChange.query.one();cid=change.id
        assert change.actor_id==aid and change.status=='pendente'
        assert Lot.query.filter(Lot.quantity>0).count()==1
    assert c.post(f'/lotes/proposta/{cid}/aprovar').status_code==403
    manager=login(app,'loja','senhaseguradolojista')
    manager.post(f'/lotes/proposta/{cid}/aprovar')
    with app.app_context():
        assert LotChange.query.one().status=='aprovada'
        assert sorted(l.quantity for l in Lot.query.filter(Lot.quantity>0))==[10,10]
        assert sum(b.quantity for b in Balance.query.all())==20


def test_receipt_inline_new_product_multiple_lots_atomic(setup):
    app,admin,staff,pid=setup;c=login(app)
    with app.app_context():
        r=Receipt(document_key='NF-NOVA',imported_by=admin,payload=[{'name':'Ovo de Natal','supplier_code':'XYZ','quantity':20}]);db.session.add(r);db.session.commit();rid=r.id
    data={'product_0':'new','new_sku_0':'NEW-CISS','new_name_0':'Produto novo','new_category_0':'SAZONAIS','quantity_0':'20',
          'lot_0_code':['A','B'],'lot_0_expiry':['2027-01-01','2027-02-01'],'lot_0_quantity':['10','9']}
    c.post(f'/recebimentos/{rid}',data=data)
    with app.app_context():assert Product.query.count()==1
    data['lot_0_quantity']=['10','10'];c.post(f'/recebimentos/{rid}',data=data)
    with app.app_context():
        p=db.session.scalar(select(Product).where(Product.sku=='NEW-CISS'))
        assert p and p.category=='SAZONAIS'
        assert db.session.scalar(select(Balance.quantity).where(Balance.product_id==p.id,Balance.zone=='ARMAZENADO'))==20
        assert Lot.query.filter_by(product_id=p.id).count()==2
    c.post(f'/recebimentos/{rid}',data=data)
    with app.app_context():assert Product.query.count()==2


def test_customer_last_three_orders_and_pagination(setup):
    app,admin,staff,pid=setup
    with app.app_context():
        c=Customer(name='Cliente Alvo',active=True);db.session.add(c);db.session.commit()
        move(pid,staff,'entrada',20,'','LOJA','Entrada de teste')
        for i in range(5):direct_sale(staff,c.id,[(pid,1)],f'Pedido {i+1}')
        for i in range(11):db.session.add(Product(sku=f'P{i}',name=f'Produto {i}',category='MIX'))
        db.session.commit()
    c=login(app);html=c.get('/clientes?q=Alvo').text
    assert html.count('<details>')==3
    assert html.count('TRUFA ALPINO')==3
    html=c.get('/produtos').text
    assert 'Próxima' in html and html.count('>Editar</a>')==10


def test_profile_verification_and_admin_temporary_password(setup,monkeypatch):
    app,admin,staff,pid=setup;app.config['PUBLIC_BASE_URL']='http://localhost';mail=[]
    monkeypatch.setattr('app.account.send_email',lambda to,subject,body:mail.append((to,subject,body)))
    c=login(app,'loja','senhaseguradolojista')
    c.post('/perfil',data={'name':'Gestor','email':'gestor@example.org','avatar':'avatar-4','current_password':'senhaseguradolojista'})
    c.post('/perfil/verificar-email')
    assert len(mail)==1
    path=mail[-1][2].split('http://localhost')[1].strip()
    assert c.get(path).status_code==200;c.post(path)
    with app.app_context():assert db.session.get(User,staff).email_verified
    assert c.post(path).status_code==400
    admin_client=login(app)
    admin_client.post(f'/usuarios/{staff}/resetar-senha',data={'admin_password':'senhaseguradeadministrador'})
    temp=mail[-1][2].split('Senha temporária: ')[1].split('\n')[0]
    assert c.get('/').status_code==302
    c2=login(app,'loja',temp)
    assert c2.get('/movimentar').location.endswith('/perfil')
    c2.post('/perfil',data={'name':'Gestor','email':'gestor@example.org','avatar':'avatar-4','current_password':temp,'new_password':'nova-senha-gestor-123','confirm_password':'nova-senha-gestor-123'})
    assert c2.get('/').status_code==200
    assert c2.get('/usuarios').status_code==403


def test_forgot_password_token_is_single_use(setup,monkeypatch):
    app,admin,staff,pid=setup;app.config['PUBLIC_BASE_URL']='http://localhost';mail=[]
    monkeypatch.setattr('app.account.send_email',lambda to,subject,body:mail.append(body))
    with app.app_context():u=db.session.get(User,staff);u.email='loja@example.org';u.email_verified=True;db.session.commit()
    app.config['WTF_CSRF_ENABLED']=False;c=app.test_client();c.post('/esqueci-senha',data={'email':'loja@example.org'})
    path=mail[-1].split('http://localhost')[1].split('\n')[0]
    assert c.get(path).status_code==200
    c.post(path,data={'password':'senha-recuperada-123','confirm_password':'senha-recuperada-123'})
    assert c.get(path).status_code==400
    assert login(app,'loja','senha-recuperada-123').get('/').status_code==200
