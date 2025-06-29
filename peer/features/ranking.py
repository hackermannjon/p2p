from utils.logger import log
from .network import send_to_tracker

def show_scores(peer_port, username):
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
            tier = stats.get('tier', 'bronze')
            print(f"{i+1}. {uname}: Pontuação = {score} Tier={tier} (Uploads: {uploads}, Uptime: {uptime_min:.1f} min)")
        print("------------------------------")
    else:
        log(f"Não foi possível buscar o ranking: {res.get('message')}", "ERROR")

