import socket
import threading
import json
import datetime
import os
import sys

# Garanta que o diretório pai esteja no PYTHONPATH para permitir "import utils"
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from auth_manager import register_user, authenticate_user, log
from utils.config import TRACKER_HOST, TRACKER_PORT

# --- ESTRUTURAS DE DADOS ---

# Armazena metadados de arquivos
# formato: { filename: {"size": int, "hash": str, "chunk_hashes": [str], "peers": [(ip, port)]} }
files_db = {}

# Armazena peers atualmente logados
# formato: { (ip, port): { "username": str, "login_time": datetime } }
active_peers = {}

# Armazena pontuações de incentivo para cada usuário (persistente enquanto o tracker rodar)
# formato: { username: {"uploads": int, "uptime_seconds": int, "score": float} }
peer_scores = {}

# Armazena salas de chat
# formato: { room_name: {"moderator": str, "address": "ip:port", "members": [usernames] } }
chat_rooms = {}

# Endereço do tracker definido em config.json
HOST, PORT = TRACKER_HOST, TRACKER_PORT

# --- LÓGICA DE INCENTIVO ---

def calculate_score(stats):
    """Calcula a pontuação de um peer com base em suas estatísticas."""
    # Métrica híbrida: 1 ponto por upload, 0.01 pontos por segundo online.
    score = (stats.get("uploads", 0) * 1.0) + (stats.get("uptime_seconds", 0) * 0.01)
    return round(score, 2)

def initialize_peer_score(username):
    """Inicializa a pontuação para um novo usuário ou um usuário que retorna."""
    if username not in peer_scores:
        peer_scores[username] = {"uploads": 0, "uptime_seconds": 0, "score": 0}
        log(f"Pontuação inicializada para o usuário '{username}'", "INFO")

# --- LÓGICA PRINCIPAL DO TRACKER ---

