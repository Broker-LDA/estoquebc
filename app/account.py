"""Perfil, verificação de e-mail e senhas temporárias de uso individual."""
import hashlib
import re
import secrets
import smtplib
import ssl
from datetime import timedelta,timezone
from email.message import EmailMessage
from flask import Blueprint,current_app,request,render_template,url_for,redirect,flash,abort
from flask_login import login_required,current_user,login_user,logout_user
from sqlalchemy import select,update
from sqlalchemy.exc import IntegrityError
from . import db
from .models import User,AccountToken,AccountAudit,AuthThrottle,utcnow
from .views import admin_only,finish

account=Blueprint('account',__name__)
AVATARS=[f'avatar-{i}' for i in range(1,7)]+['chocolate','logo-1','logo-2','logo-3']


def email_address(value):
    value=value.strip().lower()
    if len(value)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value):raise ValueError('Informe um e-mail válido.')
    return value


def send_email(to,subject,body):
    config=current_app.config
    if not config.get('SMTP_HOST') or not config.get('SMTP_FROM'):raise ValueError('Envio indisponível: o TI precisa configurar SMTP_HOST e SMTP_FROM.')
    msg=EmailMessage();msg['From']=config['SMTP_FROM'];msg['To']=to;msg['Subject']=subject;msg.set_content(body)
    try:
        if config['SMTP_SSL']:
            server=smtplib.SMTP_SSL(config['SMTP_HOST'],config['SMTP_PORT'],timeout=12,context=ssl.create_default_context())
        else:server=smtplib.SMTP(config['SMTP_HOST'],config['SMTP_PORT'],timeout=12)
        with server:
            if not config['SMTP_SSL']:server.starttls(context=ssl.create_default_context())
            if config.get('SMTP_USER'):server.login(config['SMTP_USER'],config.get('SMTP_PASSWORD',''))
            server.send_message(msg)
    except (OSError,smtplib.SMTPException) as exc:
        raise ValueError('Não foi possível enviar o e-mail. Confira a configuração SMTP com o TI.') from exc


def issue_token(user,purpose,value):
    base=current_app.config.get('PUBLIC_BASE_URL','').rstrip('/')
    if not base.startswith(('https://','http://localhost','http://127.0.0.1')):
        raise ValueError('Configure PUBLIC_BASE_URL com o endereço HTTPS oficial do sistema.')
    db.session.execute(update(AccountToken).where(AccountToken.user_id==user.id,AccountToken.purpose==purpose,AccountToken.used.is_(False)).values(used=True))
    raw=secrets.token_urlsafe(32)
    db.session.add(AccountToken(user_id=user.id,digest=hashlib.sha256(raw.encode()).hexdigest(),purpose=purpose,value=value,expires_at=utcnow()+timedelta(minutes=30)))
    return base+url_for('account.verify_email' if purpose=='email' else 'account.recover',token=raw)


def throttle():
    key=hashlib.sha256(('recovery:'+str(request.remote_addr)).encode()).hexdigest()
    row=db.session.scalar(select(AuthThrottle).where(AuthThrottle.key==key).with_for_update())
    now=utcnow()
    if not row:
        row=AuthThrottle(key=key,attempts=0,started_at=now);db.session.add(row)
    elif (now-row.started_at.replace(tzinfo=timezone.utc)).total_seconds()>900:row.attempts=0;row.started_at=now
    row.attempts+=1;allowed=row.attempts<=10
    try:db.session.commit()
    except IntegrityError:db.session.rollback();return False
    return allowed


@account.route('/perfil',methods=['GET','POST'])
@login_required
def profile():
    if request.method=='POST':
        def action():
            if not current_user.check_password(request.form.get('current_password','')):raise ValueError('Senha atual incorreta.')
            name=request.form.get('name','').strip()
            avatar=request.form.get('avatar','')
            if not 2<=len(name)<=120 or avatar not in AVATARS:raise ValueError('Confira nome e avatar.')
            new=request.form.get('new_password','')
            if current_user.must_change_password and not new:raise ValueError('Defina sua nova senha para continuar.')
            if new:
                if new!=request.form.get('confirm_password'):raise ValueError('As senhas não conferem.')
                if current_user.check_password(new):raise ValueError('Escolha uma senha diferente da atual.')
                current_user.set_password(new);current_user.must_change_password=False;current_user.temporary_until=None
                db.session.execute(update(AccountToken).where(AccountToken.user_id==current_user.id,AccountToken.purpose=='reset').values(used=True))
            address=request.form.get('email','').strip()
            if address and address!=current_user.email:
                address=email_address(address)
                if db.session.scalar(select(User.id).where(User.email==address,User.id!=current_user.id)):raise ValueError('E-mail indisponível.')
                current_user.pending_email=address
            current_user.name=name;current_user.avatar=avatar
            db.session.add(AccountAudit(actor_id=current_user.id,user_id=current_user.id,action='Perfil atualizado'))
            db.session.commit();login_user(current_user,remember=False,fresh=True)
        return finish(action,'Perfil atualizado. Se alterou o e-mail, solicite a verificação abaixo.',request.path)
    return render_template('profile.html',avatars=AVATARS)


