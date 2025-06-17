import socket
import json
import os
import threading
import hashlib
from queue import Queue
import time

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.logger import log
from utils.chunk_manager import split_file_into_chunks, reassemble_chunks, CHUNK_SIZE

# --- Configurações ---
TRACKER_HOST, TRACKER_PORT = 'localhost', 9000
SHARED_FOLDER = 'shared'
DOWNLOADS_FOLDER = 'downloads'
NUM_DOWNLOAD_THREADS = 4 # Número de conexões paralelas para download

# --- Variáveis de Estado Globais ---
peer_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
peer_host = 'localhost'
peer_port = 0 # Porta será definida pelo SO
peer_addr = (peer_host, peer_port)

logged_in = False
username = ""
local_files_metadata = {} # { "filename.ext": {"file_hash": "...", "chunk_hashes": [...] } }
network_files_db = {} # Armazena a lista de arquivos da rede recebida do tracker

# --- Lógica do Servidor do Peer (para atender outros peers) ---

def handle_peer_request(conn, addr):
    """Lida com uma requisição TCP de outro peer."""
    try:
        request_data = conn.recv(1024).decode()
        request = json.loads(request_data)
        log(f"Requisição TCP recebida de {addr}: {request}", "NETWORK")

        if request.get("action") == "request_chunk":
            file_name = request.get("file_name")
            chunk_index = request.get("chunk_index")
            
            # Constrói o caminho para o arquivo de chunk solicitado
            chunk_file_path = os.path.join(SHARED_FOLDER, f"{file_name}_chunks", f"chunk_{chunk_index}")

            if os.path.exists(chunk_file_path):
                with open(chunk_file_path, 'rb') as f:
                    chunk_data = f.read()
                conn.sendall(chunk_data)
                log(f"Chunk {chunk_index} de '{file_name}' enviado para {addr}", "SUCCESS")
            else:
                # Envia uma resposta de erro se o chunk não for encontrado
                conn.sendall(b'ERROR: Chunk not found')
                log(f"Chunk {chunk_index} de '{file_name}' não encontrado para {addr}", "WARNING")

    except json.JSONDecodeError:
        log(f"Erro ao decodificar JSON de {addr}", "ERROR")
    except Exception as e:
        log(f"Erro ao lidar com a requisição de {addr}: {e}", "ERROR")
    finally:
        conn.close()

