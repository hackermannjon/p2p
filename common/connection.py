import socket
from common.protocol import parse_message, create_message


def send_message(host, port, action, data):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect((host, port))
            msg = create_message(action, data)
            s.sendall(msg.encode())
            response = s.recv(4096).decode()
            return parse_message(response)
    except socket.timeout:
        return {"status": False, "message": "Timeout na conexao com o servidor"}
    except ConnectionRefusedError:
        return {"status": False, "message": "Nao foi possivel conectar ao servidor"}
    except Exception as e:
        return {"status": False, "message": f"Erro na comunicacao: {str(e)}"}

