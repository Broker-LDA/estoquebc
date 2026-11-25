"""Recebimentos revisados, clientes, lotes, vendas diretas e inventário em lote."""
import io
import re
from datetime import date
from uuid import uuid4
from xml.sax.saxutils import escape
from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash, Response, jsonify
from flask_login import login_required, current_user
from sqlalchemy import select,or_,func
from . import db
from .models import Customer, Product, Receipt, Movement, Lot, StockCount, CountLine, DirectSale, SupplierProduct, LotChange, utcnow
from .services import move, direct_sale, positive_integer, nonnegative_integer
from .views import finish

ops = Blueprint('ops', __name__)


def parse_invoice(file):
    import pdfplumber
    with pdfplumber.open(file) as pdf:
        if len(pdf.pages) > 10:
            raise ValueError('Envie um DANFE de até 10 páginas.')
        lines = []
        full = ''
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=0.5, y_tolerance=1) or ''
            full += text
            pending = None
            for raw in text.splitlines():
                textline = raw.strip()
                if re.fullmatch(r'\d{17}', textline):
                    pending = textline
                    continue
                match = re.match(r'(.+?)\s+\d{8}\s+\d{2,3}\s+\d{4}\s+UN\s+(\d+(?:[.,]\d+)?)\s+', textline)
                if pending and match:
                    qty = match[2].replace(',', '.')
                    if not float(qty).is_integer():
                        raise ValueError('Quantidade fracionada não suportada: revise a unidade da nota.')
                    lines.append({'supplier_code': pending, 'name': match[1].strip(), 'quantity': int(float(qty))})
                    pending = None
                elif pending and re.fullmatch(r'\d', textline):
                    # Código do fornecedor está quebrado na coluna do DANFE.
                    if lines:
                        lines[-1]['supplier_code'] += textline
                    pending = None
                elif lines and re.fullmatch(r'\d', textline):
                    if len(lines[-1]['supplier_code']) == 17:
                        lines[-1]['supplier_code'] += textline
        key = re.search(r'(?:\d{4}\s+){10}\d{4}', full)
        import hashlib
        document_key = re.sub(r'\s', '', key[0]) if key else hashlib.sha256(full.encode()).hexdigest()
        if not lines:
            raise ValueError('Não foi possível reconhecer os itens. Use entrada manual; PDF digitalizado exige OCR externo.')
        return document_key, lines


@ops.route('/clientes', methods=['GET','POST'])
@login_required
def customers():
    if request.method == 'POST':
        def action():
            name = request.form.get('name','').strip()
            if not 2 <= len(name) <= 120:
                raise ValueError('Informe nome de 2 a 120 caracteres.')
            cid = request.form.get('id', type=int)
            c = db.get_or_404(Customer, cid) if cid else Customer()
            c.name = name
            c.document = request.form.get('document','').strip()[:30] or None
            c.phone = request.form.get('phone','').strip()[:40]
            c.active = request.form.get('active') == 'on'
            db.session.add(c); db.session.commit()
        return finish(action,'Cliente salvo.',request.path)
    q=request.args.get('q','').strip()[:100];status=request.args.get('status','')
    query=select(Customer)
    if q:query=query.where(or_(Customer.name.ilike(f'%{q}%'),Customer.document.ilike(f'%{q}%'),Customer.phone.ilike(f'%{q}%')))
    if status in ('ativo','inativo'):query=query.where(Customer.active.is_(status=='ativo'))
    pagination=db.paginate(query.order_by(Customer.name),page=max(1,request.args.get('page',1,type=int) or 1),per_page=10,error_out=False)
    customers=pagination.items
    ranked=select(DirectSale.id,DirectSale.customer_id,DirectSale.created_at,func.row_number().over(partition_by=DirectSale.customer_id,order_by=(DirectSale.created_at.desc(),DirectSale.id.desc())).label('rn')).where(DirectSale.customer_id.in_([c.id for c in customers])).subquery()
    sales=db.session.execute(select(ranked).where(ranked.c.rn<=3).order_by(ranked.c.created_at.desc())).mappings().all()
    history={c.id:[] for c in customers}
    entries=db.session.scalars(select(Movement).where(Movement.sale_id.in_([x['id'] for x in sales]))).all()
    for row in sales:history[row['customer_id']].append(dict(row,items=[m for m in entries if m.sale_id==row['id']]))
    return render_template('customers.html', customers=customers,history=history,pagination=pagination,q=q,status=status)


