import socket
import json
import os
import threading
import hashlib
from queue import Queue
import time
import sys

# O sys.path.append foi removido pois assume-se uma estrutura de pastas local
# Se os módulos estiverem em um diretório 'utils', a importação deve ser ajustada
# Ex: from utils.logger import log
# Para simplificar e rodar de forma autônoma, definirei uma função log simples aqui.

def log(msg, level="INFO"):
    """Função de log simples para evitar dependências externas."""
    now = time.strftime("%H:%M:%S")
    print(f"[{now}] [{level.upper()}] {msg}")

# --- Módulos que antes eram importados, agora definidos localmente para portabilidade ---

CHUNK_SIZE = 1024 * 1024 

def split_file_into_chunks(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
    file_name = os.path.basename(file_path)
    chunks_dir = os.path.join(os.path.dirname(file_path), f"{file_name}_chunks")
    os.makedirs(chunks_dir, exist_ok=True)
    chunk_hashes = []
    file_hash_obj = hashlib.sha256()
    with open(file_path, 'rb') as f:
        chunk_index = 0
        while True:
            chunk_data = f.read(CHUNK_SIZE)
            if not chunk_data: break
            chunk_hash = hashlib.sha256(chunk_data).hexdigest()
            chunk_hashes.append(chunk_hash)
            file_hash_obj.update(chunk_data)
            chunk_file_path = os.path.join(chunks_dir, f"chunk_{chunk_index}")
            with open(chunk_file_path, 'wb') as chunk_f:
                chunk_f.write(chunk_data)
            chunk_index += 1
    return file_hash_obj.hexdigest(), chunk_hashes

def reassemble_chunks(chunks_dir, output_file, total_chunks):
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'wb') as f_out:
        for i in range(total_chunks):
            chunk_path = os.path.join(chunks_dir, f"chunk_{i}")
            if not os.path.exists(chunk_path):
                raise FileNotFoundError(f"Chunk ausente para reconstrução: {chunk_path}")
            with open(chunk_path, 'rb') as f_in:
                f_out.write(f_in.read())
    log(f"Arquivo '{output_file}' reconstruído com sucesso a partir de {total_chunks} chunks.", "SUCCESS")


# --- Configurações ---
TRACKER_HOST, TRACKER_PORT = 'localhost', 9000
SHARED_FOLDER = 'shared'
DOWNLOADS_FOLDER = 'downloads'
NUM_DOWNLOAD_THREADS = 4

# --- Variáveis de Estado Globais ---
peer_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
peer_host = 'localhost'
peer_port = 0 
peer_tcp_server_socket = None

logged_in = False
username = ""
local_files_metadata = {}
network_files_db = {}
chat_active = False

# --- LÓGICA DE COMUNICAÇÃO (CHAT E ARQUIVOS) ---

def handle_chat_session(conn, remote_username):
    """Gerencia uma sessão de chat ativa."""
    global chat_active
    chat_active = True
    log(f"Sessão de chat iniciada com {remote_username}. Digite '/quit' para sair.", "NETWORK")
    
    def receive_messages():
        # CORREÇÃO APLICADA AQUI
        global chat_active
        while chat_active:
            try:
                data = conn.recv(1024)
                if not data:
                    break
                print(f"\r[{remote_username}]: {data.decode()}\n> ", end="")
            except (ConnectionResetError, ConnectionAbortedError, OSError):
                break
            except Exception as e:
                log(f"Erro ao receber mensagem: {e}", "ERROR")
                break
        
        if chat_active:
            log(f"Conexão de chat com {remote_username} encerrada.", "NETWORK")
            chat_active = False

    receiver_thread = threading.Thread(target=receive_messages, daemon=True)
    receiver_thread.start()

    while chat_active:
        try:
            msg = input("> ")
            if not chat_active:
                break
            if msg == '/quit':
                break
            conn.sendall(msg.encode())
        except Exception as e:
            log(f"Não foi possível enviar a mensagem: {e}", "ERROR")
            break

    chat_active = False
    conn.close()
    print("\nSaindo do modo de chat...")


