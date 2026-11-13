# Dicionário de dados e KPIs

**Nunca inventar nomes de colunas ou fórmulas específicas de um ERP**. Registrar após inspeção da base de origem.

| KPI | Fórmula autorizada | Unidade | Grão | Janela | Fonte | Exclusões | Status |
|---|---|---|---|---|---|---|---|
| Faturamento bruto | A validar | R$ | Unidade/período | A validar | A mapear | A validar | Pendente |
| Quantidade vendida | A validar | Unidade física | Produto/unidade/período | A validar | A mapear | A validar | Pendente |
| Margem bruta (%) | A validar | % | Produto/unidade/período | A validar | A mapear | A validar | Pendente |
| Ruptura | A validar | Indicador/percentual | SKU/unidade/período | A validar | A mapear | A validar | Pendente |

## KPIs DEMONSTRATIVOS do pipeline DEMO-4A (só fixtures fictícias)

Fonte: `tests/fixtures/demo_4a/` (contrato em `docs/CONTRATOS_DADOS.md`, "Pipeline DEMO-4A"). Período: o declarado na execução (teste: 2026-10-01 a 2026-10-31, inclusive, competência em America/Sao_Paulo). Valores em `Decimal`; R$ com 2 casas.

| KPI | Fórmula | Unidade | Grão | Filtro | Limitações |
|---|---|---|---|---|---|
| Registros recebidos | contagem de linhas físicas, sem o cabeçalho | registros | entidade × lote | nenhum | inclui linhas malformadas, duplicatas e linhas fora do período |
| Registros válidos | contagem de status `VALIDO` | registros | entidade × lote | — | pode incluir alertas não bloqueantes |
| Registros em quarentena | contagem de status `QUARENTENA` | registros | entidade × lote | — | a categoria usa o motivo principal |
| Registros fora do período | contagem de status `FORA_PERIODO` | registros | entidade × lote (só vendas pode ser > 0) | — | exclusão por filtro, não inconsistência; não somar com duplicatas |
| Duplicatas descartadas | contagem de status `DUPLICATA_DESCARTADA` | registros | entidade × lote | — | cópias de duplicata exata; a primeira cópia segue avaliada |
| Taxa de inconsistência | quarentena ÷ recebidos, 4 casas, ROUND_HALF_UP | proporção | entidade × lote | — | o denominador inclui duplicatas e linhas fora do período, o que dilui a taxa; não pondera por valor; com recebidos = 0, é `indisponível` (não 0) |
| Faturamento bruto válido | Σ valor_calculado das vendas `VALIDO`, igual a Σ quantidade × preço declarado, arredondado por linha | R$ | empresa × período | status `VALIDO` | não deduz devoluções, descontos nem impostos (não modelados); o tratamento tributário do preço é desconhecido; inclui vendas de produtos `INATIVO` (alerta `PRODUTO_INATIVO`) |
| Faturamento por unidade | idem | R$ | empresa × unidade (posto) × período | idem | idem |
| Faturamento por produto | idem | R$ | empresa × produto × período | idem | soma os postos da mesma empresa; idem |
| Quantidade vendida | Σ quantidade das vendas `VALIDO` | L, UN ou KG, conforme o produto | empresa × produto × período | idem | **nunca soma unidades de medida diferentes** |
| Estoque disponível | quantidade_disponivel das linhas de estoque `VALIDO` | L, UN ou KG | empresa × unidade × produto × data de referência | status `VALIDO` | foto de posição, **não aditiva no tempo**: só se agrega na mesma data de referência e na mesma unidade de medida, nunca entre datas; não indica consumo, compra, perda nem cobertura; não é "estoque do período" do faturamento, e cada valor é apresentado com a própria data de referência |

**Não calculados (faltam dados):** margem, CMV, markup, giro, cobertura, ruptura e ticket médio.

**Sem total entre empresas:** no DEMO-4A, nenhum indicador soma empresas diferentes.

**Reconciliação:** Σ por unidade = Σ por produto = total da empresa, dentro de cada empresa.

**Pendências para dados reais:** se `preco_unitario` inclui impostos; se haverá consolidação entre empresas.

## Avisos de consistência

- **Margem bruta** e **markup** usam denominadores diferentes.
- **Venda de combustíveis** pode ter litros; **itens de conveniência** podem ter unidades. Não somar grandezas heterogêneas.
- **Resultado bruto, resultado operacional e lucro líquido** não são equivalentes.
- Não comparar períodos sem considerar dias úteis, unidade ativa e fechamento.
- Consolidar apenas entidades pertencentes à mesma empresa/escopo autorizado.
