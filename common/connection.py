"""Camada de comunicação TCP entre peers.

Este módulo reúne rotinas básicas de envio e recebimento utilizando
``socket.socket``. Ele isola o restante do código de detalhes como tempo de
espera e formatação das mensagens, servindo como uma interface simples para
trocar dados estruturados entre os nós da rede.
"""

import socket  # Provê comunicação de rede de baixo nível (sockets TCP/IP).
from common.protocol import parse_message, create_message

def send_message(host: str, port: int, action: str, data: dict) -> dict:
    """Envia um comando para outro peer ou serviço e aguarda a resposta.

    Esta função encapsula toda a mecânica de abertura de socket, envio da
    mensagem e leitura do retorno. Utilizamos JSON para manter o formato dos
    dados bem definido e facilmente depurável.

    Args:
        host (str): IP ou hostname do destino.
        port (int): Porta TCP do destino.
        action (str): Ação solicitada pelo protocolo.
        data (dict): Conteúdo adicional a ser enviado junto com a ação.

    Returns:
        dict: Estrutura já decodificada contendo a resposta.
    """

    # P: Como garantir que a conexão não fique pendurada indefinidamente?
    # R: Utilizamos ``settimeout`` para limitar o tempo de espera em cada operação
    #    de rede. Se o tempo for excedido, um ``socket.timeout`` é disparado.
    #    Isso evita que o cliente fique bloqueado caso o servidor tenha algum
    #    problema ou simplesmente não envie resposta alguma.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            # Estabelecemos o tempo máximo de espera para todas as operações
            # subsequentes neste socket.
            s.settimeout(5)

            # Conecta ao destino (tracker ou outro peer)
            s.connect((host, port))

            # Serializa os dados da requisição para o formato acordado
            msg = create_message(action, data)
            s.sendall(msg.encode())

            # Após o envio, aguardamos a resposta em até 5 segundos
            response = s.recv(4096).decode()

            # Convertemos a resposta JSON em dicionário Python para fácil uso
            return parse_message(response)
    except socket.timeout:
        # Qualquer atraso acima do limite definido gera esta exceção.
        # Informamos o problema ao chamador para que ele possa tentar novamente
        # ou notificar o usuário.
        return {"status": False, "message": "Timeout na conexão com o servidor"}
    except ConnectionRefusedError:
        # A porta existe mas não há ninguém ouvindo ou o serviço está negando
        # conexões. Essa informação é útil para descobrir se o destino está de
        # fato offline.
        return {"status": False, "message": "Não foi possível conectar ao servidor"}
    except Exception as e:
        # Qualquer outro erro (ex: pacote malformado) chega até aqui.
        return {"status": False, "message": f"Erro na comunicação: {str(e)}"}

