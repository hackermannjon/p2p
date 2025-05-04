import hashlib

users_db = {}  # username -> hashed_password

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
