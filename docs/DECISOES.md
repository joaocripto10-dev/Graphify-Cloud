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

## ADR-003 — Autonomia controlada das permissões (18/11/2026)

**Status:** **Etapa 1 instalada** em 18/11/2026. O `.claude/settings.json` é idêntico ao candidato e foi homologado no manifesto de 18/11/2026, às 18:21. A matriz interativa foi executada **em parte** em 18 e 21/11/2026 (ver Evidências). **A Etapa 2 (`defaultMode: acceptEdits`) não foi instalada e continua bloqueada.** O commit foi feito em 24/11/2026, depois da restauração do SSD, com os arquivos conferidos contra o manifesto.

**Situação:**
- **Atrito medido:** numa sessão de 210 comandos de shell, 123 casavam com alguma regra `ask`, e 106 deles eram `python` (suítes de teste e verificações). A regra `Bash(python:*)` pede confirmação até para testes já revisados.
- **Limite das regras:** na documentação oficial do Claude Code, a ordem é deny > ask > allow, e a especificidade não muda essa ordem. Um `allow` específico não vence o `ask` de `python`. No modo `auto`, um classificador aprova o que não casa com regra nenhuma.
- **Incidentes de configuração (autoria não comprovada):**
  - **16/11/2026, 11:34:45 (−03:00):** `.claude/settings.json` apareceu com uma segunda chave `"ask"`. O leitor JSON padrão fica com a última chave, e a configuração efetiva ficou sem `Bash(python:*)`.
  - **17/11/2026, 10:53:45 (−03:00):** o arquivo apareceu sem `Bash(python:*)` em `ask`, com regras de `unittest` em `allow` e sem uma vírgula, ou seja, JSON inválido. Pela documentação, um arquivo inválido é pulado inteiro, com as regras `deny` e os hooks. O log do hook ficou cerca de 1 minuto sem registros.
  - **O que se sabe da origem:** o log do hook não registra escrita no arquivo, e as regras inseridas têm a forma dos comandos de teste aprovados naquele instante. O quadro é compatível com a opção "não perguntar de novo" do cartão de aprovação do VS Code, mas isso não foi provado.
  - **Correção:** nos dois casos, o arquivo foi restaurado para a versão do Git.

**Alternativas:**
- Liberar `Bash(python -I -m unittest … *)`: exige tirar o `ask` de `python` e aceita argumentos livres. Descartada.
- Modo `auto`: delega a um classificador as decisões que hoje são manuais. Descartada.
- Sandbox do Bash: não existe no Windows nativo (só no WSL2). Fora do escopo.
- Executor homologado com regras exatas. Escolhida.

**Decisão:**
- **Executor:** `bash scripts/testar.sh <modalidade>` é o único caminho liberado sem confirmação para executar Python.
  - **Regras exatas, sem curinga:** `motor`, `motor-zoneinfo`, `governanca`, `tudo`, `conferir` e `demo`.
  - **Modalidade `arquivo test_<nome>.py`:** existe, mas não tem regra de liberação e pede confirmação.
  - **`Bash(python:*)`:** continua em `ask`.
- **Homologação por manifesto:** `scripts/homologacao.manifest` guarda o SHA-256 de todo arquivo de `scripts/`, `src/` e `tests/`, do hook de governança, de `.claude/settings.json` e de `.gitattributes`.
  - **Recusa:** o executor não roda se houver arquivo novo, alterado ou removido, ou qualquer link simbólico ou junção.
  - **Configuração reescrita:** como o `settings.json` está no manifesto, qualquer reescrita dele, como as dos dois incidentes, bloqueia as execuções liberadas até uma nova homologação.
  - **Nova homologação:** `bash scripts/homologar.sh` grava o manifesto e **sempre pede confirmação**. Antes de aprovar, `bash scripts/testar.sh conferir` lista o que mudou.
- **Verificações em cada execução, nesta ordem:**
  1. argumentos fechados;
  2. raiz física derivada do local do executor, e não do diretório atual;
  3. `python`, `git` e utilitários resolvidos fora do repositório;
  4. ambiente limpo, com lista fechada de variáveis;
  5. núcleo de verificação conferido em shell;
  6. validador estrito sobre `.claude/settings.json` e, se existir, `.claude/settings.local.json`;
  7. conjunto completo contra o manifesto, sem nenhum link;
  8. remoção de bytecode em cache;
  9. depois de cada suíte, o conjunto é conferido de novo, e uma mudança durante a execução invalida o resultado (código 3).
