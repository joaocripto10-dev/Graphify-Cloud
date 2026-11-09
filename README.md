# Kit Claude Code + Graphify | Engenharia e Inteligência de Dados

**Versão:** 1.0 — 09/11/2026  
**Ambiente-alvo:** Windows, VS Code com extensão Claude Code (também funciona no terminal integrado).

Este é um **esqueleto de instruções e fluxos de trabalho**, não um sistema de BI implementado nem um conjunto de agentes autônomos já em execução. O Claude Code é o orquestrador; os subagentes são ativados sob demanda. Graphify disponibiliza o grafo de conhecimento do código/documentos, não substitui um ETL ou o banco de dados.

## Instalação no seu projeto existente (recomendada)

1. Descompacte o ZIP em uma pasta temporária, por exemplo `C:\Temp\kit_claude_graphify_vscode`.
2. Abra **PowerShell no VS Code**; execute o instalador seguro (sem sobrescrever arquivos existentes):

   ```powershell
   & 'C:\Temp\kit_claude_graphify_vscode\INSTALAR_NO_PROJETO.ps1' -Destino 'C:\CAMINHO\DO\SEU\PROJETO'
   ```

   Se preferir projeto novo, crie primeiro a pasta e abra-a no VS Code. Você também pode copiar manualmente `CLAUDE.md`, `.claude/`, `docs/`, `scripts/` e `.gitignore` para um projeto *novo*.
3. No terminal PowerShell, no diretório **raiz do projeto**, confirme que o gerenciador `uv` está disponível:

   ```powershell
   uv --version
   ```

   Se não estiver, instale por um método oficial e reinicie o terminal, por exemplo:

   ```powershell
   winget install --id astral-sh.uv -e
   ```

4. Ainda na raiz do projeto, instale o Graphify e integre ao Claude:

   ```powershell
   .\scripts\instalar-graphify.ps1
   ```

   O script solicitará aprovação interativa antes de executar a instalação/integração. Se já houver Graphify instalado e precisar adicionar as extensões, use `-Reinstalar` **apenas depois de avaliar o impacto**.
5. No painel Claude Code do VS Code, inicie nova sessão depois de criar `.claude/agents/` e digite:

   ```text
   /graphify .
   ```

   A skill oficial é instalada pelo Graphify. Se a skill não aparecer, confira o terminal, reinicie a sessão Claude Code e execute `graphify --help`.
6. Peça para o Claude executar a skill de diagnóstico:

   ```text
   /diagnosticar-dados Analise a estrutura atual do projeto, fontes de dados, integrações, riscos e primeiros passos. Não altere arquivos.
   ```

## Arquivos importantes

- `CLAUDE.md`: instruções permanentes da sessão principal (orquestração).
- `.claude/agents/*.md`: 7 subagentes especializados persistentes no projeto.
- `.claude/skills/*/SKILL.md`: comandos de diagnóstico, consolidação, auditoria e atualização do grafo.
- `docs/`: dicionário, contratos, decisões, fluxos e contexto empresarial.
- `scripts/verificar-ambiente.ps1`: checagem local não destrutiva.
- `scripts/instalar-graphify.ps1`: instalação/registro oficial, com confirmação.
- `.gitignore`: evita versionar dados brutos, segredos, memórias locais e saídas locais.

## Como o trabalho é distribuído

A **sessão principal Claude Code** lê `CLAUDE.md` e funciona como coordenador. Ela delega tarefas pontuais aos subagentes, cada qual com instruções, permissões e memória própria (`memory: local`). As definições dos agentes persistem em arquivos de projeto, e suas memórias pessoais permanecem no computador, separadas do Git. O histórico da sessão não equivale a um banco de dados.

## Segurança e convivência com repositórios existentes

O instalador não sobrescreve arquivos existentes; preserva `CLAUDE.md`, `.claude/skills/graphify/`, `.claude/settings.json` e os módulos já presentes. Para `.gitignore`, apenas acrescenta as regras novas sem remover as antigas.

Antes de rodar a integração oficial, revise `git status`. A integração Graphify pode criar/editar arquivos de configuração e hooks. Confira o diff antes de fazer commit.

**O grafo não é versionado.** `graphify-out/` (incluindo `graph.json`, `GRAPH_REPORT.md`, `graph.html` e `cache/`) fica fora do Git. Depois de clonar o repositório, instale o Graphify (passos 3 e 4) e reconstrua o grafo localmente com `/graphify .` no Claude Code. Os hooks em `.claude/settings.json` chamam `graphify` pelo PATH, então o executável precisa estar acessível (`uv tool update-shell` e reiniciar o VS Code).

**Nunca use banco de produção ou dados pessoais reais para um teste inicial.** Inicie com amostras anônimas e dados sintéticos.

## Comandos úteis

```powershell
# Verificações locais do kit:
.\scripts\verificar-ambiente.ps1

# Atualização do grafo após alterações aprovadas:
graphify update .

# Consultas ao grafo gerado:
graphify query "Quais módulos dependem do modelo de vendas?"
graphify explain "NomeDoModulo"
graphify path "NomeDaOrigem" "NomeDoDestino"
```

> Não presuma que todos os comandos de consulta funcionarão antes de criar o grafo com `/graphify .`. As funções semânticas de documentos podem depender de backend e de autorização para uso externo.

## Fontes oficiais

- https://github.com/Graphify-Labs/graphify
- https://docs.graphify.com/open-source/installation
- https://code.claude.com/docs/en/sub-agents
- https://code.claude.com/docs/en/skills
- https://code.claude.com/docs/en/vs-code
