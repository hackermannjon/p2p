import socket
import threading
import json
from auth_manager import register_user, authenticate_user

files_db = {}     # filename -> {"size": int, "hash": str, "peers": [ip]}
active_peers = {} # ip -> username

HOST, PORT = 'localhost', 9000

def handle_client(conn, addr):
    data = conn.recv(4096).decode()
    try:
        request = json.loads(data)
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
                response = {"status": False, "message": "Credenciais invalidas."}

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

    except Exception as e:
        response = {"status": False, "error": str(e)}

    conn.sendall(json.dumps(response).encode())
    conn.close()

def start_tracker():
    server = socket.socket()
    server.bind((HOST, PORT))
    server.listen()
    print(f"[TRACKER] Rodando em {HOST}:{PORT}")

    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_client, args=(conn, addr)).start()

if __name__ == "__main__":
    start_tracker()
