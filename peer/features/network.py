# peer/features/network.py
"""Camada de rede responsável por comunicação entre peer e tracker."""

import socket  # Sockets TCP para envio de mensagens.
import json    # Serialização das mensagens trocadas com o tracker.
from utils.logger import log
import utils.config as config

# Este módulo contém apenas uma função utilitária de rede. Centralizar as
# comunicações com o tracker facilita ajustes futuros (ex: mudar para UDP ou
# adicionar criptografia) sem modificar o restante do código.

def send_to_tracker(data):
    """Envia uma mensagem TCP ao tracker e retorna a resposta como dict."""
    # P: Por que abrir e fechar o socket a cada requisição?
    # R: As mensagens são eventuais e curtas. Manter conexões permanentes
    #    aumentaria a complexidade sem ganhos significativos.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(10)
            s.connect((config.TRACKER_HOST, config.TRACKER_PORT))
            s.sendall(json.dumps(data).encode())
            response = s.recv(8192).decode()
            # Decodificamos a resposta em JSON para retornar um dicionário
            return json.loads(response)
    except socket.timeout:
        log("Timeout na comunicação com o tracker.", "ERROR")
        return {"status": False, "message": "Tracker não respondeu."}
    except ConnectionRefusedError:
        log("Conexão com o tracker recusada.", "ERROR")
        return {"status": False, "message": "Tracker offline."}
    except Exception as e:
        log(f"Erro de comunicação com o tracker: {e}", "ERROR")
        return {"status": False, "message": str(e)}