@ops.route('/vendas-diretas', methods=['GET','POST'])
@login_required
def sales():
    if request.method == 'POST':
        def action():
            ids = request.form.getlist('product_id'); quantities = request.form.getlist('quantity')
            if len(ids) != len(quantities):
                raise ValueError('Itens inválidos.')
            token = request.form.get('token','')
            if not re.fullmatch(r'[a-f0-9-]{36}', token):
                raise ValueError('Reabra o formulário de venda.')
            direct_sale(current_user.id, request.form.get('customer_id',type=int),
                        [(int(pid),qty) for pid,qty in zip(ids,quantities) if pid and qty],
                        request.form.get('reason',''),request.form.get('reference',''), token)
            return redirect(url_for('main.movements'))
        return finish(action,'Venda direta registrada.',request.path)
    return render_template('sales.html', items=db.session.scalars(select(Product).where(Product.active.is_(True)).order_by(Product.name)).all(),
                           customers=db.session.scalars(select(Customer).where(Customer.active.is_(True)).order_by(Customer.name)).all(), token=str(uuid4()))


@ops.route('/recebimentos', methods=['GET','POST'])
@login_required
def receipts():
    if request.method == 'POST':
        def action():
            f = request.files.get('invoice')
            if not f or not f.filename.lower().endswith('.pdf'):
                raise ValueError('Selecione um PDF.')
            try:
                key, lines = parse_invoice(f.stream)
            except ValueError:
                raise
            except Exception as exc:
                raise ValueError('PDF inválido ou não reconhecido.') from exc
            existing = db.session.scalar(select(Receipt).where(Receipt.document_key==key))
            if existing:
                if existing.confirmed_at:
                    raise ValueError('Esta nota já foi recebida.')
                return redirect(url_for('ops.receipt_detail',rid=existing.id))
            r = Receipt(document_key=key, imported_by=current_user.id,payload=lines)
            db.session.add(r);db.session.commit()
            return redirect(url_for('ops.receipt_detail',rid=r.id))
        return finish(action,'Nota extraída. Revise os vínculos antes de confirmar.',request.path)
    return render_template('receipts.html', receipts=db.session.scalars(select(Receipt).order_by(Receipt.id.desc())).all())


@ops.route('/recebimentos/<int:rid>', methods=['GET','POST'])
@login_required
def receipt_detail(rid):
    r = db.get_or_404(Receipt,rid)
    if request.method=='POST':
        def action():
            receipt = db.session.scalar(select(Receipt).where(Receipt.id==rid).with_for_update())
            if receipt.confirmed_at:
                raise ValueError('Nota já confirmada.')
            prepared=[]
            confirmed_payload=[]
            for i,row in enumerate(receipt.payload):
                selected=request.form.get(f'product_{i}','')
                qty=positive_integer(request.form.get(f'quantity_{i}'))
                if selected=='new':
                    sku=request.form.get(f'new_sku_{i}','').strip().upper()
                    name=request.form.get(f'new_name_{i}',row['name']).strip()
                    category=request.form.get(f'new_category_{i}','MIX')
                    if not 1<=len(sku)<=40 or not 2<=len(name)<=180 or category not in ('MIX','INVENTARIO','SAZONAIS','ACESSORIOS'):
                        raise ValueError('Confira CISS/código provisório, descrição e categoria do novo produto.')
                    if db.session.scalar(select(Product.id).where(Product.sku==sku)):
                        raise ValueError('Código já existe: vincule esse item ao produto existente.')
                    product=Product(sku=sku,name=name,category=category,unit='UN',active=True,sale_multiple=1,min_store=0)
                    db.session.add(product);db.session.flush()
                    from .models import Balance
                    for zone in ('LOJA','ARMAZENADO'):db.session.add(Balance(product_id=product.id,zone=zone,quantity=0))
                else:product=db.session.get(Product,int(selected or 0))
                if not product or not product.active:raise ValueError('Selecione ou crie o produto na própria prévia.')
                codes=request.form.getlist(f'lot_{i}_code');expiries=request.form.getlist(f'lot_{i}_expiry');quantities=request.form.getlist(f'lot_{i}_quantity')
                if not codes:
                    codes=[request.form.get(f'lot_{i}','') or 'Não identificado'];expiries=[request.form.get(f'expiry_{i}','')];quantities=[str(qty)]
                if not len(codes)==len(expiries)==len(quantities) or len(codes)>100:raise ValueError('Divisão de lotes inválida.')
                parts=[]
                for code,expiry,quantity in zip(codes,expiries,quantities):
                    code=code.strip();n=positive_integer(quantity)
                    if not code or len(code)>80:raise ValueError('Informe lote de cada parte recebida.')
                    exp=date.fromisoformat(expiry) if expiry else None
                    if product.category!='ACESSORIOS' and exp is None:raise ValueError('Informe validade de cada lote alimentício.')
                    parts.append({'code':code,'expiry':str(exp or ''),'quantity':n})
                    prepared.append((product.id,n,exp,code))
                if sum(part['quantity'] for part in parts)!=qty:raise ValueError(f"A soma dos lotes deve ser igual a {qty} unidades de {product.name}.")
                alias=db.session.scalar(select(SupplierProduct).where(SupplierProduct.supplier_code==row['supplier_code']).with_for_update())
                if alias and alias.product_id!=product.id:raise ValueError('Código do fornecedor já está vinculado a outro produto. Consulte o TI.')
                if not alias:db.session.add(SupplierProduct(supplier_code=row['supplier_code'],product_id=product.id))
                confirmed_payload.append(dict(row,ciss=product.sku,confirmed_quantity=qty,parts=parts))
            for pid,qty,expiry,code in sorted(prepared,key=lambda x:x[0]):
                move(pid,current_user.id,'entrada',qty,'','ARMAZENADO','Recebimento de nota fiscal',receipt.document_key,lot_code=code,expires_on=expiry,commit=False)
            receipt.payload=confirmed_payload
            receipt.confirmed_at=utcnow();db.session.commit()
        return finish(action,'Recebimento confirmado no armazenado.',url_for('ops.receipt_detail',rid=rid))
    items=db.session.scalars(select(Product).where(Product.active.is_(True)).order_by(Product.name)).all()
    # Só sugere igualdade de descrição. Nunca assume código do fornecedor = CISS.
    aliases={a.supplier_code:a.product_id for a in db.session.scalars(select(SupplierProduct))}
    suggestions={i:aliases.get(row['supplier_code']) or next((p.id for p in items if p.name.casefold()==row['name'].casefold()),None) for i,row in enumerate(r.payload)}
    return render_template('receipt_detail.html',receipt=r,items=items,suggestions=suggestions)


