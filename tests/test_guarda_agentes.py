"""Suite deterministica do hook .claude/hooks/guarda_agentes.py (ETAPAS 3G/3H).

Executa o hook como subprocesso, com eventos sinteticos no stdin. Todos os alvos ficam
em diretorios temporarios: um projeto falso (CLAUDE_PROJECT_DIR) e uma pasta pessoal falsa
(USERPROFILE/HOME). Nenhum arquivo real de configuracao e lido como alvo nem alterado.
O hook nunca grava os alvos; ele so decide. A unica escrita dele e o log no projeto falso.

Uso:   python -I tests/test_guarda_agentes.py
Outro: GUARDA_HOOK=<caminho do hook> python -I tests/test_guarda_agentes.py
Saida: uma linha por caso (PASS/FAIL/SKIP) e exit 1 se algum caso falhar.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

RAIZ_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.environ.get('GUARDA_HOOK') or os.path.join(RAIZ_REPO, '.claude', 'hooks', 'guarda_agentes.py')

NEGA, SEGUE = 2, 0


def preparar():
    tmp = tempfile.mkdtemp(prefix='guarda_teste_')
    proj = os.path.join(tmp, 'projeto')
    casa = os.path.join(tmp, 'casa')
    planos = os.path.join(casa, '.claude', 'plans')
    fora = os.path.join(tmp, 'fora')
    for d in (proj, planos, fora):
        os.makedirs(d)
    return tmp, proj, casa, planos, fora


def barra(p):
    return p.replace('\\', '/')


def main():
    tmp, proj, casa, planos, fora = preparar()
    env = dict(os.environ, CLAUDE_PROJECT_DIR=proj, USERPROFILE=casa, HOME=casa)
    log = os.path.join(proj, 'outputs', 'governanca', 'hook_guarda_log.jsonl')
    P = barra(proj)
    PL = barra(planos)

    def ev(tool, agente='', agent_id=None, **inp):
        e = {'tool_name': tool, 'tool_input': inp, 'cwd': proj, 'session_id': 'teste'}
        if agente:
            e['agent_type'] = agente
        if agent_id:
            e['agent_id'] = agent_id
        return json.dumps(e)

    def bash(cmd, agente=''):
        return ev('Bash', agente, command=cmd)

    # Destinos simbolicos dentro da pasta de planos apontando para fora.
    juncao, simbolico = os.path.join(planos, 'juncao.md'), os.path.join(planos, 'link.md')
    pula_juncao = pula_link = None
    try:
        import _winapi
        _winapi.CreateJunction(fora, juncao)
    except Exception as e:  # nao Windows ou sem suporte
        try:
            os.symlink(fora, juncao, target_is_directory=True)
        except Exception as e2:
            pula_juncao = f'juncao/symlink de diretorio indisponivel: {e!r} / {e2!r}'
    alvo_fora = os.path.join(fora, 'alvo.md')
    with open(alvo_fora, 'w', encoding='utf-8') as f:
        f.write('alvo externo de teste\n')
    try:
        os.symlink(alvo_fora, simbolico)
    except Exception as e:
        pula_link = f'symlink de arquivo exige modo desenvolvedor/privilegio no Windows: {e!r}'

    casos = [
        # --- Regex ESCRITA_PY: leituras nao podem ser bloqueadas ---
        ('R00 leitura open(var, encoding=) com aspas apos o )', bash("python -c \"hook = '.claude/hooks/x.py'; src = open(hook, encoding='utf-8').read(); print('sintaxe OK')\""), SEGUE),
        ('R01 leitura open() simples citando .claude/', bash("python -c \"print(open('.claude/settings.json').read())\""), SEGUE),
        ('R02 leitura open() de data/raw com newline=', bash("python -c \"import csv; r = list(csv.reader(open('data/raw/vendas.csv', newline='')))\""), SEGUE),
        ('R03 leitura com encoding= e aspas depois do )', bash("python -c \"import json; json.load(open('.claude/settings.json', encoding='utf-8')); data = 1; print('ok')\""), SEGUE),
        ('R04 leitura modo explicito r', bash("python -c \"print(open('data/raw/vendas.csv', 'r', encoding='utf-8').read())\""), SEGUE),
        ('R05 leitura modo rb', bash("python -c \"print(len(open('data/raw/vendas.csv', 'rb').read()))\""), SEGUE),
        # --- Regex ESCRITA_PY: escritas continuam detectadas ---
        ('R06 escrita modo w em data/raw', bash("python -c \"open('data/raw/x.csv','w').write('x')\""), NEGA),
        ('R07 escrita mode=a em data/raw', bash("python -c \"f = open('data/raw/x.csv', mode='a')\""), NEGA),
        ('R08 escrita modo r+ em data/raw', bash("python -c \"f = open('data/raw/x.csv', 'r+')\""), NEGA),
        ('R09 escrita modo wb citando .claude/', bash("python -c \"open('.claude/settings.json', 'wb')\""), NEGA),
        ('R10 escrita Path.open(w) em data/raw', bash("python -c \"import pathlib; pathlib.Path('data/raw/x.csv').open('w')\""), NEGA),
        ('R11 escrita modo x em data/raw', bash("python -c \"open('data/raw/novo.csv', 'x')\""), NEGA),
        ('R12 write_text em data/raw', bash("python -c \"import pathlib; pathlib.Path('data/raw/x.csv').write_text('x')\""), NEGA),
        ('R13 analitico python w em outputs', bash("python -c \"open('outputs/x.txt','w').write('x')\"", 'qualidade-dados'), NEGA),
        # --- Redirecionamento e shell (regras atuais) ---
        ('S01 append em data/raw (engenheiro)', bash('echo x >> data/raw/demo.txt', 'engenheiro-dados'), NEGA),
        ('S02 redirecionamento por analitico', bash('echo t > outputs/a.txt', 'qualidade-dados'), NEGA),
        ('S03 leitura com 2>&1 por analitico', bash('git log 2>&1', 'qualidade-dados'), SEGUE),
        ('S04 git status principal', bash('git status'), SEGUE),
        ('S05 rm citando .claude/', bash('rm .claude/agents/x.md'), NEGA),
        # --- Excecao de planos ---
        ('P01 plano valido Write principal', ev('Write', file_path=PL + '/plano-valido-3h.md', content='x'), SEGUE),
        ('P02 plano valido Edit principal', ev('Edit', file_path=PL + '/plano-valido-3h.md', old_string='a', new_string='b'), SEGUE),
        ('P03 plano por subagente (agent_type)', ev('Write', 'Plan', file_path=PL + '/plano-valido-3h.md', content='x'), NEGA),
        ('P04 plano por subagente (so agent_id)', ev('Write', agent_id='abc123', file_path=PL + '/plano-valido-3h.md', content='x'), NEGA),
        ('P05 plano por agente do projeto', ev('Write', 'engenheiro-dados', file_path=PL + '/plano-valido-3h.md', content='x'), NEGA),
        ('P06 arquivo fora da pasta de planos', ev('Write', file_path=barra(casa) + '/.claude/outro.md', content='x'), NEGA),
        ('P07 settings pessoal fora de plans', ev('Write', file_path=barra(casa) + '/.claude/settings.json', content='x'), NEGA),
        ('P08 subdiretorio de plans', ev('Write', file_path=PL + '/sub/plano.md', content='x'), NEGA),
        ('P09 traversal plans/../', ev('Write', file_path=PL + '/../settings.json', content='x'), NEGA),
        ('P10 traversal para pasta irma', ev('Write', file_path=PL + '/../plans-mal/plano.md', content='x'), NEGA),
        ('P11 nome invalido (maiusculas)', ev('Write', file_path=PL + '/Plano.md', content='x'), NEGA),
        ('P12 nome invalido (extensao .txt)', ev('Write', file_path=PL + '/plano.txt', content='x'), NEGA),
        ('P13 nome invalido (sublinhado)', ev('Write', file_path=PL + '/plano_x.md', content='x'), NEGA),
        ('P14 NotebookEdit em plans', ev('NotebookEdit', notebook_path=PL + '/plano.md'), NEGA),
        ('P15 MultiEdit em plans', ev('MultiEdit', file_path=PL + '/plano.md'), NEGA),
        ('P16 juncao em plans apontando para fora', ev('Write', file_path=PL + '/juncao.md', content='x'), NEGA, pula_juncao),
        ('P17 symlink de arquivo apontando para fora', ev('Write', file_path=PL + '/link.md', content='x'), NEGA, pula_link),
        ('P18 Bash redirecionando para plans', bash(f'echo x > {PL}/plano.md'), NEGA),
        ('P19 PowerShell Set-Content em plans', ev('PowerShell', command=f'Set-Content -Path "{planos}\\plano.md" -Value x'), NEGA),
        ('P20 python w em plans', bash(f"python -c \"open('{PL}/plano.md','w').write('x')\""), NEGA),
        # --- Memorias e caminhos protegidos ---
        ('M01 analitico grava propria memoria', ev('Write', 'qualidade-dados', file_path=P + '/.claude/agent-memory-local/qualidade-dados/n.md'), SEGUE),
        ('M02 auditor grava memoria alheia', ev('Write', 'auditor-independente', file_path=P + '/.claude/agent-memory-local/qualidade-dados/n.md'), NEGA),
        ('M03 analitico grava outputs', ev('Write', 'qualidade-dados', file_path=P + '/outputs/x.txt'), NEGA),
        ('M04 engenheiro edita data/raw', ev('Edit', 'engenheiro-dados', file_path=P + '/data/raw/x.csv'), NEGA),
        ('M05 dev grava .claude/agents', ev('Write', 'desenvolvedor-sistemas', file_path=P + '/.claude/agents/x.md'), NEGA),
        ('M06 principal grava settings.json do projeto', ev('Write', file_path=P + '/.claude/settings.json'), NEGA),
        ('M07 principal grava CLAUDE.md', ev('Edit', file_path=P + '/CLAUDE.md'), NEGA),
        ('M08 bi grava data/curated', ev('Write', 'especialista-bi', file_path=P + '/data/curated/x.csv'), NEGA),
        ('M09 bi grava data/analytics', ev('Write', 'especialista-bi', file_path=P + '/data/analytics/x.csv'), SEGUE),
        ('M10 engenheiro grava data/staging', ev('Write', 'engenheiro-dados', file_path=P + '/data/staging/x.csv'), SEGUE),
        ('M11 principal grava fora do projeto', ev('Write', file_path='c:/windows/temp/x.txt'), NEGA),
        # --- Entradas invalidas (falha fechada) ---
        ('X01 JSON invalido', '{nao-json', NEGA),
        ('X02 JSON que nao e objeto', '[]', NEGA),
    ]

    falhas = pulos = 0
    for caso in casos:
        nome, entrada, esperado = caso[:3]
        pular = caso[3] if len(caso) > 3 else None
        if pular:
            pulos += 1
            print(f'SKIP {nome} | {pular}')
            continue
        r = subprocess.run([sys.executable, '-I', HOOK], input=entrada, text=True,
                           capture_output=True, env=env, timeout=30)
        ok = r.returncode == esperado
        if ok and nome.startswith('P01'):
            # A decisao do plano valido precisa constar no log de governanca.
            with open(log, encoding='utf-8') as f:
                ultima = json.loads(f.read().splitlines()[-1])
            ok = ultima.get('decisao') == 'permitido_plano'
            if not ok:
                print(f'     log sem permitido_plano: {ultima}')
        falhas += not ok
        print(f"{'PASS' if ok else 'FAIL'} {nome} | exit {r.returncode} esperado {esperado} | {r.stderr.strip()[:100]}")

    # Nenhum alvo pode ter sido criado ou alterado pelo hook.
    criados = [p for p in (os.path.join(planos, 'plano-valido-3h.md'), os.path.join(fora, 'settings.json')) if os.path.exists(p)]
    with open(alvo_fora, encoding='utf-8') as f:
        intacto = f.read() == 'alvo externo de teste\n'
    if criados or not intacto:
        falhas += 1
        print(f'FAIL Z01 hook nao grava alvos | criados={criados} alvo_externo_intacto={intacto}')
    else:
        print('PASS Z01 hook nao grava alvos')

    print(f'HOOK {HOOK}')
    print(f'TOTAL {len(casos) + 1} casos | {falhas} falhas | {pulos} pulados')
    shutil.rmtree(tmp, ignore_errors=True)
    sys.exit(1 if falhas else 0)


if __name__ == '__main__':
    main()
