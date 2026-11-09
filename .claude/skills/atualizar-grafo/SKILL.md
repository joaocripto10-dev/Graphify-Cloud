---
name: atualizar-grafo
description: Verifica a configuração do Graphify e planeja atualizações pontuais e seguras do grafo.
disable-model-invocation: true
---

Escopo: $ARGUMENTS

1. Verifique a instalação `graphify --help`, o estado do repositório e o diretório `graphify-out/`.
2. Revise arquivos/pastas a excluir da indexação e os riscos de enviar documentos para modelos externos.
3. Se ainda não houver grafo, recomende a skill oficial `/graphify .`; não presuma que foi executada.
4. Se houver grafo e o usuário tiver aprovado a atualização, execute `graphify update .` a partir da raiz.
5. Valide `GRAPH_REPORT.md` e `graph.json` **se existirem** e faça consultas direcionadas.
6. Relate comandos efetivamente executados, saída observada, alertas e caminhos dos arquivos.
