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

## Pipeline DEMO-4A: consolidação demonstrativa (FASE 4A, 10/11/2026)

> **Status: DEMONSTRATIVO.** Vale só para as fixtures fictícias de `tests/fixtures/demo_4a/`. Não aplicar a dados reais sem um contrato próprio aprovado. Base: o contrato demonstrativo da ETAPA 3E, com os desvios indicados.

**ID:** DEMO-4A
**Objetivo:** validar, deduplicar, colocar em quarentena e consolidar vendas × produtos de 2 unidades (Posto Alfa e Posto Beta); publicar a posição de estoque e os indicadores reconciliados.

### Fontes e grão (cabeçalho obrigatório, nesta ordem; UTF-8; separador vírgula; ponto decimal)
| Arquivo | Colunas | Grão / chave |
|---|---|---|
| `unidades.csv` | empresa, unidade, nome | (empresa, unidade) |
| `produtos.csv` | empresa, codigo_produto, descricao, categoria, unidade_medida, status_cadastral | (empresa, codigo_produto) |
| `vendas.csv` | empresa, unidade, id_venda, data, codigo_produto, quantidade, preco_unitario, valor_calculado | uma linha de venda: (empresa, unidade, id_venda) |
| `estoque.csv` | empresa, unidade, codigo_produto, data_referencia, quantidade_disponivel | foto de posição: (empresa, unidade, codigo_produto, data_referencia) |

- `id_venda` identifica a **linha** de venda. Ele é único dentro de (empresa, unidade). A regra definitiva de unicidade continua pendente (3E §12).
- Linha física: o cabeçalho é a linha 1. O lote é `DEMO4A-` mais os 12 primeiros caracteres hexadecimais do SHA-256 da lista ordenada `nome_arquivo:sha256`.
- O cadastro de produtos é segregado por empresa e **não** é validado contra `unidades.csv`.

### Normalização (registrada em `transformacoes.csv`)
- Cada campo passa por `strip()` de espaços. Quando o valor muda, isso é registrado. Não há outras correções automáticas.
- **Datas de venda:**
  - Formatos aceitos: `AAAA-MM-DD` e `AAAA-MM-DDTHH:MM:SS±HH:MM`. O fuso é obrigatório quando há hora.
  - Datas com hora são convertidas para **America/Sao_Paulo**, e a data local define a competência. Cada conversão é registrada.
  - Sem a base `tzdata`, usa-se **UTC−03:00 fixo**, válido só para instantes a partir de 2019-02-17, quando terminou o último horário de verão. Uma data com hora anterior a isso vira `DATA_INVALIDA` enquanto se usar o fallback. O uso do fallback é registrado no manifesto.
- **`data_referencia` do estoque:** só `AAAA-MM-DD`.

### Regras por linha (todas as causas aplicáveis são registradas)
Uma regra que depende de um campo ausente ou inválido não é avaliada. Exemplo: sem empresa, não se verifica o cadastro do produto. Assim se evitam causas em cascata.

As regras de relacionamento são independentes entre si. Empresa e unidade incoerentes não impedem a verificação do produto no cadastro da empresa informada. `UNIDADE_MEDIDA_DIVERGENTE` e `PRODUTO_INATIVO` exigem um produto válido e uma quantidade decimal válida.

