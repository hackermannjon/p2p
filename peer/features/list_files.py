# peer/features/list_files.py
"""Consulta ao tracker para listar arquivos disponíveis."""

from utils.logger import log
from .network import send_to_tracker

# P: Por que esta funcionalidade é importante para o usuário?
# R: Sem esta listagem, o peer não sabe quais arquivos estão disponíveis na
#    rede e em quais peers encontrá-los. Este passo é essencial antes de iniciar
#    qualquer download.

def list_network_files(peer_port, username):
    """
    Busca e exibe os arquivos disponíveis na rede.
    Retorna um dicionário com os arquivos da rede para uso no download.
    """
    res = send_to_tracker({"action": "list_files", "port": peer_port, "username": username})
    # P: O tracker já filtra os peers por pontuação?
    # R: Sim. A lista de peers de cada arquivo já chega ordenada pelo tracker,
    #    permitindo iniciar o download escolhendo quem possui maior score.
    if res and res.get('files'):
        network_files_db = res['files']
        log("Arquivos disponíveis na rede:", "INFO")
        if not network_files_db:
            print("Nenhum arquivo encontrado.")
            return {}

        for name, meta in network_files_db.items():
            peer_count = len(meta['peers'])
            # A lista de peers já vem ordenada pelo tracker
            best_score = meta['peers'][0]['score'] if peer_count > 0 else 0
            print(f"- {name} (Tamanho: {meta['size']} B, Peers: {peer_count}, Melhor Pontuação: {best_score})")
        # O retorno é utilizado pelo menu principal para iniciar downloads
        return network_files_db
    else:
        log("Não foi possível listar os arquivos.", "ERROR")
        return {}

