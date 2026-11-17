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

**Atualização FASE 4B (16/11/2026):** implementação autorizada pelo usuário, ainda **sem commit**.
- **B12 decidido:** recorte sem venda `VALIDO` não gera linha, e ausência não é zero. Está documentado no contrato e no dicionário, e a reconciliação acusa linha indevida, inclusive de valor zero.
- **R1 tratado:**
  - **Nova verificação:** `indicadores_taxa_<entidade>`, por aritmética inteira e independente do cálculo em Decimal.
  - **Relatório:** usa a taxa publicada e reconciliada.
- **R2 tratado:**
  - **Novas verificações:** `indicadores_chaves_<indicador>` (5 indicadores) e `indicadores_catalogo`, com esperados recalculados a partir do staging.
  - **Correções da auditoria (achados D1 e D2):**
    - **O que passava:** a primeira auditoria publicou linhas de contagem e de taxa com empresa preenchida, além de lote, período, fórmula e fonte adulterados.
    - **Catálogo:** `indicadores_catalogo` passou a conferir a identidade completa de cada linha (chaves, unidade do valor, lote e período).
    - **Metadados:** entrou `indicadores_metadados`, para fórmula, grão, filtro e fonte por (indicador, entidade).
  - **Total:** a reconciliação passou de 21 para 32 verificações.
- **R3 tratado:** com testes de falha provocada por mock, na API e na linha de comando, que devolve o código 3. Não é publicado nada, o lote anterior fica intacto e não sobram resíduos. O código de publicação não foi alterado.
- **R4 tratado:** com o arquivo TZif da base IANA 2026c, de domínio público (`tests/fixtures/tzif/PROVENIENCIA.md`), e `PYTHONTZPATH` absoluto em subprocesso. São testados o horário de verão de 2000 a 2018, os limites de novembro de 2018 e fevereiro de 2019, e o fallback forçado.
- **Pendentes mantidos:** M1, B8, comparação na deduplicação, separador do lote e atomicidade da publicação.
- **Parecer do `auditor-independente`:** na primeira rodada, PENDENTE (achados D1, D2, D3 e D7). Na reauditoria do delta, **APROVADO com ressalva** para o escopo técnico.
- **Riscos residuais da 4B (severidade Baixa):**
  - **Metadados:** `indicadores_metadados` confere unicidade, e não conteúdo. Uma fórmula, fonte, filtro ou grão alterado de forma uniforme é publicado. Valores, chaves, lote e período não são afetados.
  - **Independência parcial do recálculo (D5):** usa o mesmo staging e as mesmas funções decimais. Isso é mitigado pelos testes contra o gabarito.
  - **Pulos condicionais (D6):** os testes de quebra de linha pulam sem o Git ou sem o commit `1f70e76`, por exemplo num clone raso. O fallback forçado pula se o pacote `tzdata` estiver instalado.
  - **P17 real:** continua PENDENTE (WinError 1314). O teste simulado não o substitui.

---

## ADR-002 — Bytes das fixtures independentes de `core.autocrlf` (16/11/2026)

**Situação:**
- **Origem do risco:** o Git for Windows vem com `core.autocrlf=true` na configuração do sistema. Num clone novo, as fixtures saíam com CRLF: os 5 hashes mudavam e o lote passava a `DEMO4A-1ccefdf75a4a` em vez de `DEMO4A-cc6f21e0d609`.
- **Por que passava despercebido:** a suíte não percebia, porque recalcula os esperados a partir da própria árvore de trabalho.
- **Os blobs estavam íntegros:** só a extração os convertia.

**Alternativas:**
- `* text=auto` global: muda todos os arquivos de texto do repositório e não foi testada.
- Exigir `core.autocrlf=false` de cada pessoa: não persiste num novo checkout.
- Atualizar os hashes esperados: esconderia a mudança.
- Regra restrita às fixtures.

**Decisão:** criar o `.gitattributes` com a regra única `tests/fixtures/** -text`. O índice já estava em LF, e os IDs de blob do índice, da árvore e de `1f70e76` são iguais. Por isso não houve renormalização nem regravação de fixtures.

**Responsável:** orquestrador, com aprovação do usuário (FASE 4B).

**Impactos:** só a extração dos arquivos sob `tests/fixtures/` muda; os demais arquivos seguem a configuração de cada máquina.

**Evidências:** `tests/test_consolidacao_eol.py`. Ele testa:
- os blobs de `1f70e76` contra a árvore;
- a ausência de CR nas fixtures;
- o atributo `-text` só nas fixtures;
- o lote `DEMO4A-cc6f21e0d609`;
- um clone temporário com `core.autocrlf=true`, com controle de que a conversão está ativa, um novo checkout e as 14 saídas idênticas;
- o detector de CRLF.

Na prova de mutação, sem a regra os testes do clone e do atributo falham (14 falhas).

**Migração de clones existentes:** um clone feito antes desta regra pode ter fixtures em CRLF.
1. Depois de atualizar o repositório, rode `git ls-files --eol tests/fixtures`. O esperado é `i/lf w/lf attr/-text`.
2. Se aparecer `w/crlf`, apague as fixtures da árvore e restaure-as do Git: `git checkout -- tests/fixtures`.
3. **Nunca** rode `git add -A` nem `git add --renormalize` num clone com fixtures em CRLF, porque isso gravaria blobs CRLF.
4. Confirme com `python -I -m unittest discover -s tests -p "test_consolidacao_eol.py"`.

**Reversão:** remover o `.gitattributes` e o teste. As fixtures não precisam ser alteradas.

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
