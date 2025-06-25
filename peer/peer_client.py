"""Interface de linha de comando do peer.

Este script permite registrar usuários, efetuar login e consultar o tracker
utilizando mensagens UDP. Foi concebido para fins didáticos a fim de testar os
recursos do projeto P2P sem a necessidade de uma interface gráfica.
"""

import socket  # Prover comunicação em rede para enviar/receber datagramas.
import json    # Utilizado para codificar e decodificar mensagens JSON.

TRACKER_HOST, TRACKER_PORT = 'localhost', 9000

# Socket e porta fixa após login
peer_socket = None
peer_port = None
peer_addr = None

def send_to_tracker(data: dict) -> dict:
    """Envia um pacote JSON para o tracker e aguarda a resposta.

    Esta rotina assume que ``peer_socket`` já está configurado e usando uma
    porta fixa. Apesar de o UDP não garantir entrega, na prática o tracker e o
    peer estão na mesma máquina (ou rede local), o que minimiza perdas. Ainda
    assim, definimos um ``timeout`` para detectar a ausência de resposta.
    """

    # P: O que acontece se o tracker não responder?
    # R: O socket possui um timeout configurado. Caso não haja resposta nesse
    #    período, retornamos uma mensagem de erro para o usuário.

    if peer_socket is None:
        raise RuntimeError("Socket do peer ainda não foi inicializado.")

    message = json.dumps(data).encode()
    # Envia o datagrama diretamente ao tracker
    peer_socket.sendto(message, (TRACKER_HOST, TRACKER_PORT))

    try:
        # Aguarda a resposta que deve chegar em poucos milissegundos
        response, _ = peer_socket.recvfrom(4096)

        # Converte o JSON de volta para dicionário para facilitar o acesso
        return json.loads(response.decode())
    except socket.timeout:
        # Sem resposta dentro do timeout configurado
        return {"status": False, "message": "Tracker não respondeu"}

def main() -> None:
    """Loop principal do cliente interativo.

    Exibe um menu de opções que permite registrar usuários, efetuar login e
    consultar informações mantidas pelo tracker. As operações são basicamente
    solicitações UDP que utilizam as funções ``send_to_tracker`` e ``send_raw``.
    """

    global peer_socket, peer_port, peer_addr

    print("=== Cliente Peer P2P (UDP) ===")
    logged_in = False
    username = ""

    # P: Como mantemos o cliente esperando comandos do usuário de forma
    #    ininterrupta?
    # R: Utilizamos um loop infinito que só é quebrado quando o usuário escolhe
    #    sair. Dentro dele tratamos as opções do menu.
    while True:
        if not logged_in:
            print("\n1. Registrar\n2. Login\n0. Sair")
        else:
            print(f"\n[Logado como {username}:{peer_port}]")
            print("3. Anunciar Arquivos\n4. Listar Arquivos\n5. Logout\n6. Informações do peer\n7. Ver todos os peers\n0. Sair")

        op = input("\nEscolha: ")

        # P: Como acontece o fluxo de registro de um novo usuário?
        # R: Utilizamos um socket UDP temporário para enviar os dados ao tracker,
        #    pois ainda não possuímos um socket persistente nesta fase.
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

        # P: E o processo de login? Por que é necessário informar a porta?
        # R: Cada peer precisa escutar em uma porta fixa para que outros peers
        #    possam entrar em contato diretamente. Por isso pedimos a porta no
        #    momento do login.
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

        # P: Como o peer informa ao tracker quais arquivos possui?
        # R: A ação ``announce`` envia uma lista de arquivos com seus hashes e
        #    tamanhos, permitindo que outros peers localizem quem possui cada
        #    recurso.
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

        # P: De que forma obtemos a lista de arquivos disponíveis na rede?
        # R: Solicitamos ao tracker via ``list_files`` e ele devolve os metadados
        #    de todos os arquivos anunciados.
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

        # P: Qual comando permite consultar as informações do próprio peer no
        #    tracker?
        # R: ``get_peer`` retorna os dados de login associados ao par
        #    identificado por IP e porta.
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

        # P: Como visualizar todos os peers que estão conectados ao tracker?
        # R: O comando ``get_all_peer`` retorna uma lista com endereço e horário
        #    de login de cada usuário ativo, permitindo diagnósticos da rede.
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
    """Realiza um envio simples usando um socket UDP fornecido.

    Utilizado principalmente no cadastro de usuários, antes que o peer tenha um
    socket permanente configurado. Ao separar esta rotina evitamos repetição de
    código no fluxo principal.
    """

    # P: Por que temos uma função separada para uso de sockets temporários?
    # R: Durante o registro ainda não possuímos um socket persistente. Esta
    #    função simplifica o envio de mensagens isoladas e o tratamento de timeout.
    try:
        # Envio e recebimento seguem o mesmo padrão do socket principal
        sock.sendto(json.dumps(data).encode(), (TRACKER_HOST, TRACKER_PORT))
        response, _ = sock.recvfrom(4096)
        return json.loads(response.decode())
    except socket.timeout:
        # Caso não haja retorno no tempo previsto
        return {"status": False, "message": "Tracker não respondeu"}

if __name__ == "__main__":
    main()
