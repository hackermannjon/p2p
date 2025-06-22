import json
import subprocess
import time
import os
from utils.config import CONFIG_PATH, detect_local_ip


def main():
    ip = detect_local_ip()
    port = 9000
    with open(CONFIG_PATH, 'w') as f:
        json.dump({'tracker_ip': ip, 'tracker_port': port}, f, indent=4)
    tracker_proc = subprocess.Popen(['python3', 'tracker/tracker_server.py'])
    time.sleep(1)
    try:
        subprocess.call(['python3', 'peer/peer_client.py', '--host', ip])
    finally:
        tracker_proc.terminate()
        tracker_proc.wait()


if __name__ == '__main__':
    main()
