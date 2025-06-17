import socket
import threading
import json
import datetime
from auth_manager import register_user, authenticate_user, log

files_db = {}      # filename -> {"size": int, "hash": str, "chunk_hashes": [str], "peers": [(ip, port)]}
active_peers = {}  # (ip, port) -> { username, login_time }

HOST, PORT = 'localhost', 9000

def handle_request(data, addr, server):
    try:
        request = json.loads(data.decode())
        action = request.get("action")
        response = {}

        ip, port = addr
        peer_key = (ip, request.get("port", port))

        log(f"Requisição '{action}' recebida de {ip}:{port}", "INFO")

        if action == "register":
            ok, msg = register_user(request['username'], request['password'])
            log(f"Registro de usuário '{request['username']}': {msg}", "INFO")
            response = {"status": ok, "message": msg}

        elif action == "login":
            ok = authenticate_user(request['username'], request['password'])
            if ok:
                active_peers[peer_key] = {
                    "username": request['username'],
                    "login_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                log(f"Usuário '{request['username']}' logado com sucesso em {peer_key}", "SUCCESS")
                response = {"status": True, "message": "Login realizado."}
            else:
                log(f"Falha no login para '{request['username']}'", "WARNING")
                response = {"status": False, "message": "Credenciais inválidas."}

        elif action == "announce":
            files = request.get("files", [])
            for f in files:
                entry = files_db.setdefault(f['name'], {
                    "size": f['size'],
                    "hash": f['hash'],
                    "chunk_hashes": f.get("chunk_hashes", []), # MODIFICADO: Adicionado suporte para hashes de chunks
                    "peers": []
                })
                if peer_key not in entry['peers']:
                    entry['peers'].append(peer_key)
                    log(f"Peer {peer_key} anunciou arquivo '{f['name']}'", "INFO")
            response = {"status": True, "message": "Arquivos registrados."}

        elif action == "list_files":
            log(f"Peer {peer_key} requisitou a lista de arquivos", "INFO")
            serializable_db = {}
            for fname, meta in files_db.items():
                serializable_db[fname] = {
                    "size": meta["size"],
                    "hash": meta["hash"],
                    "chunk_hashes": meta["chunk_hashes"], # MODIFICADO: Inclui hashes de chunks na resposta
                    "peers": [f"{ip}:{pt}" for ip, pt in meta["peers"]]
                }
            response = {"files": serializable_db}

        elif action == "get_peer":
            peer_data = active_peers.get(peer_key)
            if peer_data:
                response = {
                    "status": True,
                    "peer": {
                        "ip": peer_key[0],
                        "port": peer_key[1],
                        **peer_data
                    }
                }
            else:
                response = {"status": False, "message": "Nenhum peer logado com esse IP/porta"}

        elif action == "get_all_peer":
            log("Listagem de todos os peers ativos requisitada", "INFO")
            all_peers = [
                {
                    "ip": ip,
                    "port": pt,
                    **data
                }
                for (ip, pt), data in active_peers.items()
            ]
            response = {"status": True, "peers": all_peers}

        else:
            log(f"Ação desconhecida: {action}", "WARNING")
            response = {"status": False, "message": "Ação desconhecida"}

    except Exception as e:
        log(f"Erro ao processar requisição de {addr}: {e}", "ERROR")
        response = {"status": False, "error": str(e)}

    server.sendto(json.dumps(response).encode(), addr)

def start_tracker():
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind((HOST, PORT))
    log(f"Tracker (UDP) iniciado em {HOST}:{PORT}", "INFO")

    try:
        while True:
            data, addr = server.recvfrom(4096)
            thread = threading.Thread(target=handle_request, args=(data, addr, server))
            thread.daemon = True
            thread.start()
    except KeyboardInterrupt:
        print("\n[*] Encerrando o tracker...")
    except Exception as e:
        print(f"[!] Erro: {e}")
    finally:
        server.close()

if __name__ == "__main__":
    start_tracker()