import os
from datetime import timedelta
from pathlib import Path
from flask import Flask, abort, redirect, request, url_for
from flask_login import LoginManager, current_user
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
from dotenv import load_dotenv
from sqlalchemy import event

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
migrate = Migrate()


def create_app(config=None):
    load_dotenv(Path(__file__).resolve().parent.parent / '.env')
    app = Flask(__name__)
    app.config.update(
        APP_ENV=os.getenv('APP_ENV', 'development').lower(),
        TRUST_PROXY=os.getenv('TRUST_PROXY', 'false').lower() == 'true',
        TRUSTED_HOSTS=[host.strip() for host in os.getenv('TRUSTED_HOSTS', '').split(',') if host.strip()] or None,
        SECRET_KEY=os.getenv('SECRET_KEY'),
        SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE', 'true').lower() == 'true',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        MAX_CONTENT_LENGTH=8 * 1024 * 1024,
        MAX_FORM_PARTS=2000,
        EXPIRY_ALERT_DAYS=int(os.getenv("EXPIRY_ALERT_DAYS", "40")),
        COUNT_INTERVAL_DAYS=int(os.getenv('COUNT_INTERVAL_DAYS', '15')),
    )
    app.config.update({k: os.getenv(k, '') for k in ('SMTP_HOST','SMTP_USER','SMTP_PASSWORD','SMTP_FROM','PUBLIC_BASE_URL')})
    app.config['SMTP_PORT']=int(os.getenv('SMTP_PORT','587'))
    app.config['SMTP_SSL']=os.getenv('SMTP_SSL','false').lower()=='true'
    if config:
        app.config.update(config)
    if not app.config['SECRET_KEY'] or len(app.config['SECRET_KEY']) < 32:
        raise RuntimeError('Defina SECRET_KEY aleatória com pelo menos 32 caracteres.')
    if not app.config['SQLALCHEMY_DATABASE_URI']:
        raise RuntimeError('Defina DATABASE_URL.')
    from .runtime import configure_runtime
    configure_runtime(app)
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = 'main.login'
    login_manager.login_message = 'Entre com sua conta para continuar.'

    from .models import User
    @login_manager.user_loader
    def load_user(identifier):
        try:
            user_id, version = map(int, identifier.split(':'))
        except (ValueError, AttributeError):
            return None
        user = db.session.get(User, user_id)
        return user if user and user.active and user.auth_version == version else None

    @app.before_request
    def protect():
        # Recursos públicos do PWA e sondas não consultam a sessão ou tabelas de usuários.
        if request.endpoint in ('static', 'ops.sw', 'system.install', 'system.health'):
            return
        if current_user.is_authenticated and not request.endpoint == 'main.logout':
            from flask import session
            session.permanent = True
        from .permissions import enforce_permissions
        return enforce_permissions()

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'no-referrer' if request.endpoint in ('account.recover','account.verify_email') else 'strict-origin-when-cross-origin'
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; worker-src 'self'; manifest-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        if app.config['SESSION_COOKIE_SECURE']:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response

    if app.config['TRUST_PROXY']:
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    from .views import bp
    app.register_blueprint(bp)
    from .operations import ops
    app.register_blueprint(ops)
    from .account import account
    app.register_blueprint(account)
    from .lotwork import lotwork
    app.register_blueprint(lotwork)
    from .system import system
    app.register_blueprint(system)
    from .commands import register_commands
    register_commands(app)
    return app
