# Dicionário de dados e KPIs

**Nunca inventar nomes de colunas ou fórmulas específicas de um ERP**. Registrar após inspeção da base de origem.

| KPI | Fórmula autorizada | Unidade | Grão | Janela | Fonte | Exclusões | Status |
|---|---|---|---|---|---|---|---|
| Faturamento bruto | A validar | R$ | Unidade/período | A validar | A mapear | A validar | Pendente |
| Quantidade vendida | A validar | Unidade física | Produto/unidade/período | A validar | A mapear | A validar | Pendente |
| Margem bruta (%) | A validar | % | Produto/unidade/período | A validar | A mapear | A validar | Pendente |
| Ruptura | A validar | Indicador/percentual | SKU/unidade/período | A validar | A mapear | A validar | Pendente |

## Avisos de consistência

- **Margem bruta** e **markup** usam denominadores diferentes.
- **Venda de combustíveis** pode ter litros; **itens de conveniência** podem ter unidades. Não somar grandezas heterogêneas.
- **Resultado bruto, resultado operacional e lucro líquido** não são equivalentes.
- Não comparar períodos sem considerar dias úteis, unidade ativa e fechamento.
- Consolidar apenas entidades pertencentes à mesma empresa/escopo autorizado.
