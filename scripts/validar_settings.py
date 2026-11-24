"""Validador ESTRITO da configuracao de permissoes do Claude Code (FASE 4B.1, ADR-003).

O json padrao aceita chaves repetidas e fica com a ultima, em silencio; este validador as
rejeita. Tambem confere as invariantes de governanca do arquivo compartilhado
(.claude/settings.json) e, se informado, do arquivo local (.claude/settings.local.json).

Uso: python -I -B scripts/validar_settings.py <settings.json> [<settings.local.json>]
Saida: 0 = valido; 1 = violacoes (listadas); 2 = JSON invalido ou chave repetida.

Perfil do arquivo compartilhado:
- base (sempre): regras deny e ask homologadas presentes; allow restrito a uma lista fechada;
  hooks exatamente iguais aos homologados; bypass desligado; escrita fora do projeto
  bloqueada; nenhuma chave desconhecida.
- autonomia (quando ha qualquer regra de autonomia em allow, ou defaultMode acceptEdits):
  regras exatas do executor de testes, protecao do executor, do manifesto e das fixtures,
  leituras do Git endurecidas, confirmacao para interpretadores, rede e Git que altera
  estado, modo auto desligado.
Mudar regra ou hook de proposito exige atualizar este arquivo (e homologar de novo).
"""
import json
import sys

HOOK_GUARDA = 'python -I "$CLAUDE_PROJECT_DIR/.claude/hooks/guarda_agentes.py"'
HOOKS_HOMOLOGADOS = {
    'PreToolUse': [
        {'matcher': 'Edit|Write|NotebookEdit|MultiEdit|Bash|PowerShell',
         'hooks': [{'type': 'command', 'command': HOOK_GUARDA, 'timeout': 10,
                    'onFailure': 'block'}]},
        {'matcher': 'Bash|Grep',
         'hooks': [{'type': 'command', 'command': 'graphify hook-guard search', 'timeout': 10}]},
        {'matcher': 'Read|Glob',
         'hooks': [{'type': 'command', 'command': 'graphify hook-guard read', 'timeout': 10}]},
    ],
    'SessionStart': [
        {'matcher': 'compact',
         'hooks': [{'type': 'command', 'command': 'graphify hook-guard compact', 'timeout': 10}]},
    ],
}
FERRAMENTAS_GUARDA = ('Edit', 'Write', 'NotebookEdit', 'MultiEdit', 'Bash', 'PowerShell')

DENY_BASE = (
    'Edit(./data/raw/**)', 'Edit(./.claude/settings.json)', 'Edit(./.claude/settings.local.json)',
    'Edit(./.claude/agents/**)', 'Edit(./.claude/skills/**)', 'Edit(./.claude/hooks/**)',
    'Edit(./CLAUDE.md)', 'Edit(./.claude/CLAUDE.md)', 'Edit(./.gitignore)', 'Edit(./.git/**)',
    'Read(./.env)', 'Read(./.env.*)', 'Read(./**/*.pem)', 'Read(./**/*.key)',
)
ASK_BASE = (
    'Bash(python:*)', 'Bash(py:*)', 'Bash(powershell:*)', 'Bash(pwsh:*)', 'Bash(sh -c:*)',
    'Bash(bash -c:*)', 'Bash(rm:*)', 'Bash(mv:*)', 'Bash(cp:*)', 'Bash(git commit:*)',
    'Bash(git push:*)', 'Bash(git reset:*)', 'Bash(git checkout:*)', 'Bash(git restore:*)',
    'PowerShell',
)
ALLOW_BASE = (
    'Bash(git status:*)', 'Bash(git diff:*)', 'Bash(git log:*)', 'Bash(graphify query:*)',
    'Bash(graphify explain:*)', 'Bash(graphify path:*)', 'Bash(sha256sum:*)',
    'Edit(./.claude/agent-memory-local/**)',
)

EXECUTOR = 'scripts/testar.sh'
ALLOW_EXECUTOR = tuple(f'Bash(bash scripts/testar.sh {s})' for s in
                       ('motor', 'motor-zoneinfo', 'governanca', 'tudo', 'conferir', 'demo'))
