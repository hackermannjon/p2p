
"""Funções auxiliares para envio de mensagens via TCP ao tracker ou peers."""

import socket  # Biblioteca de rede de baixo nível do Python
from common.protocol import parse_message, create_message


def send_message(host, port, action, data):
    """Envia uma mensagem codificada e retorna a resposta já decodificada.

    Args:
        host (str): IP ou hostname do destino.
        port (int): Porta TCP do destino.
        action (str): Nome da ação que será enviada no protocolo.
        data (dict): Payload adicional da mensagem.
    """

    try:
        # P: Como garantimos que o socket seja fechado corretamente?
        # R: Utilizamos o gerenciador de contexto ``with`` que encerra o socket
        #    automaticamente ao sair do bloco, mesmo em caso de erro.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect((host, port))
            msg = create_message(action, data)
            s.sendall(msg.encode())
            response = s.recv(4096).decode()
            return parse_message(response)
    except socket.timeout:
        # Servidor não respondeu dentro do tempo limite
        return {"status": False, "message": "Timeout na conexao com o servidor"}
    except ConnectionRefusedError:
        # Destino não está aceitando conexões na porta especificada
        return {"status": False, "message": "Nao foi possivel conectar ao servidor"}
    except Exception as e:
        # Qualquer outro erro é repassado em formato de string
        return {"status": False, "message": f"Erro na comunicacao: {str(e)}"}

