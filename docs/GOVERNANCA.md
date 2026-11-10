# Governança de permissões multiagente

**Situação:** implementada para **testes com dados fictícios**. Não é isolamento do sistema operacional.

## Camadas de controle

1. **Regras de permissão** em `.claude/settings.json`, avaliadas na ordem deny → ask → allow.
   - **deny:** editar `data/raw/**`, `.claude/settings*.json`, `.claude/agents/**`, `.claude/skills/**`, `.claude/hooks/**`, `CLAUDE.md`, `.claude/CLAUDE.md`, `.gitignore` e `.git/**`; ler `.env*`, `*.pem` e `*.key`.
   - **ask:** `python`, `py`, PowerShell, `sh -c`/`bash -c`, `rm`, `mv`, `cp`, e os comandos git `commit`, `push`, `reset`, `checkout` e `restore`.
   - **allow:** `git status/diff/log`, `graphify query/explain/path`, `sha256sum` e escrita em `.claude/agent-memory-local/**`. O Claude Code só aplica as regras `allow` do projeto depois que a pasta é marcada como confiável no modo interativo.
   - `disableBypassPermissionsMode: "disable"` e `blockWritesOutsideWorkingDirectories: true`.
2. **Hook `.claude/hooks/guarda_agentes.py`** (PreToolUse de Edit, Write, NotebookEdit, MultiEdit, Bash e PowerShell): identifica o agente pelo `agent_type` e restringe a escrita ao escopo dele. Qualquer erro interno bloqueia a ação. Cada decisão é registrada em `outputs/governanca/hook_guarda_log.jsonl`, ignorado pelo Git.
   - **Exceção de planos (ETAPA 3H):** Write/Edit da **sessão principal** (sem `agent_type` nem `agent_id`) em um arquivo **diretamente** dentro de `~/.claude/plans/`, com nome `[a-z0-9-]+.md`, segue para as regras normais de permissão, com a decisão `permitido_plano` no log. O caminho é resolvido com `realpath`, então `..`, subpastas, junções e links simbólicos que apontem para fora continuam bloqueados. A exceção não vale para subagentes, Bash, PowerShell, Python, NotebookEdit ou MultiEdit.
   - **Testes:** `python -I tests/test_guarda_agentes.py` executa a suíte determinística do hook em diretórios temporários.
3. **`permissionMode: default`** nos agentes analíticos e no auditor. Só vale quando a sessão principal também está em `default`.
4. **Painel do VS Code:** configurar `"claudeCode.initialPermissionMode": "default"` nas configurações do usuário, porque o padrão desde a versão 2.1.283 é o modo automático.

## Escopo de escrita por agente

| Agente | Pode gravar |
|---|---|
| arquiteto-solucoes, qualidade-dados, analista-negocios, auditor-independente | só a própria memória (`.claude/agent-memory-local/<agente>/`) |
| engenheiro-dados | `data/staging`, `data/curated`, `data/analytics`, `outputs` e a própria memória |
| desenvolvedor-sistemas | `scripts`, `src`, `tests`, `outputs` e a própria memória |
| especialista-bi | `data/analytics`, `outputs` e a própria memória |
| todos | nunca os caminhos protegidos da camada 1 |

## Limitações conhecidas

- **Windows nativo não tem sandbox:** processos externos e scripts aprovados podem escrever em qualquer lugar.
- **As regras de Edit não cobrem scripts:** elas valem para as ferramentas de arquivo e para redirecionamentos, não para Python ou Node que abram arquivos por conta própria.
- **O hook é heurístico**, baseado no texto do comando. Ele não detecta caminhos montados dinamicamente nem scripts gravados em arquivo. Nesses casos, a única barreira é a aprovação do usuário, porque o Python sempre pergunta.
- **`ESCRITA_PY` é uma expressão regular, não um analisador de Python.** Desde a ETAPA 3H, só conta como escrita uma string de modo (`w`, `a`, `x`, `+`, com `r`/`b`/`t`) depois de vírgula ou de `mode=` em `open(...)`, ou como primeiro argumento de `.open(...)`. Ela não detecta, entre outros: modo em variável (`open(p, m)`), `open(os.path.join(a, b), 'w')` (parênteses aninhados antes do modo) e `os.open(..., os.O_WRONLY)`.
- **"Sim, e não perguntar de novo"** grava uma liberação permanente em `.claude/settings.local.json`. Revise esse arquivo periodicamente.
- **Escritas auxiliares esperadas:** `graphify-out/cache/` (hooks e consultas), `.claude/agent-memory-local/` (memória) e `outputs/governanca/` (log do hook).
- **`data/raw` fica fora do Git:** a imutabilidade se prova pelo hash SHA-256 de cada lote.

## Manutenção administrativa

Alterações nos arquivos protegidos são feitas manualmente, ou por uma sessão do Claude Code aberta fora deste diretório, e sempre entram num commit próprio e revisado. Não use o modo bypass.

## Antes de usar dados reais

- Isolamento adicional: WSL2 com sandbox (`failIfUnavailable: true`) ou uma conta/máquina dedicada.
- Dados brutos com permissão somente leitura no NTFS.
- Contratos de dados aprovados, porque os atuais valem só para demonstração.
- Revisão de privacidade antes de indexar documentos no grafo.
