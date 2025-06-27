import os
import socket
import threading
import time
import json
import argparse
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from features import announce, chat, download, list_files, ranking, group_chat
from features.network import send_to_tracker
from utils.logger import log

SHARED_FOLDER = 'shared'
DOWNLOADS_FOLDER = 'downloads'

peer_host = '0.0.0.0'
peer_port = 0
peer_tcp_server_socket = None

logged_in = False
username = ""
network_files_db = {}


def handle_peer_request(conn, addr):
    try:
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
                })
                tier = score_res.get("tier", "bronze") if score_res else "bronze"
                delay_map = {"bronze": 10, "prata": 5, "ouro": 2, "diamante": 0}
                time.sleep(delay_map.get(tier, 0))
                conn.sendall(chunk_data)

                send_to_tracker({
                    "action": "report_upload",
                    "username": username,
                    "port": peer_port
                })
            conn.close()
        
        elif action == "initiate_chat":
            remote_username = request.get("from_user", "Desconhecido")
            print(f"\n\r[!] Requisição de chat recebida de '{remote_username}'.")
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
            break
    log("Servidor TCP do peer foi encerrado.", "INFO")


def login_user():
    global logged_in, username, peer_port, peer_tcp_server_socket, server_thread
    u = input("Usuário: ")
    p = input("Senha: ")

    peer_tcp_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    peer_tcp_server_socket.bind((peer_host, 0))
    peer_port = peer_tcp_server_socket.getsockname()[1]
    peer_tcp_server_socket.listen(10)

    res = send_to_tracker({"action": "login", "port": peer_port, "username": u, "password": p})
    if res and res.get('status'):
        logged_in = True
        username = u
        log(f"Login bem-sucedido como '{username}'", "SUCCESS")
        server_thread = threading.Thread(target=peer_server_logic, daemon=True)
        server_thread.start()
    else:
        log(f"Falha no login: {res.get('message')}", "ERROR")
        peer_tcp_server_socket.close()

def register_user():
    u = input("Usuário: ")
    p = input("Senha: ")
    res = send_to_tracker({"action": "register", "username": u, "password": p})
    if res and res.get('status'):
        print(res.get('message'))
    else:
        log(res.get('message', 'Falha no registro'), 'ERROR')

def logout_user():
    global logged_in, username, peer_tcp_server_socket
    log("Deslogando do tracker...", "INFO")
    send_to_tracker({"action": "logout", "port": peer_port, "username": username})
    logged_in = False
    username = ""
    
    
    if peer_tcp_server_socket:
        peer_tcp_server_socket.close()
        peer_tcp_server_socket = None

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

                if choice == '1': announce.announce_files(peer_port, username)
                elif choice == '2': network_files_db = list_files.list_network_files(peer_port, username)
                elif choice == '3':
                    if not network_files_db:
                        log("Liste os arquivos primeiro (opção 2).", "WARNING")
                        continue
                    file_to_download = input("Digite o nome do arquivo para baixar: ")
                    if file_to_download in network_files_db:
                        download.download_file(file_to_download, network_files_db[file_to_download], username)
                    else:
                        log("Arquivo não encontrado na lista da rede.", "ERROR")
                elif choice == '4': ranking.show_scores(peer_port, username)
                elif choice == '5': chat.start_chat_client(peer_port, username)
                elif choice == '6': group_chat.show_menu(peer_port, username)
                elif choice == '7': logout_user()

    except KeyboardInterrupt:
        print("\nSaindo...")
    finally:
        if logged_in:
            logout_user()
        print("Peer encerrado.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    from utils.config import detect_local_ip, set_tracker_address, TRACKER_HOST, TRACKER_PORT
    peer_host = '0.0.0.0'
    parser.add_argument('--tracker', default=f'{TRACKER_HOST}:{TRACKER_PORT}', help='Endereco do tracker no formato IP:PORT')
    args = parser.parse_args()
    host_port = args.tracker
    if ':' in host_port:
        t_host, t_port = host_port.split(':', 1)
        set_tracker_address(t_host, int(t_port))
    else:
        set_tracker_address(host_port, TRACKER_PORT)
    main()