ALLOW_AUTONOMIA = ALLOW_EXECUTOR + (
    'Bash(git show *)', 'Bash(git rev-parse *)', 'Bash(git ls-files *)',
    'Bash(git check-attr *)',
)
DENY_GIT_SAIDA = 'Bash(git *--output*)'  # qualquer subcomando: --output grava arquivo
DENY_AUTONOMIA = (
    'Edit(./**/testar.sh)', 'Edit(./**/homologar.sh)', 'Edit(./**/lib_homologacao.sh)',
    'Edit(./**/homologacao.py)', 'Edit(./**/validar_settings.py)',
    'Edit(./**/homologacao.manifest)', 'Edit(./tests/fixtures/**)', 'Edit(./.gitattributes)',
    'Edit(./.claude/commands/**)', 'Edit(./.mcp.json)', 'Edit(./.vscode/**)',
    DENY_GIT_SAIDA,
    'Bash(git diff *--ext-diff*)', 'Bash(git log *--ext-diff*)', 'Bash(git show *--ext-diff*)',
    'Bash(git diff *--no-index*)', 'Bash(git diff *.env*)',
)
ASK_AUTONOMIA = (
    'Bash(bash scripts/homologar.sh:*)',
    # interpretadores e execucao indireta
    'Bash(python3:*)', 'Bash(python.exe:*)', 'Bash(pythonw:*)', 'Bash(py.exe:*)',
    'Bash(node:*)', 'Bash(npx:*)', 'Bash(perl:*)', 'Bash(ruby:*)', 'Bash(sh:*)',
    'Bash(source:*)', 'Bash(eval:*)', 'Bash(env:*)', 'Bash(xargs:*)', 'Bash(cmd:*)',
    'Bash(cmd.exe:*)',
    # instalacao e rede
    'Bash(pip:*)', 'Bash(pip3:*)', 'Bash(npm:*)', 'Bash(curl:*)', 'Bash(wget:*)',
    # escrita por shell que o modo acceptEdits aprovaria sozinho ou que o hook nao ve
    'Bash(sed:*)', 'Bash(tee:*)', 'Bash(rmdir:*)', 'Bash(ln:*)', 'Bash(dd:*)',
    # Git que altera estado, configuracao ou diretorio de trabalho
    'Bash(git add:*)', 'Bash(git pull:*)', 'Bash(git fetch:*)', 'Bash(git clone:*)',
    'Bash(git switch:*)', 'Bash(git branch:*)', 'Bash(git merge:*)', 'Bash(git rebase:*)',
    'Bash(git stash:*)', 'Bash(git config:*)', 'Bash(git clean:*)', 'Bash(git rm:*)',
    'Bash(git mv:*)', 'Bash(git apply:*)', 'Bash(git am:*)', 'Bash(git worktree:*)',
    'Bash(git init:*)', 'Bash(git remote:*)', 'Bash(git submodule:*)',
    'Bash(git update-index:*)', 'Bash(git tag:*)', 'Bash(git cherry-pick:*)',
    'Bash(git revert:*)', 'Bash(git -c:*)', 'Bash(git -C:*)',
)

CHAVES_RAIZ = {'permissions', 'hooks', '$schema'}
CHAVES_PERMISSOES = {'deny', 'ask', 'allow', 'defaultMode', 'disableAutoMode',
                     'disableBypassPermissionsMode', 'blockWritesOutsideWorkingDirectories'}
MODOS_PROIBIDOS = ('bypassPermissions', 'auto')
MODOS_ACEITOS = (None, 'default', 'acceptEdits', 'plan')

# Arquivo local (.claude/settings.local.json): so listas de permissao, sem liberacao ampla.
CHAVES_RAIZ_LOCAL = {'permissions', '$schema'}
CHAVES_PERMISSOES_LOCAL = {'allow', 'ask', 'deny'}
FERRAMENTAS_SEM_FILTRO = {'Bash', 'Edit', 'Write', 'MultiEdit', 'NotebookEdit', 'PowerShell'}
COMANDOS_SENSIVEIS = {
    'python', 'python3', 'pythonw', 'py', 'pip', 'pip3', 'node', 'npm', 'npx', 'perl', 'ruby',
    'php', 'awk', 'gawk', 'bash', 'sh', 'zsh', 'dash', 'cmd', 'powershell', 'pwsh', 'env',
    'xargs', 'source', 'eval', 'exec', 'find', 'sed', 'tee', 'dd', 'ln', 'rm', 'rmdir', 'mv',
    'cp', 'curl', 'wget', 'ssh', 'scp', 'make', 'timeout', 'nohup', 'time', 'command',
}
GIT_SOMENTE_LEITURA = {'status', 'diff', 'log', 'show', 'rev-parse', 'ls-files', 'check-attr',
                       'blame', 'describe'}


