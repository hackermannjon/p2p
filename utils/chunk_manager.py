import os
import hashlib

# Define um tamanho de chunk padrão (1MB). Pode ser ajustado.
CHUNK_SIZE = 1024 * 1024 

def split_file_into_chunks(file_path):
    """
    Divide um arquivo em chunks, salva-os em uma subpasta e retorna o hash do arquivo
    completo e uma lista ordenada com o hash de cada chunk.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

    file_name = os.path.basename(file_path)
    # Cria uma pasta para armazenar os chunks do arquivo, ex: 'shared/meuarquivo.pdf_chunks/'
    chunks_dir = os.path.join(os.path.dirname(file_path), f"{file_name}_chunks")
    os.makedirs(chunks_dir, exist_ok=True)

    chunk_hashes = []
    file_hash_obj = hashlib.sha256()
    
    with open(file_path, 'rb') as f:
        chunk_index = 0
        while True:
            chunk_data = f.read(CHUNK_SIZE)
            if not chunk_data:
                break
            
            # Calcula o hash do chunk e adiciona à lista
            chunk_hash = hashlib.sha256(chunk_data).hexdigest()
            chunk_hashes.append(chunk_hash)
            
            # Atualiza o hash do arquivo completo
            file_hash_obj.update(chunk_data)

            # Salva o chunk em um arquivo separado
            chunk_file_path = os.path.join(chunks_dir, f"chunk_{chunk_index}")
            with open(chunk_file_path, 'wb') as chunk_f:
                chunk_f.write(chunk_data)
            
            chunk_index += 1

    return file_hash_obj.hexdigest(), chunk_hashes

def reassemble_chunks(chunks_dir, output_file, total_chunks):
    """
    Reconstrói o arquivo original a partir de uma pasta de chunks.
    """
    # Garante que o diretório de saída exista
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'wb') as f_out:
        for i in range(total_chunks):
            chunk_path = os.path.join(chunks_dir, f"chunk_{i}")
            if not os.path.exists(chunk_path):
                raise FileNotFoundError(f"Chunk ausente para reconstrução: {chunk_path}")
            
            with open(chunk_path, 'rb') as f_in:
                f_out.write(f_in.read())

    print(f"Arquivo '{output_file}' reconstruído com sucesso a partir de {total_chunks} chunks.")