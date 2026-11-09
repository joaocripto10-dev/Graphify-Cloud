# Contratos de dados (modelo inicial)

Este modelo é **proposta, não esquema confirmado**. Preencher a partir das bases reais antes de codificar transformações.

| Entidade | Origem | Grão | Chave/ID | Campo temporal | SLA de atualização | Dono | Status |
|---|---|---|---|---|---|---|---|
| Vendas | A mapear | A definir | A definir | A definir | A definir | A definir | Pendente |
| Produtos | A mapear | A definir | A definir | A definir | A definir | A definir | Pendente |
| Estoque | A mapear | A definir | A definir | A definir | A definir | A definir | Pendente |
| Unidades | A mapear | A definir | A definir | A definir | A definir | A definir | Pendente |

## Invariantes mínimos

- Identidade da fonte e do lote preservada.
- Totais de origem e destino reconciliados; diferenças justificadas e registradas.
- Chaves de junção explícitas e verificadas contra cardinalidade esperada.
- Datas e timezone declarados.
- Unidades de medida registradas (litros, itens, R$, porcentagem etc.).
- Valores nulos e duplicidades tratados por regra previamente aprovada.
- Histórico de transformações e regras mantido com versionamento.
- Dados brutos imutáveis; correção via novo lote ou processamento.

## Modelo para cada pipeline

**ID:**  
**Objetivo:**  
**Fontes e campos:**  
**Grão/chaves:**  
**Transformações:**  
**Regras de exclusão:**  
**Campos e tipos de saída:**  
**Teste de reconciliação:**  
**Testes de qualidade:**  
**Tratamento de erro:**  
**Política de atualização:**  
**Responsável e aprovador:**
