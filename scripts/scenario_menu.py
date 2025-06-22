import subprocess

MENU = """
Selecione o cenario:
1. Iniciar tracker e primeiro peer (host)
2. Iniciar peer adicional
3. Iniciar somente tracker
0. Sair
"""


def main():
    while True:
        choice = input(MENU + '> ')
        if choice == '1':
            subprocess.call(['python3', 'scripts/start_tracker_and_peer.py'])
        elif choice == '2':
            subprocess.call(['python3', 'scripts/start_peer.py'])
        elif choice == '3':
            subprocess.call(['python3', 'tracker/tracker_server.py'])
        elif choice == '0':
            break
        else:
            print('Opcao invalida.')


if __name__ == '__main__':
    main()