def handle_peer_request(conn, addr):
    """Lida com requisições TCP de outros peers (chunks ou chat)."""
    try:
        request_data = conn.recv(1024).decode()
        request = json.loads(request_data)
        log(f"Requisição TCP recebida de {addr}: {request.get('action')}", "NETWORK")

        action = request.get("action")
        if action == "request_chunk":
            file_name = request.get("file_name")
            chunk_index = request.get("chunk_index")
            chunk_file_path = os.path.join(SHARED_FOLDER, f"{file_name}_chunks", f"chunk_{chunk_index}")

            if os.path.exists(chunk_file_path):
                with open(chunk_file_path, 'rb') as f:
                    chunk_data = f.read()
                conn.sendall(chunk_data)
                # INCENTIVO: Reporta o upload para o tracker
                send_to_tracker({
                    "action": "report_upload", 
                    "username": username,
                    "port": peer_port
                })
                log(f"Chunk {chunk_index} de '{file_name}' enviado para {addr}. Ponto reportado.", "SUCCESS")
            else:
                conn.sendall(b'ERROR: Chunk not found')
                log(f"Chunk {chunk_index} de '{file_name}' não encontrado para {addr}", "WARNING")
            conn.close()
        
        elif action == "initiate_chat":
            remote_username = request.get("from_user", "Desconhecido")
            print(f"\n\r[!] Requisição de chat recebida de '{remote_username}'. Entrando no modo de chat.")
            # A conexão é passada para a função de chat, que será responsável por fechá-la
            handle_chat_session(conn, remote_username)
            return # Retorna para não fechar a conexão no 'finally'

    except (json.JSONDecodeError, ConnectionResetError):
        log(f"Conexão de {addr} encerrada.", "INFO")
    except Exception as e:
        log(f"Erro ao lidar com a requisição de {addr}: {e}", "ERROR")
    finally:
        # A conexão de chat é gerenciada separadamente, então não fechamos aqui
        if 'action' in locals() and locals()['action'] != 'initiate_chat':
            conn.close()


def peer_server_logic():
    """Cria um servidor TCP para escutar por requisições de outros peers."""
    global peer_tcp_server_socket
    peer_tcp_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    peer_tcp_server_socket.bind((peer_host, peer_port))
    peer_tcp_server_socket.listen(10)
    log(f"Peer escutando por conexões TCP em {peer_host}:{peer_port}", "INFO")

    while True:
        try:
            conn, addr = peer_tcp_server_socket.accept()
            thread = threading.Thread(target=handle_peer_request, args=(conn, addr), daemon=True)
            thread.start()
        except OSError:
             # Socket foi fechado, encerrar o loop
             break
    log("Servidor TCP do peer foi encerrado.", "INFO")


# --- LÓGICA DE DOWNLOAD (com incentivo) ---

class DownloaderThread(threading.Thread):
    def __init__(self, file_name, file_hash, chunk_queue, prioritized_peers, temp_dir):
        super().__init__()
        self.file_name = file_name
        self.file_hash = file_hash
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
                            s.settimeout(5)
                            s.connect((peer_ip, int(peer_tcp_port)))
                            request = {"action": "request_chunk", "file_name": self.file_name, "chunk_index": chunk_index}
                            s.sendall(json.dumps(request).encode())
                            
                            response_chunks = []
                            bytes_received = 0
                            # Loop para garantir que todos os dados do chunk sejam recebidos
                            while True:
                                part = s.recv(4096)
                                if not part: break
                                response_chunks.append(part)
                                bytes_received += len(part)
                            response = b''.join(response_chunks)

                        if hashlib.sha256(response).hexdigest() == expected_hash:
                            chunk_path = os.path.join(self.temp_dir, f"chunk_{chunk_index}")
                            with open(chunk_path, 'wb') as f: f.write(response)
                            log(f"Chunk {chunk_index} baixado de {peer_addr_str}", "SUCCESS")
                            success = True
                            break
                        else:
                            log(f"Falha na verificação de hash para o chunk {chunk_index} do peer {peer_addr_str}", "WARNING")
                    except Exception as e:
                        log(f"Não foi possível baixar o chunk {chunk_index} de {peer_addr_str}: {e}", "ERROR")
                if not success:
                    self.chunk_queue.put((chunk_index, expected_hash))
                    time.sleep(1)
            finally:
                self.chunk_queue.task_done()

