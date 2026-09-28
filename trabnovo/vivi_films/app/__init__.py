import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_mail import Mail
from flask_wtf import CSRFProtect

db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()
mail = Mail()
csrf = CSRFProtect()

login_manager.login_view = 'routes.login'
login_manager.login_message = 'Faça login para continuar.'
login_manager.login_message_category = 'info'

MAIL_USER = os.environ.get("VIDI_MAIL_USER", "suporte.vidifilms@gmail.com")
MAIL_PASS = os.environ.get("VIDI_MAIL_PASS", "feszavtnmpqxxybg")


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.update(
        SECRET_KEY=os.environ.get("VIDI_SECRET_KEY", "troque-esta-chave-em-producao"),
        SQLALCHEMY_DATABASE_URI="sqlite:///vidifilms.db",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAIL_SERVER="smtp.gmail.com",
        MAIL_PORT=587,
        MAIL_USE_TLS=True,
        MAIL_USERNAME=MAIL_USER,
        MAIL_PASSWORD=MAIL_PASS,
        MAX_CONTENT_LENGTH=4 * 1024 * 1024,
        WTF_CSRF_ENABLED=True,
    )

    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)

    from app.routes import routes
    app.register_blueprint(routes)

    with app.app_context():
        from app import models  # noqa: F401
        db.create_all()
        _seed_achievements()

    return app


def _seed_achievements():
    from app.models import Achievement
    if Achievement.query.count() > 0:
        return
    padrao = [
        ("Primeiro Filme", "Avaliou o primeiro filme.",           "🎬", 1),
        ("Cinéfilo",       "Avaliou 5 filmes.",                   "🍿", 5),
        ("Crítico",        "Avaliou 20 filmes.",                  "🏆", 20),
        ("Sociável",       "Enviou 10 mensagens nos chats.",      "💬", 10),
        ("Poliglota",      "3 gêneros diferentes na biblioteca.", "🌍", 3),
    ]
    for nome, desc, icone, meta in padrao:
        db.session.add(Achievement(name=nome, description=desc, icon=icone, target=meta))
    db.session.commit()