def peer_server_logic():
    """Cria um servidor TCP para escutar por requisições de outros peers."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((peer_host, peer_port))
    server_socket.listen(5)
    log(f"Peer escutando por conexões TCP em {peer_host}:{peer_port}", "INFO")

    while True:
        conn, addr = server_socket.accept()
        thread = threading.Thread(target=handle_peer_request, args=(conn, addr))
        thread.daemon = True
        thread.start()

# --- Lógica de Download ---

class DownloaderThread(threading.Thread):
    def __init__(self, file_name, file_hash, chunk_queue, peer_list, temp_dir):
        super().__init__()
        self.file_name = file_name
        self.file_hash = file_hash
        self.chunk_queue = chunk_queue
        self.peer_list = peer_list
        self.temp_dir = temp_dir
        self.daemon = True

    def run(self):
        while not self.chunk_queue.empty():
            try:
                chunk_index, expected_hash = self.chunk_queue.get()

                success = False
                for peer_addr_str in self.peer_list:
                    try:
                        # Conecta-se ao peer e solicita o chunk
                        peer_ip, peer_tcp_port = peer_addr_str.split(':')
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                            s.connect((peer_ip, int(peer_tcp_port)))
                            request = {
                                "action": "request_chunk",
                                "file_name": self.file_name,
                                "chunk_index": chunk_index
                            }
                            s.sendall(json.dumps(request).encode())
                            
                            # Recebe os dados do chunk
                            response = s.recv(CHUNK_SIZE + 1024) # Buffer um pouco maior
                            
                        # Valida o hash do chunk recebido
                        if hashlib.sha256(response).hexdigest() == expected_hash:
                            chunk_path = os.path.join(self.temp_dir, f"chunk_{chunk_index}")
                            with open(chunk_path, 'wb') as f:
                                f.write(response)
                            log(f"Chunk {chunk_index} baixado e verificado com sucesso do peer {peer_addr_str}", "SUCCESS")
                            success = True
                            break # Sai do loop de peers, pois o chunk foi baixado
                        else:
                            log(f"Falha na verificação de hash para o chunk {chunk_index} do peer {peer_addr_str}", "WARNING")
                    
                    except Exception as e:
                        log(f"Não foi possível baixar o chunk {chunk_index} de {peer_addr_str}: {e}", "ERROR")
                
                if not success:
                    # Se falhou em todos os peers, coloca o chunk de volta na fila
                    log(f"Não foi possível baixar o chunk {chunk_index} de nenhum peer. Recolocando na fila.", "WARNING")
                    self.chunk_queue.put((chunk_index, expected_hash))
                    time.sleep(1) # Espera um pouco antes de tentar novamente

            finally:
                self.chunk_queue.task_done()

def download_file(file_name, file_info):
    """Gerencia o processo de download paralelo de um arquivo."""
    log(f"Iniciando download de '{file_name}'...", "INFO")
    
    file_hash = file_info['hash']
    chunk_hashes = file_info['chunk_hashes']
    peers = file_info['peers']
    
    if not peers:
        log("Nenhum peer disponível para este arquivo.", "ERROR")
        return

    # Cria diretório temporário para os chunks
    temp_dir = os.path.join(DOWNLOADS_FOLDER, f"temp_{file_hash}")
    os.makedirs(temp_dir, exist_ok=True)
    
    # Cria a fila de trabalho (chunks a baixar)
    chunk_queue = Queue()
    for i, chash in enumerate(chunk_hashes):
        chunk_queue.put((i, chash))
        
    # Inicia as threads de download
    threads = []
    for _ in range(NUM_DOWNLOAD_THREADS):
        thread = DownloaderThread(file_name, file_hash, chunk_queue, peers, temp_dir)
        thread.start()
        threads.append(thread)
        
    chunk_queue.join() # Espera a fila ser esvaziada
    log("Todos os chunks foram baixados. Reconstruindo arquivo...", "INFO")
    
    # Reconstrói o arquivo final
    final_path = os.path.join(DOWNLOADS_FOLDER, file_name)
    reassemble_chunks(temp_dir, final_path, len(chunk_hashes))
    
    # Validação final
    with open(final_path, 'rb') as f:
        final_hash = hashlib.sha256(f.read()).hexdigest()

    if final_hash == file_hash:
        log(f"Arquivo '{file_name}' baixado e verificado com sucesso!", "SUCCESS")
        # Limpa os chunks temporários
        for f in os.listdir(temp_dir):
            os.remove(os.path.join(temp_dir, f))
        os.rmdir(temp_dir)
    else:
        log(f"Falha na verificação do arquivo final! Hash esperado: {file_hash}, obtido: {final_hash}", "ERROR")


# --- Funções do Menu Principal ---

def send_to_tracker(data):
    """Envia uma mensagem UDP para o tracker e aguarda a resposta."""
    try:
        peer_socket.sendto(json.dumps(data).encode(), (TRACKER_HOST, TRACKER_PORT))
        response, _ = peer_socket.recvfrom(4096)
        return json.loads(response.decode())
    except Exception as e:
        log(f"Erro de comunicação com o tracker: {e}", "ERROR")
        return {"status": False, "message": str(e)}

def announce_files():
    """Prepara e anuncia arquivos da pasta 'shared' para o tracker."""
    global local_files_metadata
    os.makedirs(SHARED_FOLDER, exist_ok=True)
    files_to_announce = []

    for filename in os.listdir(SHARED_FOLDER):
        # Ignora as pastas de chunks que criamos
        if os.path.isdir(os.path.join(SHARED_FOLDER, filename)):
            continue
        
        file_path = os.path.join(SHARED_FOLDER, filename)
        file_size = os.path.getsize(file_path)

        log(f"Processando arquivo '{filename}' para anunciar...", "INFO")
        file_hash, chunk_hashes = split_file_into_chunks(file_path)

        # Salva metadados localmente
        local_files_metadata[filename] = { "file_hash": file_hash, "chunk_hashes": chunk_hashes }
        
        files_to_announce.append({
            "name": filename,
            "size": file_size,
            "hash": file_hash,
            "chunk_hashes": chunk_hashes
        })

    if not files_to_announce:
        log("Nenhum arquivo encontrado na pasta 'shared' para anunciar.", "WARNING")
        return

    res = send_to_tracker({
        "action": "announce",
        "port": peer_port,
        "files": files_to_announce
    })
    
    if res and res.get('status'):
        log("Arquivos anunciados com sucesso!", "SUCCESS")
    else:
        log(f"Falha ao anunciar arquivos: {res.get('message')}", "ERROR")

def list_network_files():
    """Busca e exibe os arquivos disponíveis na rede."""
    global network_files_db
    res = send_to_tracker({"action": "list_files", "port": peer_port})
    if res and res.get('files'):
        network_files_db = res['files']
        log("Arquivos disponíveis na rede:", "INFO")
        if not network_files_db:
            print("Nenhum arquivo encontrado.")
            return

        for name, meta in network_files_db.items():
            print(f"- {name} (Tamanho: {meta['size']} bytes, Peers: {len(meta['peers'])})")
    else:
        log("Não foi possível listar os arquivos.", "ERROR")
        network_files_db = {}


def main():
    global peer_socket, peer_port, logged_in, username
    
    # O SO escolhe uma porta UDP livre
    peer_socket.bind((peer_host, 0))
    peer_port = peer_socket.getsockname()[1]
    
    # Garante que as pastas existem
    os.makedirs(SHARED_FOLDER, exist_ok=True)
    os.makedirs(DOWNLOADS_FOLDER, exist_ok=True)
    
    server_thread = None
    
    while True:
        if not logged_in:
            print("\n1. Registrar\n2. Login\n3. Sair")
            choice = input("> ")
            if choice == '1':
                u = input("Usuário: ")
                p = input("Senha: ")
                res = send_to_tracker({"action": "register", "username": u, "password": p})
                log(res.get('message'), "INFO" if res.get('status') else "ERROR")
            elif choice == '2':
                u = input("Usuário: ")
                p = input("Senha: ")
                res = send_to_tracker({"action": "login", "port": peer_port, "username": u, "password": p})
                if res and res.get('status'):
                    logged_in = True
                    username = u
                    log(f"Login bem-sucedido como '{username}'", "SUCCESS")
                    # Inicia o servidor TCP do peer após o login
                    server_thread = threading.Thread(target=peer_server_logic)
                    server_thread.daemon = True
                    server_thread.start()
                else:
                    log(f"Falha no login: {res.get('message')}", "ERROR")
            elif choice == '3':
                break
        else:
            print(f"\nLogado como: {username}")
            print("1. Anunciar meus arquivos (da pasta 'shared')")
            print("2. Listar arquivos na rede")
            print("3. Baixar arquivo")
            print("4. Logout")
            choice = input("> ")

            if choice == '1':
                announce_files()
            elif choice == '2':
                list_network_files()
            elif choice == '3':
                if not network_files_db:
                    log("Liste os arquivos primeiro (opção 2) para saber o que baixar.", "WARNING")
                    continue
                file_to_download = input("Digite o nome do arquivo para baixar: ")
                if file_to_download in network_files_db:
                    download_file(file_to_download, network_files_db[file_to_download])
                else:
                    log("Arquivo não encontrado na lista da rede.", "ERROR")
            elif choice == '4':
                # Implementar logout no tracker se necessário (enviar msg)
                logged_in = False
                username = ""
                # Idealmente, o programa deveria fechar a thread do servidor aqui
                log("Logout realizado.", "INFO")

    peer_socket.close()
    print("Peer encerrado.")

if __name__ == "__main__":
    main()