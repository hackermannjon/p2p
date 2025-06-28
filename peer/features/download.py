
"""Rotinas de download paralelas para arquivos compartilhados.

Este módulo concentra a lógica de múltiplas threads que baixam "chunks" de
diversos peers ao mesmo tempo. Cada bloco de código possui comentários em
formato de perguntas e respostas para facilitar o estudo.
"""

import json
import os
import threading  # Permite a criação de várias threads de download
import hashlib  # Garante integridade calculando hashes SHA-256
from queue import Queue, Empty  # Estruturas seguras para compartilhar tarefas
import socket
from threading import Lock
from itertools import cycle  # Facilita o rodízio entre os peers disponíveis

from utils.logger import log
from utils.chunk_manager import reassemble_chunks
from .network import send_to_tracker

DOWNLOADS_FOLDER = 'downloads'
MAX_CHUNK_RETRIES = 3
TIER_THREADS = {'bronze': 1, 'prata': 2, 'ouro': 3, 'diamante': 4}

class DownloaderThread(threading.Thread):
    """Thread responsável por baixar chunks individuais.

    P: Por que usamos várias threads para baixar um único arquivo?
    R: Cada thread tenta obter um chunk de um peer diferente. Isso aproveita ao
       máximo a largura de banda disponível e respeita o limite de paralelismo
       definido pelo tier do usuário.
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
        """Loop principal que tenta baixar os chunks atribuídos.

        P: O que acontece se um peer não possuir o chunk solicitado?
        R: A thread consulta o próximo peer no ``cycle``. Se todos falharem, o
           chunk é colocado de volta na fila para uma nova tentativa.
        """

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
    """Baixa um arquivo dividindo o trabalho entre várias threads.

    P: Como é determinado o número de threads simultâneas?
    R: O tracker informa o ``tier`` do usuário. Cada tier permite um número
       máximo de threads definido em ``TIER_THREADS``.

    Args:
        file_name (str): Nome do arquivo a ser baixado.
        file_info (dict): Metadados enviados pelo tracker, incluindo lista de
            peers e hashes dos chunks.
        username (str): Usuário atual, necessário para relatar uploads.
    """

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

    # P: Como as threads sabem quais chunks ainda precisam ser baixados?
    # R: Utilizamos uma fila ``Queue`` que armazena tuplas (index, hash). Cada
    #    thread consome dessa fila e devolve o chunk em caso de falha.
    chunk_queue = Queue()
    attempts = {}
    lock = Lock()
    for i, chash in enumerate(chunk_hashes):
        chunk_queue.put((i, chash))

    # P: Como escolher o próximo peer sem favorecer sempre o mesmo?
    # R: ``cycle`` cria um iterador infinito que percorre a lista em ordem,
    #    permitindo um rodízio simples entre os peers disponíveis.
    peer_cycle = cycle(prioritized_peers)
    # trava simples para impedir que duas threads avancem o ciclo ao mesmo tempo
    peer_lock = Lock()
    threads = []
    # P: Como limitamos o número de threads para respeitar o tier do usuário?
    # R: ``threads_allowed`` define o limite máximo. Criamos somente até esse
    #    valor ou a quantidade de peers disponíveis, o que for menor.
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
        log(
            f"Arquivo '{file_name}' baixado e verificado com sucesso! Threads usadas: {len(threads)} (tier {tier})",
            "SUCCESS",
        )

        for f in os.listdir(temp_dir):
            os.remove(os.path.join(temp_dir, f))
        os.rmdir(temp_dir)
    else:
        log(f"Falha na verificacao do arquivo final! Hash esperado: {file_hash}, obtido: {final_hash}", "ERROR")
