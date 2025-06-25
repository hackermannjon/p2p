"""Manipulação de arquivos em pedaços (chunks) para o sistema P2P."""

import os
import hashlib  # Funções de hash usadas para verificar integridade dos dados.

# Define um tamanho de chunk padrao (1MB). Pode ser ajustado.
CHUNK_SIZE = 1024 * 1024


def split_file_into_chunks(file_path):
    """Divide um arquivo em chunks e retorna seu hash e dos chunks."""
    # P: Por que dividir o arquivo em pedaços?
    # R: Em um sistema P2P é mais eficiente transferir pequenos pedaços
    #    paralelamente de vários peers. Cada chunk possui um hash para garantir
    #    que não houve corrupção durante a transferência.
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Arquivo nao encontrado: {file_path}")

    file_name = os.path.basename(file_path)
    chunks_dir = os.path.join(os.path.dirname(file_path), f"{file_name}_chunks")
    # Cada arquivo recebe uma pasta com seus chunks, facilitando a organização
    os.makedirs(chunks_dir, exist_ok=True)

    chunk_hashes = []
    file_hash_obj = hashlib.sha256()  # Acumulador para o hash do arquivo inteiro

    with open(file_path, 'rb') as f:
        chunk_index = 0
        while True:
            chunk_data = f.read(CHUNK_SIZE)
            if not chunk_data:
                break
            chunk_hash = hashlib.sha256(chunk_data).hexdigest()
            chunk_hashes.append(chunk_hash)
            file_hash_obj.update(chunk_data)
            chunk_file_path = os.path.join(chunks_dir, f"chunk_{chunk_index}")
            with open(chunk_file_path, 'wb') as chunk_f:
                # Armazena cada pedaço em disco para que outros peers possam
                # solicitá-lo individualmente
                chunk_f.write(chunk_data)
            chunk_index += 1

    return file_hash_obj.hexdigest(), chunk_hashes


def reassemble_chunks(chunks_dir, output_file, total_chunks):
    """Reconstrói o arquivo original a partir dos chunks."""
    # P: Como temos certeza de que o arquivo final é idêntico ao original?
    # R: O reagrupamento ocorre seguindo a ordem dos chunks e, após a
    #    reconstrução, normalmente o hash do arquivo é comparado com o hash
    #    informado no metadata.
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'wb') as f_out:
        for i in range(total_chunks):
            chunk_path = os.path.join(chunks_dir, f"chunk_{i}")
            if not os.path.exists(chunk_path):
                raise FileNotFoundError(f"Chunk ausente: {chunk_path}")
            with open(chunk_path, 'rb') as f_in:
                f_out.write(f_in.read())
    print(f"Arquivo '{output_file}' reconstruido com sucesso a partir de {total_chunks} chunks.")
    # Mensagem meramente informativa para o usuário acompanhar o progresso

