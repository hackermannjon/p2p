"""Rotinas de autenticação do tracker.

Este arquivo concentra o armazenamento de credenciais dos usuários e funções
auxiliares para registro, validação e registro de eventos no console. O banco de
dados aqui é simplesmente um dicionário em memória, suficiente para fins de
estudo.
"""

import hashlib  # Utilizado para gerar hashes seguros das senhas.
import datetime  # Garante registro de logs com carimbo temporal.

users_db = {}  # username -> hashed_password

def hash_password(password: str) -> str:
    """Converte a senha em um hash seguro.

    Armazenar a senha em texto puro seria um erro grave de segurança. Ao gerar
    um hash SHA-256, garantimos que a representação gravada em ``users_db`` não
    pode ser revertida facilmente, reduzindo o impacto de um eventual vazamento.
    """
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(username: str, password: str) -> tuple[bool, str]:
    """Insere um novo usuário no banco de dados local.

    Args:
        username (str): Nome escolhido pelo usuário.
        password (str): Senha em texto que será imediatamente convertida para
            hash.

    Returns:
        tuple[bool, str]: Indica sucesso e traz uma mensagem para exibição ao
            cliente.
    """
    if username in users_db:
        return False, "Usuario ja existe."
    users_db[username] = hash_password(password)
    return True, "Usuario registrado com sucesso."

def authenticate_user(username: str, password: str) -> bool:
    """Confere se usuário e senha conferem com o registro existente.

    A senha fornecida é novamente convertida para hash e comparada com o valor
    armazenado. Dessa forma o texto original nunca é guardado na memória por
    muito tempo.
    """
    hashed = hash_password(password)
    return users_db.get(username) == hashed

def get_all_users() -> dict:
    """Expõe a base de usuários para depuração ou testes.

    Não é recomendável utilizar esta função em produção, pois expõe os hashes
    de senha. Serve apenas como utilitário interno durante o desenvolvimento.
    """
    return users_db

def log(msg: str, level: str = "INFO") -> None:
    """Imprime mensagens formatadas indicando o nível do evento.

    Cada nível possui uma cor específica para facilitar a visualização no
    terminal. A função é simples, mas já fornece noção de horário e gravidade de
    cada ação registrada no tracker.
    """

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
