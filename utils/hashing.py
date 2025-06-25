"""Funções auxiliares para cálculo de hashes criptográficos.

Utilizado principalmente para verificar integridade de arquivos e autenticar
dados sensíveis. Aqui centralizamos o uso do ``hashlib`` para facilitar eventuais
mudanças de algoritmo.
"""

import hashlib  # Biblioteca padrão para gerar hashes como SHA-256.

def calcular_hash(data: bytes) -> str:
    """Gera o resumo criptográfico (SHA-256) de ``data``.

    Args:
        data (bytes): Dados em bytes que terão seu hash calculado.

    Returns:
        str: Valor hexadecimal representando o hash.
            Este valor pode ser armazenado para posterior comparação.
    """

    # P: Por que utilizamos SHA-256 aqui?
    # R: Essa função provê integridade, garantindo que qualquer alteração nos
    #    bytes originais resulte em um valor de hash completamente diferente.
    # A função ``sha256`` retorna um objeto de hash incremental. Como a entrada
    # já está completa, utilizamos diretamente ``hexdigest`` para obter a string
    # hexadecimal final.
    return hashlib.sha256(data).hexdigest()

