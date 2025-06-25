"""Leitura das configurações básicas do sistema (IP e porta do tracker)."""

import json  # Para carregar o arquivo config.json
import os
import socket  # Usado para descobrir o IP local automaticamente

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')
# Por padrao, o arquivo ``config.json`` fica na raiz do projeto e pode ser
# editado manualmente para alterar o IP/porta do tracker.


def detect_local_ip():
    """Tenta descobrir o IP local da maquina."""
    # P: Por que conectar ao DNS do Google para descobrir o IP?
    # R: É uma técnica simples: abrimos um socket UDP para um endereço externo
    #    e consultamos o IP atribuído à interface de saída.
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
    """Carrega configuracoes do tracker, priorizando variaveis de ambiente."""
    # P: Em qual ordem as configurações são consideradas?
    # R: Primeiro lê ``config.json`` se existir. Depois, variáveis de ambiente
    #    ``TRACKER_HOST`` e ``TRACKER_PORT`` podem sobrescrever esses valores.
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
# Após a leitura do arquivo ou das variáveis de ambiente, os valores ficam
# disponíveis em constantes globais para uso por todo o sistema.


def set_tracker_address(host: str, port: int):
    """Altera o endereco do tracker em tempo de execucao."""
    # P: Por que permitir alterar o endereço em tempo real?
    # R: Em ambientes de teste é comum iniciar o tracker em portas diferentes.
    #    Atualizando essas variáveis globais, todo o sistema passa a usar o novo
    #    endereço sem reiniciar processos.
    global TRACKER_HOST, TRACKER_PORT
    if host:
        TRACKER_HOST = host
    if port:
        TRACKER_PORT = port

