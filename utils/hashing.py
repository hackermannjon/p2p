"""Funções simples de hash para validação de dados."""

# Este módulo isola o cálculo de hash para que, se necessário, possamos alterar
# o algoritmo (ex.: para SHA-1 ou SHA-3) em apenas um lugar.

import hashlib  # Biblioteca de hashes criptográficos (SHA-256).

def calcular_hash(data):
    """Retorna o SHA-256 de ``data`` (bytes)."""
    # P: Por que o SHA-256 é usado aqui?
    # R: É um algoritmo amplamente suportado e suficientemente seguro para
    #    verificar integridade dos chunks sem ser lento.
    return hashlib.sha256(data).hexdigest()