| Código | Entidades | Condição | Gravidade | Bloqueia |
|---|---|---|---|---|
| `LINHA_MALFORMADA` | todas | número de colunas diferente do cabeçalho (a linha não é interpretada) | Alta | sim |
| `CAMPO_OBRIGATORIO_AUSENTE` | todas | campo de chave/identidade vazio: empresa, unidade, id_venda, data, codigo_produto, quantidade, descricao, categoria, unidade_medida, status_cadastral, data_referencia, quantidade_disponivel, nome | Alta | sim |
| `CONFLITO_ID` | todas | mesma chave com conteúdo normalizado diferente: **todas** as ocorrências | Crítica | sim |
| `DATA_INVALIDA` | vendas, estoque | fora do formato aceito ou data inexistente | Alta | sim |
| `EMPRESA_UNIDADE_INCONSISTENTE` | vendas, estoque | a unidade existe no cadastro, mas em **outra** empresa | Crítica | sim |
| `UNIDADE_FORA_DOMINIO` | vendas, estoque | a unidade não existe no cadastro em nenhuma empresa | Alta | sim |
| `PRODUTO_SEM_CADASTRO` | vendas, estoque | o código não existe no cadastro **da mesma empresa** | Alta | sim |
| `CHAVE_RELACIONAMENTO_INVALIDA` | vendas, estoque | o código existe na empresa, mas nenhum cadastro dele é válido (quarentena) | Alta | sim |
| `UNIDADE_MEDIDA_FORA_DOMINIO` | produtos | unidade_medida ∉ {L, UN, KG} | Alta | sim |
| `STATUS_CADASTRAL_INVALIDO` | produtos | status_cadastral ∉ {ATIVO, INATIVO} | Média | sim |
| `QUANTIDADE_INVALIDA` | vendas, estoque | não é decimal ou tem mais de 3 casas; em vendas, ≤ 0; no estoque, < 0 (zero vale) | Alta | sim |
| `UNIDADE_MEDIDA_DIVERGENTE` | vendas, estoque | quantidade não inteira para produto em UN | Alta | sim |
| `PRECO_AUSENTE` | vendas | preco_unitario vazio. **Nunca vira zero** | Alta | sim |
| `PRECO_INVALIDO` | vendas | não é decimal com ponto, tem mais de 3 casas ou é ≤ 0 | Alta | sim |
| `VALOR_AUSENTE` | vendas | valor_calculado vazio | Alta | sim |
| `VALOR_INVALIDO` | vendas | não é decimal com ponto ou tem mais de 2 casas | Alta | sim |
| `VALOR_DIVERGENTE` | vendas | só com quantidade > 0, preço > 0 e valor válidos: valor ≠ `(quantidade × preço)` arredondado a 2 casas (ROUND_HALF_UP) | Crítica | sim |
| `PRODUTO_INATIVO` | vendas, estoque | produto válido com status INATIVO | Baixa | **não** (alerta) |
| `DUPLICATA_EXATA` | todas | linha idêntica, após normalização, a uma linha anterior da mesma chave | Crítica | descarta a cópia |

**Esclarecimentos** (vieram do gabarito independente; nenhum muda o resultado):
- **Leitura do CSV:** segue a RFC 4180. Um campo entre aspas, como `"3,50"`, é uma única coluna. Um registro que ocupa mais de uma linha física vira `LINHA_MALFORMADA`.
- **Linha malformada:** não é interpretada. As colunas normalizadas ficam vazias, sem id nem competência, e só `conteudo_original` é preservado.
- **`VALOR_INVALIDO`:** confere só o formato e as casas, **não o sinal**. Valores 0,00 ou negativos só são avaliados por `VALOR_DIVERGENTE`, que exige quantidade e preço > 0.
- **"Existe na empresa":** qualquer linha de `produtos.csv` daquela empresa e código, inclusive as que estão em quarentena. Isso decide entre `CHAVE_RELACIONAMENTO_INVALIDA` e `PRODUTO_SEM_CADASTRO`.
- **Empresa:** não há domínio de empresa na 4A. A empresa só é verificada pela coerência com a unidade.
- **Chave incompleta:** uma chave com componente vazio continua valendo para a deduplicação, com o vazio como valor.
- **Competência:** é preenchida sempre que a data de venda é válida, em qualquer status.
- **Comparação de quantidades:** é numérica, pelo valor em Decimal, não pela escala textual.

- **Motivo principal:** é o primeiro código bloqueante, na ordem da tabela acima. A contagem por categoria usa o motivo principal; o arquivo `ocorrencias.csv` lista **todas** as causas.
- **Duplicidade:** é avaliada no arquivo inteiro, antes do filtro de período, e ignora linhas malformadas.
  - A primeira linha física de um grupo de duplicatas exatas é avaliada normalmente.
  - As cópias seguintes ganham o status `DUPLICATA_DESCARTADA`.

### Status de cada linha (exatamente um)
1. `DUPLICATA_DESCARTADA`: cópia de duplicata exata.
2. `QUARENTENA`: pelo menos 1 causa bloqueante.
3. `FORA_PERIODO`: só para vendas sem causa bloqueante cuja data de competência fica fora do período declarado (intervalo fechado). É uma exclusão por filtro, não uma inconsistência.
4. `VALIDO`: os demais casos. Podem ter alertas não bloqueantes.

