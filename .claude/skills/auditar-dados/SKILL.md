---
name: auditar-dados
description: Executa revisão independente de KPIs, SQL, pipeline, integridade e evidências.
disable-model-invocation: true
---

Objetivo: $ARGUMENTS

1. Convocar o `auditor-independente` com contexto limitado e critérios explícitos.
2. Validar origem das fontes, filtros, versões, granularidades, cálculos e reconciliações.
3. Quando seguro, reproduzir testes não destrutivos; não acessar produção nem escrever em bases reais.
4. Reportar **APROVADO / PENDENTE / REPROVADO**, justificando com evidências localizáveis.
5. Listar bloqueios e correções exigidas. Não certificar funcionalidades que não foram verificadas.
