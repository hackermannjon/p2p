# peer/features/network.py
import socket
import json
from utils.logger import log
from utils.config import TRACKER_HOST, TRACKER_PORT

def send_to_tracker(data, peer_socket):
    """
    Envia uma mensagem UDP para o tracker e aguarda a resposta.
    O socket do peer é passado como argumento.
    """
    try:
        peer_socket.sendto(json.dumps(data).encode(), (TRACKER_HOST, TRACKER_PORT))
        # Aumentado para acomodar listas grandes (ranking, arquivos)
        response, _ = peer_socket.recvfrom(8192)
        return json.loads(response.decode())
    except Exception as e:
        log(f"Erro de comunicação com o tracker: {e}", "ERROR")
        return {"status": False, "message": str(e)}
