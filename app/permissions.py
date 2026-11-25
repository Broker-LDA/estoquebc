from functools import wraps
from flask import abort
from flask_login import login_required,current_user


def managers(view):
    @wraps(view)
    @login_required
    def wrapped(*args,**kwargs):
        if current_user.role not in ('admin','lojista'):abort(403)
        return view(*args,**kwargs)
    return wrapped


def enforce_permissions():
    """Controle no servidor, inclusive para URLs e POSTs digitados manualmente."""
    from flask import request,redirect,url_for
    if not current_user.is_authenticated:return
    if current_user.must_change_password and request.endpoint not in ('account.profile','main.logout','static'):
        return redirect(url_for('account.profile'))
    if current_user.role=='assistente':
        allowed={'static','ops.sw','main.dashboard','main.products','ops.customers','ops.lots','ops.batch_count',
                 'ops.history_pdf','main.movements','main.export_movements','main.counts','main.new_count',
                 'main.count_detail','main.count_line','main.count_submit','main.logout','account.profile',
                 'account.verify_email','account.send_verification','lotwork.propose','lotwork.audit','lotwork.export_pdf'}
        if request.endpoint not in allowed or (request.endpoint=='ops.customers' and request.method!='GET'):
            abort(403)
