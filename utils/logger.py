"""Ferramentas de log simples com uso de cores.

Apesar de minimalista, este módulo permite diferenciar mensagens de erro e
sucesso no terminal utilizando códigos ANSI. As cores ajudam a depurar o
comportamento do tracker e dos peers.
"""

import datetime  # Fornece funções de data e hora utilizadas no carimbo do log.

def log(msg: str, level: str = "INFO") -> None:
    """Imprime uma mensagem no console com cores e timestamp.

    Args:
        msg (str): Texto da mensagem a ser exibida.
        level (str): Nível de log (INFO, SUCCESS, WARNING ou ERROR).

    A função não retorna nada: serve apenas para organizar saídas durante o
    desenvolvimento, evitando que cada módulo precise lidar com códigos de cor
    manualmente.
    """

    # P: Como formatamos a saída de log com horário e cor?
    # R: Capturamos o horário atual e escolhemos a cor conforme o nível
    #    informado. Em seguida, montamos a string final usando códigos ANSI
    #    para colorir o texto no terminal.
    now = datetime.datetime.now().strftime("%H:%M:%S")

    color_map = {
        "INFO": "\033[94m",     # Azul
        "SUCCESS": "\033[92m",  # Verde
        "WARNING": "\033[93m",  # Amarelo
        "ERROR": "\033[91m",    # Vermelho
    }
    # Estes códigos (ESC[xxm) são interpretados pela maioria dos terminais como
    # cores diferentes, realçando cada nível de log.

    end_color = "\033[0m"
    color = color_map.get(level.upper(), "")
    print(f"{color}[{now}] [{level.upper()}] {msg}{end_color}")
