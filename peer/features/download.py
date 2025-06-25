# peer/features/download.py
"""Funções e classes relacionadas ao download de arquivos em chunks."""

import json
import os
import threading  # Para criar múltiplas threads de download.
import hashlib     # Verificação de integridade dos chunks.
from queue import Queue  # Estrutura de tarefas para as threads.
import socket
from threading import Lock

from utils.logger import log
from utils.chunk_manager import reassemble_chunks, CHUNK_SIZE

DOWNLOADS_FOLDER = 'downloads'
NUM_DOWNLOAD_THREADS = 4
MAX_CHUNK_RETRIES = 3

class DownloaderThread(threading.Thread):
    """Thread responsável por baixar um único chunk de cada vez."""
    def __init__(self, file_name, chunk_queue, prioritized_peers, temp_dir, username, attempts, lock):
        super().__init__()
        self.file_name = file_name
        self.chunk_queue = chunk_queue
        self.prioritized_peers = prioritized_peers
        self.temp_dir = temp_dir
        self.username = username
        self.attempts = attempts
        self.lock = lock
        self.daemon = True

    def run(self):
        # P: Como garantir que várias threads não baixem o mesmo chunk?
        # R: Os índices de chunks são armazenados em uma ``Queue``. Cada thread
        #    chama ``get()`` que remove um item exclusivo para ela.
        while not self.chunk_queue.empty():
            try:
                chunk_index, expected_hash = self.chunk_queue.get()
                success = False
                for peer_addr_str in self.prioritized_peers:
                    # P: De onde veio esta lista ``prioritized_peers``?
                    # R: Ela é enviada pelo tracker já ordenada pela
                    #    pontuação de colaboração de cada peer que possui o arquivo.
                    try:
                        peer_ip, peer_tcp_port = peer_addr_str.split(':')
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                            # P: Por que definir um timeout nas conexões de download?
                            # R: Assim evitamos que uma thread fique bloqueada
                            #    indefinidamente caso o peer remoto não responda.
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

                        # P: Como garantimos que o chunk recebido não foi corrompido?
                        # R: Calculamos seu hash e comparamos com o valor esperado
                        #    informado pelo tracker no metadata.
                        if hashlib.sha256(response).hexdigest() == expected_hash:
                            chunk_path = os.path.join(self.temp_dir, f"chunk_{chunk_index}")
                            with open(chunk_path, "wb") as f:
                                f.write(response)
                            log(f"Chunk {chunk_index} baixado de {peer_addr_str}", "SUCCESS")
                            success = True
                            break
                        else:
                            log(
                                f"Falha de hash no chunk {chunk_index} de {peer_addr_str}",
                                "WARNING",
                            )

                    except Exception as e:
                        log(
                            f"Não foi possível baixar chunk {chunk_index} de {peer_addr_str}: {e}",
                            "ERROR",
                        )
                
                if not success:
                    with self.lock:
                        self.attempts[chunk_index] = self.attempts.get(chunk_index, 0) + 1
                        attempts = self.attempts[chunk_index]
                    if attempts < MAX_CHUNK_RETRIES:
                        log(f"Recolocando chunk {chunk_index} na fila.", "WARNING")
                        self.chunk_queue.put((chunk_index, expected_hash))
                    else:
                        log(f"Falha permanente no chunk {chunk_index}", "ERROR")

            finally:
                self.chunk_queue.task_done()

def download_file(file_name, file_info, username):
    """Gerencia o processo completo de download de um arquivo."""
    log(f"Iniciando download de '{file_name}'...", "INFO")
    
    file_hash = file_info['hash']
    chunk_hashes = file_info['chunk_hashes']
    prioritized_peers = [p['peer'] for p in file_info['peers']]
    # P: Por que ordenar os peers pela pontuação recebida do tracker?
    # R: Assim damos preferência a quem mais colaborou, incentivando
    #    compartilhamentos futuros.
    
    if not prioritized_peers:
        log("Nenhum peer disponível para este arquivo.", "ERROR")
        return

    log(f"Ordem de peers (baseado em pontuação): {prioritized_peers}", "INFO")
    temp_dir = os.path.join(DOWNLOADS_FOLDER, f"temp_{file_hash}")
    os.makedirs(temp_dir, exist_ok=True)
    
    chunk_queue = Queue()
    attempts = {}
    lock = Lock()
    for i, chash in enumerate(chunk_hashes):
        chunk_queue.put((i, chash))
        
    threads = []
    for _ in range(min(NUM_DOWNLOAD_THREADS, len(prioritized_peers))):
        thread = DownloaderThread(file_name, chunk_queue, prioritized_peers, temp_dir, username, attempts, lock)
        thread.start()
        threads.append(thread)

    # Aguarda todas as threads terminarem seus downloads
    chunk_queue.join()

    missing = [i for i in range(len(chunk_hashes)) if not os.path.exists(os.path.join(temp_dir, f"chunk_{i}"))]
    if missing:
        log(f"Falha no download dos chunks: {missing}", "ERROR")
        return

    log("Todos os chunks foram baixados. Reconstruindo arquivo...", "INFO")
    
    final_path = os.path.join(DOWNLOADS_FOLDER, file_name)
    reassemble_chunks(temp_dir, final_path, len(chunk_hashes))
    
    with open(final_path, 'rb') as f:
        final_hash = hashlib.sha256(f.read()).hexdigest()

    if final_hash == file_hash:
        log(f"Arquivo '{file_name}' baixado e verificado com sucesso!", "SUCCESS")
        for f in os.listdir(temp_dir):
            os.remove(os.path.join(temp_dir, f))
        os.rmdir(temp_dir)
    else:
        # P: O que acontece se a soma de verificação do arquivo final não bater?
        # R: Reportamos o erro e mantemos os chunks temporários para análise,
        #    permitindo ao usuário tentar novamente ou verificar a origem do
        #    problema.
        log(f"Falha na verificação do arquivo final! Hash esperado: {file_hash}, obtido: {final_hash}", "ERROR")