@account.post('/perfil/verificar-email')
@login_required
def send_verification():
    def action():
        address=current_user.pending_email or current_user.email
        if not address:raise ValueError('Cadastre um e-mail no perfil primeiro.')
        last=db.session.scalar(select(AccountToken).where(AccountToken.user_id==current_user.id,AccountToken.purpose=='email').order_by(AccountToken.id.desc()))
        if last and (utcnow()-last.created_at.replace(tzinfo=timezone.utc)).total_seconds()<60:raise ValueError('Aguarde um minuto antes de reenviar.')
        url=issue_token(current_user,'email',address)
        send_email(address,'Brasil Cacau - confirme seu e-mail','Confirme seu endereço em até 30 minutos:\n'+url)
        db.session.commit()
    return finish(action,'Verificação enviada. Confira sua caixa de e-mail.',url_for('account.profile'))


@account.route('/confirmar-email/<token>',methods=['GET','POST'])
def verify_email(token):
    t=db.session.scalar(select(AccountToken).where(AccountToken.digest==hashlib.sha256(token.encode()).hexdigest(),AccountToken.purpose=='email').with_for_update())
    valid=t and not t.used and t.expires_at.replace(tzinfo=timezone.utc)>utcnow()
    if not valid:return render_template('token.html',valid=False),400
    if request.method=='POST':
        u=db.session.get(User,t.user_id)
        if not u.active or t.value!=(u.pending_email or u.email):abort(400)
        u.email=t.value;u.pending_email=None;u.email_verified=True;t.used=True
        try:db.session.commit()
        except IntegrityError:
            db.session.rollback();flash('Este e-mail já está vinculado a outra conta.','error');return redirect(url_for('main.login'))
        flash('E-mail verificado.','success');return redirect(url_for('account.profile') if current_user.is_authenticated else url_for('main.login'))
    return render_template('token.html',valid=True)


@account.route('/esqueci-senha',methods=['GET','POST'])
def forgot():
    if request.method=='POST':
        generic='Se houver uma conta ativa com esse e-mail verificado, enviaremos as instruções. Você também pode solicitar ao TI.'
        if throttle():
            try:
                address=email_address(request.form.get('email',''))
                u=db.session.scalar(select(User).where(User.email==address,User.email_verified.is_(True),User.active.is_(True)))
                if u:
                    url=issue_token(u,'reset',u.email)
                    send_email(u.email,'Brasil Cacau - redefinição de senha','Defina sua senha em até 30 minutos:\n'+url+'\nSe não solicitou, ignore esta mensagem.')
                    db.session.commit()
            except (ValueError,IntegrityError):db.session.rollback()
        flash(generic,'success');return redirect(request.path)
    return render_template('forgot.html')


@account.route('/recuperar-senha/<token>',methods=['GET','POST'])
def recover(token):
    t=db.session.scalar(select(AccountToken).where(AccountToken.digest==hashlib.sha256(token.encode()).hexdigest(),AccountToken.purpose=='reset').with_for_update())
    if not t or t.used or t.expires_at.replace(tzinfo=timezone.utc)<=utcnow():return render_template('token.html',valid=False),400
    u=db.session.get(User,t.user_id)
    if not u.active or not u.email_verified or u.email!=t.value:abort(400)
    if request.method=='POST':
        try:
            password=request.form.get('password','')
            if password!=request.form.get('confirm_password'):raise ValueError('As senhas não conferem.')
            u.set_password(password);u.must_change_password=False;u.temporary_until=None;u.failed_attempts=0;u.locked_until=None;t.used=True
            db.session.add(AccountAudit(actor_id=u.id,user_id=u.id,action='Senha recuperada por e-mail'))
            db.session.commit();logout_user();flash('Senha redefinida. Entre novamente.','success');return redirect(url_for('main.login'))
        except ValueError as exc:db.session.rollback();flash(str(exc),'error')
    return render_template('recover.html')


@account.post('/usuarios/<int:uid>/resetar-senha')
@admin_only
def admin_reset(uid):
    if not current_user.check_password(request.form.get('admin_password','')):
        flash('Confirme sua senha de administrador.','error');return redirect(url_for('main.users'))
    target=db.session.scalar(select(User).where(User.id==uid).with_for_update())
    if not target or not target.active:abort(404)
    if target.id==current_user.id:
        flash('Altere sua própria senha em Meu perfil.','error');return redirect(url_for('account.profile'))
    temporary=secrets.token_urlsafe(12)
    target.set_password(temporary);target.must_change_password=True;target.temporary_until=utcnow()+timedelta(hours=24)
    target.failed_attempts=0;target.locked_until=None
    db.session.execute(update(AccountToken).where(AccountToken.user_id==uid,AccountToken.purpose=='reset').values(used=True))
    db.session.add(AccountAudit(actor_id=current_user.id,user_id=uid,action='Senha temporária gerada pelo administrador'))
    db.session.commit()
    delivered=False;error=''
    if target.email and target.email_verified:
        try:
            send_email(target.email,'Brasil Cacau - acesso temporário',f'Login: {target.username}\nSenha temporária: {temporary}\nVálida por 24 horas. Troca obrigatória no próximo acesso.')
            delivered=True
        except ValueError as exc:error=str(exc)
    return render_template('temporary_password.html',target=target,temporary=None if delivered else temporary,delivered=delivered,error=error)