def download_file(file_name, file_info):
    """Gerencia o download paralelo de um arquivo, usando a ordem de peers priorizada."""
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
    for i, chash in enumerate(chunk_hashes): chunk_queue.put((i, chash))
        
    threads = []
    num_threads = min(NUM_DOWNLOAD_THREADS, len(prioritized_peers))
    for _ in range(num_threads):
        thread = DownloaderThread(file_name, file_hash, chunk_queue, prioritized_peers, temp_dir)
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
        try:
            for f in os.listdir(temp_dir): os.remove(os.path.join(temp_dir, f))
            os.rmdir(temp_dir)
        except OSError as e:
            log(f"Não foi possível limpar a pasta temporária: {e}", "WARNING")
    else:
        log(f"Falha na verificação do arquivo final! Hash esperado: {file_hash}, obtido: {final_hash}", "ERROR")

# --- FUNÇÕES DO MENU ---

def send_to_tracker(data):
    """Envia uma mensagem UDP para o tracker e aguarda a resposta."""
    try:
        peer_socket.sendto(json.dumps(data).encode(), (TRACKER_HOST, TRACKER_PORT))
        response, _ = peer_socket.recvfrom(8192)
        return json.loads(response.decode())
    except Exception as e:
        log(f"Erro de comunicação com o tracker: {e}", "ERROR")
        return {"status": False, "message": str(e)}

def announce_files():
    global local_files_metadata
    os.makedirs(SHARED_FOLDER, exist_ok=True)
    files_to_announce = []
    for filename in os.listdir(SHARED_FOLDER):
        if os.path.isdir(os.path.join(SHARED_FOLDER, filename)): continue
        file_path = os.path.join(SHARED_FOLDER, filename)
        file_size = os.path.getsize(file_path)
        log(f"Processando arquivo '{filename}' para anunciar...", "INFO")
        file_hash, chunk_hashes = split_file_into_chunks(file_path)
        local_files_metadata[filename] = { "file_hash": file_hash, "chunk_hashes": chunk_hashes }
        files_to_announce.append({
            "name": filename, "size": file_size, "hash": file_hash, "chunk_hashes": chunk_hashes
        })
    if not files_to_announce:
        log("Nenhum arquivo encontrado na pasta 'shared' para anunciar.", "WARNING")
        return
    res = send_to_tracker({"action": "announce", "port": peer_port, "username": username, "files": files_to_announce})
    if res and res.get('status'): log("Arquivos anunciados com sucesso!", "SUCCESS")
    else: log(f"Falha ao anunciar arquivos: {res.get('message')}", "ERROR")

def list_network_files():
    global network_files_db
    res = send_to_tracker({"action": "list_files", "port": peer_port, "username": username})
    if res and res.get('files'):
        network_files_db = res['files']
        log("Arquivos disponíveis na rede:", "INFO")
        if not network_files_db:
            print("Nenhum arquivo encontrado.")
            return
        for name, meta in network_files_db.items():
            peer_count = len(meta['peers'])
            best_score = meta['peers'][0]['score'] if peer_count > 0 else 0
            print(f"- {name} (Tamanho: {meta['size']} B, Peers: {peer_count}, Melhor Pontuação: {best_score})")
    else:
        log("Não foi possível listar os arquivos.", "ERROR")
        network_files_db = {}

def show_scores():
    res = send_to_tracker({"action": "get_scores", "port": peer_port, "username": username})
    if res and res.get('status'):
        scores = res.get('scores', [])
        print("\n--- Ranking de Colaboração ---")
        if not scores:
            print("Nenhuma pontuação registrada ainda.")
            return
        for i, (uname, stats) in enumerate(scores):
            uptime_min = stats['uptime_seconds'] / 60
            print(f"{i+1}. {uname}: Pontuação = {stats['score']} (Uploads: {stats['uploads']}, Uptime: {uptime_min:.1f} min)")
        print("------------------------------")
    else:
        log(f"Não foi possível buscar o ranking: {res.get('message')}", "ERROR")

