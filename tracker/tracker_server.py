"""Servidor centralizador que mantém o estado da rede P2P."""

import socket
import threading
import json
import datetime
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from auth_manager import register_user, authenticate_user, log, users_db
from utils.config import TRACKER_HOST, TRACKER_PORT

files_db = {}
active_peers = {}
peer_scores = {}
chat_rooms = {}

STATE_FILE = os.path.join(os.path.dirname(__file__), 'tracker_state.json')
POPULATE_FILE = os.path.join(os.path.dirname(__file__), '..', 'populate', 'tracker_state.json')


def load_state():
    """Carrega o estado persistido do tracker."""

    source = None
    if os.path.exists(STATE_FILE) and os.path.getsize(STATE_FILE) > 2:
        source = STATE_FILE
    elif os.path.exists(POPULATE_FILE):
        source = POPULATE_FILE
    if source:
        with open(source, 'r') as f:
            data = json.load(f)
            users_db.update(data.get('users', {}))
            peer_scores.update(data.get('scores', {}))
            chat_rooms.update(data.get('rooms', {}))
        for info in chat_rooms.values():
            info['old'] = True
        for stats in peer_scores.values():
            score = calculate_score(stats)
            stats['score'] = score
            stats['tier'] = determine_tier(score)
        if source == POPULATE_FILE:
            save_state()


def save_state():
    data = {'users': users_db, 'scores': peer_scores, 'rooms': chat_rooms}
    with open(STATE_FILE, 'w') as f:
        json.dump(data, f)


HOST, PORT = TRACKER_HOST, TRACKER_PORT


def calculate_score(stats):
    score = (stats.get('uploads', 0)) + (stats.get('uptime_seconds', 0) * 0.01)
    return round(score, 2)


def determine_tier(score):
    """Converte a pontuação numérica em um nível de incentivo."""

    if score < 10:
        return 'bronze'
    if score < 20:
        return 'prata'
    if score < 30:
        return 'ouro'
    return 'diamante'


def initialize_peer_score(username):
    if username not in peer_scores:
        peer_scores[username] = {'uploads': 0, 'uptime_seconds': 0, 'score': 0, 'tier': 'bronze'}


