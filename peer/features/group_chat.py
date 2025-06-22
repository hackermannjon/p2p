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


def start_moderator_room(room_name):
    rooms[room_name] = {
        'members': {},
        'banned': set(),
        'log_file': os.path.join(LOG_DIR, f"{room_name}.log")
    }


def accept_member(conn, room_name, member_username):
    info = rooms.get(room_name)
    if not info:
        conn.close()
        return
    if member_username in info.get('banned', set()):
        conn.sendall(b'Voce foi banido desta sala.\n')
        conn.close()
        return

    members = info['members']
    members[member_username] = conn
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
    threading.Thread(target=_member_session, args=(conn, room_name, member_username), daemon=True).start()


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
                start_moderator_room(room)
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
            if is_moderator and msg.startswith('/ban '):
                target = msg.split(' ', 1)[1]
                info = rooms.get(room_name)
                if info and target in info['members']:
                    ban_conn = info['members'].pop(target)
                    info['banned'].add(target)
                    ban_conn.sendall(b'Voce foi expulso pelo moderador.\n')
                    ban_conn.close()
                    broadcast(room_name, f'{target} foi expulso da sala.')
                    send_to_tracker({'action': 'room_member_update', 'room_name': room_name, 'username': target, 'event': 'leave'})
                continue
            conn.sendall(msg.encode())
    except KeyboardInterrupt:
        pass
    conn.close()