O estoque não tem filtro de período: cada foto vale para a própria `data_referencia`, sem inferir consumo, compra ou perda.

### Consolidação
- **Vendas:** as vendas `VALIDO` recebem os atributos do produto válido pela junção (empresa, codigo_produto).
  - Cada chave aparece uma única vez em `produtos_validos`. Isso é verificado antes da junção.
  - A contagem depois da junção é igual à de antes.
  - Cada linha carrega lote, `arquivo_origem`, `linha_origem` e `sha256_origem`.
- **Estoque:** a posição separada contém as linhas de estoque `VALIDO`.
- **Dinheiro:** é calculado em `Decimal` a partir do texto, nunca em float. O preço aceita até 3 casas (combustível) e o valor da linha tem 2. O faturamento é a soma dos valores das linhas válidas.

### Reconciliação (qualquer falha interrompe o pipeline com erro)
- **Contagens:** recebidos = válidos + quarentena + fora do período + duplicatas descartadas, por entidade. Cada linha física aparece exatamente uma vez no staging.
- **Faturamento por recorte:** Σ por unidade = total da empresa = Σ por produto, dentro de cada empresa.
- **Faturamento entre camadas:** Σ em curated = Σ das linhas válidas em staging.
- **Junção:** a contagem antes da junção é igual à de depois.
- **Rastreabilidade:** linhas válidas não têm causa bloqueante; linhas em quarentena têm pelo menos uma.

### Desvios em relação ao contrato da ETAPA 3E
- **Devoluções:** quantidade negativa vai para `QUANTIDADE_INVALIDA`. Devoluções não são modeladas.
- **Quantidade:** pode ser decimal, para litros e quilos, exceto em UN.
- **Preço:** aceita 3 casas.
- **Período:** `FORA_PERIODO` deixou de contar como inconsistência.

### Tratamento de erro, preservação e idempotência
- **Rejeição do lote inteiro:** o lote é rejeitado com erro explícito quando há arquivo ausente, vazio ou fora de UTF-8, ou cabeçalho diferente do contrato. Nesse caso não se grava nenhuma saída parcial.
- **Preservação:** a entrada é só lida, nunca gravada. O pipeline recusa entrada dentro de `data/` e saída fora de `data/staging`, `data/curated`, `data/analytics` e `outputs`.
- **Idempotência:** a mesma entrada gera arquivos de dados idênticos byte a byte. Só `execucao.json` contém horário.

### Interface (estável; os testes dependem dela)
- **API:** `consolidacao.pipeline.executar(entrada, inicio, fim, raiz) -> dict`.
  - `entrada` é o diretório com os 4 CSVs; `inicio` e `fim` são do tipo `datetime.date`; `raiz` é a raiz onde ficam `data/` e `outputs/`.
  - Retorna `{"lote": str, "diretorios": {"staging","curated","analytics","outputs": str}, "reconciliacao_ok": True}`.
- **Erros** (em `consolidacao.erros`):
  - `LoteRejeitado`: arquivo ausente, vazio, fora de UTF-8 ou com cabeçalho diferente.
  - `ReconciliacaoFalhou`.
  - `CaminhoNaoPermitido`: entrada dentro de `<raiz>/data/` ou saída fora das pastas permitidas.
  - Todos derivam de `ErroPipeline`. Em caso de erro, nenhuma pasta do lote fica criada.
- **Linha de comando:** `python -I scripts/executar_demo_4a.py --entrada DIR --periodo AAAA-MM-DD:AAAA-MM-DD [--raiz DIR]`. A raiz padrão é a do repositório.
  - Códigos de saída: 0 = ok; 2 = `LoteRejeitado`; 3 = `ReconciliacaoFalhou`; 4 = `CaminhoNaoPermitido`; 1 = outro erro.
- **Pastas:** `<raiz>/data/staging/demo_4a/<lote>/`, `<raiz>/data/curated/demo_4a/<lote>/`, `<raiz>/data/analytics/demo_4a/<lote>/` e `<raiz>/outputs/demo_4a/<lote>/`. Reexecutar o mesmo lote substitui o conteúdo por inteiro.

