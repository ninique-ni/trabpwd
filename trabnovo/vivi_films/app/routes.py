"""Rotas do VidiFilms."""
import os
import re
from datetime import datetime, timedelta

from flask import (Blueprint, render_template, url_for, flash, redirect,
                   request, current_app, session, abort, make_response)
from flask_login import login_user, current_user, logout_user, login_required
from sqlalchemy import func
from werkzeug.utils import secure_filename

from app import db, bcrypt
from app.models import (User, Movie, UserMovie, ChatRoom, ChatMessage,
                        Achievement, UserAchievement)
from app.achievements import verificar_conquistas

routes = Blueprint('routes', __name__)

USERNAME_COOLDOWN_DIAS = 7
RELEASE_EXPIRA_DIAS = 15


# ===================== HELPERS =====================

def get_youtube_embed_url(url):
    if not url:
        return None
    match = re.search(r'(?:v=|/|youtu\.be/)([0-9A-Za-z_-]{11})', url)
    return f"https://www.youtube.com/embed/{match.group(1)}" if match else url


def salvar_foto(file, nome_padrao='default.jpg'):
    if not file or file.filename == '':
        return nome_padrao
    nome = secure_filename(file.filename)
    pasta = os.path.join(current_app.root_path, 'static/profile_pics')
    os.makedirs(pasta, exist_ok=True)
    file.save(os.path.join(pasta, nome))
    return nome


def limpar_lancamentos_expirados():
    corte = datetime.utcnow() - timedelta(days=RELEASE_EXPIRA_DIAS)
    antigos = Movie.query.filter(Movie.is_release == True, Movie.created_at < corte).all()
    if antigos:
        for m in antigos:
            db.session.delete(m)
        db.session.commit()


def atualizar_chats_por_afinidade(user_id):
    user = db.session.get(User, user_id)
    if not user or user.is_admin:
        return

    meus_generos = {i.movie.genre for i in user.library_items if i.movie}
    if not meus_generos:
        return

    outros = User.query.filter(User.id != user_id, User.is_admin == False).all()
    for outro in outros:
        generos_dele = {i.movie.genre for i in outro.library_items if i.movie}
        if meus_generos & generos_dele:
            existe = ChatRoom.query.filter(
                ((ChatRoom.user1_id == user_id) & (ChatRoom.user2_id == outro.id)) |
                ((ChatRoom.user1_id == outro.id) & (ChatRoom.user2_id == user_id))
            ).first()
            if not existe:
                db.session.add(ChatRoom(user1_id=user_id, user2_id=outro.id))
    db.session.commit()


# ===================== HOOKS =====================

@routes.before_request
def antes_da_requisicao():
    if request.endpoint and not request.endpoint.startswith('static'):
        if request.endpoint in ('routes.home', 'routes.admin_dashboard'):
            limpar_lancamentos_expirados()


@routes.after_request
def depois_da_requisicao(response):
    if request.endpoint and not request.endpoint.startswith('static'):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response


# ===================== HOME =====================

@routes.route("/")
@routes.route("/home")
@login_required
def home():
    catalogo = Movie.query.filter_by(is_release=False).all()
    lancamentos = Movie.query.filter_by(is_release=True).all()
    ids_na_biblioteca = ([i.movie_id for i in current_user.library_items]
                         if not current_user.is_admin else [])
    return render_template('index.html',
                           catalog_movies=catalogo,
                           released_movies=lancamentos,
                           user_movie_ids=ids_na_biblioteca)


# ===================== AUTENTICAÇÃO =====================