- **Validador (`scripts/validar_settings.py`):** rejeita JSON inválido e chaves repetidas, e confere a configuração compartilhada.
  - **Regras:** as 14 regras `deny` e as 15 `ask` homologadas têm de estar presentes, e o `allow` só aceita regras de uma lista fechada.
  - **Hooks:** têm de ser exatamente iguais aos homologados, sem evento, comando ou chave a mais ou a menos.
  - **Modos e chaves:** bypass e `auto` proibidos, e nenhuma chave desconhecida.
  - **Perfil de autonomia:** é exigido quando há qualquer regra de autonomia em `allow` ou `defaultMode: acceptEdits`. Ele cobra as proteções do executor, do manifesto e das fixtures, as leituras do Git endurecidas, as confirmações novas e o modo `auto` desligado.
  - **Arquivo local:** só pode conter listas de permissão, sem liberação ampla nem de interpretador.
- **Configuração candidata:** só acrescenta regras à homologada, que tinha 14 `deny`, 15 `ask` e 8 `allow`. A candidata tem 31, 66 e 18.
  - **`allow` novos:** as 6 modalidades exatas do executor e 4 leituras do Git (`show`, `rev-parse`, `ls-files` e `check-attr`).
  - **`deny` novos:**
    - edição do executor e do núcleo de homologação em qualquer pasta, das fixtures, do `.gitattributes`, de `.claude/commands`, de `.mcp.json` e de `.vscode`;
    - `git … --output`, que grava arquivo em qualquer subcomando;
    - `git diff/log/show --ext-diff`, `git diff --no-index` e `git diff` sobre `.env`.
  - **`ask` novos:**
    - `homologar.sh`;
    - outros interpretadores e execução indireta (`sh`, `source`, `eval`, `env`, `xargs`, `cmd`);
    - instalação de pacotes e rede;
    - escrita por shell (`sed`, em qualquer forma, `tee`, `rmdir`, `ln`, `dd`);
    - os comandos do Git que alteram estado, inclusive `git -c` e `git -C`.
  - **Fora do `allow` por falta de evidência:**
    - `git rev-list` e `git cat-file`: aceitam `--output` e filtros;
    - `graphify update .`: não foi possível confirmar que nunca usa LLM quando há chave de API no ambiente.
- **Instalação em duas etapas:**
  - **Etapa 1:** a configuração candidata **sem** `defaultMode`. O modo continua sendo o escolhido na sessão.
  - **Etapa 2:** acrescenta `defaultMode: acceptEdits`. Só é instalada depois que a matriz interativa provar que as regras `deny` seguram a escrita por shell nesse modo.
  - **Motivo:** em `acceptEdits`, `mkdir`, `touch`, `rm`, `rmdir`, `mv`, `cp` e `sed` são aprovados sozinhos dentro do projeto. O hook não protege o executor, o manifesto nem as fixtures; só as regras `deny` o fazem, e a documentação não garante que elas valem para `touch`, `cp` e `mv`.
- **Fim de linha:** `.gitattributes` ganhou `scripts/*.sh text eol=lf`, para o `bash` executar os scripts em clones com `core.autocrlf=true`.
- **Uso do "não perguntar de novo":** não usar essa opção gravando no arquivo compartilhado. Se o cliente gravar ali, o executor passa a recusar (manifesto e validador), e o desvio aparece na próxima execução.

**Responsável:** orquestrador, com aprovação do usuário. O `settings.json` só é instalado manualmente pelo usuário.

**Impactos:**
- Testes homologados e leituras do Git deixam de pedir confirmação.
- Mudar código de `scripts/`, `src/` ou `tests/` passa a exigir **uma** confirmação de homologação por conjunto, em vez de uma por execução de teste.
- O executor, o validador e o manifesto ficam protegidos contra edição pelas ferramentas de arquivo. Alterá-los é manutenção manual, como a do hook.

**Evidências:**
- `tests/test_seguranca_autonomia.py`, com 51 testes simulados. O unittest conta 52, porque coleta também o auxiliar `testar` de `TestExecutor`. Eles cobrem:
  - os dois incidentes reproduzidos;
  - teste novo não homologado não executa;
  - alteração ou bytecode plantado durante a execução invalida o resultado;
  - ambiente limpo;
  - link e junção recusados;
  - `python` plantado no repositório recusado;
  - configuração corrompida ou alterada bloqueando a execução;
  - o fluxo de instalação do perfil de autonomia.
- Suíte completa pelo executor: 193 testes com 0 falhas e 1 pulado em cada um dos dois modos de fuso; governança com 53 casos e 0 falhas. O `motor` e a `governanca` rodaram sobre o conjunto homologado final. O `motor-zoneinfo` rodou antes da homologação final, em 18/11, às 15:14.
- Revisão independente de segurança:
  - **Primeira rodada:** PENDENTE, com 3 achados altos (A1 a A3), 7 médios e 8 baixos, tratados nesta versão.
  - **Reavaliação:** **APROVADO PARA INSTALAÇÃO DA ETAPA 1**. A etapa 2 continua pendente da matriz interativa.
