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
    logged_in = False
    
    while True:
        if not logged_in:
            print("\n1. Registrar\n2. Login\n0. Sair")
        else:
            print("\n3. Anunciar Arquivos\n4. Listar Arquivos\n5. Logout\n0. Sair")
        
        op = input("\nEscolha: ")

        if op == "1" and not logged_in:
            u = input("Usuario: ").strip()
            p = input("Senha: ").strip()
            if not u or not p:
                print("[!] Usuario e senha não podem estar vazios")
                continue
            res = send_to_tracker({"action": "register", "username": u, "password": p})
            print(f"\n[{'✓' if res['status'] else '✗'}] {res['message']}")

        elif op == "2" and not logged_in:
            u = input("Usuario: ").strip()
            p = input("Senha: ").strip()
            if not u or not p:
                print("[!] Usuario e senha não podem estar vazios")
                continue
            res = send_to_tracker({"action": "login", "username": u, "password": p})
            if res['status']:
                logged_in = True
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
                    "files": [{"name": name, "size": size, "hash": hsh}]
                })
                print(f"\n[{'✓' if res['status'] else '✗'}] {res['message']}")
            except ValueError:
                print("[!] Tamanho deve ser um número válido")

        elif op == "4" and logged_in:
            res = send_to_tracker({"action": "list_files"})
            if not res.get('files'):
                print("\n[i] Nenhum arquivo registrado no tracker")
            else:
                print("\nArquivos disponíveis:")
                for name, meta in res['files'].items():
                    print(f"\n- {name}")
                    print(f"  Tamanho: {meta['size']} bytes")
                    print(f"  Hash: {meta['hash']}")
                    print(f"  Peers: {len(meta['peers'])} disponível(is)")

        elif op == "5" and logged_in:
            logged_in = False
            print("\n[✓] Logout realizado com sucesso")

        elif op == "0":
            print("\n[✓] Encerrando cliente...")
            break
        
        else:
            print("\n[!] Opção inválida ou não disponível no momento")

if __name__ == "__main__":
    main()
