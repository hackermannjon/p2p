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
                        s.settimeout(10)
                        s.connect((peer_ip, int(peer_tcp_port)))
                        request = {
                            "action": "request_chunk",
                            "file_name": self.file_name,
                            "chunk_index": chunk_index,
                            "username": self.username,
                        }
                        s.sendall(json.dumps(request).encode())
                        response_parts = []
                        while True:
                            part = s.recv(4096)
                            if not part:
                                break
                            response_parts.append(part)
                    response = b"".join(response_parts)
                    if response and hashlib.sha256(response).hexdigest() == expected_hash:
                        chunk_path = os.path.join(self.temp_dir, f"chunk_{chunk_index}")
                        with open(chunk_path, "wb") as f:
                            f.write(response)
                        log(f"Chunk {chunk_index} baixado de {peer_addr_str}", "SUCCESS")
                        success = True
                        break
                except Exception as e:
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
                    log(f"Falha permanente no chunk {chunk_index}", "ERROR")
            self.chunk_queue.task_done()


def download_file(file_name, file_info, username):
    res = send_to_tracker({"action": "get_peer_score", "target_username": username})
    tier = res.get("tier", "bronze") if res else "bronze"
    threads_allowed = TIER_THREADS.get(tier, 1)

    file_hash = file_info["hash"]
    chunk_hashes = file_info["chunk_hashes"]
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
        final_hash = hashlib.sha256(f.read()).hexdigest()

    if final_hash == file_hash:
        log(f"Arquivo '{file_name}' baixado e verificado com sucesso!", "SUCCESS")
        for f in os.listdir(temp_dir):
            os.remove(os.path.join(temp_dir, f))
        os.rmdir(temp_dir)
    else:
        log(f"Falha na verificacao do arquivo final! Hash esperado: {file_hash}, obtido: {final_hash}", "ERROR")
