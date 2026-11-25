"""Relatórios vetoriais de estoque e lotes com fontes incorporadas."""
import io
from pathlib import Path
from xml.sax.saxutils import escape
from flask import current_app,Response
from sqlalchemy import select
from . import db
from .models import Product,Lot,Movement,LotChange,utcnow


def stock_report(mode='history',entries=None):
    from reportlab.platypus import SimpleDocTemplate,Paragraph,LongTable,Table,TableStyle,Spacer,Image,PageBreak,KeepTogether
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape,A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    if 'CacauSans' not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont('CacauSans',str(Path(current_app.static_folder)/'fonts/DejaVuSans.ttf')))
    ink=colors.HexColor('#54222c');orange=colors.HexColor('#ed6c32');cream=colors.HexColor('#fbf6ef')
    normal=ParagraphStyle('body',fontName='CacauSans',fontSize=8,leading=11,textColor=colors.HexColor('#64574f'),splitLongWords=True)
    head=ParagraphStyle('thead',parent=normal,fontSize=8,textColor=colors.white)
    title=ParagraphStyle('title',parent=normal,fontSize=21,leading=28,textColor=ink,spaceAfter=8)
    section=ParagraphStyle('section',parent=normal,fontSize=13,leading=20,textColor=ink,spaceBefore=18,spaceAfter=9)
    def p(v,style=normal):return Paragraph(escape(str(v if v is not None and v != '' else '—')).replace('\n','<br/>'),style)
    def table(headers,rows,widths):
        data=[[p(x,head) for x in headers]]+[[p(x) for x in row] for row in rows]
        if len(data)==1:data.append([p('Nenhum registro.')]+[p('') for _ in headers[1:]])
        t=LongTable(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),ink),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,cream]),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10),('LEFTPADDING',(0,0),(-1,-1),10),('RIGHTPADDING',(0,0),(-1,-1),10),('LINEBELOW',(0,0),(-1,0),2,orange)]))
        return t
    output=io.BytesIO();doc=SimpleDocTemplate(output,pagesize=landscape(A4),leftMargin=32,rightMargin=32,topMargin=38,bottomMargin=35,title='Brasil Cacau | Relatório de estoque',author='Brasil Cacau')
    story=[];logo=Image(str(Path(current_app.static_folder)/'img/bc-logo-2(1).png'),width=47,height=47)
    heading='Histórico operacional' if mode=='history' else 'Estoque por lote e validade'
    story += [Table([[logo,Paragraph('Brasil Cacau<br/>'+heading,title)]],colWidths=[65,713]),p('CONTROLE INTERNO · Gerado em '+utcnow().strftime('%d/%m/%Y às %H:%M UTC')),Spacer(1,17)]
    if mode=='history':
        entries=list(entries if entries is not None else db.session.scalars(select(Movement).order_by(Movement.id.desc())))
        story+=[table(['Registros no relatório','Unidades recebidas','Vendas diretas (unidades)'],[[len(entries),sum(m.quantity for m in entries if m.kind=='entrada'),sum(m.quantity for m in entries if m.kind=='venda')]],[259,259,260]),Paragraph('01 / Rastreabilidade dos movimentos',section)]
        rows=[]
        for m in entries:rows.append([f'#{m.id}\n'+m.occurred_at.strftime('%d/%m/%Y %H:%M'),f'{m.sku_snapshot} · {m.name_snapshot}',f'{m.kind.replace("_"," ")} · {m.quantity} un',f'{m.source or "Externo"} → {m.destination or "Externo"}',m.customer.name if m.customer else 'Operação interna',f'{m.actor.name} · {m.reason}\nRef.: {m.reference or "—"}\nPedido: {m.sale_id or "—"}'])
        story += [table(['ID / Data UTC','CISS / Produto','Operação / Unidades','Origem / Destino','Cliente','Operador / Motivo / Referência'],rows,[77,173,94,100,104,230]),PageBreak(),Paragraph('02 / Posição atual por lote',section),p('Esta seção apresenta o estoque no momento da emissão. Não representa o saldo histórico na data de cada movimento.'),Spacer(1,12)]
    else:story+=[p('Totais por produto, com loja e armazenado separados no detalhamento. Somente lotes com unidades.'),Spacer(1,12)]
    from .lotwork import grouped_lots
    rows=[]
    for product in db.session.scalars(select(Product).order_by(Product.name)):
        groups=grouped_lots(product.id)
        if not groups:continue
        for row in groups:rows.append([product.sku+' · '+product.name,row['code'],row['expiry'] or 'Não informada',row['LOJA'],row['ARMAZENADO'],row['LOJA']+row['ARMAZENADO']])
    story.append(table(['CISS / Produto','Lote','Validade','Loja','Armazenado','Total'],rows,[278,160,110,70,90,70]))
    if mode=='lots':
        story += [Paragraph('Alterações recentes de lote — últimas 30 propostas',section)]
        changes=db.session.scalars(select(LotChange).order_by(LotChange.id.desc()).limit(30)).all()
        story.append(table(['Proposta / Produto','Solicitado por','Status / Aprovação','Motivo'],[[f'#{c.id} · {c.product.name}',c.actor.name+' · '+c.created_at.strftime('%d/%m/%Y %H:%M UTC'),c.status+' · '+(c.reviewer.name if c.reviewer else 'Aguardando revisão'),c.reason] for c in changes],[240,180,180,178]))
    def footer(canvas,doc):
        width,height=landscape(A4);canvas.setStrokeColor(orange);canvas.setLineWidth(2);canvas.line(32,height-20,width-32,height-20)
        canvas.setFillColor(ink);canvas.setFont('CacauSans',7);canvas.drawString(32,17,'Brasil Cacau · Uso interno · Quantidades em unidades físicas');canvas.drawRightString(width-32,17,f'Página {doc.page}')
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return Response(output.getvalue(),mimetype='application/pdf',headers={'Content-Disposition':f'attachment; filename=brasil-cacau-{mode}.pdf'})