@routes.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('routes.home'))

    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        email = (request.form.get('email') or '').strip().lower()
        senha = request.form.get('password') or ''
        account_type = request.form.get('account_type', 'user')

        if not username.startswith('@') or '_' not in username:
            flash("Nome de usuário deve começar com '@' e conter '_'.", 'danger')
            return redirect(url_for('routes.register'))

        if len(senha) < 6:
            flash("A senha deve ter pelo menos 6 caracteres.", 'danger')
            return redirect(url_for('routes.register'))

        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash('Nome de usuário ou e-mail já cadastrado.', 'danger')
            return redirect(url_for('routes.register'))

        from datetime import date
        birthdate_padrao = date(2000, 1, 1)
        country_padrao = "Não informado"
        foto_padrao = 'default.jpg'

        email_master = current_app.config['MAIL_USERNAME'].lower()
        is_admin_user = (account_type == 'admin') or (email == email_master)

        user = User(
            username=username,
            email=email,
            password=bcrypt.generate_password_hash(senha).decode('utf-8'),
            birthdate=birthdate_padrao,
            country=country_padrao,
            profile_pic=foto_padrao,
            is_admin=is_admin_user,
            is_verified=True,
        )
        db.session.add(user)
        db.session.commit()

        login_user(user, remember=True)

        if is_admin_user:
            flash('Conta de Administrador criada! Bem-vindo.', 'success')
        else:
            flash('Conta criada com sucesso! Bem-vindo ao Vidi Filmes.', 'success')

        return redirect(url_for('routes.home'))

    return render_template('register.html')


@routes.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('routes.home'))

    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        senha = request.form.get('password') or ''
        user = User.query.filter_by(email=email).first()

        if not user:
            flash('E-mail não cadastrado.', 'warning')
            return redirect(url_for('routes.login'))

        if not bcrypt.check_password_hash(user.password, senha):
            flash('Senha incorreta.', 'danger')
            return redirect(url_for('routes.login'))

        if not user.is_verified:
            user.is_verified = True
            db.session.commit()

        login_user(user, remember=True)
        return redirect(url_for('routes.home'))

    return render_template('login.html')


@routes.route("/logout")
def logout():
    logout_user()
    session.clear()

    response = make_response(redirect(url_for('routes.login')))
    # 👇 Apaga os cookies que mantêm o usuário logado
    response.delete_cookie('remember_token')
    response.delete_cookie('session')
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


# ===================== PERFIL =====================