class ChaveRepetida(ValueError):
    pass


def _sem_repeticao(pares):
    vistas = set()
    for chave, _ in pares:
        if chave in vistas:
            raise ChaveRepetida(f'chave JSON repetida: {chave!r}')
        vistas.add(chave)
    return dict(pares)


def carregar_texto(texto):
    """Interpreta o JSON rejeitando chaves repetidas em qualquer nivel."""
    cfg = json.loads(texto, object_pairs_hook=_sem_repeticao)
    if not isinstance(cfg, dict):
        raise ValueError('a raiz da configuracao deve ser um objeto JSON')
    return cfg


def carregar(caminho):
    with open(caminho, encoding='utf-8') as f:
        return carregar_texto(f.read())


def _lista(perm, nome, achados, prefixo=''):
    valor = perm.get(nome, [])
    if not isinstance(valor, list) or not all(isinstance(r, str) for r in valor):
        achados.append(f'{prefixo}{nome} deve ser uma lista de textos')
        return []
    achados += [f'{prefixo}{nome}: regra repetida {r!r}'
                for r in sorted({r for r in valor if valor.count(r) > 1})]
    return valor


def autonomia_ativa(cfg):
    perm = cfg.get('permissions', {})
    if not isinstance(perm, dict):
        return False
    allow = [r for r in perm.get('allow', []) if isinstance(r, str)]
    return (perm.get('defaultMode') == 'acceptEdits'
            or any(r in ALLOW_AUTONOMIA or EXECUTOR in r for r in allow))


def _violacoes_hooks(cfg):
    hooks = cfg.get('hooks')
    if not isinstance(hooks, dict):
        return ['hooks ausentes']
    if hooks == HOOKS_HOMOLOGADOS:
        return []
    v = ['hooks diferentes dos homologados (evento, matcher, comando ou chave a mais ou a menos)']
    grupos = [g for g in hooks.get('PreToolUse', []) if isinstance(g, dict)]
    guardas = [(g, h) for g in grupos for h in g.get('hooks', [])
               if isinstance(h, dict) and 'guarda_agentes' in str(h.get('command', ''))]
    if len(guardas) != 1:
        v.append(f'hook guarda_agentes deve aparecer exatamente 1 vez (achado {len(guardas)})')
    else:
        grupo, hook = guardas[0]
        if hook.get('command') != HOOK_GUARDA or hook.get('type') != 'command':
            v.append('hook guarda_agentes: comando diferente do homologado')
        if hook.get('onFailure') != 'block':
            v.append('hook guarda_agentes deve ter onFailure = block (falha fechada)')
        cobertas = str(grupo.get('matcher', '')).split('|')
        v += [f'hook guarda_agentes nao cobre {f}' for f in FERRAMENTAS_GUARDA
              if f not in cobertas]
    return v


def violacoes_projeto(cfg):
    """Violacoes do arquivo compartilhado (.claude/settings.json)."""
    v = [f'chave desconhecida na raiz: {k}' for k in sorted(set(cfg) - CHAVES_RAIZ)]
    perm = cfg.get('permissions')
    if not isinstance(perm, dict):
        return v + ['permissions ausente']
    v += [f'chave desconhecida em permissions: {k}' for k in sorted(set(perm) - CHAVES_PERMISSOES)]
    deny, ask, allow = (_lista(perm, n, v) for n in ('deny', 'ask', 'allow'))
    v += [f'deny sem a regra obrigatoria {r}' for r in DENY_BASE if r not in deny]
    v += [f'ask sem a regra obrigatoria {r}' for r in ASK_BASE if r not in ask]
    permitidos = set(ALLOW_BASE) | set(ALLOW_AUTONOMIA)
    v += [f'allow fora da lista homologada: {r}' for r in allow if r not in permitidos]
    if perm.get('disableBypassPermissionsMode') != 'disable':
        v.append('disableBypassPermissionsMode deve ser "disable"')
    if perm.get('blockWritesOutsideWorkingDirectories') is not True:
        v.append('blockWritesOutsideWorkingDirectories deve ser true')
    modo = perm.get('defaultMode')
    if modo in MODOS_PROIBIDOS:
        v.append(f'modo proibido em defaultMode: {modo}')
    elif modo not in MODOS_ACEITOS:
        v.append(f'defaultMode desconhecido: {modo!r}')
    if perm.get('disableAutoMode', 'disable') != 'disable':
        v.append('disableAutoMode, se presente, deve ser "disable"')
    v += _violacoes_hooks(cfg)
    if autonomia_ativa(cfg):
        v += [f'autonomia: allow sem a regra exata {r}' for r in ALLOW_EXECUTOR[:4]
              if r not in allow]
        v += [f'autonomia: deny sem a regra obrigatoria {r}' for r in DENY_AUTONOMIA
              if r not in deny]
        v += [f'autonomia: ask sem a regra obrigatoria {r}' for r in ASK_AUTONOMIA
              if r not in ask]
        if perm.get('disableAutoMode') != 'disable':
            v.append('autonomia: disableAutoMode deve ser "disable"')
    return v


