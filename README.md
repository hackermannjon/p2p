# Sistema P2P Simplificado

Projeto para a disciplina CIC0236 - Teleinformática e Redes 2.

Funcionalidades:

-   Comunicação entre peers
-   Compartilhamento de arquivos
-   Múltiplas conexões paralelas
-   Validação de dados por hash
-   Mecanismo de incentivo

### Requirements

socket
threading
json
hashlib
os
time
datetime
logging

relatorio 3: Entrega 3 – Comunicação via Chat, Mecanismo de Incentivo e Análise de Desempenho
Objetivo: Adicionar funcionalidades de interação e inteligência ao sistema, promovendo colaboração entre peers e mensurando o desempenho da rede. Consolidação em relatório e demais ajustes e considerações da tarefa anterior (Entrega 2)

Componentes:

Chat entre peers (mensagens diretas via socket).
Mecanismo de incentivo baseado em:
Volume de dados enviados.
Tempo conectado.
Número de respostas bem-sucedidas.
Alteração dinâmica do comportamento do sistema:
Mais conexões ou maior largura de banda para peers com pontuação maior.
Coleta de métricas de desempenho:
Tempo de download com e sem múltiplas conexões.
Efeito do mecanismo de incentivo.
Verificação de integridade dos arquivos.

Saídas esperadas:
Sistema completo, com chat funcional e incentivo atuando sobre o comportamento da rede.
Análise comparativa de desempenho (vide abaixo)
Relatório final contendo:
Arquitetura completa.
Métrica de incentivo.
Resultados dos testes com gráficos e conclusões.

============== 17/06/2025 ====== INICIO

DESAFIO/BONUS:

Salas Privadas com Moderação e Histórico Persistente

Implementação de salas de chat privadas com as seguintes funcionalidades:

Gerenciamento de Salas:
-Criação/exclusão de salas privadas por um peer moderador.
-Inclusão e exclusão de peers na sala
-Capacidade de listar as salas existentes e membros ativos em cada uma.
-Controle de acesso: apenas peers autorizados/convidados podem ingressar e interagir.

Comunicação em Sala (Broadcast):
-Mensagens enviadas por qualquer membro devem ser distribuídas para todos os demais membros da sala (modelo broadcast).
-Cada mensagem deve incluir remetente, timestamp e nome da sala.

Histórico de Mensagens Persistente:
-As mensagens trocadas na sala devem ser armazenadas em um log local persistente (ex: arquivo .txt ou estrutura JSON).
-Quando um peer ingressa em uma sala, ele deve ser capaz de:
-- Acessar as mensagens anteriores daquela sala.
-- Receber novas mensagens em tempo real a partir do momento de entrada.
-- O moderador pode definir o tamanho máximo do histórico (ex: Por TimeStamp ou M mensagens).
-- Pode ser implementado centralmente (armazenado no moderador) ou distribuído (replicado por todos os membros da sala, conforme arquitetura adotada).

Segurança e Consistência:

-   Prever mecanismos simples para garantir a integridade e autenticidade das mensagens no histórico (ex: hashes, timestamps).
-   Evitar duplicação de mensagens no histórico para peers que se reconectam ou recebem mensagens retransmitidas.
    BONUS: A equipe que implementar corretamente terá adicionado 0,5 ponto na média final das provas.
    ============== 17/06/2025 ====== FIM

Análise de Desempenho

1. Testes com Diferentes Conexões

Meça o tempo necessário para transferir um arquivo com 2, 3 e 4 conexões paralelas (utilize arquivos com tamanho significativo para poder mensurar os tempos, ex: 1, 10, 100, 1000 Mb). Repita o teste ao menos 10 vezes, com diferentes peers e calcule a média, desvio padrão entre os testes
Avalie a eficiência do mecanismo de checksum para identificar e corrigir erros. 2. Comparação com Transferência Única

Compare a taxa de transferência e a latência entre conexões paralelas e uma conexão única.

relatorio final: Ir para o conteúdo principal
Aprender3
Página inicial
Painel
Meus cursos
10
TR2_2025
Trabalho Final - 3a Entrega FINAL