def handle_request(conn, addr):
    """Processa a mensagem recebida de um peer."""

    try:
        data = conn.recv(4096)
        if not data:
            conn.close()
            return
        request = json.loads(data.decode())
        action = request.get('action')
        response = {}

        ip, port = addr
        peer_listening_port = request.get('port', port)
        peer_key = (ip, peer_listening_port)
        username = request.get('username')

        if action == 'register':
            ok, msg = register_user(request['username'], request['password'])
            if ok:
                initialize_peer_score(request['username'])
                save_state()
            response = {'status': ok, 'message': msg}

        elif action == 'login':
            ok = authenticate_user(request['username'], request['password'])
            if ok:
                initialize_peer_score(request['username'])
                active_peers[peer_key] = {'username': request['username'], 'login_time': datetime.datetime.now()}
                response = {'status': True, 'message': 'Login realizado.'}
            else:
                response = {'status': False, 'message': 'Credenciais inválidas.'}

        elif action == 'logout':
            if peer_key in active_peers:
                session_duration = datetime.datetime.now() - active_peers[peer_key]['login_time']
                uptime_seconds = int(session_duration.total_seconds())
                user_stats = peer_scores.get(username, {})
                user_stats['uptime_seconds'] = user_stats.get('uptime_seconds', 0) + uptime_seconds
                user_stats['score'] = calculate_score(user_stats)
                user_stats['tier'] = determine_tier(user_stats['score'])
                peer_scores[username] = user_stats
                save_state()
                del active_peers[peer_key]
                for file_meta in files_db.values():
                    if peer_key in file_meta['peers']:
                        file_meta['peers'].remove(peer_key)
                response = {'status': True, 'message': 'Logout realizado com sucesso.'}
            else:
                response = {'status': False, 'message': 'Peer não estava logado.'}

        elif action == 'announce':
            if peer_key not in active_peers:
                response = {'status': False, 'message': 'Ação não permitida. Faça login primeiro.'}
            else:
                files = request.get('files', [])
                for f in files:
                    entry = files_db.setdefault(f['name'], {
                        'size': f['size'],
                        'hash': f['hash'],
                        'chunk_hashes': f.get('chunk_hashes', []),
                        'peers': []
                    })
                    if peer_key not in entry['peers']:
                        entry['peers'].append(peer_key)
                response = {'status': True, 'message': 'Arquivos registrados.'}

        elif action == 'list_files':
            serializable_db = {}
            for fname, meta in files_db.items():
                peers_with_scores = []
                for ip_peer, port_peer in meta['peers']:
                    peer_info = active_peers.get((ip_peer, port_peer))
                    if peer_info:
                        uname = peer_info.get('username')
                        stats = peer_scores.get(uname, {})
                        score = stats.get('score', 0)
                        tier = stats.get('tier', 'bronze')
                        peers_with_scores.append({'peer': f'{ip_peer}:{port_peer}', 'score': score, 'tier': tier})
                peers_with_scores.sort(key=lambda x: x['score'], reverse=True)
                serializable_db[fname] = {
                    'size': meta['size'],
                    'hash': meta['hash'],
                    'chunk_hashes': meta['chunk_hashes'],
                    'peers': peers_with_scores
                }
            response = {'files': serializable_db}

        elif action == 'report_upload':
            if username and username in peer_scores:
                peer_scores[username]['uploads'] += 1
                peer_scores[username]['score'] = calculate_score(peer_scores[username])
                peer_scores[username]['tier'] = determine_tier(peer_scores[username]['score'])
                save_state()
                response = {'status': True}
            else:
                response = {'status': False, 'message': 'Usuário não encontrado para premiar.'}

        elif action == 'get_scores':
            sorted_scores = sorted(peer_scores.items(), key=lambda item: item[1]['score'], reverse=True)
            response = {'status': True, 'scores': sorted_scores}

        elif action == 'get_peer_score':
            target = request.get('target_username')
            stats = peer_scores.get(target, {})
            response = {'status': True, 'score': stats.get('score', 0), 'tier': stats.get('tier', 'bronze')}

        elif action == 'get_active_peers':
            peer_list = [{'username': v['username'], 'address': f'{k[0]}:{k[1]}'} for k, v in active_peers.items() if k != peer_key]
            response = {'status': True, 'peers': peer_list}

        elif action == 'create_room':
            room = request.get('room_name')
            if room in chat_rooms:
                response = {'status': False, 'message': 'Sala ja existe'}
            else:
                chat_rooms[room] = {
                    'moderator': username,
                    'address': f'{ip}:{peer_listening_port}',
                    'members': [],
                    'old': False
                }
                save_state()
                response = {'status': True}

        elif action == 'list_rooms':
            rooms_filtered = {r: info for r, info in chat_rooms.items() if not info.get('old')}
            response = {'status': True, 'rooms': rooms_filtered}

        elif action == 'delete_room':
            room = request.get('room_name')
            info = chat_rooms.get(room)
            if info and info.get('moderator') == username:
                del chat_rooms[room]
                save_state()
                response = {'status': True}
            else:
                response = {'status': False, 'message': 'Sala nao encontrada ou permissao negada'}

        elif action == 'room_member_update':
            room = request.get('room_name')
            member = request.get('username')
            event = request.get('event')
            info = chat_rooms.get(room)
            if info:
                members = info.setdefault('members', [])
                if event == 'join' and member not in members:
                    members.append(member)
                if event == 'leave' and member in members:
                    members.remove(member)
                save_state()
                response = {'status': True}
            else:
                response = {'status': False, 'message': 'Sala inexistente'}

        else:
            response = {'status': False, 'message': 'Ação desconhecida'}
    except Exception as e:
        log(f"Erro ao processar requisição de {addr}: {e}", "ERROR")
        response = {'status': False, 'error': str(e)}
    conn.sendall(json.dumps(response).encode())
    conn.close()


def start_tracker():
    """Loop principal do tracker, aceitando conexões TCP."""

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen(15)
    log(f"Tracker (TCP) iniciado em {HOST}:{PORT}", "INFO")
    try:
        while True:
            # Para cada nova conexão delegamos o processamento a uma thread,
            # permitindo que o tracker atenda múltiplos peers em paralelo.
            conn, addr = server.accept()
            thread = threading.Thread(target=handle_request, args=(conn, addr), daemon=True)
            thread.start()
    except KeyboardInterrupt:
        print("\n[*] Encerrando o tracker...")
    finally:
        server.close()


if __name__ == '__main__':
    import argparse
    from utils.config import set_tracker_address

    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default=HOST, help='Endereco para o tracker')
    parser.add_argument('--port', type=int, default=PORT, help='Porta do tracker')
    args = parser.parse_args()

    set_tracker_address(args.host, args.port)
    HOST, PORT = args.host, args.port
    load_state()
    start_tracker()
