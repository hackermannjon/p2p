import socket
import threading
import json
from auth_manager import register_user, authenticate_user

files_db = {}     # filename -> {"size": int, "hash": str, "peers": [ip]}
active_peers = {} # ip -> username

HOST, PORT = 'localhost', 9000

def handle_request(data, addr, server):
    try:
        request = json.loads(data.decode())
        action = request.get("action")
        response = {}

        if action == "register":
            ok, msg = register_user(request['username'], request['password'])
            response = {"status": ok, "message": msg}

        elif action == "login":
            ok = authenticate_user(request['username'], request['password'])
            if ok:
                active_peers[addr[0]] = request['username']
                response = {"status": True, "message": "Login realizado."}
            else:
                response = {"status": False, "message": "Credenciais inválidas."}

        elif action == "announce":
            files = request.get("files", [])
            for f in files:
                entry = files_db.setdefault(f['name'], {
                    "size": f['size'],
                    "hash": f['hash'],
                    "peers": []
                })
                if addr[0] not in entry['peers']:
                    entry['peers'].append(addr[0])
            response = {"status": True, "message": "Arquivos registrados."}

        elif action == "list_files":
            response = {"files": files_db}

        else:
            response = {"status": False, "message": "Ação desconhecida"}

    except Exception as e:
        response = {"status": False, "error": str(e)}

    # Enviar resposta para o remetente
    server.sendto(json.dumps(response).encode(), addr)

def start_tracker():
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind((HOST, PORT))
    print(f"[*] Tracker (UDP) iniciado em {HOST}:{PORT}")

    try:
        while True:
            data, addr = server.recvfrom(4096)
            print(f"[*] Mensagem recebida de {addr[0]}:{addr[1]}")
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
