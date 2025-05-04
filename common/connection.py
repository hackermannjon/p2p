import socket
from common.protocol import parse_message, create_message

def send_message(host, port, action, data):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, port))
        msg = create_message(action, data)
        s.sendall(msg.encode())
        response = s.recv(4096).decode()
        return parse_message(response)
