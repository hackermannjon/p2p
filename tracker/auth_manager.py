"""Gerencia usuários do tracker (registro, autenticação e logging)."""

import hashlib
import datetime

users_db = {}


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def register_user(username, password):
    if username in users_db:
        return False, "Usuario ja existe."
    users_db[username] = hash_password(password)
    return True, "Usuario registrado com sucesso."


def authenticate_user(username, password):
    hashed = hash_password(password)
    return users_db.get(username) == hashed


def get_all_users():
    return users_db


def log(msg, level="INFO"):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    color_map = {
        "INFO": "\033[94m",
        "SUCCESS": "\033[92m",
        "WARNING": "\033[93m",
        "ERROR": "\033[91m",
    }
    end_color = "\033[0m"
    color = color_map.get(level.upper(), "")
    print(f"{color}[{now}] [{level.upper()}] {msg}{end_color}")