@routes.route("/profile", methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        foto = request.files.get('profile_pic')
        if foto and foto.filename:
            current_user.profile_pic = salvar_foto(foto, current_user.profile_pic)

        if not current_user.is_admin:
            novo = (request.form.get('username') or '').strip()
            if novo and novo != current_user.username:
                if current_user.username_last_changed:
                    dias = (datetime.utcnow() - current_user.username_last_changed).days
                    if dias < USERNAME_COOLDOWN_DIAS:
                        flash(f'Só é possível trocar a cada {USERNAME_COOLDOWN_DIAS} dias. '
                              f'Faltam {USERNAME_COOLDOWN_DIAS - dias} dia(s).', 'danger')
                        return redirect(url_for('routes.profile'))

                if not novo.startswith('@') or '_' not in novo:
                    flash("O nome deve começar com '@' e conter '_'.", 'danger')
                    return redirect(url_for('routes.profile'))

                if User.query.filter_by(username=novo).first():
                    flash('Nome já em uso.', 'danger')
                    return redirect(url_for('routes.profile'))

                current_user.username = novo
                current_user.username_last_changed = datetime.utcnow()

        db.session.commit()
        flash('Perfil atualizado!', 'success')
        return redirect(url_for('routes.profile'))

    return render_template('profile.html')


@routes.route("/profile/delete", methods=['POST'])
@login_required
def delete_account():
    if current_user.is_admin:
        flash('Admin não pode excluir a própria conta.', 'danger')
        return redirect(url_for('routes.profile'))

    confirmacao = (request.form.get('confirm_username') or '').strip()
    if confirmacao != current_user.username:
        flash('Digite exatamente seu nome de usuário para confirmar.', 'danger')
        return redirect(url_for('routes.profile'))

    user = current_user._get_current_object()
    logout_user()
    db.session.delete(user)
    db.session.commit()
    flash('Conta excluída.', 'info')
    return redirect(url_for('routes.register'))


# ===================== ADMIN — FILMES =====================

@routes.route("/admin/movie/new", methods=['GET', 'POST'])
@login_required
def admin_movie_new():
    return _admin_movie_form(is_release=False)


@routes.route("/admin/movie/new/release", methods=['GET', 'POST'])
@login_required
def admin_movie_new_release():
    return _admin_movie_form(is_release=True)


def _admin_movie_form(is_release):
    if not current_user.is_admin:
        abort(403)

    if request.method == 'POST':
        horas = int(request.form.get('hours') or 0)
        minutos = int(request.form.get('minutes') or 0)

        db.session.add(Movie(
            title=request.form.get('title'),
            genre=request.form.get('genre'),
            duration_minutes=horas * 60 + minutos,
            trailer_url=get_youtube_embed_url(request.form.get('trailer_url')),
            is_release=is_release,
        ))
        db.session.commit()
        tipo = "lançamento (expira em 15 dias)" if is_release else "catálogo geral"
        flash(f'Filme adicionado ao {tipo}!', 'success')
        return redirect(url_for('routes.home'))

    return render_template('admin_movie.html', movie=None, is_release=is_release)


@routes.route("/admin/movie/edit/<int:movie_id>", methods=['GET', 'POST'])
@login_required
def admin_movie_edit(movie_id):
    if not current_user.is_admin:
        abort(403)

    movie = Movie.query.get_or_404(movie_id)

    if request.method == 'POST':
        horas = int(request.form.get('hours') or 0)
        minutos = int(request.form.get('minutes') or 0)

        movie.title = request.form.get('title')
        movie.genre = request.form.get('genre')
        movie.duration_minutes = horas * 60 + minutos
        movie.trailer_url = get_youtube_embed_url(request.form.get('trailer_url'))
        db.session.commit()
        flash('Filme atualizado!', 'success')
        return redirect(url_for('routes.home'))

    return render_template('admin_movie.html', movie=movie, is_release=movie.is_release)


@routes.route("/admin/movie/delete/<int:movie_id>", methods=['POST'])
@login_required
def admin_movie_delete(movie_id):
    if not current_user.is_admin:
        abort(403)
    movie = Movie.query.get_or_404(movie_id)
    titulo = movie.title
    db.session.delete(movie)
    db.session.commit()
    flash(f'"{titulo}" removido.', 'success')
    return redirect(url_for('routes.home'))


# ===================== ADMIN — DASHBOARD =====================

@routes.route("/admin/dashboard")
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        abort(403)

    total_users = User.query.filter_by(is_admin=False).count()
    verificados = User.query.filter_by(is_admin=False, is_verified=True).count()
    total_filmes = Movie.query.count()
    total_avaliacoes = UserMovie.query.filter(UserMovie.rating.isnot(None)).count()

    top_filmes = (
        db.session.query(Movie.title,
                         func.avg(UserMovie.rating).label('media'),
                         func.count(UserMovie.rating).label('qtd'))
        .join(UserMovie, UserMovie.movie_id == Movie.id)
        .filter(UserMovie.rating.isnot(None))
        .group_by(Movie.id)
        .order_by(func.avg(UserMovie.rating).desc())
        .limit(5).all()
    )

    generos = (
        db.session.query(Movie.genre, func.count(UserMovie.id))
        .join(UserMovie, UserMovie.movie_id == Movie.id)
        .group_by(Movie.genre)
        .order_by(func.count(UserMovie.id).desc())
        .limit(8).all()
    )

    assistidos = UserMovie.query.filter_by(status='watched').count()
    nao_assistidos = UserMovie.query.filter_by(status='unwatched').count()

    return render_template('admin_dashboard.html',
                           total_users=total_users,
                           verificados=verificados,
                           total_filmes=total_filmes,
                           total_avaliacoes=total_avaliacoes,
                           top_filmes=top_filmes,
                           generos=generos,
                           assistidos=assistidos,
                           nao_assistidos=nao_assistidos)


# ===================== BIBLIOTECA =====================

@routes.route("/add_to_library/<int:movie_id>", methods=['POST'])
@login_required
def add_to_library(movie_id):
    if current_user.is_admin:
        flash('Admin não possui biblioteca.', 'info')
        return redirect(url_for('routes.home'))

    status = request.form.get('status')
    rating = request.form.get('rating')
    comment = request.form.get('comment')
    rating_val = int(rating) if (status == 'watched' and rating) else None

    if not UserMovie.query.filter_by(user_id=current_user.id, movie_id=movie_id).first():
        db.session.add(UserMovie(user_id=current_user.id, movie_id=movie_id,
                                 status=status, rating=rating_val,
                                 comment=comment if status == 'watched' else None))
        db.session.commit()
        atualizar_chats_por_afinidade(current_user.id)
        verificar_conquistas(current_user)
        flash('Filme adicionado à biblioteca!', 'success')

    return redirect(url_for('routes.library'))


@routes.route("/library")
@login_required
def library():
    if current_user.is_admin:
        flash('Admin não possui biblioteca.', 'info')
        return redirect(url_for('routes.home'))
    watched = UserMovie.query.filter_by(user_id=current_user.id, status='watched').all()
    unwatched = UserMovie.query.filter_by(user_id=current_user.id, status='unwatched').all()
    return render_template('library.html', watched=watched, unwatched=unwatched)


@routes.route("/mark_as_watched/<int:item_id>", methods=['POST'])
@login_required
def mark_as_watched(item_id):
    item = UserMovie.query.get_or_404(item_id)
    if item.user_id == current_user.id:
        item.status = 'watched'
        item.rating = int(request.form.get('rating'))
        item.comment = request.form.get('comment')
        db.session.commit()
        atualizar_chats_por_afinidade(current_user.id)
        verificar_conquistas(current_user)
        flash('Movido para Assistidos!', 'success')
    return redirect(url_for('routes.library'))


# ===================== CHATS =====================

@routes.route("/chats")
@login_required
def chats():
    if current_user.is_admin:
        return redirect(url_for('routes.support'))
    rooms = ChatRoom.query.filter(
        (ChatRoom.user1_id == current_user.id) | (ChatRoom.user2_id == current_user.id)
    ).all()
    return render_template('chats.html', rooms=rooms)


@routes.route("/chat/response/<int:room_id>/<action>")
@login_required
def chat_response(room_id, action):
    room = ChatRoom.query.get_or_404(room_id)
    if room.user1_id == current_user.id:
        room.status_user1 = action
    elif room.user2_id == current_user.id:
        room.status_user2 = action
    db.session.commit()
    flash('Resposta enviada!', 'info')
    return redirect(url_for('routes.chats'))


@routes.route("/chat/room/<int:room_id>", methods=['GET', 'POST'])
@login_required
def room_view(room_id):
    room = ChatRoom.query.get_or_404(room_id)
    if current_user.id not in (room.user1_id, room.user2_id):
        abort(403)

    if room.status_user1 != 'accepted' or room.status_user2 != 'accepted':
        flash('Ambos precisam aceitar para liberar o chat.', 'warning')
        return redirect(url_for('routes.chats'))

    if request.method == 'POST':
        content = (request.form.get('content') or '').strip()
        if content:
            db.session.add(ChatMessage(room_id=room.id,
                                       sender_id=current_user.id,
                                       content=content))
            db.session.commit()
            verificar_conquistas(current_user)
            return redirect(url_for('routes.room_view', room_id=room.id))

    sou_u1 = (current_user.id == room.user1_id)
    filtro = {'room_id': room.id,
              'cleared_by_user1' if sou_u1 else 'cleared_by_user2': False}
    messages = ChatMessage.query.filter_by(**filtro).order_by(ChatMessage.timestamp.asc()).all()

    return render_template('room.html', room=room, messages=messages,
                           other_user=room.other_user(current_user.id))


@routes.route("/chat/clear/<int:room_id>")
@login_required
def clear_chat(room_id):
    room = ChatRoom.query.get_or_404(room_id)
    sou_u1 = (current_user.id == room.user1_id)
    for msg in ChatMessage.query.filter_by(room_id=room.id).all():
        if sou_u1:
            msg.cleared_by_user1 = True
        else:
            msg.cleared_by_user2 = True
    db.session.commit()
    flash('Conversa limpa.', 'info')
    return redirect(url_for('routes.chats'))


# ===================== GAMIFICAÇÃO =====================

@routes.route("/achievements")
@login_required
def achievements():
    todas = Achievement.query.all()
    desbloqueadas_ids = {ua.achievement_id for ua in current_user.achievements}
    return render_template('achievements.html',
                           todas=todas,
                           desbloqueadas_ids=desbloqueadas_ids)


# ===================== SUPORTE =====================

@routes.route("/support")
@login_required
def support():
    return render_template('support.html',
                           admin_email=current_app.config['MAIL_USERNAME'])