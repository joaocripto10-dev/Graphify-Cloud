---
name: diagnosticar-dados
description: Inventaria o projeto e as bases de forma não destrutiva antes da implantação de engenharia de dados e BI.
disable-model-invocation: true
---

Faça um diagnóstico **somente leitura**, com foco em: $ARGUMENTS

1. Leia `CLAUDE.md`, `docs/CONTEXTO_NEGOCIO.md`, `docs/CONTRATOS_DADOS.md`, `docs/WORKFLOW.md`.
2. Confira ambiente e estado do Git sem gravar alterações.
3. Use o Graphify para navegar nas dependências se o grafo existir; se não existir, registre a pendência e indique `/graphify .` após revisão de privacidade.
4. Delegue `arquiteto-solucoes`, `engenheiro-dados` e `qualidade-dados` quando couber. O diagnóstico é somente leitura.
5. Identifique bases presentes, formatos, donos, granularidades, qualidade e indicadores viáveis.
6. Entregue diagnóstico, riscos, alternativas e plano incremental com critérios de aceite. **Pare antes da implementação**.
