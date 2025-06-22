# peer/peer_client.py
import os
import socket
import threading
import time
import json
import argparse

# Módulos de funcionalidades refatorados
from features import announce, chat, download, list_files, ranking, group_chat
from features.network import send_to_tracker

# Módulos de utilidades
from utils.logger import log

# --- CONFIGURAÇÕES E ESTADO GLOBAL ---
SHARED_FOLDER = 'shared'
DOWNLOADS_FOLDER = 'downloads'

peer_host = '0.0.0.0'
peer_port = 0
peer_socket = None # Socket UDP para o tracker
peer_tcp_server_socket = None # Socket TCP para outros peers

logged_in = False
username = ""
network_files_db = {} # Cache local da lista de arquivos da rede

# --- LÓGICA DO SERVIDOR DO PEER ---

def handle_peer_request(conn, addr):
    """Lida com requisições TCP de outros peers (chunks ou chat)."""
    try:
        # Aumentado o buffer para garantir que a requisição JSON seja recebida
        request_data = conn.recv(1024).decode()
        request = json.loads(request_data)
        action = request.get("action")
        log(f"Requisição TCP '{action}' recebida de {addr}", "NETWORK")

        if action == "request_chunk":
            file_name = request.get("file_name")
            chunk_index = request.get("chunk_index")
            requester_username = request.get("username")
            chunk_file_path = os.path.join(SHARED_FOLDER, f"{file_name}_chunks", f"chunk_{chunk_index}")

            if os.path.exists(chunk_file_path):
                with open(chunk_file_path, 'rb') as f:
                    chunk_data = f.read()

                score_res = send_to_tracker({
                    "action": "get_peer_score",
                    "target_username": requester_username
                }, peer_socket)
                score = score_res.get("score", 0) if score_res else 0

                THROTTLE_THRESHOLD = 5
                BYTES_PER_SECOND_LIMIT = 512 * 1024
                if score < THROTTLE_THRESHOLD:
                    packet_size = 4096
                    delay = packet_size / BYTES_PER_SECOND_LIMIT
                    for i in range(0, len(chunk_data), packet_size):
                        conn.sendall(chunk_data[i:i+packet_size])
                        time.sleep(delay)
                else:
                    conn.sendall(chunk_data)

                send_to_tracker({
                    "action": "report_upload",
                    "username": username,
                    "port": peer_port
                }, peer_socket)
            conn.close()
        
        elif action == "initiate_chat":
            remote_username = request.get("from_user", "Desconhecido")
            print(f"\n\r[!] Requisição de chat recebida de '{remote_username}'.")
            # Delega para a função de chat, que gerencia o ciclo de vida da conexão
            chat.handle_chat_session(conn, remote_username)

        elif action == "join_room":
            room_name = request.get("room_name")
            member_user = request.get("username")
            group_chat.accept_member(conn, room_name, member_user)
            return

    except (json.JSONDecodeError, ConnectionResetError) as e:
        log(f"Conexão de {addr} encerrada ou inválida: {e}", "INFO")
        conn.close()
    except Exception as e:
        log(f"Erro ao lidar com a requisição de {addr}: {e}", "ERROR")
        conn.close()

def peer_server_logic():
    """Cria e gerencia o servidor TCP que escuta outros peers."""
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
             break # Socket foi fechado, encerrar o loop
    log("Servidor TCP do peer foi encerrado.", "INFO")

# --- FUNÇÕES DE CONTROLE ---

def login_user():
    """Lida com a lógica de login do usuário."""
    global logged_in, username, peer_port, peer_socket, server_thread
    u = input("Usuário: ")
    p = input("Senha: ")
    
    # Cria sockets para esta sessão de login
    peer_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    peer_socket.bind((peer_host, 0)) # SO escolhe uma porta livre
    peer_port = peer_socket.getsockname()[1]

    res = send_to_tracker({"action": "login", "port": peer_port, "username": u, "password": p}, peer_socket)
    if res and res.get('status'):
        logged_in = True
        username = u
        log(f"Login bem-sucedido como '{username}'", "SUCCESS")
        # Inicia o servidor TCP do peer após o login
        server_thread = threading.Thread(target=peer_server_logic, daemon=True)
        server_thread.start()
    else:
        log(f"Falha no login: {res.get('message')}", "ERROR")
        peer_socket.close()

def register_user():
    """Lida com a lógica de registro de usuário."""
    # Para registrar, não precisamos de um socket ativo
    temp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    u = input("Usuário: ")
    p = input("Senha: ")
    res = send_to_tracker({"action": "register", "username": u, "password": p}, temp_socket)
    log(res.get('message'), "INFO" if res.get('status') else "ERROR")
    temp_socket.close()

def logout_user():
    """Lida com a lógica de logout."""
    global logged_in, username, peer_tcp_server_socket, peer_socket
    log("Deslogando do tracker...", "INFO")
    send_to_tracker({"action": "logout", "port": peer_port, "username": username}, peer_socket)
    logged_in = False
    username = ""
    
    # Fecha os sockets da sessão
    if peer_tcp_server_socket:
        peer_tcp_server_socket.close()
        peer_tcp_server_socket = None
    if peer_socket:
        peer_socket.close()
        peer_socket = None

# --- LOOP PRINCIPAL DA APLICAÇÃO ---

def main():
    global network_files_db
    os.makedirs(SHARED_FOLDER, exist_ok=True)
    os.makedirs(DOWNLOADS_FOLDER, exist_ok=True)
    
    try:
        while True:
            if chat.chat_active_flag.is_set():
                time.sleep(1)
                continue
            
            if not logged_in:
                print("\n1. Registrar\n2. Login\n3. Sair")
                choice = input("> ")
                if choice == '1': register_user()
                elif choice == '2': login_user()
                elif choice == '3': break
            else:
                print(f"\nLogado como: {username} | Porta: {peer_port}")
                print("1. Anunciar meus arquivos")
                print("2. Listar arquivos na rede")
                print("3. Baixar arquivo")
                print("4. Ver Ranking de Colaboração")
                print("5. Chat com outro peer")
                print("6. Salas de Chat (Grupo)")
                print("7. Logout")
                choice = input("> ")

                if choice == '1': announce.announce_files(peer_port, username, peer_socket)
                elif choice == '2': network_files_db = list_files.list_network_files(peer_port, username, peer_socket)
                elif choice == '3':
                    if not network_files_db:
                        log("Liste os arquivos primeiro (opção 2).", "WARNING")
                        continue
                    file_to_download = input("Digite o nome do arquivo para baixar: ")
                    if file_to_download in network_files_db:
                        download.download_file(file_to_download, network_files_db[file_to_download], username)
                    else:
                        log("Arquivo não encontrado na lista da rede.", "ERROR")
                elif choice == '4': ranking.show_scores(peer_port, username, peer_socket)
                elif choice == '5': chat.start_chat_client(peer_port, username, peer_socket)
                elif choice == '6': group_chat.show_menu(peer_port, username, peer_socket)
                elif choice == '7': logout_user()

    except KeyboardInterrupt:
        print("\nSaindo...")
    finally:
        if logged_in:
            logout_user()
        print("Peer encerrado.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    from utils.config import detect_local_ip
    default_host = os.environ.get('PEER_HOST', detect_local_ip())
    parser.add_argument('--host', default=default_host, help='IP para escutar conexoes TCP')
    args = parser.parse_args()
    peer_host = args.host
    main()
