import argparse
import getpass
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from core.encriptacion import encriptar_texto

load_dotenv(ROOT_DIR / ".env")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Crea el primer usuario administrador de RiobambaTour."
    )
    parser.add_argument("--username", default=os.getenv("ADMIN_USERNAME"))
    parser.add_argument("--email", default=os.getenv("ADMIN_EMAIL"))
    parser.add_argument("--password", default=os.getenv("ADMIN_PASSWORD"))
    parser.add_argument(
        "--usar-password-default",
        action="store_true",
        help="Usa ADMIN_DEFAULT_PASSWORD desde .env sin pedir password interactivo.",
    )
    parser.add_argument(
        "--nombre-completo",
        default=os.getenv("ADMIN_NOMBRE_COMPLETO") or os.getenv("ADMIN_FULL_NAME"),
    )
    parser.add_argument(
        "--doble-auth",
        action="store_true",
        default=os.getenv("ADMIN_DOBLE_AUTH", "false").lower() == "true",
        help="Activa verificacion por correo en el login del super-admin.",
    )
    parser.add_argument("--database-url", default=os.getenv("ADMIN_DATABASE_URL"))
    return parser.parse_args()


def pedir_valor(nombre: str, valor_actual: str | None, secreto: bool = False) -> str:
    if valor_actual:
        return valor_actual

    if secreto:
        return getpass.getpass(f"{nombre}: ").strip()

    return input(f"{nombre}: ").strip()


def resolver_database_url(database_url: str | None) -> str:
    url = database_url or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL no esta configurada")

    parsed = make_url(url)
    if parsed.host == "postgres-apis" and not Path("/.dockerenv").exists():
        parsed = parsed.set(host="127.0.0.1")

    return parsed.render_as_string(hide_password=False)


def crear_admin(
    username: str,
    email: str,
    password: str,
    database_url: str | None,
    nombre_completo: str | None = None,
    doble_auth: bool = False,
) -> None:
    engine = create_engine(resolver_database_url(database_url), pool_pre_ping=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with SessionLocal() as db:
        existe = db.execute(
            text(
                """
                SELECT id_usuario, activo
                FROM conversacion.usuario
                WHERE username = :username OR email = :email
                """
            ),
            {"username": username, "email": email},
        ).mappings().first()

        if existe:
            raise RuntimeError(
                "Ya existe un usuario con ese username o email "
                f"(id_usuario={existe['id_usuario']})"
            )

        id_cargo = db.execute(
            text(
                """
                SELECT id_cargo
                FROM conversacion.cargo
                WHERE nombre = 'Super administrador' AND activo = TRUE
                """
            )
        ).scalar()
        if not id_cargo:
            raise RuntimeError("Cargo 'Super administrador' no configurado en la base de datos")

        usuario = db.execute(
            text(
                """
                INSERT INTO conversacion.usuario (
                    id_cargo, nombre_completo, username, password, email, autentificacion_doble, activo
                )
                VALUES (
                    :id_cargo,
                    :nombre_completo,
                    :username,
                    :password,
                    :email,
                    :autentificacion_doble,
                    TRUE
                )
                RETURNING id_usuario, id_cargo, username, email, autentificacion_doble
                """
            ),
            {
                "id_cargo": id_cargo,
                "nombre_completo": nombre_completo or username,
                "username": username,
                "password": encriptar_texto(password),
                "email": email,
                "autentificacion_doble": doble_auth,
            },
        ).mappings().one()
        db.commit()

    print(
        "Admin creado: "
        f"id_usuario={usuario['id_usuario']} "
        f"id_cargo={usuario['id_cargo']} "
        f"username={usuario['username']} "
        f"email={usuario['email']} "
        f"rol=super-admin "
        f"doble_auth={usuario['autentificacion_doble']}"
    )


def main() -> None:
    args = parse_args()
    username = pedir_valor("Username admin", args.username)
    email = pedir_valor("Email admin", args.email)
    password_default = os.getenv("ADMIN_DEFAULT_PASSWORD") if args.usar_password_default else None
    password = pedir_valor("Password admin", args.password or password_default, secreto=True)
    nombre_completo = pedir_valor("Nombre completo admin", args.nombre_completo or args.username)

    if not username or not email or not password or not nombre_completo:
        raise RuntimeError("username, email, password y nombre completo son obligatorios")

    crear_admin(
        username=username,
        email=email,
        password=password,
        database_url=args.database_url,
        nombre_completo=nombre_completo,
        doble_auth=args.doble_auth,
    )


if __name__ == "__main__":
    main()