def start_chat_client():
    global chat_active
    res = send_to_tracker({"action": "get_active_peers", "port": peer_port, "username": username})
    if not (res and res.get('status') and res.get('peers')):
        log("Nenhum outro peer ativo para conversar.", "WARNING")
        return

    print("\n--- Peers Ativos para Chat ---")
    active_peers_list = res['peers']
    for i, peer_info in enumerate(active_peers_list):
        print(f"{i+1}. {peer_info['username']}")
    print("------------------------------")
    
    try:
        choice = int(input("Escolha o número do peer para conversar (ou 0 para cancelar): "))
        if choice == 0 or choice > len(active_peers_list):
            return
        
        target_peer = active_peers_list[choice - 1]
        target_ip, target_port = target_peer['address'].split(':')

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((target_ip, int(target_port)))
        request = {"action": "initiate_chat", "from_user": username}
        s.sendall(json.dumps(request).encode())
        handle_chat_session(s, target_peer['username'])

    except (ValueError, IndexError):
        log("Seleção inválida.", "ERROR")
    except Exception as e:
        log(f"Não foi possível iniciar o chat: {e}", "ERROR")
        chat_active = False

def logout_from_tracker():
    """Notifica o tracker sobre o logout."""
    global logged_in, username, peer_tcp_server_socket
    log("Deslogando do tracker...", "INFO")
    send_to_tracker({"action": "logout", "port": peer_port, "username": username})
    logged_in = False
    username = ""
    if peer_tcp_server_socket:
        peer_tcp_server_socket.close()
        peer_tcp_server_socket = None

# --- MAIN LOOP ---

def main():
    global peer_socket, peer_port, logged_in, username
    
    os.makedirs(SHARED_FOLDER, exist_ok=True)
    os.makedirs(DOWNLOADS_FOLDER, exist_ok=True)
    
    server_thread = None
    
    try:
        while True:
            if chat_active:
                time.sleep(1)
                continue
            
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
                    
                    peer_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    peer_socket.bind((peer_host, 0))
                    peer_port = peer_socket.getsockname()[1]

                    res = send_to_tracker({"action": "login", "port": peer_port, "username": u, "password": p})
                    if res and res.get('status'):
                        logged_in = True
                        username = u
                        log(f"Login bem-sucedido como '{username}'", "SUCCESS")
                        server_thread = threading.Thread(target=peer_server_logic, daemon=True)
                        server_thread.start()
                    else:
                        log(f"Falha no login: {res.get('message')}", "ERROR")
                        peer_socket.close()
                elif choice == '3':
                    break
            else:
                print(f"\nLogado como: {username} | Porta: {peer_port}")
                print("1. Anunciar meus arquivos")
                print("2. Listar arquivos na rede")
                print("3. Baixar arquivo")
                print("4. Ver Ranking de Colaboração")
                print("5. Chat com outro peer")
                print("6. Logout")
                choice = input("> ")

                if choice == '1': announce_files()
                elif choice == '2': list_network_files()
                elif choice == '3':
                    if not network_files_db:
                        log("Liste os arquivos primeiro (opção 2).", "WARNING")
                        continue
                    file_to_download = input("Digite o nome do arquivo para baixar: ")
                    if file_to_download in network_files_db:
                        download_file(file_to_download, network_files_db[file_to_download])
                    else:
                        log("Arquivo não encontrado na lista da rede.", "ERROR")
                elif choice == '4': show_scores()
                elif choice == '5': start_chat_client()
                elif choice == '6':
                    logout_from_tracker()
                    # Fecha o socket UDP aqui para que possa ser reaberto no próximo login
                    peer_socket.close()

    except KeyboardInterrupt:
        print("\nSaindo...")
    finally:
        if logged_in:
            logout_from_tracker()
        if not peer_socket._closed:
            peer_socket.close()
        print("Peer encerrado.")

if __name__ == "__main__":
    main()
