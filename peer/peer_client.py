import socket
import json

TRACKER_HOST, TRACKER_PORT = 'localhost', 9000

# Socket e porta fixa após login
peer_socket = None
peer_port = None
peer_addr = None

def send_to_tracker(data):
    if peer_socket is None:
        raise RuntimeError("Socket do peer ainda não foi inicializado.")

    message = json.dumps(data).encode()
    peer_socket.sendto(message, (TRACKER_HOST, TRACKER_PORT))

    try:
        response, _ = peer_socket.recvfrom(4096)
        return json.loads(response.decode())
    except socket.timeout:
        return {"status": False, "message": "Tracker não respondeu"}

def main():
    global peer_socket, peer_port, peer_addr

    print("=== Cliente Peer P2P (UDP) ===")
    logged_in = False
    username = ""

    while True:
        if not logged_in:
            print("\n1. Registrar\n2. Login\n0. Sair")
        else:
            print(f"\n[Logado como {username}:{peer_port}]")
            print("3. Anunciar Arquivos\n4. Listar Arquivos\n5. Logout\n6. Informações do peer\n7. Ver todos os peers\n0. Sair")

        op = input("\nEscolha: ")

        if op == "1" and not logged_in:
            u = input("Usuário: ").strip()
            p = input("Senha: ").strip()
            if not u or not p:
                print("[!] Usuário e senha não podem estar vazios")
                continue
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as temp_socket:
                temp_socket.settimeout(3)
                res = send_raw(temp_socket, {
                    "action": "register",
                    "username": u,
                    "password": p
                })
            print(f"\n[{'✓' if res['status'] else '✗'}] {res['message']}")

        elif op == "2" and not logged_in:
            u = input("Usuário: ").strip()
            p = input("Senha: ").strip()

            try:
                port = int(input("Porta fixa do peer (ex: 65173): ").strip())
                peer_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                peer_socket.bind(('localhost', port))  # Porta fixa
                peer_socket.settimeout(3)
                peer_port = port
                peer_addr = ('localhost', port)
            except Exception as e:
                print(f"[!] Erro ao criar socket: {e}")
                continue

            res = send_to_tracker({
                "action": "login",
                "username": u,
                "password": p,
                "port": peer_port
            })

            if res['status']:
                logged_in = True
                username = u
            else:
                peer_socket.close()
                peer_socket = None
                peer_port = None
            print(f"\n[{'✓' if res['status'] else '✗'}] {res['message']}")

        elif op == "3" and logged_in:
            try:
                name = input("Nome do arquivo: ").strip()
                size = int(input("Tamanho (bytes): "))
                hsh = input("Hash (SHA-256): ").strip()
                if not name or not hsh:
                    print("[!] Nome e hash são obrigatórios")
                    continue
                res = send_to_tracker({
                    "action": "announce",
                    "port": peer_port,
                    "files": [{"name": name, "size": size, "hash": hsh}]
                })
                print(f"\n[{'✓' if res['status'] else '✗'}] {res['message']}")
            except ValueError:
                print("[!] Tamanho deve ser um número válido")

        elif op == "4" and logged_in:
            res = send_to_tracker({"action": "list_files", "port": peer_port})
            if not res.get('files'):
                print("\n[i] Nenhum arquivo registrado no tracker")
            else:
                print("\nArquivos disponíveis:")
                for name, meta in res['files'].items():
                    print(f"\n- {name}")
                    print(f"  Tamanho: {meta['size']} bytes")
                    print(f"  Hash: {meta['hash']}")
                    print(f"  Peers: {', '.join(meta['peers'])}")

        elif op == "6" and logged_in:
            res = send_to_tracker({"action": "get_peer", "port": peer_port})
            if not res.get("status"):
                print(f"\n✗ {res.get('message')}")
            else:
                print("\nPeer logado:")
                peer = res['peer']
                print(f"Usuário: {peer['username']}")
                print(f"IP: {peer['ip']}")
                print(f"Porta: {peer['port']}")
                print(f"Login em: {peer['login_time']}")

        elif op == "7" and logged_in:
            res = send_to_tracker({"action": "get_all_peer"})
            print("\nPeers ativos:")
            for peer in res.get("peers", []):
                print(f"- {peer['username']} em {peer['ip']}:{peer['port']} (desde {peer['login_time']})")

        elif op == "5" and logged_in:
            logged_in = False
            username = ""
            peer_socket.close()
            peer_socket = None
            peer_port = None
            print("\n[✓] Logout realizado com sucesso")

        elif op == "0":
            if peer_socket:
                peer_socket.close()
            print("\n[✓] Encerrando cliente...")
            break

        else:
            print("\n[!] Opção inválida ou não disponível no momento")

def send_raw(sock, data):
    try:
        sock.sendto(json.dumps(data).encode(), (TRACKER_HOST, TRACKER_PORT))
        response, _ = sock.recvfrom(4096)
        return json.loads(response.decode())
    except socket.timeout:
        return {"status": False, "message": "Tracker não respondeu"}

if __name__ == "__main__":
    main()
