import subprocess
from utils.config import detect_local_ip


def main():
    ip = detect_local_ip()
    subprocess.call(['python3', 'peer/peer_client.py', '--host', ip])


if __name__ == '__main__':
    main()
