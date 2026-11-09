# Workflow operacional multiagente

1. **Entrada:** pergunta de negócio, escopo, período, sistemas, forma de acesso e restrições.
2. **Reconhecimento:** principal + `arquiteto-solucoes` mapeiam repositório e Graphify. Sem gravações nesta etapa.
3. **Inventário:** `engenheiro-dados` enumera fontes, granularidades, chaves e caminho de ingestão.
4. **Qualidade:** `qualidade-dados` cria perfil da base e matriz de exceções, preferencialmente sem alterar registros.
5. **Proposta:** principal aprova contratos, arquitetura, critérios de aceite e alterações antes da implementação.
6. **Implementação:** `engenheiro-dados` / `desenvolvedor-sistemas`, com tarefas de escrita não concorrentes.
7. **Análise:** `analista-negocios` define métricas; `especialista-bi` apresenta painéis, sempre identificando cobertura dos dados.
8. **Auditoria:** `auditor-independente` reproduz cálculos e revisa evidências sem editar código.
9. **Fechamento:** principal consolida artefatos, documentação, testes, riscos e próximos passos.

## Contrato de retorno de um subagente

- **Demanda:** pergunta e escopo.
- **Fontes consultadas:** caminhos reais, período e versão.
- **Constatações:** fatos com evidência e localização.
- **Inferências:** hipóteses e incertezas, separadas das constatações.
- **Mudanças:** arquivos alterados (quando autorizado).
- **Validação:** testes executados e resultados (incluindo falhas).
- **Pendências e recomendação:** próximas decisões e bloqueios.

## Política de execução

- Nenhuma consulta SQL de escrita em produção sem autorização explícita.
- Nenhuma alteração concorrente no mesmo arquivo.
- Nenhum dataset bruto é incluído em prompts, logs de agente ou memória persistente.
- O Graphify complementa a descoberta de dependências; a verdade operacional é determinada por fontes identificáveis e testes de reconciliação.
