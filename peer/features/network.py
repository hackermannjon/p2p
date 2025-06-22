# peer/features/network.py
import socket
import json
from utils.logger import log
from utils.config import TRACKER_HOST, TRACKER_PORT

def send_to_tracker(data):
    """Envia uma mensagem TCP ao tracker e retorna a resposta como dict."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(10)
            s.connect((TRACKER_HOST, TRACKER_PORT))
            s.sendall(json.dumps(data).encode())
            response = s.recv(8192).decode()
            return json.loads(response)
    except socket.timeout:
        log("Timeout na comunicação com o tracker.", "ERROR")
        return {"status": False, "message": "Tracker não respondeu."}
    except ConnectionRefusedError:
        log("Conexão com o tracker recusada.", "ERROR")
        return {"status": False, "message": "Tracker offline."}
    except Exception as e:
        log(f"Erro de comunicação com o tracker: {e}", "ERROR")
        return {"status": False, "message": str(e)}
