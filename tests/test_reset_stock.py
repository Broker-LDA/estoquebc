from test_workflows import setup
from app import db
from app.models import Balance, Lot, Movement, Product, User, StockCount
from app.services import move, start_count


def test_reset_authenticated_atomic_preserves_catalog_and_history(setup):
    app,admin,staff,pid=setup
    with app.app_context():
        move(pid,staff,'entrada',10,'','ARMAZENADO','Entrada para teste')
        move(pid,staff,'transferencia',4,'ARMAZENADO','LOJA','Reposição vitrine')
    runner=app.test_cli_runner()
    result=runner.invoke(args=['reset-stock','--admin','admin','--dry-run'],input='senhaseguradeadministrador\n')
    assert result.exit_code==0,result.output
    with app.app_context():
        assert sum(b.quantity for b in Balance.query.all())==10
    result=runner.invoke(args=['reset-stock','--admin','loja'],input='senhaseguradolojista\n')
    assert result.exit_code!=0
    with app.app_context():start_count(staff)
    result=runner.invoke(args=['reset-stock','--admin','admin'],input='senhaseguradeadministrador\nZERAR\n')
    assert result.exit_code!=0 and 'conferências abertas' in result.output
    result=runner.invoke(args=['reset-stock','--admin','admin','--cancel-open-counts'],input='senhaseguradeadministrador\nCANCELAR\n')
    assert result.exit_code!=0
    with app.app_context():
        assert sum(b.quantity for b in Balance.query.all())==10
        assert StockCount.query.first().status=='rascunho'
    result=runner.invoke(args=['reset-stock','--admin','admin','--cancel-open-counts'],input='senhaseguradeadministrador\nZERAR\n')
    assert result.exit_code==0,result.output
    with app.app_context():
        assert sum(b.quantity for b in Balance.query.all())==0
        assert sum(l.quantity for l in Lot.query.all())==0
        assert Product.query.count()==1 and User.query.count()==2
        assert Movement.query.count()==4
        assert Movement.query.filter_by(kind='ajuste_teste').count()==2
        assert StockCount.query.first().status=='cancelada'
        # Um recebimento novo funciona depois da zeragem.
        move(pid,staff,'entrada',8,'','ARMAZENADO','Novo recebimento teste')
        assert sum(b.quantity for b in Balance.query.all())==8