Trabalho Final - 3a Entrega FINAL
Condições de conclusão
Aberto: segunda-feira, 9 jun. 2025, 00:00
Vencimento: quarta-feira, 25 jun. 2025, 23:59
Entrega 3 – Comunicação via Chat, Mecanismo de Incentivo e Análise de Desempenho
Objetivo: Adicionar funcionalidades de interação e inteligência ao sistema, promovendo colaboração entre peers e mensurando o desempenho da rede. Consolidação em relatório e demais ajustes e considerações da tarefa anterior (Entrega 2)

Componentes:

Chat entre peers (mensagens diretas via socket).
Mecanismo de incentivo baseado em:
Volume de dados enviados.
Tempo conectado.
Número de respostas bem-sucedidas.
Alteração dinâmica do comportamento do sistema:
Mais conexões ou maior largura de banda para peers com pontuação maior.
Coleta de métricas de desempenho:
Tempo de download com e sem múltiplas conexões.
Efeito do mecanismo de incentivo.
Verificação de integridade dos arquivos.

Saídas esperadas:
Sistema completo, com chat funcional e incentivo atuando sobre o comportamento da rede.
Análise comparativa de desempenho (vide abaixo)
Relatório final contendo:
Arquitetura completa.
Métrica de incentivo.
Resultados dos testes com gráficos e conclusões.

============== 17/06/2025 ====== INICIO

DESAFIO/BONUS:

Salas Privadas com Moderação e Histórico Persistente

Implementação de salas de chat privadas com as seguintes funcionalidades:

Gerenciamento de Salas:
-Criação/exclusão de salas privadas por um peer moderador.
-Inclusão e exclusão de peers na sala
-Capacidade de listar as salas existentes e membros ativos em cada uma.
-Controle de acesso: apenas peers autorizados/convidados podem ingressar e interagir.

Comunicação em Sala (Broadcast):
-Mensagens enviadas por qualquer membro devem ser distribuídas para todos os demais membros da sala (modelo broadcast).
-Cada mensagem deve incluir remetente, timestamp e nome da sala.

Histórico de Mensagens Persistente:
-As mensagens trocadas na sala devem ser armazenadas em um log local persistente (ex: arquivo .txt ou estrutura JSON).
-Quando um peer ingressa em uma sala, ele deve ser capaz de:
-- Acessar as mensagens anteriores daquela sala.
-- Receber novas mensagens em tempo real a partir do momento de entrada.
-- O moderador pode definir o tamanho máximo do histórico (ex: Por TimeStamp ou M mensagens).
-- Pode ser implementado centralmente (armazenado no moderador) ou distribuído (replicado por todos os membros da sala, conforme arquitetura adotada).

Segurança e Consistência:

-   Prever mecanismos simples para garantir a integridade e autenticidade das mensagens no histórico (ex: hashes, timestamps).
-   Evitar duplicação de mensagens no histórico para peers que se reconectam ou recebem mensagens retransmitidas.
    BONUS: A equipe que implementar corretamente terá adicionado 0,5 ponto na média final das provas.
    ============== 17/06/2025 ====== FIM

Análise de Desempenho

1. Testes com Diferentes Conexões

Meça o tempo necessário para transferir um arquivo com 2, 3 e 4 conexões paralelas (utilize arquivos com tamanho significativo para poder mensurar os tempos, ex: 1, 10, 100, 1000 Mb). Repita o teste ao menos 10 vezes, com diferentes peers e calcule a média, desvio padrão entre os testes
Avalie a eficiência do mecanismo de checksum para identificar e corrigir erros. 2. Comparação com Transferência Única

Compare a taxa de transferência e a latência entre conexões paralelas e uma conexão única.

Status de envio
Status de envio Nenhum envio foi feito ainda
Status da avaliação Não há notas
Tempo restante 3 dias 12 horas restando
Última modificação -
Comentários sobre o envio
Comentários (0)
Conheça os serviços do CEAD:
Banco de elementos gráficos
Cursos de capacitação
Ferramentas Digitais
Palestras e Oficinas

Baixe o moodle versão mobile
Endereço do CEAD:
Campus Darcy Ribeiro, Gleba A, 70910-900, Brasília - DF, Brasil.

Email: cead@unb.br

Telefone: (61) 3107-4297
Redes sociais do CEAD:

Copyright © 2023 Universidade de Brasília. Todos os direitos reservados. Melhor visualizado nos navegadores Google Chrome e Mozilla Firefox

©Tema Trema
