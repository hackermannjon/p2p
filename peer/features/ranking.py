# peer/features/ranking.py
"""Visualização de pontuação (mecanismo de incentivo)."""

from utils.logger import log
from .network import send_to_tracker

# P: Qual o objetivo do mecanismo de pontuação?
# R: Premiar peers que enviam dados e permanecem online, fornecendo-lhes maior
#    prioridade no download dos arquivos e incentivando colaboração.

def show_scores(peer_port, username):
    """Busca e exibe o ranking de pontuação dos peers."""
    # P: Por que exibir o ranking localmente se os dados estão no tracker?
    # R: A função consulta o tracker e mostra os usuários com melhor score,
    #    incentivando a colaboração ao tornar a pontuação visível a todos.
    res = send_to_tracker({"action": "get_scores", "port": peer_port, "username": username})
    if res and res.get('status'):
        scores = res.get('scores', [])
        print("\n--- Ranking de Colaboração ---")
        if not scores:
            print("Nenhuma pontuação registrada ainda.")
            return
        
        for i, (uname, stats) in enumerate(scores):
            uptime_min = stats.get('uptime_seconds', 0) / 60
            uploads = stats.get('uploads', 0)
            score = stats.get('score', 0)
            print(f"{i+1}. {uname}: Pontuação = {score} (Uploads: {uploads}, Uptime: {uptime_min:.1f} min)")
        print("------------------------------")
    else:
        log(f"Não foi possível buscar o ranking: {res.get('message')}", "ERROR")

