"""Funções auxiliares para padronizar mensagens JSON entre peers e tracker."""

# P: Como garantir que todos os módulos se comuniquem no mesmo formato?
# R: Utilizamos funções utilitárias para serializar e deserializar JSON.
#    Assim, tanto o tracker quanto os peers seguem a mesma estrutura de
#    mensagens, evitando incompatibilidades.

import json  # Módulo para manipulação de JSON em Python.

def create_message(action, data):
    """Serializa uma estrutura de dados em formato JSON padronizado."""
    return json.dumps({
        "action": action,
        **data
    })

def parse_message(raw):
    """Converte uma string JSON recebida em dicionário."""
    return json.loads(raw)
