from datetime import datetime
from flask_login import UserMixin
from app import db, login_manager


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    birthdate = db.Column(db.Date, nullable=False)
    country = db.Column(db.String(50), nullable=False)
    profile_pic = db.Column(db.String(120), default='default.jpg')
    is_admin = db.Column(db.Boolean, default=False)
    is_verified = db.Column(db.Boolean, default=False)
    verification_code = db.Column(db.String(4))
    username_last_changed = db.Column(db.DateTime)

    library_items = db.relationship('UserMovie', backref='user',
                                    cascade="all, delete-orphan")
    achievements = db.relationship('UserAchievement', backref='user',
                                   cascade="all, delete-orphan")

    @property
    def watched_count(self):
        return sum(1 for i in self.library_items if i.status == 'watched')

    @property
    def message_count(self):
        return ChatMessage.query.filter_by(sender_id=self.id).count()

    @property
    def distinct_genres(self):
        return len({i.movie.genre for i in self.library_items if i.movie})


class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    genre = db.Column(db.String(50), nullable=False)
    duration_minutes = db.Column(db.Integer, default=0)
    trailer_url = db.Column(db.String(300))
    is_release = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def formatted_duration(self):
        h, m = divmod(self.duration_minutes, 60)
        if h and m:
            return f"{h}h {m}min"
        return f"{h}h" if h else f"{m}min"


class UserMovie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    movie_id = db.Column(db.Integer, db.ForeignKey('movie.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    rating = db.Column(db.Integer)
    comment = db.Column(db.Text)

    movie = db.relationship('Movie',
                            backref=db.backref('user_movies', cascade='all, delete-orphan'))


class ChatRoom(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user1_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user2_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status_user1 = db.Column(db.String(20), default='pending')
    status_user2 = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user1 = db.relationship('User', foreign_keys=[user1_id])
    user2 = db.relationship('User', foreign_keys=[user2_id])
    messages = db.relationship('ChatMessage', backref='room',
                               cascade="all, delete-orphan")

    def other_user(self, current_id):
        return self.user2 if self.user1_id == current_id else self.user1

    def status_of(self, user_id):
        return self.status_user1 if self.user1_id == user_id else self.status_user2


class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('chat_room.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    cleared_by_user1 = db.Column(db.Boolean, default=False)
    cleared_by_user2 = db.Column(db.Boolean, default=False)

    sender = db.relationship('User', foreign_keys=[sender_id])


class Achievement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(200), nullable=False)
    icon = db.Column(db.String(10), default='🏅')
    target = db.Column(db.Integer, default=1)


class UserAchievement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    achievement_id = db.Column(db.Integer, db.ForeignKey('achievement.id'), nullable=False)
    unlocked_at = db.Column(db.DateTime, default=datetime.utcnow)

    achievement = db.relationship('Achievement')