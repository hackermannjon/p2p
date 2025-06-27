from utils.logger import log
from .network import send_to_tracker

def list_network_files(peer_port, username):
    res = send_to_tracker({"action": "list_files", "port": peer_port, "username": username})
    if res and res.get('files'):
        network_files_db = res['files']
        log("Arquivos disponíveis na rede:", "INFO")
        if not network_files_db:
            print("Nenhum arquivo encontrado.")
            return {}

        for name, meta in network_files_db.items():
            peer_count = len(meta['peers'])
            best_tier = meta['peers'][0]['tier'] if peer_count > 0 else 'bronze'
            print(f"- {name} (Tamanho: {meta['size']} B, Peers: {peer_count}, Melhor Tier: {best_tier})")
        return network_files_db
    else:
        log("Não foi possível listar os arquivos.", "ERROR")
        return {}

