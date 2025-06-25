"""Utilidades para troca de mensagens entre peer e tracker via TCP."""

import socket  # Módulo para comunicação de baixo nível em rede (sockets TCP).
from common.protocol import parse_message, create_message


# P: Qual a responsabilidade principal deste módulo?
# R: Abstrair o envio de mensagens JSON através de conexões TCP, tratando
#    erros comuns (timeout, recusa de conexão) e retornando um dicionário já
#    decodificado para quem chamou.


def send_message(host, port, action, data):
    """Envia uma mensagem JSON para um servidor e retorna a resposta.

    Args:
        host (str): IP ou hostname de destino.
        port (int): Porta TCP do servidor.
        action (str): Ação/protocolo que será codificada na mensagem.
        data (dict): Dados adicionais a serem enviados.

    Returns:
        dict: Resposta já decodificada em formato de dicionário.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect((host, port))
            msg = create_message(action, data)
            s.sendall(msg.encode())
            response = s.recv(4096).decode()
            return parse_message(response)
    except socket.timeout:
        # P: Como a função reage se o servidor demorar a responder?
        # R: Um timeout resulta em um dicionário de erro específico,
        #    permitindo que o chamador trate a falha sem travar o programa.
        return {"status": False, "message": "Timeout na conexao com o servidor"}
    except ConnectionRefusedError:
        # P: E se o tracker ou peer estiver offline?
        # R: Este erro indica que não há servidor escutando no endereço
        #    informado. Retornamos uma mensagem de falha simples.
        return {"status": False, "message": "Nao foi possivel conectar ao servidor"}
    except Exception as e:
        # Captura quaisquer outras falhas inesperadas para que o chamador não
        # precise lidar com exceções diretamente.
        return {"status": False, "message": f"Erro na comunicacao: {str(e)}"}

