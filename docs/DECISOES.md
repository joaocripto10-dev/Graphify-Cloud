# Registro de decisões técnicas (ADR simplificado)

## ADR-000 — Critérios iniciais (09/11/2026)

**Status:** Proposta inicial, a validar no repositório real.  
**Decisão:** Claude Code orquestra especialistas; Graphify apoia consultas estruturais; dados operacionais permanecem em armazenamento separado, com camadas raw/staging/curated/analytics quando necessário.  
**Justificativa:** reduzir releitura de repositórios e permitir qualidade e rastreabilidade.  
**Riscos:** custo por subagente, inferências no grafo, vazamento de dados se indexados externamente, duplicação de ferramentas existentes.  
**Próxima ação:** diagnóstico do repositório antes de qualquer implementação.

---

## ADR-001 — Motor demonstrativo de consolidação DEMO-4A (10/11/2026)

**Situação:** primeiro módulo funcional. Usa só dados fictícios. O ambiente tem Python 3.14 com a biblioteca padrão, sem pandas, pytest nem tzdata.
**Alternativas:** pandas/duckdb (exigem instalação); banco local (fora do escopo); biblioteca padrão.
**Decisão:**
- **Pacote e testes:** `src/consolidacao/`, só com a biblioteca padrão (`csv`, `decimal`, `hashlib`, `zoneinfo`, `json`), testado com `unittest`.
- **Fontes:** as fixtures ficam em `tests/fixtures/demo_4a/`, porque `data/raw` é protegido.
- **Saídas:** vão para `data/{staging,curated,analytics}/demo_4a/<lote>/` e `outputs/demo_4a/<lote>/`, fora do Git.
- **Fuso:** America/Sao_Paulo quando houver base de fusos; senão, UTC−03:00 fixo, registrado no manifesto.
**Responsável:** orquestrador; implementação pelo `desenvolvedor-sistemas`; auditoria pelo `auditor-independente`.
**Impactos:** nenhum arquivo protegido nem dependência nova. As regras valem só para a demonstração (3E §12 continua pendente).
**Evidências:** suíte `tests/test_consolidacao_*.py`, gabarito independente `tests/fixtures/demo_4a/gabarito.json` e parecer do auditor.
**Reversão:** apagar `src/consolidacao/`, `scripts/executar_demo_4a.py`, `tests/fixtures/demo_4a/` e os testes; reverter as seções dos documentos.

**Registro da validação (10/11/2026):**
- **Processo:**
  - O gabarito foi calculado à mão pelo `qualidade-dados`, sem ver o `LEIAME.md` nem o código.
  - A implementação e os testes foram escritos por agentes distintos, cada um sem acesso ao trabalho do outro. A evidência vem dos registros de execução:
    - O implementador fez 0 leituras do gabarito, do `LEIAME.md` e dos testes.
    - O autor dos testes só listou nomes de arquivos em `src/` (`ls`), sem abrir conteúdo.
  - O `auditor-independente` recalculou às cegas (etapa 1), sem acesso ao gabarito, às saídas ou aos testes, e chegou aos mesmos números, inclusive o lote.
  - Limitação de independência: os "Esclarecimentos" do contrato vieram das ambiguidades levantadas pelo gabarito, então a interpretação do gabarito entrou na especificação usada pela implementação.
- **Correções feitas:**
  - Um teste foi corrigido. Ele confundia o valor obrigatório `fallback_utc-03:00` com um horário; a exceção vale só para esse enumerado.
  - Um teste foi acrescentado para a saída redirecionada para fora da raiz por junção ou link simbólico.
  - A reconciliação ganhou 5 verificações (achados B1 e B2 do auditor): o indicador de faturamento publicado tem de bater com a soma do curated, e os indicadores de contagem publicados têm de bater com o status das linhas.
  - O grão de `registros_fora_periodo` foi corrigido no dicionário.
- **Decisões da implementação mantidas** (o contrato admite essas leituras; nenhuma afeta as fixtures):
  - **Quantidades na deduplicação:** são comparadas pelo valor numérico (`1` = `1.0`); preço e valor, como texto.
  - **Lote:** usa `nome:sha256` em lista ordenada, unida por LF e sem LF final.
  - **Cópias descartadas:** recebem `DUPLICATA_EXATA` como causa e motivo principal.
  - **Rejeição do lote:** acontece também com BOM e com erro de parsing CSV.
  - **CONVERTE_FUSO:** é registrado mesmo quando o horário local não muda.
  - **Instantes perto do limite do fallback:** são recusados de forma conservadora entre 02:00Z e 03:00Z de 2019-02-17.
- **Pendentes de definição antes de dados reais:**
  - **M1:** se uma unidade em quarentena "existe no cadastro".
  - **B8:** se um preço ou valor inteiro sem ponto (`4`) é aceito.
  - **B12:** se a ausência de vendas válidas gera indicador zero ou nenhum.
  - **Comparação na deduplicação:** se deve ser textual ou numérica.
  - **Separador do lote** no contrato.
  - **Publicação:** a troca das 4 camadas não é atômica se o processo for morto no meio, e as pastas `demo_4a` vazias continuam existindo depois de um erro na publicação.
- **Parecer do `auditor-independente`:** APROVADO para o escopo demonstrativo (só fixtures fictícias), com condicionantes.
- **Riscos residuais (severidade Baixa)** — R1 a R4 serão tratados na **Fase 4B**:
  - **R1:** a `taxa_inconsistencia` publicada não é reconciliada.
  - **R2:** uma linha de faturamento de empresa sem vendas válidas não seria detectada pela reconciliação.
  - **R3:** não há teste gravado que provoque `ReconciliacaoFalhou` nem o código de saída 3 da linha de comando.
  - **R4:** o caminho com `zoneinfo` e horário de verão não foi testado; o ambiente não tem `tzdata`, e o teste fica ignorado.
  - **R5:** as fixtures e o gabarito não estavam versionados. Fica resolvido com o commit desta versão.

---

## Modelo de nova decisão

**ID / data:**  
**Situação:**  
**Alternativas:**  
**Decisão:**  
**Responsável:**  
**Impactos:**  
**Evidências:**  
**Reversão:**
