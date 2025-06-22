import os
import json
import socket
import threading
from datetime import datetime
from utils.logger import log
from .network import send_to_tracker

rooms = {}
LOG_DIR = 'group_logs'
os.makedirs(LOG_DIR, exist_ok=True)


def _log_message(room, message):
    path = os.path.join(LOG_DIR, f"{room}.log")
    with open(path, 'a') as f:
        f.write(message + '\n')


def start_moderator_room(room_name, moderator):
    """Inicializa a estrutura de uma nova sala."""
    rooms[room_name] = {
        'members': {},
        'banned': set(),
        'pending': {},  # usuarios aguardando aprovacao
        'moderator': moderator,
        'log_file': os.path.join(LOG_DIR, f"{room_name}.log")
    }


def _finalize_join(room_name, member_username):
    """Move o usuario pendente para a lista de membros e inicia a sessao."""
    info = rooms.get(room_name)
    if not info:
        return
    entry = info.get('pending', {}).pop(member_username, None)
    if not entry:
        return
    conn = entry['conn']
    approved = entry['approved']
    entry['event'].set()
    if not approved:
        # Moderador negou a entrada
        info['banned'].add(member_username)
        try:
            conn.sendall(b'Voce foi banido desta sala.\n')
        except Exception:
            pass
        conn.close()
        return

    info['members'][member_username] = conn
    try:
        with open(info['log_file'], 'r') as f:
            for line in f:
                conn.sendall(line.encode())
    except FileNotFoundError:
        pass
    send_to_tracker({
        'action': 'room_member_update',
        'room_name': room_name,
        'username': member_username,
        'event': 'join'
    })
    broadcast(room_name, f'{member_username} entrou na sala.')
    threading.Thread(target=_member_session, args=(conn, room_name, member_username), daemon=True).start()


def approve_member(room_name, member_username):
    info = rooms.get(room_name)
    if not info:
        return
    entry = info.get('pending', {}).get(member_username)
    if entry:
        entry['approved'] = True
        _finalize_join(room_name, member_username)


def deny_member(room_name, member_username):
    info = rooms.get(room_name)
    if not info:
        return
    entry = info.get('pending', {}).get(member_username)
    if entry:
        entry['approved'] = False
        _finalize_join(room_name, member_username)


def accept_member(conn, room_name, member_username):
    info = rooms.get(room_name)
    if not info:
        conn.close()
        return
    if member_username in info.get('banned', set()):
        try:
            conn.sendall(b'Voce foi banido desta sala.\n')
        except Exception:
            pass
        conn.close()
        return

    # Moderador entra automaticamente
    if member_username == info.get('moderator'):
        info['members'][member_username] = conn
        send_to_tracker({
            'action': 'room_member_update',
            'room_name': room_name,
            'username': member_username,
            'event': 'join'
        })
        threading.Thread(target=_member_session, args=(conn, room_name, member_username), daemon=True).start()
        return

    # Solicita aprovacao do moderador
    entry = {'conn': conn, 'approved': False, 'event': threading.Event()}
    info.setdefault('pending', {})[member_username] = entry
    mod_conn = info['members'].get(info['moderator'])
    if mod_conn:
        try:
            mod_conn.sendall(f"[SOLICITACAO] {member_username} deseja entrar. Use /sim {member_username} ou /nao {member_username}\n".encode())
        except Exception:
            pass
    try:
        conn.sendall(b'Aguardando aprovacao do moderador...\n')
    except Exception:
        pass
    # Aguarda a resposta do moderador
    entry['event'].wait()
    return


def _member_session(conn, room_name, member_username):
    while True:
        try:
            data = conn.recv(1024)
            if not data:
                break
            msg = data.decode().strip()
            timestamp = datetime.now().strftime('%H:%M:%S')
            formatted = f"[{room_name}][{timestamp}] [{member_username}] {msg}"
            _log_message(room_name, formatted)
            broadcast(room_name, formatted, exclude=member_username)
        except Exception:
            break
    conn.close()
    rooms[room_name]['members'].pop(member_username, None)
    send_to_tracker({
        'action': 'room_member_update',
        'room_name': room_name,
        'username': member_username,
        'event': 'leave'
    })


