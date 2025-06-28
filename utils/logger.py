import datetime


def log(msg, level="INFO"):
    """Imprime mensagens coloridas para facilitar a depuração."""

    now = datetime.datetime.now().strftime("%H:%M:%S")
    color_map = {
        "INFO": "\033[94m",
        "SUCCESS": "\033[92m",
        "WARNING": "\033[93m",
        "ERROR": "\033[91m",
        "NETWORK": "\033[96m",
    }
    end_color = "\033[0m"
    color = color_map.get(level.upper(), "")
    print(f"{color}[{now}] [{level.upper()}] {msg}{end_color}")