### Esquema das saídas
Todos os arquivos são UTF-8, sem BOM, com terminador `\n`, vírgula como separador e aspas mínimas.

**Representação dos valores:**
- `arquivo_origem` é só o nome do arquivo (por exemplo, `vendas.csv`), nunca o caminho absoluto.
- Listas como `causas` e `alertas` usam `|`, na ordem da tabela de regras.
- Dinheiro sai com 2 casas fixas; quantidades, com a escala de origem (somas sem notação exponencial); a taxa, com 4 casas; vazio é string vazia.

| Arquivo | Colunas (nesta ordem) | Ordenação |
|---|---|---|
| staging `manifesto.json` | lote, contrato="DEMO-4A", fuso {nome, modo: "zoneinfo" ou "fallback_utc-03:00"}, periodo {inicio, fim}, arquivos [{arquivo, sha256, bytes, linhas_fisicas, registros, codificacao}] — **sem horário** | arquivos por nome |
| staging `<entidade>.csv` (unidades, produtos, vendas, estoque) | lote, arquivo_origem, linha_origem, sha256_origem, status, motivo_principal, causas, alertas, conteudo_original, colunas do contrato (normalizadas) e, só em vendas, competencia | linha_origem |
| curated `vendas_consolidadas.csv` | lote, empresa, unidade, id_venda, competencia, data_original, codigo_produto, descricao, categoria, unidade_medida, status_cadastral, quantidade, preco_unitario, valor, alertas, arquivo_origem, linha_origem, sha256_origem | empresa, unidade, id_venda |
| curated `produtos_validos.csv` | lote, empresa, codigo_produto, descricao, categoria, unidade_medida, status_cadastral, arquivo_origem, linha_origem | empresa, codigo_produto |
| curated `estoque_posicao.csv` | lote, empresa, unidade, codigo_produto, data_referencia, quantidade_disponivel, unidade_medida, alertas, arquivo_origem, linha_origem | empresa, unidade, codigo_produto, data_referencia |
| curated `quarentena.csv` | lote, entidade, arquivo_origem, linha_origem, motivo_principal, causas, gravidade_maxima, conteudo_original | entidade, linha_origem |
| curated `ocorrencias.csv` | lote, entidade, arquivo_origem, linha_origem, codigo, gravidade, bloqueante (sim/nao), principal (sim/nao), campo, detalhe | entidade, linha_origem, ordem do código |
| curated `transformacoes.csv` | lote, entidade, arquivo_origem, linha_origem, campo, valor_antes, valor_depois, regra (NORMALIZA_ESPACOS, CONVERTE_FUSO, DESCARTA_DUPLICATA, EXCLUI_FORA_PERIODO, EXCLUI_QUARENTENA) | entidade, linha_origem, campo, regra |
| analytics `indicadores.csv` | lote, indicador, entidade, empresa, unidade, codigo_produto, data_referencia, unidade_medida, valor, unidade_valor, formula, grao, filtro, periodo_inicio, periodo_fim, fonte | indicador, entidade, empresa, unidade, codigo_produto, data_referencia |
| outputs `reconciliacao.json` | {"ok": bool, "verificacoes": [{id, descricao, esperado, obtido, ok}]} | por id |
| outputs `relatorio_qualidade.md` | resumo determinístico: contagens, motivos principais e totais | — |
| outputs `execucao.json` | inicio, fim, duração, versão do Python — **o único arquivo com horário** | — |

**Identificadores dos indicadores:**
- **Contagens:** `registros_recebidos`, `registros_validos`, `registros_quarentena`, `registros_fora_periodo`, `duplicatas_descartadas` e `taxa_inconsistencia`, cada um por entidade.
- **Faturamento:** `faturamento_bruto_valido` (empresa), `faturamento_por_unidade` (empresa, unidade) e `faturamento_por_produto` (empresa, codigo_produto).
- **Quantidade e estoque:** `quantidade_vendida` (empresa, codigo_produto, unidade_medida) e `estoque_disponivel` (empresa, unidade, codigo_produto, data_referencia, unidade_medida).

**Responsável e aprovador:** orquestrador e `desenvolvedor-sistemas` / usuário. Auditoria: `auditor-independente`.

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
