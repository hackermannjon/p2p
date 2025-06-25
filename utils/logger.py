"""Logger simples usado por todos os componentes."""

import datetime  # Para registrar horário das mensagens.


def log(msg, level="INFO"):
    """Imprime uma mensagem colorida no terminal."""
    # P: Para que serve cada cor?
    # R: As cores ajudam a distinguir tipos de mensagem (erro, aviso, sucesso)
    #    durante a execução no console.
    now = datetime.datetime.now().strftime("%H:%M:%S")
    color_map = {
        "INFO": "\033[94m",     # Azul
        "SUCCESS": "\033[92m",  # Verde
        "WARNING": "\033[93m",  # Amarelo
        "ERROR": "\033[91m",    # Vermelho
        "NETWORK": "\033[96m",  # Ciano (para tráfego de rede)
    }
    # Obs.: Os códigos ANSI funcionam em terminais compatíveis. Em ambientes
    # que não suportam cores, as mensagens aparecerão sem formatação.
    end_color = "\033[0m"
    color = color_map.get(level.upper(), "")
    print(f"{color}[{now}] [{level.upper()}] {msg}{end_color}")


