"""Agrupamento e aprovação de alterações de lote; quantidades sempre inteiras."""
from datetime import date
from flask import Blueprint,request,render_template,url_for,redirect,current_app
from flask_login import login_required,current_user
from sqlalchemy import select
from . import db
from .models import Lot,LotChange,Product,Movement,utcnow
from .services import lock_balances,nonnegative_integer
from .permissions import managers
from .views import finish

lotwork=Blueprint('lotwork',__name__)


def snapshot(pid):
    return [{'id':l.id,'code':l.code,'expiry':str(l.expires_on or ''),'zone':l.zone,'quantity':l.quantity}
            for l in db.session.scalars(select(Lot).where(Lot.product_id==pid,Lot.quantity>0).order_by(Lot.id))]


def edit_token(pid):
    from itsdangerous import URLSafeSerializer
    from .models import Balance
    balances={b.zone:b for b in db.session.scalars(select(Balance).where(Balance.product_id==pid))}
    return URLSafeSerializer(current_app.secret_key,salt='lot-edit').dumps({'pid':pid,'rows':snapshot(pid),'versions':{z:b.version for z,b in balances.items()}})


def grouped_lots(pid):
    rows={}
    for l in db.session.scalars(select(Lot).where(Lot.product_id==pid,Lot.quantity>0).order_by(Lot.expires_on.asc().nullslast(),Lot.code)):
        key=(l.code,str(l.expires_on or ''))
        if key not in rows:rows[key]={'code':l.code,'expiry':key[1],'LOJA':0,'ARMAZENADO':0}
        rows[key][l.zone]+=l.quantity
    return list(rows.values())


def normalized_proposal(form):
    codes=form.getlist('code');expiries=form.getlist('expiry');stores=form.getlist('store');stored=form.getlist('stored')
    if not len(codes)==len(expiries)==len(stores)==len(stored) or len(codes)>200:raise ValueError('Confira as linhas de lote.')
    result=[];seen=set()
    for code,expiry,a,b in zip(codes,expiries,stores,stored):
        code=code.strip()
        qty_a=nonnegative_integer(a or '0');qty_b=nonnegative_integer(b or '0')
        if not qty_a and not qty_b:continue
        if not code or len(code)>80:raise ValueError('Informe a identificação do lote (até 80 caracteres).')
        if expiry:date.fromisoformat(expiry)
        if (code,expiry) in seen:raise ValueError('Lote e validade repetidos: reúna as quantidades na mesma linha.')
        seen.add((code,expiry))
        for zone,qty in [('LOJA',qty_a),('ARMAZENADO',qty_b)]:
            if qty:result.append({'code':code,'expiry':expiry,'zone':zone,'quantity':qty})
    return result


@lotwork.post('/lotes/<int:pid>/propor')
@login_required
def propose(pid):
    def action():
        product=db.session.scalar(select(Product).where(Product.id==pid).with_for_update())
        if not product:raise ValueError('Produto não encontrado.')
        balances=lock_balances(pid)
        if db.session.scalar(select(LotChange.id).where(LotChange.product_id==pid,LotChange.status=='pendente')):
            raise ValueError('Já há uma proposta pendente para este produto.')
        reason=request.form.get('reason','').strip()
        if not 5<=len(reason)<=300:raise ValueError('Informe o motivo (5 a 300 caracteres).')
        from itsdangerous import URLSafeSerializer, BadSignature
        try:original=URLSafeSerializer(current_app.secret_key,salt='lot-edit').loads(request.form.get('snapshot',''))
        except BadSignature:raise ValueError('Reabra a edição do produto antes de salvar.')
        if original!={'pid':pid,'rows':snapshot(pid),'versions':{z:b.version for z,b in balances.items()}}:
            raise ValueError('O estoque mudou enquanto você editava. Recarregue e confira os novos saldos.')
        before=snapshot(pid);after=normalized_proposal(request.form)
        for z in ('LOJA','ARMAZENADO'):
            if sum(x['quantity'] for x in before if x['zone']==z)!=balances[z].quantity:
                raise ValueError('Lotes e saldo divergentes. Contate o TI.')
        db.session.add(LotChange(product_id=pid,actor_id=current_user.id,reason=reason,before=before,after=after,
                                versions={z:balances[z].version for z in balances}))
        db.session.commit()
    return finish(action,'Proposta salva. Aguarda aprovação de lojista ou administrador.',url_for('ops.lots'))


def review_change(cid,reviewer_id,approve):
    c=db.session.scalar(select(LotChange).where(LotChange.id==cid).with_for_update())
    if not c or c.status!='pendente':raise ValueError('Proposta já analisada ou indisponível.')
    if approve:
        product=db.session.scalar(select(Product).where(Product.id==c.product_id).with_for_update())
        balances=lock_balances(c.product_id)
        if snapshot(c.product_id)!=c.before or any(balances[z].version!=c.versions[z] for z in balances):
            raise ValueError('Estoque ou lotes mudaram após a proposta. Rejeite e solicite nova contagem.')
        for l in db.session.scalars(select(Lot).where(Lot.product_id==c.product_id).with_for_update()):l.quantity=0
        for row in c.after:db.session.add(Lot(product_id=c.product_id,code=row['code'],expires_on=date.fromisoformat(row['expiry']) if row['expiry'] else None,zone=row['zone'],quantity=row['quantity']))
        for z,b in balances.items():
            qty=sum(x['quantity'] for x in c.after if x['zone']==z);diff=qty-b.quantity
            b.quantity=qty;b.version+=1
            if diff:db.session.add(Movement(product_id=product.id,sku_snapshot=product.sku,name_snapshot=product.name,actor_id=reviewer_id,
                kind='ajuste_lote',quantity=abs(diff),source=z if diff<0 else None,destination=z if diff>0 else None,
                reason=c.reason,reference=f'LOTE-PROPOSTA-{c.id}'))
    c.status='aprovada' if approve else 'rejeitada';c.reviewer_id=reviewer_id;c.reviewed_at=utcnow();db.session.commit()


@lotwork.post('/lotes/proposta/<int:cid>/<action>')
@managers
def review(cid,action):
    if action not in ('aprovar','rejeitar'):raise ValueError('Ação inválida.')
    return finish(lambda:review_change(cid,current_user.id,action=='aprovar'),'Proposta analisada.',url_for('lotwork.audit'))


@lotwork.get('/lotes/historico')
@login_required
def audit():
    return render_template('lot_audit.html',changes=db.session.scalars(select(LotChange).order_by(LotChange.id.desc()).limit(200)).all())


@lotwork.get('/lotes/relatorio.pdf')
@login_required
def export_pdf():
    from .reports import stock_report
    return stock_report('lots')