def avisos_projeto(cfg):
    """Fragilidades conhecidas que nao invalidam a configuracao base homologada."""
    perm = cfg.get('permissions', {})
    deny = perm.get('deny', []) if isinstance(perm, dict) else []
    if DENY_GIT_SAIDA not in deny:
        return [f'sem {DENY_GIT_SAIDA}: "git diff/log --output=<arquivo>" grava sem confirmacao '
                '(corrigido no perfil autonomia)']
    return []


def _regra_local_ampla(regra):
    if regra in FERRAMENTAS_SEM_FILTRO:
        return True
    if '(' not in regra or not regra.endswith(')'):
        return False
    ferramenta, corpo = regra[:-1].split('(', 1)
    if ferramenta == 'PowerShell':
        return True
    if ferramenta in ('Edit', 'Write'):
        return corpo.strip() in ('*', '**', './**', '/**', '//**', '~/**')
    if ferramenta != 'Bash':
        return False
    corpo = corpo.strip()
    palavras = (corpo[:-2] if corpo.endswith(':*') else corpo).split()
    if not palavras or palavras[0].startswith('*'):
        return True
    comando = palavras[0].replace('\\', '/').rsplit('/', 1)[-1].lower()
    if comando.endswith('.exe'):
        comando = comando[:-4]
    if comando == 'git':  # leituras do Git podem ser liberadas localmente; o resto, nao
        return len(palavras) < 2 or palavras[1] not in GIT_SOMENTE_LEITURA
    return comando in COMANDOS_SENSIVEIS


def violacoes_local(cfg):
    """Violacoes do arquivo local (.claude/settings.local.json)."""
    v = [f'local: chave nao permitida na raiz: {k}' for k in sorted(set(cfg) - CHAVES_RAIZ_LOCAL)]
    perm = cfg.get('permissions', {})
    if not isinstance(perm, dict):
        return v + ['local: permissions deve ser um objeto']
    v += [f'local: chave nao permitida em permissions: {k}'
          for k in sorted(set(perm) - CHAVES_PERMISSOES_LOCAL)]
    allow = _lista(perm, 'allow', v, 'local: ')
    v += [f'local: allow amplo ou de comando sensivel: {r}' for r in allow
          if _regra_local_ampla(r)]
    return v


def validar_arquivo(caminho, local=False):
    """(codigo, mensagens): 0 valido, 1 violacoes, 2 JSON invalido ou chave repetida."""
    try:
        cfg = carregar(caminho)
    except (ValueError, OSError) as e:  # JSONDecodeError e ChaveRepetida derivam de ValueError
        return 2, [f'INVALIDO: {e}']
    achados = violacoes_local(cfg) if local else violacoes_projeto(cfg)
    return (1 if achados else 0), [f'VIOLACAO: {a}' for a in achados]


def main(argv):
    if len(argv) not in (2, 3):
        print(__doc__, file=sys.stderr)
        return 2
    pior = 0
    for indice, caminho in enumerate(argv[1:]):
        local = indice == 1
        rotulo = 'local' if local else 'projeto'
        codigo, mensagens = validar_arquivo(caminho, local=local)
        for m in mensagens:
            print(f'[{rotulo}] {m}', file=sys.stderr)
        if codigo == 0:
            perfil = ''
            if not local:
                cfg = carregar(caminho)
                perfil = ' (perfil autonomia)' if autonomia_ativa(cfg) else ' (perfil base)'
                for aviso in avisos_projeto(cfg):
                    print(f'[{rotulo}] AVISO: {aviso}', file=sys.stderr)
            print(f'[{rotulo}] configuracao valida{perfil}')
        pior = max(pior, codigo)
    return pior


if __name__ == '__main__':
    sys.exit(main(sys.argv))