- Versão do cliente: extensão Claude Code 2.1.325 no VS Code. Os campos `onFailure` (a partir da 2.1.295) e `blockWritesOutsideWorkingDirectories` (a partir da 2.1.314) são oficiais.
- Falha fechada observada: em 18/11/2026, o hook guarda estourou o tempo limite com a máquina ocupada, e a chamada foi bloqueada ("blocking because onFailure is block").
- **Matriz interativa, parcial (18 e 21/11/2026), segundo o log do hook:**
  - **Negado pelo hook:**
    - `Write` fora do projeto;
    - escrita de subagentes fora do próprio escopo (`data/curated`, `docs/`, `outputs/`);
    - comando de shell que cita `data/raw`.
  - **Escrita por shell nos demais caminhos** (`echo >`, `cd … &&`, variável, aspas partidas, `touch`, `cp`, `mv`) em `tests/fixtures/`, `scripts/` e `outputs/`: o hook não classifica o destino e manda para aprovação.
  - **Ao menos uma escrita por shell em `tests/fixtures/` foi efetivada:** `tests/fixtures/zz_matriz.txt` ficou no disco. Portanto, **as regras `deny` de `Edit` não seguram escrita por shell**, e a premissa da Etapa 2 **não** se confirmou.
  - O arquivo residual, que não está no manifesto, faz o executor recusar com código 3 até ser removido à mão. Ele não foi versionado.
  - Não foi registrado, regra por regra, o que o usuário aprovou e o que o cliente bloqueou. É preciso consolidar isso antes de qualquer decisão sobre a Etapa 2.

**Riscos e limitações:**
- **Não é isolamento do sistema operacional.** Testes são código e rodam com as permissões do usuário. O manifesto garante que só roda o que foi homologado, e não que o código homologado seja inofensivo.
- **Janela entre verificar e executar (A3).** Um arquivo alterado durante a execução pode rodar. A reverificação depois de cada suíte detecta a mudança, mas não a impede, e não vê uma alteração desfeita antes do fim. Sem `acceptEdits`, essa escrita pede confirmação.
- **A regra de permissão casa o texto do comando, e não o arquivo.** Um arquivo chamado `scripts/testar.sh` em outra pasta, com `git init` próprio, casaria com a regra se o diretório atual fosse mudado. A mitigação é o `deny` de edição, em qualquer pasta, para os arquivos do núcleo; o caso entra na matriz efetiva.
- **A verificação do núcleo é circular:** o executor confere a si mesmo. A proteção real é o `deny` de edição, somado à revisão no Git.
- **`git diff` lê fora do repositório (M1).** Quando recebe um caminho externo, ele entra sozinho no modo sem índice e lê o arquivo. Isso já existia na configuração homologada. Os `deny` novos cobrem só `--no-index` explícito e `.env`.
- **A configuração homologada anterior permitia `git diff --output=<arquivo>`** sem confirmação. O perfil de autonomia fecha isso; até a instalação, o validador só avisa.
- **O executor grava sem passar pelo hook (B7):** os logs em `outputs/testes/` e, na modalidade `demo`, as pastas `data/staging`, `data/curated`, `data/analytics` e `outputs/demo_4a`. Qualquer agente com Bash consegue acioná-lo.
- **O `PATH` é herdado (B8):** só se recusa ferramenta que esteja dentro do repositório.
- **Regras Bash não são fronteira de segurança** (documentação oficial).
- **Requisitos:** Python 3.12 ou mais recente, por causa de `os.path.isjunction` e de `shutil.rmtree(onexc=)`, e bash 4 ou mais recente (Git Bash no Windows), com um comando `python` no `PATH`. Sem `python`, o executor falha com código 70. O hook, que está com `onFailure: block`, bloqueia as ferramentas de edição e de shell no projeto.
- **Comportamentos não documentados** ficam para a validação interativa:
  - se a correspondência de caminhos diferencia maiúsculas no Windows;
  - a lista de variáveis de ambiente aceitas como prefixo;
  - a aplicação das regras `deny` de edição a `touch`, `cp` e `mv`.

**Reversão:**
- restaurar `.claude/settings.json` do Git;
- remover `scripts/testar.sh`, `homologar.sh`, `lib_homologacao.sh`, `homologacao.py`, `validar_settings.py`, `homologacao.manifest` e `tests/test_seguranca_autonomia.py`;
- reverter a linha nova do `.gitattributes`.

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
