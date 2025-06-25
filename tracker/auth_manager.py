"""Gerencia usuários do tracker (registro, autenticação e logging)."""

import hashlib  # Utilizado para gerar hashes seguros de senhas.
import datetime  # Manipulação de datas/hora para registrar eventos.

# Este módulo concentra as funções de autenticação do tracker.

users_db = {}  # username -> hashed_password
# Em uma aplicação real, este dicionário seria substituído por um banco de dados
# permanente; aqui fica somente em memória para simplificar.


def hash_password(password):
    """Gera o hash SHA-256 de uma senha em texto claro."""
    # P: Por que utilizar hash em vez de armazenar a senha diretamente?
    # R: O hash é uma forma de proteger a senha caso o banco seja exposto.
    #    Mesmo conhecendo o hash, não é trivial descobrir a senha original.
    return hashlib.sha256(password.encode()).hexdigest()


def register_user(username, password):
    """Registra um novo usuário no banco em memória.

    Args:
        username (str): Nome de usuário desejado.
        password (str): Senha em texto claro.

    Returns:
        tuple: (status (bool), mensagem (str)) indicando o resultado.
    """
    if username in users_db:
        return False, "Usuario ja existe."
    users_db[username] = hash_password(password)
    return True, "Usuario registrado com sucesso."


def authenticate_user(username, password):
    """Verifica se a senha informada corresponde à armazenada."""
    hashed = hash_password(password)
    return users_db.get(username) == hashed


def get_all_users():
    """Retorna o dicionário completo de usuários."""
    return users_db


def log(msg, level="INFO"):
    """Imprime mensagens coloridas para facilitar o debug do tracker."""
    # P: Como é produzido o formato colorido no terminal?
    # R: São usados códigos ANSI de cores. Cada nível (INFO, SUCCESS, ...)
    #    possui um código diferente definido em `color_map`.
    now = datetime.datetime.now().strftime("%H:%M:%S")
    color_map = {
        "INFO": "\033[94m",     # Azul
        "SUCCESS": "\033[92m",  # Verde
        "WARNING": "\033[93m",  # Amarelo
        "ERROR": "\033[91m",    # Vermelho
    }
    end_color = "\033[0m"
    color = color_map.get(level.upper(), "")
    print(f"{color}[{now}] [{level.upper()}] {msg}{end_color}")

