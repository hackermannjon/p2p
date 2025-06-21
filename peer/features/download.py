# peer/features/download.py
import json
import os
import threading
import hashlib
from queue import Queue
import socket

from utils.logger import log
from utils.chunk_manager import reassemble_chunks, CHUNK_SIZE

DOWNLOADS_FOLDER = 'downloads'
NUM_DOWNLOAD_THREADS = 4

class DownloaderThread(threading.Thread):
    def __init__(self, file_name, chunk_queue, prioritized_peers, temp_dir):
        super().__init__()
        self.file_name = file_name
        self.chunk_queue = chunk_queue
        self.prioritized_peers = prioritized_peers
        self.temp_dir = temp_dir
        self.daemon = True

    def run(self):
        while not self.chunk_queue.empty():
            try:
                chunk_index, expected_hash = self.chunk_queue.get()
                success = False
                for peer_addr_str in self.prioritized_peers:
                    try:
                        peer_ip, peer_tcp_port = peer_addr_str.split(':')
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                            s.settimeout(10)
                            s.connect((peer_ip, int(peer_tcp_port)))
                            request = {"action": "request_chunk", "file_name": self.file_name, "chunk_index": chunk_index}
                            s.sendall(json.dumps(request).encode())
                            
                            response_parts = []
                            while True:
                                part = s.recv(4096)
                                if not part: break
                                response_parts.append(part)
                            response = b''.join(response_parts)

                        if hashlib.sha256(response).hexdigest() == expected_hash:
                            chunk_path = os.path.join(self.temp_dir, f"chunk_{chunk_index}")
                            with open(chunk_path, 'wb') as f: f.write(response)
                            log(f"Chunk {chunk_index} baixado de {peer_addr_str}", "SUCCESS")
                            success = True
                            break
                        else:
                            log(f"Falha de hash no chunk {chunk_index} de {peer_addr_str}", "WARNING")
                    
                    except Exception as e:
                        log(f"Não foi possível baixar chunk {chunk_index} de {peer_addr_str}: {e}", "ERROR")
                
                if not success:
                    log(f"Recolocando chunk {chunk_index} na fila.", "WARNING")
                    self.chunk_queue.put((chunk_index, expected_hash))

            finally:
                self.chunk_queue.task_done()

def download_file(file_name, file_info):
    log(f"Iniciando download de '{file_name}'...", "INFO")
    
    file_hash = file_info['hash']
    chunk_hashes = file_info['chunk_hashes']
    prioritized_peers = [p['peer'] for p in file_info['peers']]
    
    if not prioritized_peers:
        log("Nenhum peer disponível para este arquivo.", "ERROR")
        return

    log(f"Ordem de peers (baseado em pontuação): {prioritized_peers}", "INFO")
    temp_dir = os.path.join(DOWNLOADS_FOLDER, f"temp_{file_hash}")
    os.makedirs(temp_dir, exist_ok=True)
    
    chunk_queue = Queue()
    for i, chash in enumerate(chunk_hashes):
        chunk_queue.put((i, chash))
        
    threads = []
    for _ in range(min(NUM_DOWNLOAD_THREADS, len(prioritized_peers))):
        thread = DownloaderThread(file_name, chunk_queue, prioritized_peers, temp_dir)
        thread.start()
        threads.append(thread)
        
    chunk_queue.join()
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
        log(f"Falha na verificação do arquivo final! Hash esperado: {file_hash}, obtido: {final_hash}", "ERROR")
