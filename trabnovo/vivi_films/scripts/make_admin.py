"""
make_admin.py
Transforma um usuário comum em administrador.
Uso:  py scripts/make_admin.py
"""
import sys
from pathlib import Path

# Garante que a raiz do projeto (vivi_films/) esteja no sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app, db
from app.models import User


def main():
    app = create_app()

    with app.app_context():
        # Lista todos os usuários para você escolher
        usuarios = User.query.order_by(User.id).all()

        if not usuarios:
            print("\n[!] Nenhum usuário cadastrado ainda.")
            print("    Cadastre-se primeiro pelo site em /register.\n")
            return

        print("\n=== Usuários cadastrados ===")
        for u in usuarios:
            marca = " [ADMIN]" if u.is_admin else ""
            verif = " ✔" if u.is_verified else " (não verificado)"
            print(f"  ID {u.id:>3} | {u.username:<30} | {u.email:<40}{verif}{marca}")
        print()

        entrada = input("Digite o ID do usuário que virará admin: ").strip()

        try:
            user_id = int(entrada)
        except ValueError:
            print("\n[!] ID inválido. Digite apenas números.\n")
            return

        user = db.session.get(User, user_id)

        if not user:
            print(f"\n[!] Usuário com ID {user_id} não encontrado.\n")
            return

        user.is_admin = True
        user.is_verified = True   # também verificamos para evitar bloqueio
        db.session.commit()

        print(f"\n[✔] Pronto! '{user.username}' agora é ADMIN e está verificado.")
        print("    Feche o servidor (Ctrl+C) e rode de novo: py run.py")
        print("    Depois faça logout e login novamente.\n")


if __name__ == "__main__":
    main()