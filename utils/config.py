"""Leitura das configurações básicas do sistema (IP e porta do tracker)."""

import json
import os
import socket

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')


def detect_local_ip():
    """Tenta descobrir o IP local da máquina."""

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


def load_config():
    """Carrega configurações do arquivo e de variáveis de ambiente."""

    data = {}

    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r') as f:
            data = json.load(f)

    env_host = os.environ.get('TRACKER_HOST')
    env_port = os.environ.get('TRACKER_PORT')

    if env_host:
        data['tracker_ip'] = env_host
    if env_port:
        try:
            data['tracker_port'] = int(env_port)
        except ValueError:
            pass

    data.setdefault('tracker_ip', detect_local_ip())
    if data.get('tracker_ip') == 'auto':
        data['tracker_ip'] = detect_local_ip()
    data.setdefault('tracker_port', 9000)
    return data

_data = load_config()
TRACKER_HOST = _data['tracker_ip']
TRACKER_PORT = _data['tracker_port']


def set_tracker_address(host: str, port: int):
    """Permite alterar o endereço do tracker em tempo de execução."""

    global TRACKER_HOST, TRACKER_PORT
    if host:
        TRACKER_HOST = host
    if port:
        TRACKER_PORT = port

