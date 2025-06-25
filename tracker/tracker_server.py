"""Servidor centralizado para orquestração da rede P2P.

Ele recebe requisições via UDP dos peers, gerencia usuários logados e mantém
um índice de quais arquivos estão disponíveis em cada nó. Por ser uma
implementação didática, todas as estruturas de dados residem em memória.
"""

import socket      # Módulo para comunicação em rede via sockets.
import threading   # Permite lidar com várias conexões simultâneas.
import json        # Serialização das mensagens trocadas com os peers.
import datetime    # Utilizado para registrar o momento do login.
from auth_manager import register_user, authenticate_user, log

files_db = {}     # filename -> {"size": int, "hash": str, "peers": [(ip, port)]}
active_peers = {} # (ip, port) -> { username, login_time }

HOST, PORT = 'localhost', 9000

def handle_request(data: bytes, addr: tuple[str, int], server: socket.socket) -> None:
    """Processa uma única requisição UDP enviada por um peer.

    Cada datagrama recebido é tratado isoladamente nesta função. Dependendo do
    valor de ``action`` diferentes operações são executadas, como cadastro,
    login e anúncio de arquivos.
    """

    try:
        # Decodificamos o JSON recebido do peer
        request = json.loads(data.decode())
        action = request.get("action")
        response = {}

        ip, port = addr
        # ``peer_key`` identifica unicamente um peer pelo IP e porta anunciada
        peer_key = (ip, request.get("port", port))

        log(f"Requisição '{action}' recebida de {ip}:{port}", "INFO")

        if action == "register":
            ok, msg = register_user(request['username'], request['password'])
            log(f"Registro de usuário '{request['username']}': {msg}", "INFO")
            response = {"status": ok, "message": msg}

        elif action == "login":
            # P: Como o tracker autentica um peer que deseja se conectar?
            # R: Verificamos usuário e senha usando ``authenticate_user`` e, em
            #    caso positivo, armazenamos o horário de login no dicionário
            #    ``active_peers``.
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
            # P: De que maneira um peer informa que possui arquivos para compartilhar?
            # R: Ele envia uma lista de arquivos (nome, tamanho e hash) para que o
            #    tracker registre em ``files_db`` quem são os distribuidores de cada
            #    recurso.
            files = request.get("files", [])
            for f in files:
                entry = files_db.setdefault(f['name'], {
                    "size": f['size'],
                    "hash": f['hash'],
                    "peers": []
                })
                if peer_key not in entry['peers']:
                    entry['peers'].append(peer_key)
                    log(f"Peer {peer_key} anunciou arquivo '{f['name']}'", "INFO")
            response = {"status": True, "message": "Arquivos registrados."}

        elif action == "list_files":
            # P: Como o peer descobre quem possui determinado arquivo?
            # R: O tracker mantém ``files_db`` com todos os anúncios e retorna
            #    para o solicitante uma lista com tamanho, hash e quais peers
            #    possuem cada item.
            log(f"Peer {peer_key} requisitou a lista de arquivos", "INFO")
            serializable_db = {}
            for fname, meta in files_db.items():
                serializable_db[fname] = {
                    "size": meta["size"],
                    "hash": meta["hash"],
                    "peers": [f"{ip}:{pt}" for ip, pt in meta["peers"]]
                }
            response = {"files": serializable_db}

        elif action == "get_peer":
            # P: Qual a finalidade desta ação?
            # R: Permite ao peer recuperar seus próprios dados de login
            #    armazenados no tracker, útil para conferência e depuração.
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
            # P: Por que precisamos da lista completa de peers?
            # R: Algumas operações, como escolha de fontes para download, podem
            #    requerer conhecer todos os participantes online. O tracker
            #    devolve então um resumo de ``active_peers``.
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
        # Qualquer falha inesperada na manipulação da mensagem cai aqui.
        log(f"Erro ao processar requisição de {addr}: {e}", "ERROR")
        response = {"status": False, "error": str(e)}

    # Enviamos a resposta (mesmo em caso de erro) para que o peer saiba o
    # resultado da sua solicitação
    server.sendto(json.dumps(response).encode(), addr)

def start_tracker() -> None:
    """Laço principal do servidor UDP.

    Cria o socket, associa a porta configurada e passa a aguardar datagramas.
    Cada pacote recebido gera uma thread de atendimento para não bloquear novas
    conexões.
    """

    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind((HOST, PORT))
    log(f"Tracker (UDP) iniciado em {HOST}:{PORT}", "INFO")

    # P: Como o tracker consegue lidar com vários peers se conectando ao mesmo
    #    tempo sem travar?
    # R: Cada datagrama recebido é processado em uma nova thread, permitindo que
    #    o servidor continue escutando a próxima requisição imediatamente.
    try:
        while True:
            data, addr = server.recvfrom(4096)
            # Para cada datagrama criamos uma nova thread que executará
            # ``handle_request``. Esse design simples evita que o tracker pare de
            # responder enquanto processa outra requisição.
            thread = threading.Thread(target=handle_request, args=(data, addr, server))
            thread.daemon = True
            thread.start()
    except KeyboardInterrupt:
        # Permite encerrar o servidor com Ctrl+C sem mostrar traceback
        print("\n[*] Encerrando o tracker...")
    except Exception as e:
        # Qualquer erro inesperado na etapa de escuta é reportado aqui
        print(f"[!] Erro: {e}")
    finally:
        # Garantimos que o socket seja fechado ao sair
        server.close()

if __name__ == "__main__":
    start_tracker()
