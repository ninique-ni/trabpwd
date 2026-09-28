"""Lógica de gamificação (conquistas)."""
from app import db
from app.models import Achievement, UserAchievement


REGRAS = {
    "Primeiro Filme": lambda u: u.watched_count,
    "Cinéfilo":       lambda u: u.watched_count,
    "Crítico":        lambda u: u.watched_count,
    "Sociável":       lambda u: u.message_count,
    "Poliglota":      lambda u: u.distinct_genres,
}


def verificar_conquistas(user):
    if user.is_admin:
        return

    ja_tem = {ua.achievement_id for ua in user.achievements}
    desbloqueou = False

    for conquista in Achievement.query.all():
        if conquista.id in ja_tem:
            continue
        regra = REGRAS.get(conquista.name)
        if regra and regra(user) >= conquista.target:
            db.session.add(UserAchievement(user_id=user.id,
                                           achievement_id=conquista.id))
            desbloqueou = True

    if desbloqueou:
        db.session.commit()