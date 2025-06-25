"""Definição do formato de mensagens da rede.

Todas as interações entre tracker e peers ocorrem através de estruturas JSON
com um campo ``action`` indicando a operação desejada. Centralizar estas
funções aqui permite que qualquer mudança no protocolo seja refletida em todo o
sistema de maneira consistente.
"""

import json  # Módulo para serialização e desserialização de dados em JSON.

def create_message(action: str, data: dict) -> str:
    """Monta uma mensagem seguindo o protocolo do sistema.

    A estrutura final sempre conterá ao menos o campo ``action``. Os demais
    elementos são definidos pelo chamador através do ``data``. Esta função
    centraliza o ``json.dumps`` para que todos os módulos utilizem a mesma
    codificação (UTF-8) e formatação.

    Args:
        action (str): Ação que o destinatário deverá executar.
        data (dict): Parâmetros adicionais da mensagem.

    Returns:
        str: Mensagem JSON formatada pronta para ser enviada pelo socket.
    """

    # P: Por que utilizamos JSON para as mensagens?
    # R: O formato é leve, legível e possui suporte nativo em diversas linguagens,
    #    facilitando a interoperabilidade entre os componentes.
    return json.dumps({
        "action": action,
        **data
    })

def parse_message(raw: str) -> dict:
    """Decodifica uma mensagem recebida da rede.

    Esta função é o inverso de ``create_message``: ela pega a string obtida pelo
    socket e converte para um dicionário de forma segura.

    Args:
        raw (str): Mensagem recebida pelo socket.

    Returns:
        dict: Dados extraídos da mensagem em formato de alto nível.
    """

    # P: Como recuperamos os dados enviados pela rede?
    # R: Basta chamar ``json.loads`` para transformar a string novamente em um
    #    dicionário e acessar seus campos normalmente.
    #    Qualquer erro de decodificação resultará em ``json.JSONDecodeError``,
    #    permitindo tratamento apropriado pelo chamador.
    return json.loads(raw)

