import json
import os
import socket

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')


def detect_local_ip():
    """Tenta descobrir o IP local da maquina."""
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
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r') as f:
            data = json.load(f)
    else:
        data = {}
    data.setdefault('tracker_ip', detect_local_ip())
    if data.get('tracker_ip') == 'auto':
        data['tracker_ip'] = detect_local_ip()
    data.setdefault('tracker_port', 9000)
    return data

_data = load_config()
TRACKER_HOST = _data['tracker_ip']
TRACKER_PORT = _data['tracker_port']
