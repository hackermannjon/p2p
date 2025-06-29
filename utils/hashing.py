import hashlib

def calcular_hash(data):
    return hashlib.sha256(data).hexdigest()

