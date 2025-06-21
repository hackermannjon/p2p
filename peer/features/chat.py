# peer/features/chat.py
import socket
import json
import threading
from utils.logger import log
from .network import send_to_tracker

chat_active_flag = threading.Event()

def handle_chat_session(conn, remote_username):
    """Gerencia uma sessão de chat ativa. Esta função bloqueia até o chat terminar."""
    chat_active_flag.set()
    log(f"Sessão de chat iniciada com {remote_username}. Digite '/quit' para sair.", "NETWORK")
    
    def receive_messages():
        while chat_active_flag.is_set():
            try:
                data = conn.recv(1024)
                if not data:
                    break
                print(f"\r[{remote_username}]: {data.decode()}\n> ", end="")
            except (ConnectionResetError, ConnectionAbortedError, OSError):
                break
        chat_active_flag.clear() # Sinaliza para a thread de envio parar

    receiver_thread = threading.Thread(target=receive_messages, daemon=True)
    receiver_thread.start()

    while chat_active_flag.is_set():
        try:
            msg = input("> ")
            if not chat_active_flag.is_set():
                break
            if msg == '/quit':
                break
            conn.sendall(msg.encode())
        except (KeyboardInterrupt, EOFError):
            break
        except Exception as e:
            log(f"Não foi possível enviar a mensagem: {e}", "ERROR")
            break

    chat_active_flag.clear()
    conn.close()
    print("\nSaindo do modo de chat...")

def start_chat_client(peer_port, username, peer_socket):
    """Inicia o processo para um cliente começar uma conversa."""
    res = send_to_tracker({"action": "get_active_peers", "port": peer_port, "username": username}, peer_socket)
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
        if not (0 < choice <= len(active_peers_list)):
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
