"""Hook PreToolUse de governanca do Graphify-Cloud (ETAPA 3E).

Restringe escritas por agente, conforme a matriz aprovada. Sem dependencias externas.
Entrada: JSON do Claude Code via stdin (tool_name, tool_input, agent_type, cwd...).
Saida: exit 0 = segue para as regras de permissao normais; exit 2 = bloqueia (motivo no stderr).

LIMITACAO: a analise de comandos Bash/PowerShell e heuristica (texto do comando). Scripts
gravados em arquivo, caminhos montados dinamicamente ou ofuscacao NAO sao detectados.
Isto NAO e isolamento do sistema operacional.
"""
import json
import os
import re
import sys
from datetime import datetime, timezone

PROTEGIDOS = (
    'data/raw/', '.claude/settings.json', '.claude/settings.local.json', '.claude/agents/',
    '.claude/skills/', '.claude/hooks/', 'claude.md', '.claude/claude.md', '.gitignore', '.git/', '.env',
)
ANALITICOS = {'arquiteto-solucoes', 'qualidade-dados', 'analista-negocios', 'auditor-independente'}
ESCOPO = {
    'engenheiro-dados': ('data/staging/', 'data/curated/', 'data/analytics/', 'outputs/'),
    'desenvolvedor-sistemas': ('scripts/', 'src/', 'tests/', 'outputs/'),
    'especialista-bi': ('data/analytics/', 'outputs/'),
}
FERRAMENTAS_ARQUIVO = {'Edit', 'Write', 'NotebookEdit', 'MultiEdit'}
SHELL = {'Bash', 'PowerShell'}

ESCRITA_SHELL = re.compile(
    r'(^|[\s;&|(])(tee|rm|rmdir|mv|cp|touch|mkdir|truncate|dd|install|ln|chmod|chown|unlink)(\s|$)'
    r'|sed\s+(-[a-z]*i|--in-place)'
    r'|(set-content|add-content|out-file|new-item|remove-item|move-item|copy-item|rename-item|clear-content|export-csv)\b',
    re.I)
ESCRITA_PY = re.compile(
    r"open\([^)]*['\"][^'\"]*[wax+][^'\"]*['\"]"
    r"|\.write_(text|bytes)\(|\.to_(csv|excel|parquet|json|sql)\("
    r"|shutil\.(copy|copy2|copyfile|copytree|move|rmtree)|os\.(remove|unlink|rename|replace|makedirs|mkdir|rmdir)\("
    r"|\.(unlink|mkdir|touch|rename|replace|rmdir)\(",
    re.I)
REDIR_SEGURO = re.compile(r'\d?>&\d|&>\s*/dev/null|\d?>\s*/dev/null|\d?>\s*nul\b', re.I)


def raiz(evento):
    r = os.environ.get('CLAUDE_PROJECT_DIR') or evento.get('cwd') or os.getcwd()
    return r.replace('\\', '/').rstrip('/').lower()


def relativo(caminho, base):
    p = str(caminho or '').replace('\\', '/').lower()
    for pref in (base + '/', '/' + base[0] + base[2:] + '/' if len(base) > 2 and base[1] == ':' else None):
        if pref and p.startswith(pref):
            return p[len(pref):], True
    if re.match(r'^([a-z]:/|/)', p):
        return p, False  # absoluto fora do projeto
    while p.startswith('./'):
        p = p[2:]
    return p, True


def protegido(rel):
    return any(rel == x.rstrip('/') or rel.startswith(x) for x in PROTEGIDOS) or rel.split('/')[-1].startswith('.env')


def registrar(base, evento, decisao, motivo):
    try:
        pasta = os.path.join(base, 'outputs', 'governanca')
        os.makedirs(pasta, exist_ok=True)
        with open(os.path.join(pasta, 'hook_guarda_log.jsonl'), 'a', encoding='utf-8') as f:
            f.write(json.dumps({
                'quando': datetime.now(timezone.utc).isoformat(), 'sessao': evento.get('session_id'),
                'agente': evento.get('agent_type') or 'principal', 'ferramenta': evento.get('tool_name'),
                'alvo': str(evento.get('tool_input', {}).get('file_path') or evento.get('tool_input', {}).get('command') or '')[:300],
                'decisao': decisao, 'motivo': motivo}, ensure_ascii=False) + '\n')
    except Exception:
        pass


def negar(base, evento, motivo):
    registrar(base, evento, 'negado', motivo)
    print('[guarda_agentes] BLOQUEADO: ' + motivo, file=sys.stderr)
    sys.exit(2)


def decidir(evento):
    base = raiz(evento)
    ferramenta = evento.get('tool_name', '')
    entrada = evento.get('tool_input') or {}
    agente = evento.get('agent_type') or ''

    if ferramenta in FERRAMENTAS_ARQUIVO:
        rel, dentro = relativo(entrada.get('file_path') or entrada.get('notebook_path'), base)
        if not dentro:
            negar(base, evento, f'escrita fora do projeto: {rel}')
        if protegido(rel):
            negar(base, evento, f'caminho protegido: {rel}')
        memoria = f'.claude/agent-memory-local/{agente}/'
        if agente in ANALITICOS:
            if not rel.startswith(memoria):
                negar(base, evento, f'{agente} so pode gravar a propria memoria; alvo: {rel}')
        elif agente in ESCOPO:
            if not (rel.startswith(memoria) or any(rel.startswith(x) for x in ESCOPO[agente])):
                negar(base, evento, f'{agente} fora do escopo {ESCOPO[agente]}; alvo: {rel}')
        if rel.startswith('.claude/agent-memory-local/') and agente and not rel.startswith(memoria):
            negar(base, evento, f'{agente} tentou gravar memoria de outro agente: {rel}')
        registrar(base, evento, 'permitido_pelo_hook', 'escrita dentro do escopo (segue para as regras de permissao)')
        return

    if ferramenta in SHELL:
        cmd = str(entrada.get('command') or '')
        baixo = cmd.lower().replace('\\', '/')
        primeira = REDIR_SEGURO.sub('', baixo.split('\n', 1)[0])
        eh_python = re.search(r'(^|[\s;&|(])(python3?|py)(\.exe)?(\s|$)', baixo) is not None
        escrita = bool(ESCRITA_SHELL.search(baixo if not eh_python else primeira)) or ('>' in (primeira if eh_python else REDIR_SEGURO.sub('', baixo)))
        if eh_python and ESCRITA_PY.search(cmd):
            escrita = True
        if not escrita:
            return
        cita_protegido = any(x in baixo for x in ('data/raw', '.claude/', 'claude.md', '.gitignore', '.git/', '.env'))
        if cita_protegido:
            negar(base, evento, 'comando de escrita citando caminho protegido')
        if agente in ANALITICOS:
            negar(base, evento, f'{agente} nao pode executar comandos de escrita')
        registrar(base, evento, 'escrita_shell_nao_classificada', 'segue para aprovacao (hook nao garante o destino)')


def main():
    try:
        evento = json.loads(sys.stdin.read() or '{}')
    except Exception as e:
        print('[guarda_agentes] entrada invalida: ' + str(e), file=sys.stderr)
        sys.exit(2)  # falha fechada
    try:
        decidir(evento)
    except SystemExit:
        raise
    except Exception as e:
        print('[guarda_agentes] erro interno, bloqueando por seguranca: ' + repr(e), file=sys.stderr)
        sys.exit(2)
    sys.exit(0)


if __name__ == '__main__':
    main()
