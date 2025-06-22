import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')
with open(CONFIG_PATH, 'r') as f:
    _data = json.load(f)

TRACKER_HOST = _data.get('tracker_ip', '127.0.0.1')
TRACKER_PORT = _data.get('tracker_port', 9000)
