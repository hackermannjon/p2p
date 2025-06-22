# Guia de Uso do Sistema P2P

Este documento resume os comandos de terminal para executar o tracker e os peers e testar as funcionalidades principais.

## 1. Execucao Automatizada

Use o script `scripts/scenario_menu.py` para iniciar o tracker e os peers. O IP local e a porta do tracker sao detectados automaticamente e gravados em `config.json`.

```bash
python3 scripts/scenario_menu.py
```

## 2. Iniciar o Tracker manualmente

Execute em um terminal:

```bash
python3 tracker/tracker_server.py
```

O tracker escutará no IP e porta definidos em `config.json`.

## 3. Iniciar um Peer manualmente

Em outro terminal, rode:

```bash
python3 peer/peer_client.py --host <IP_LOCAL>
```

Substitua `<IP_LOCAL>` pelo endereço pelo qual outros peers irão se conectar (por padrão usa `0.0.0.0`).

## 4. Menu Inicial

Ao iniciar o peer, escolha:

1. **Registrar** – cria um usuário.
2. **Login** – autentica e inicia o servidor do peer.
3. **Sair** – encerra o programa.

## 5. Funcionalidades Após o Login

Com o usuário logado, o menu apresenta:

1. **Anunciar meus arquivos** – compartilha arquivos da pasta `shared/`.
2. **Listar arquivos na rede** – obtém a lista de arquivos disponíveis.
3. **Baixar arquivo** – baixa um arquivo listado.
4. **Ver Ranking de Colaboração** – mostra a pontuação de cada usuário.
5. **Chat com outro peer** – abre um chat 1‑para‑1 com um peer ativo.
6. **Salas de Chat (Grupo)** – permite criar, entrar e remover salas moderadas.
7. **Logout** – finaliza a sessão.

## 6. Chat em Grupo

Escolhendo a opção **6**, é exibido outro menu:

- **Listar salas** – consulta o tracker para ver salas existentes.
- **Criar sala** – cria uma sala e se torna moderador.
- **Entrar em sala** – conecta‑se a uma sala existente.
- **Remover sala** – apaga uma sala criada por você.
- **Voltar** – retorna ao menu principal.

O moderador mantém um log em `group_logs/<sala>.log` e envia o histórico aos novos membros.

## 7. Testando o Mecanismo de Incentivo

Ao enviar chunks para outros peers, seu score aumenta. Peers com score baixo têm o download limitado (throttling). Use a opção **Ver Ranking de Colaboração** para acompanhar sua pontuação durante os testes.

## 8. Encerramento

Pressione `Ctrl+C` no terminal para encerrar o tracker ou o peer a qualquer momento.


