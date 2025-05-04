import socket
import json

TRACKER_HOST, TRACKER_PORT = 'localhost', 9000

def send_to_tracker(data):
    with socket.socket() as s:
        s.connect((TRACKER_HOST, TRACKER_PORT))
        s.sendall(json.dumps(data).encode())
        return json.loads(s.recv(4096).decode())

def main():
    print("=== Cliente Peer P2P ===")
    while True:
        print("1. Registrar\n2. Login\n3. Anunciar Arquivos\n4. Listar Arquivos\n0. Sair")
        op = input("Escolha: ")

        if op == "1":
            u, p = input("Usuario: "), input("Senha: ")
            res = send_to_tracker({"action": "register", "username": u, "password": p})
            print(res)

        elif op == "2":
            u, p = input("Usuario: "), input("Senha: ")
            res = send_to_tracker({"action": "login", "username": u, "password": p})
            print(res)

        elif op == "3":
            name = input("Nome do arquivo: ")
            size = int(input("Tamanho (bytes): "))
            hsh = input("Hash (SHA-256): ")
            res = send_to_tracker({
                "action": "announce",
                "files": [{"name": name, "size": size, "hash": hsh}]
            })
            print(res)

        elif op == "4":
            res = send_to_tracker({"action": "list_files"})
            for name, meta in res['files'].items():
                print(f"- {name}: {meta['size']} bytes, hash={meta['hash']}, peers={meta['peers']}")

        elif op == "0":
            break

if __name__ == "__main__":
    main()
