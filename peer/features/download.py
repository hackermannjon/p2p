"""Rotinas de download que utilizam múltiplos peers em paralelo."""

import json
import os
import threading
import hashlib
from queue import Queue, Empty
import socket
from threading import Lock
from itertools import cycle

from utils.logger import log
from utils.chunk_manager import reassemble_chunks
from .network import send_to_tracker

DOWNLOADS_FOLDER = 'downloads'
MAX_CHUNK_RETRIES = 3
TIER_THREADS = {'bronze': 1, 'prata': 2, 'ouro': 3, 'diamante': 4}

class DownloaderThread(threading.Thread):
    """Worker responsável por baixar chunks específicos.

    Args:
        file_name (str): nome do arquivo solicitado.
        chunk_queue (Queue): fila com os índices e hashes dos chunks.
        peers (list[str]): lista de peers priorizados para este download.
        temp_dir (str): pasta temporária onde os chunks serão salvos.
        username (str): usuário local, enviado ao peer remoto.
        attempts (dict): contador de tentativas por chunk.
        lock (Lock): sincroniza acesso ao dicionário de tentativas.
        peer_cycle (iterator): round-robin de peers para balancear requests.
        peer_lock (Lock): protege o iterador de uso simultâneo.
    """

    def __init__(self, file_name, chunk_queue, peers, temp_dir, username, attempts, lock, peer_cycle, peer_lock):
        super().__init__(daemon=True)
        self.file_name = file_name
        self.chunk_queue = chunk_queue
        self.peers = peers
        self.temp_dir = temp_dir
        self.username = username
        self.attempts = attempts
        self.lock = lock
        self.peer_cycle = peer_cycle
        self.peer_lock = peer_lock

    def run(self):
        # P: Como o thread escolhe qual peer contatar e qual chunk baixar?
        # R: Ele retira um chunk da fila compartilhada e tenta obtê-lo do
        #    próximo peer no iterador round-robin. Assim evitamos que todos os
        #    threads ataquem o mesmo peer ao mesmo tempo.
        while True:
            try:
                chunk_index, expected_hash = self.chunk_queue.get_nowait()
            except Empty:
                break
            success = False
            tried = 0
            while tried < len(self.peers):
                with self.peer_lock:
                    peer_addr_str = next(self.peer_cycle)
                peer_ip, peer_tcp_port = peer_addr_str.split(':')
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        # Ajuste do timeout: peers bronze podem demorar
                        # até 10s para responder, entao esperamos um
                        # pouco mais antes de desistir.
                        s.settimeout(20)
                        s.connect((peer_ip, int(peer_tcp_port)))
                        request = {
                            "action": "request_chunk",
                            "file_name": self.file_name,
                            "chunk_index": chunk_index,
                            "username": self.username,
                        }
                        s.sendall(json.dumps(request).encode())
                        response_parts = []
                        # P: Por que lemos o socket em partes?
                        # R: A quantidade de dados pode ser grande e não sabemos
                        #    quando o peer vai fechar a conexão, então vamos
                        #    acumulando até que `recv` retorne vazio.
                        while True:
                            part = s.recv(4096)
                            if not part:
                                break
                            response_parts.append(part)
                    response = b"".join(response_parts)
                    if response and hashlib.sha256(response).hexdigest() == expected_hash:
                        # P: Como sabemos que o pedaço recebido está integro?
                        # R: Calculamos o SHA-256 e comparamos com o hash esperado
                        #    vindo do tracker. Somente se coincidir salvamos o
                        #    chunk no disco.
                        chunk_path = os.path.join(self.temp_dir, f"chunk_{chunk_index}")
                        with open(chunk_path, "wb") as f:
                            f.write(response)
                        log(f"Chunk {chunk_index} baixado de {peer_addr_str}", "SUCCESS")
                        success = True
                        break
                except Exception as e:
                    # Se o peer falhar, tentamos o próximo da lista.
                    log(f"Nao foi possivel baixar chunk {chunk_index} de {peer_addr_str}: {e}", "ERROR")
                tried += 1
            if not success:
                with self.lock:
                    self.attempts[chunk_index] = self.attempts.get(chunk_index, 0) + 1
                    attempts = self.attempts[chunk_index]
                if attempts < MAX_CHUNK_RETRIES:
                    log(f"Recolocando chunk {chunk_index} na fila.", "WARNING")
                    self.chunk_queue.put((chunk_index, expected_hash))
                else:
                    # Depois de várias tentativas desistimos para evitar loop infinito
                    log(f"Falha permanente no chunk {chunk_index}", "ERROR")
            self.chunk_queue.task_done()


def download_file(file_name, file_info, username):
    """Realiza o download completo de um arquivo.

    P: Como o número de threads é definido?
    R: Consultamos o tracker para saber o tier do usuário e aplicamos o limite
       correspondente (mais uploads e tempo na rede geram mais threads).
    """

    res = send_to_tracker({"action": "get_peer_score", "target_username": username})
    tier = res.get("tier", "bronze") if res else "bronze"
    threads_allowed = TIER_THREADS.get(tier, 1)

    file_hash = file_info["hash"]
    chunk_hashes = file_info["chunk_hashes"]
    # P: Por que ordenamos os peers por score?
    # R: O tracker nos envia os peers já em ordem decrescente de pontuação.
    #    Dessa forma sempre tentamos baixar de quem tem melhor reputação
    #    primeiro, mas ainda usamos round-robin para distribuir a carga.
    prioritized_peers = [p["peer"] for p in file_info["peers"]]

    if not prioritized_peers:
        log("Nenhum peer disponivel para este arquivo.", "ERROR")
        return

    temp_dir = os.path.join(DOWNLOADS_FOLDER, f"temp_{file_hash}")
    os.makedirs(temp_dir, exist_ok=True)

    chunk_queue = Queue()
    attempts = {}
    lock = Lock()
    for i, chash in enumerate(chunk_hashes):
        chunk_queue.put((i, chash))

    peer_cycle = cycle(prioritized_peers)
    peer_lock = Lock()
    threads = []
    for _ in range(min(threads_allowed, len(prioritized_peers))):
        t = DownloaderThread(file_name, chunk_queue, prioritized_peers, temp_dir, username, attempts, lock, peer_cycle, peer_lock)
        t.start()
        threads.append(t)

    chunk_queue.join()

    missing = [i for i in range(len(chunk_hashes)) if not os.path.exists(os.path.join(temp_dir, f"chunk_{i}"))]
    if missing:
        log(f"Falha no download dos chunks: {missing}", "ERROR")
        return

    final_path = os.path.join(DOWNLOADS_FOLDER, file_name)
    reassemble_chunks(temp_dir, final_path, len(chunk_hashes))

    with open(final_path, "rb") as f:
        # P: A reconstrução do arquivo garantiu a integridade?
        # R: Calculamos o hash do arquivo final e comparamos com o hash
        #    original informado pelo tracker.
        final_hash = hashlib.sha256(f.read()).hexdigest()

    if final_hash == file_hash:
        log(f"Arquivo '{file_name}' baixado e verificado com sucesso!", "SUCCESS")
        # Removemos os arquivos temporários após o sucesso para economizar espaço
        for f in os.listdir(temp_dir):
            os.remove(os.path.join(temp_dir, f))
        os.rmdir(temp_dir)
    else:
        log(f"Falha na verificacao do arquivo final! Hash esperado: {file_hash}, obtido: {final_hash}", "ERROR")