def handle_request(conn, addr):
    """Processa uma requisição de um peer."""
    try:
        data = conn.recv(4096)
        if not data:
            conn.close()
            return
        request = json.loads(data.decode())
        action = request.get("action")
        response = {}

        ip, port = addr
        # A porta relevante é a porta TCP que o peer está escutando, enviada na requisição
        peer_listening_port = request.get("port", port)
        peer_key = (ip, peer_listening_port)
        username = request.get("username")

        log(f"Requisição '{action}' recebida de {addr} para o usuário '{username}'", "INFO")

        if action == "register":
            ok, msg = register_user(request['username'], request['password'])
            if ok:
                initialize_peer_score(request['username'])
            log(f"Registro de usuário '{request['username']}': {msg}", "INFO")
            response = {"status": ok, "message": msg}

        elif action == "login":
            ok = authenticate_user(request['username'], request['password'])
            if ok:
                # Garante que a pontuação seja inicializada se o tracker reiniciou
                initialize_peer_score(request['username'])
                active_peers[peer_key] = {
                    "username": request['username'],
                    "login_time": datetime.datetime.now()
                }
                log(f"Usuário '{request['username']}' logado em {peer_key}", "SUCCESS")
                response = {"status": True, "message": "Login realizado."}
            else:
                log(f"Falha no login para '{request['username']}'", "WARNING")
                response = {"status": False, "message": "Credenciais inválidas."}
        
        elif action == "logout":
            if peer_key in active_peers:
                # Calcula o tempo de atividade da sessão
                session_duration = datetime.datetime.now() - active_peers[peer_key]['login_time']
                uptime_seconds = int(session_duration.total_seconds())

                # Atualiza as estatísticas de pontuação
                user_stats = peer_scores.get(username, {})
                user_stats["uptime_seconds"] = user_stats.get("uptime_seconds", 0) + uptime_seconds
                user_stats["score"] = calculate_score(user_stats)
                peer_scores[username] = user_stats

                # Remove o peer dos ativos e de todos os arquivos que ele sediava
                del active_peers[peer_key]
                for file_meta in files_db.values():
                    if peer_key in file_meta['peers']:
                        file_meta['peers'].remove(peer_key)
                
                log(f"Usuário '{username}' {peer_key} deslogado. Uptime da sessão: {uptime_seconds}s.", "INFO")
                response = {"status": True, "message": "Logout realizado com sucesso."}
            else:
                response = {"status": False, "message": "Peer não estava logado."}

        elif action == "announce":
            if peer_key not in active_peers:
                response = {"status": False, "message": "Ação não permitida. Faça login primeiro."}
            else:
                files = request.get("files", [])
                for f in files:
                    entry = files_db.setdefault(f['name'], {
                        "size": f['size'], "hash": f['hash'], "chunk_hashes": f.get("chunk_hashes", []), "peers": []
                    })
                    if peer_key not in entry['peers']:
                        entry['peers'].append(peer_key)
                        log(f"Peer {peer_key} anunciou arquivo '{f['name']}'", "INFO")
                response = {"status": True, "message": "Arquivos registrados."}

        elif action == "list_files":
            serializable_db = {}
            for fname, meta in files_db.items():
                peers_with_scores = []
                for ip_peer, port_peer in meta["peers"]:
                    # Encontra o username do peer para buscar sua pontuação
                    peer_info = active_peers.get((ip_peer, port_peer))
                    if peer_info:
                        uname = peer_info.get("username")
                        score = peer_scores.get(uname, {}).get("score", 0)
                        peers_with_scores.append({"peer": f"{ip_peer}:{port_peer}", "score": score})

                # Ordena os peers pela pontuação (maior primeiro)
                peers_with_scores.sort(key=lambda x: x['score'], reverse=True)

                serializable_db[fname] = {
                    "size": meta["size"], "hash": meta["hash"], "chunk_hashes": meta["chunk_hashes"],
                    "peers": peers_with_scores
                }
            response = {"files": serializable_db}

        elif action == "report_upload":
            # Peer reporta que fez um upload para ganhar pontos
            if username and username in peer_scores:
                peer_scores[username]["uploads"] += 1
                peer_scores[username]["score"] = calculate_score(peer_scores[username])
                log(f"Ponto de upload registrado para '{username}'. Nova pontuação: {peer_scores[username]['score']}", "SUCCESS")
                response = {"status": True}
            else:
                response = {"status": False, "message": "Usuário não encontrado para premiar."}

        elif action == "get_scores":
            # Retorna o ranking de todos os peers
            sorted_scores = sorted(peer_scores.items(), key=lambda item: item[1]['score'], reverse=True)
            response = {"status": True, "scores": sorted_scores}

        elif action == "get_peer_score":
            target = request.get("target_username")
            sc = peer_scores.get(target, {}).get("score", 0)
            response = {"status": True, "score": sc}

        elif action == "get_active_peers":
            # Retorna peers ativos para o chat
            peer_list = [{"username": v['username'], "address": f"{k[0]}:{k[1]}"}
                         for k, v in active_peers.items() if k != peer_key]
            response = {"status": True, "peers": peer_list}

        elif action == "create_room":
            room = request.get("room_name")
            if room in chat_rooms:
                response = {"status": False, "message": "Sala ja existe"}
            else:
                chat_rooms[room] = {
                    "moderator": username,
                    "address": f"{ip}:{peer_listening_port}",
                    "members": []
                }
                log(f"Sala '{room}' criada pelo moderador {username}", "INFO")
                response = {"status": True}

        elif action == "list_rooms":
            response = {"status": True, "rooms": chat_rooms}

        elif action == "delete_room":
            room = request.get("room_name")
            info = chat_rooms.get(room)
            if info and info.get("moderator") == username:
                del chat_rooms[room]
                response = {"status": True}
            else:
                response = {"status": False, "message": "Sala nao encontrada ou permissao negada"}

        elif action == "room_member_update":
            room = request.get("room_name")
            member = request.get("username")
            event = request.get("event")
            info = chat_rooms.get(room)
            if info:
                members = info.setdefault("members", [])
                if event == "join" and member not in members:
                    members.append(member)
                    log(f"{member} entrou na sala '{room}'", "INFO")
                if event == "leave" and member in members:
                    members.remove(member)
                    log(f"{member} saiu da sala '{room}'", "INFO")
                response = {"status": True}
            else:
                response = {"status": False, "message": "Sala inexistente"}

        else:
            log(f"Ação desconhecida: {action}", "WARNING")
            response = {"status": False, "message": "Ação desconhecida"}

    except Exception as e:
        log(f"Erro ao processar requisição de {addr}: {e}", "ERROR")
        response = {"status": False, "error": str(e)}

    conn.sendall(json.dumps(response).encode())
    conn.close()

def start_tracker():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen(15)
    log(f"Tracker (TCP) iniciado em {HOST}:{PORT}", "INFO")

    try:
        while True:
            conn, addr = server.accept()
            thread = threading.Thread(target=handle_request, args=(conn, addr), daemon=True)
            thread.start()
    except KeyboardInterrupt:
        print("\n[*] Encerrando o tracker...")
    finally:
        server.close()

if __name__ == "__main__":
    start_tracker()