def broadcast(room_name, message, exclude=None):
    for uname, c in list(rooms.get(room_name, {}).get('members', {}).items()):
        if uname == exclude:
            continue
        try:
            c.sendall((message + '\n').encode())
        except Exception:
            pass


def show_menu(peer_port, username):
    while True:
        print("\n--- Salas de Chat ---")
        print("1. Listar salas")
        print("2. Criar sala")
        print("3. Entrar em sala")
        print("4. Remover sala")
        print("0. Voltar")
        choice = input('> ')
        if choice == '1':
            res = send_to_tracker({'action': 'list_rooms', 'port': peer_port, 'username': username})
            rooms_list = res.get('rooms', {}) if res else {}
            if not rooms_list:
                print('Nenhuma sala disponível.')
            else:
                for r, info in rooms_list.items():
                    members = ','.join(info.get('members', []))
                    print(f"- {r} (moderador: {info['moderator']}) [membros: {members}]")
        elif choice == '2':
            room = input('Nome da sala: ')
            res = send_to_tracker({'action': 'create_room', 'room_name': room, 'port': peer_port, 'username': username})
            if res and res.get('status'):
                start_moderator_room(room, username)
                print('Sala criada.')
            else:
                log(res.get('message', 'Erro ao criar sala'), 'ERROR')
        elif choice == '3':
            room = input('Sala para entrar: ')
            res = send_to_tracker({'action': 'list_rooms', 'port': peer_port, 'username': username})
            info = res.get('rooms', {}).get(room) if res else None
            if not info:
                log('Sala não encontrada.', 'ERROR')
                continue
            addr_ip, addr_port = info['address'].split(':')
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((addr_ip, int(addr_port)))
            req = {'action': 'join_room', 'room_name': room, 'username': username}
            s.sendall(json.dumps(req).encode())
            _group_session(s, room, username, username == info.get('moderator'))
        elif choice == '4':
            room = input('Sala para remover: ')
            res = send_to_tracker({'action': 'delete_room', 'room_name': room, 'port': peer_port, 'username': username})
            if res and res.get('status'):
                rooms.pop(room, None)
                print('Sala removida.')
            else:
                log(res.get('message', 'Falha ao remover sala'), 'ERROR')
        else:
            break


def _group_session(conn, room_name, username, is_moderator=False):
    def recv_loop():
        while True:
            try:
                data = conn.recv(1024)
                if not data:
                    break
                print('\r' + data.decode().strip() + '\n> ', end='')
            except Exception:
                break
        print('\nConexao encerrada.')

    threading.Thread(target=recv_loop, daemon=True).start()
    try:
        while True:
            msg = input('> ')
            if msg == '/quit':
                break
            if is_moderator:
                if msg.startswith('/ban '):
                    target = msg.split(' ', 1)[1]
                    info = rooms.get(room_name)
                    if info and target == info.get('moderator'):
                        print('Nao e possivel banir o moderador.')
                        continue
                    if info and target in info.get('members', {}):
                        ban_conn = info['members'].pop(target)
                        info['banned'].add(target)
                        try:
                            ban_conn.sendall(b'Voce foi expulso pelo moderador.\n')
                        except Exception:
                            pass
                        ban_conn.close()
                        broadcast(room_name, f'{target} foi expulso da sala.')
                        send_to_tracker({'action': 'room_member_update', 'room_name': room_name, 'username': target, 'event': 'leave'})
                    continue
                if msg.startswith('/sim '):
                    target = msg.split(' ', 1)[1]
                    approve_member(room_name, target)
                    continue
                if msg.startswith('/nao '):
                    target = msg.split(' ', 1)[1]
                    deny_member(room_name, target)
                    continue
            try:
                conn.sendall(msg.encode())
            except Exception:
                break
    except KeyboardInterrupt:
        pass
    conn.close()