@ops.route('/lotes',methods=['GET','POST'])
@login_required
def lots():
    if request.method=='POST':
        from flask import abort
        abort(405)  # Alterações são propostas auditadas, nunca edição silenciosa.
    from .lotwork import grouped_lots,edit_token
    q=request.args.get('q','').strip()[:100]
    query=select(Product).where(Product.active.is_(True))
    if q:query=query.where(or_(Product.name.ilike(f'%{q}%'),Product.sku.ilike(f'%{q}%')))
    pagination=db.paginate(query.order_by(Product.name),page=max(1,request.args.get('page',1,type=int) or 1),per_page=10,error_out=False)
    cards=[{'product':p,'rows':grouped_lots(p.id),'token':edit_token(p.id)} for p in pagination.items]
    pending={c.product_id:c for c in db.session.scalars(select(LotChange).where(LotChange.status=='pendente'))}
    return render_template('lots.html',cards=cards,pending=pending,pagination=pagination,q=q)


@ops.post('/conferencias/<int:cid>/salvar-lote')
@login_required
def batch_count(cid):
    try:
        count=db.session.scalar(select(StockCount).where(StockCount.id==cid).with_for_update())
        if not count or count.status!='rascunho': raise ValueError('Conferência indisponível.')
        updates=request.get_json().get('lines',[])
        if not updates or len(updates)>1000: raise ValueError('Lote de alterações inválido.')
        lines={l.id:l for l in count.lines}
        for item in updates:
            line=lines.get(int(item['id']))
            if not line: raise ValueError('Linha inválida.')
            # Evita sobrescrever a contagem feita simultaneamente por outro operador.
            old=item.get('previous')
            if old != line.counted or ('revision' in item and item['revision']!=line.revision): raise ValueError('Outra pessoa alterou esta linha. Recarregue e confira antes de salvar.')
            line.counted=nonnegative_integer(item['counted'])
            line.note=str(item.get('note',''))[:300]
            line.revision+=1
        db.session.commit()
        return jsonify(ok=True,revisions={str(line.id):line.revision for line in lines.values()})
    except (ValueError,TypeError,KeyError) as exc:
        db.session.rollback();return jsonify(ok=False,error=str(exc)),409


@ops.get('/movimentacoes.pdf')
@login_required
def history_pdf():
    from .reports import stock_report
    return stock_report('history')


@ops.get('/sw.js')
def sw():
    return current_app.send_static_file('sw.js')
