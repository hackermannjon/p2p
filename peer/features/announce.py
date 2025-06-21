# peer/features/announce.py
import os
from utils.chunk_manager import split_file_into_chunks
from utils.logger import log
from .network import send_to_tracker

SHARED_FOLDER = 'shared'

def announce_files(peer_port, username, peer_socket):
    """
    Prepara e anuncia arquivos da pasta 'shared' para o tracker.
    Retorna um dicionário com os metadados dos arquivos locais.
    """
    os.makedirs(SHARED_FOLDER, exist_ok=True)
    files_to_announce = []
    local_files_metadata = {}

    for filename in os.listdir(SHARED_FOLDER):
        # Ignora as pastas de chunks que criamos
        if os.path.isdir(os.path.join(SHARED_FOLDER, filename)):
            continue
        
        file_path = os.path.join(SHARED_FOLDER, filename)
        file_size = os.path.getsize(file_path)

        log(f"Processando arquivo '{filename}' para anunciar...", "INFO")
        file_hash, chunk_hashes = split_file_into_chunks(file_path)

        # Salva metadados localmente
        local_files_metadata[filename] = { "file_hash": file_hash, "chunk_hashes": chunk_hashes }
        
        files_to_announce.append({
            "name": filename,
            "size": file_size,
            "hash": file_hash,
            "chunk_hashes": chunk_hashes
        })

    if not files_to_announce:
        log("Nenhum arquivo encontrado na pasta 'shared' para anunciar.", "WARNING")
        return local_files_metadata

    res = send_to_tracker({
        "action": "announce",
        "port": peer_port,
        "username": username,
        "files": files_to_announce
    }, peer_socket)
    
    if res and res.get('status'):
        log("Arquivos anunciados com sucesso!", "SUCCESS")
    else:
        log(f"Falha ao anunciar arquivos: {res.get('message')}", "ERROR")

    return local_files_metadata
