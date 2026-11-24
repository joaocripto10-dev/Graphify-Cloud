"""FASE 4B.1 (ADR-003): seguranca da autonomia controlada. Testes SIMULADOS e deterministicos.

Cobrem o validador estrito de settings (inclusive os dois incidentes reais de corrupcao), o
manifesto de homologacao e o executor scripts/testar.sh numa COPIA temporaria do repositorio.
Nao exercitam o Claude Code: a matriz efetiva de permissoes (pedido de confirmacao, bloqueio,
execucao automatica) roda no VS Code e fica registrada fora desta suite.
Uso: bash scripts/testar.sh motor   (ou python -I -B -m unittest discover -s tests)
"""
import copy
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

RAIZ_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPTS = os.path.join(RAIZ_REPO, 'scripts')
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import homologacao as H  # noqa: E402
import validar_settings as V  # noqa: E402

SETTINGS = os.path.join(RAIZ_REPO, '.claude', 'settings.json')


def _remover_arvore(caminho):
    def _forcar(funcao, alvo, _exc):
        os.chmod(alvo, stat.S_IWRITE)
        funcao(alvo)
    if os.path.exists(caminho):
        shutil.rmtree(caminho, onexc=_forcar)


def _criar_juncao(alvo, link):
    """Juncao (Windows) ou symlink de diretorio; devolve None ou o motivo da falha."""
    try:
        import _winapi
        _winapi.CreateJunction(alvo, link)
        return None
    except Exception as e1:  # nao Windows ou sem suporte
        try:
            os.symlink(alvo, link, target_is_directory=True)
            return None
        except Exception as e2:
            return f'juncao/symlink indisponivel: {e1!r} / {e2!r}'


def instalada():
    return V.carregar(SETTINGS)


def base(cfg):
    """A configuracao sem nenhuma regra de autonomia (perfil base)."""
    c = copy.deepcopy(cfg)
    p = c['permissions']
    p['allow'] = [r for r in p['allow'] if r not in V.ALLOW_AUTONOMIA]
    p['deny'] = [r for r in p['deny'] if r not in V.DENY_AUTONOMIA]
    p['ask'] = [r for r in p['ask'] if r not in V.ASK_AUTONOMIA]
    p.pop('defaultMode', None)
    p.pop('disableAutoMode', None)
    return c


def autonomia(cfg):
    """A configuracao com todas as regras de autonomia (perfil candidato)."""
    c = base(cfg)
    p = c['permissions']
    p['allow'] += list(V.ALLOW_AUTONOMIA)
    p['deny'] += list(V.DENY_AUTONOMIA)
    p['ask'] += list(V.ASK_AUTONOMIA)
    p['defaultMode'] = 'acceptEdits'
    p['disableAutoMode'] = 'disable'
    return c


class _CasoValidador(unittest.TestCase):

    def setUp(self):
        self.cfg = instalada()

    def assert_viola(self, cfg, trecho):
        achados = V.violacoes_projeto(cfg)
        self.assertTrue(any(trecho in a for a in achados), f'{trecho!r} nao acusado: {achados}')

    def alterada(self, perfil, funcao):
        c = perfil(self.cfg)
        funcao(c)
        return c


class TestValidadorProjeto(_CasoValidador):
    """Perfil base: o que a configuracao compartilhada nunca pode perder."""

    def test_configuracao_instalada_e_valida(self):
        self.assertEqual(V.validar_arquivo(SETTINGS), (0, []))

    def test_perfis_base_e_autonomia_sao_validos(self):
        self.assertEqual(V.violacoes_projeto(base(self.cfg)), [])
        self.assertEqual(V.violacoes_projeto(autonomia(self.cfg)), [])
        self.assertFalse(V.autonomia_ativa(base(self.cfg)))
        self.assertTrue(V.autonomia_ativa(autonomia(self.cfg)))

    def test_incidente_1_chave_ask_duplicada(self):
        """16/11/2026: segunda chave "ask"; o json padrao aceitou e python saiu de ask."""
        c = base(self.cfg)
        originais = c['permissions']['ask']
        c['permissions']['ask'] = ['MARCA_PRIMEIRA_ASK']
        texto = json.dumps(c, indent=2).replace(
            '"ask": [\n      "MARCA_PRIMEIRA_ASK"\n    ],',
            '"ask": [\n      "Bash(python -I -m unittest discover -s tests *)"\n    ],\n'
            '    "ask": ' + json.dumps([r for r in originais if r != 'Bash(python:*)']) + ',')
        self.assertEqual(texto.count('"ask":'), 2)
        silencioso = json.loads(texto)  # o parser padrao nao reclama
        self.assertNotIn('Bash(python:*)', silencioso['permissions']['ask'])
        with self.assertRaises(V.ChaveRepetida):
            V.carregar_texto(texto)

    def test_incidente_2_json_invalido_por_virgula_ausente(self):
        """17/11/2026: regras inseridas em allow sem virgula; o arquivo inteiro foi pulado."""
        c = base(self.cfg)
        c['permissions']['ask'].remove('Bash(python:*)')
        primeira = c['permissions']['allow'][0]
        texto = json.dumps(c, indent=2).replace(
            f'"allow": [\n      "{primeira}"',
            '"allow": [\n      "Bash(python -I -m unittest discover -s tests *)"\n'
            f'      "{primeira}"')
        with self.assertRaises(json.JSONDecodeError):
            V.carregar_texto(texto)
        with tempfile.TemporaryDirectory(prefix='settings_invalido_') as tmp:
            caminho = os.path.join(tmp, 'settings.json')
            with open(caminho, 'w', encoding='utf-8') as f:
                f.write(texto)
            self.assertEqual(V.validar_arquivo(caminho)[0], 2)

    def test_incidente_2_conteudo_tambem_e_recusado_se_o_json_fosse_valido(self):
        def alterar(c):
            c['permissions']['ask'].remove('Bash(python:*)')
            c['permissions']['allow'].insert(0, 'Bash(python -I -m unittest discover -s tests *)')
        c = self.alterada(base, alterar)
        self.assert_viola(c, 'ask sem a regra obrigatoria Bash(python:*)')
        self.assert_viola(c, 'allow fora da lista homologada')

    def test_chave_repetida_em_qualquer_nivel(self):
        texto = json.dumps(base(self.cfg), indent=2)
        for chave in ('"permissions": {', '"hooks": {', '"deny": [', '"PreToolUse": ['):
            with self.subTest(chave=chave):
                fecho = '}' if chave.endswith('{') else ']'
                repetido = texto.replace(chave, chave + fecho + ',\n' + chave, 1)
                with self.assertRaises(V.ChaveRepetida):
                    V.carregar_texto(repetido)

    def test_remocao_de_qualquer_regra_obrigatoria(self):
        for lista, regras in (('deny', V.DENY_BASE), ('ask', V.ASK_BASE)):
            for regra in regras:
                with self.subTest(lista=lista, regra=regra):
                    c = self.alterada(base, lambda c: c['permissions'][lista].remove(regra))
                    self.assert_viola(c, f'{lista} sem a regra obrigatoria {regra}')

    def test_liberacoes_amplas_ou_fora_da_lista(self):
        for regra in ('Bash', 'Bash(*)', 'Bash(python *)', 'Bash(python:*)',
                      'Bash(python -I -B -m unittest discover -s tests *)',
                      'Bash(bash scripts/testar.sh *)', 'Bash(bash scripts/testar.sh arquivo *)',
                      'Bash(bash scripts/homologar.sh)', 'Bash(bash *)', 'Bash(git *)',
                      'Bash(git push:*)', 'Bash(rm:*)', 'Edit', 'Write(./**)', 'PowerShell',
                      'Bash(curl *)', 'Bash(git rev-list *)', 'Bash(git cat-file *)',
                      'Bash(graphify update .)', 'Bash(sed *)'):
            with self.subTest(regra=regra):
                c = self.alterada(autonomia, lambda c: c['permissions']['allow'].append(regra))
                self.assert_viola(c, f'allow fora da lista homologada: {regra}')

    def test_hooks_ausentes_ou_enfraquecidos(self):
        def guarda(c):
            return c['hooks']['PreToolUse'][0]
        casos = {
            'hooks ausentes': lambda c: c.pop('hooks'),
            'exatamente 1 vez (achado 0)': lambda c: c['hooks']['PreToolUse'].pop(0),
            'exatamente 1 vez (achado 2)':
                lambda c: c['hooks']['PreToolUse'].append(copy.deepcopy(guarda(c))),
            'onFailure = block': lambda c: guarda(c)['hooks'][0].pop('onFailure'),
            'nao cobre Bash': lambda c: guarda(c).__setitem__(
                'matcher', 'Edit|Write|NotebookEdit|MultiEdit|PowerShell'),
            'nao cobre Write': lambda c: guarda(c).__setitem__(
                'matcher', 'Edit|NotebookEdit|MultiEdit|Bash|PowerShell'),
            'comando diferente do homologado': lambda c: guarda(c)['hooks'][0].__setitem__(
                'command', 'python -I "$CLAUDE_PROJECT_DIR/outputs/guarda_agentes.py"'),
        }
        # Qualquer diferenca em relacao aos hooks homologados e recusada (auditoria 4B.1, M4).
        diferentes = {
            'hook do Graphify removido': lambda c: c['hooks']['PreToolUse'].pop(2),
            'chave async no hook guarda': lambda c: guarda(c)['hooks'][0].__setitem__('async', True),
            'chave if no hook guarda': lambda c: guarda(c)['hooks'][0].__setitem__('if', 'false'),
            'timeout alterado': lambda c: guarda(c)['hooks'][0].__setitem__('timeout', 1),
            'matcher com sobra': lambda c: guarda(c).__setitem__(
                'matcher', 'Edit|Write|NotebookEdit|MultiEdit|Bash|PowerShell|Read'),
            'evento adicional': lambda c: c['hooks'].__setitem__('PostToolUse', [
                {'matcher': 'Bash', 'hooks': [{'type': 'command', 'command': 'echo x'}]}]),
            'segundo hook no grupo guarda': lambda c: guarda(c)['hooks'].append(
                {'type': 'command', 'command': 'echo x'}),
        }
        for nome, alterar in diferentes.items():
            with self.subTest(caso=nome):
                self.assert_viola(self.alterada(base, alterar),
                                  'hooks diferentes dos homologados')
        self.assertEqual(self.cfg['hooks'], V.HOOKS_HOMOLOGADOS)
        self.assertIn('guarda_agentes', guarda(self.cfg)['hooks'][0]['command'])
        for trecho, alterar in casos.items():
            with self.subTest(caso=trecho):
                self.assert_viola(self.alterada(base, alterar), trecho)

    def test_modos_proibidos_e_chaves_de_seguranca(self):
        def perm(chave, valor):
            return lambda c: c['permissions'].__setitem__(chave, valor)
        casos = {
            'modo proibido em defaultMode: bypassPermissions': perm('defaultMode',
                                                                   'bypassPermissions'),
            'modo proibido em defaultMode: auto': perm('defaultMode', 'auto'),
            'defaultMode desconhecido': perm('defaultMode', 'qualquer'),
            'disableBypassPermissionsMode deve ser': perm('disableBypassPermissionsMode', 'enable'),
            'blockWritesOutsideWorkingDirectories deve ser true':
                perm('blockWritesOutsideWorkingDirectories', False),
            'disableAutoMode, se presente': perm('disableAutoMode', 'enable'),
            'chave desconhecida em permissions: additionalDirectories':
                perm('additionalDirectories', ['C:/']),
            'chave desconhecida na raiz: disableAllHooks':
                lambda c: c.__setitem__('disableAllHooks', True),
            'chave desconhecida na raiz: env': lambda c: c.__setitem__('env', {}),
        }
        for trecho, alterar in casos.items():
            with self.subTest(caso=trecho):
                self.assert_viola(self.alterada(base, alterar), trecho)
        for chave in ('disableBypassPermissionsMode', 'blockWritesOutsideWorkingDirectories'):
            with self.subTest(removida=chave):
                self.assert_viola(self.alterada(base, lambda c: c['permissions'].pop(chave)),
                                  chave)


class TestValidadorAutonomia(_CasoValidador):
    """Perfil autonomia: exigido sempre que houver regra do executor de testes em allow."""

    def test_remocao_de_protecao_ou_de_confirmacao(self):
        for lista, regras in (('deny', V.DENY_AUTONOMIA), ('ask', V.ASK_AUTONOMIA)):
            for regra in regras:
                with self.subTest(lista=lista, regra=regra):
                    c = self.alterada(autonomia, lambda c: c['permissions'][lista].remove(regra))
                    self.assert_viola(c, f'autonomia: {lista} sem a regra obrigatoria {regra}')

    def test_perfil_e_exigido_por_qualquer_regra_de_autonomia_ou_por_acceptedits(self):
        """Auditoria 4B.1 (M5): nao basta omitir a regra do executor para escapar do perfil."""
        for regra in V.ALLOW_AUTONOMIA:
            with self.subTest(regra=regra):
                c = self.alterada(base, lambda c: c['permissions']['allow'].append(regra))
                self.assertTrue(V.autonomia_ativa(c))
                self.assert_viola(c, f'autonomia: deny sem a regra obrigatoria {V.DENY_GIT_SAIDA}')
        c = self.alterada(base, lambda c: c['permissions'].__setitem__('defaultMode',
                                                                         'acceptEdits'))
        self.assertTrue(V.autonomia_ativa(c))
        self.assert_viola(c, 'autonomia: ask sem a regra obrigatoria Bash(sed:*)')
        self.assert_viola(c, 'autonomia: disableAutoMode deve ser "disable"')

    def test_gravacao_disfarcada_pelo_git_esta_negada(self):
        """Auditoria 4B.1 (A1): --output grava arquivo em qualquer subcomando do Git."""
        cand = autonomia(self.cfg)['permissions']
        self.assertIn('Bash(git *--output*)', cand['deny'])
        for regra in ('Bash(git rev-list *)', 'Bash(git cat-file *)', 'Bash(graphify update .)'):
            self.assertNotIn(regra, cand['allow'])
        self.assertEqual(V.avisos_projeto(autonomia(self.cfg)), [])
        self.assertEqual(len(V.avisos_projeto(base(self.cfg))), 1)

    def test_regras_do_executor_sao_exatas(self):
        self.assertTrue(all('*' not in r for r in V.ALLOW_EXECUTOR))
        self.assertNotIn('Bash(bash scripts/testar.sh arquivo)', V.ALLOW_AUTONOMIA)
        c = self.alterada(autonomia, lambda c: c['permissions']['allow'].remove(
            'Bash(bash scripts/testar.sh motor)'))
        self.assert_viola(c, 'autonomia: allow sem a regra exata Bash(bash scripts/testar.sh motor)')

    def test_modo_auto_precisa_estar_desligado(self):
        c = self.alterada(autonomia, lambda c: c['permissions'].pop('disableAutoMode'))
        self.assert_viola(c, 'autonomia: disableAutoMode deve ser "disable"')
        c = self.alterada(autonomia, lambda c: c['permissions'].__setitem__('defaultMode', 'auto'))
        self.assert_viola(c, 'modo proibido em defaultMode: auto')

    def test_python_arbitrario_continua_em_ask(self):
        ask = autonomia(self.cfg)['permissions']['ask']
        for regra in ('Bash(python:*)', 'Bash(python3:*)', 'Bash(py:*)', 'Bash(bash -c:*)',
                      'Bash(bash scripts/homologar.sh:*)', 'Bash(git commit:*)',
                      'Bash(git push:*)', 'Bash(rm:*)', 'Bash(python.exe:*)', 'Bash(sh:*)',
                      'Bash(sed:*)', 'Bash(tee:*)', 'Bash(git -c:*)', 'Bash(git worktree:*)'):
            with self.subTest(regra=regra):
                self.assertIn(regra, ask)


class TestValidadorLocal(unittest.TestCase):
    """settings.local.json: onde o "nao perguntar de novo" deve gravar; sem liberacao ampla."""

    def test_local_restrito_e_aceito(self):
        cfg = {'permissions': {'allow': ['Bash(ls *)', 'Bash(git status:*)', 'Bash(wc -l *)',
                                         'Edit(./docs/**)']}}
        self.assertEqual(V.violacoes_local(cfg), [])
        self.assertEqual(V.violacoes_local({}), [])

    def test_local_amplo_e_recusado(self):
        for regra in ('Bash', 'Bash(*)', 'Bash(python:*)', 'Bash(python3 -c *)',
                      'Bash(python -I -B -m unittest discover -s tests *)',
                      'Bash(bash scripts/testar.sh *)', 'Bash(git push *)', 'Bash(rm -rf *)',
                      'Bash(/usr/bin/python *)', 'PowerShell', 'PowerShell(Get-ChildItem *)',
                      'Edit', 'Edit(./**)', 'Write(**)', 'Bash(python.exe *)', 'Bash(PY.EXE -c *)',
                      'Bash(C:\\Python314\\python.exe *)', 'Bash(perl -e *)', 'Bash(sed -i *)',
                      'Bash(tee *)', 'Bash(find . -delete)', 'Bash(cmd.exe /c *)',
                      'Bash(source x.sh)', 'Bash(git -c x=y diff)', 'Bash(git cat-file *)'):
            with self.subTest(regra=regra):
                achados = V.violacoes_local({'permissions': {'allow': [regra]}})
                self.assertTrue(any(regra in a for a in achados), achados)

    def test_local_nao_relaxa_modos_nem_hooks(self):
        casos = [
            {'disableAllHooks': True},
            {'permissions': {'defaultMode': 'bypassPermissions'}},
            {'permissions': {'defaultMode': 'auto'}},
            {'permissions': {'additionalDirectories': ['C:/Users']}},
            {'permissions': {'disableBypassPermissionsMode': 'enable'}},
            {'permissions': {'disableAutoMode': 'enable'}},
            {'permissions': {'blockWritesOutsideWorkingDirectories': False}},
            {'env': {'PYTHONTZPATH': 'C:/x'}},
            {'hooks': {'PreToolUse': []}},
            {'sandbox': {'enabled': False}},
        ]
        for cfg in casos:
            with self.subTest(cfg=cfg):
                self.assertNotEqual(V.violacoes_local(cfg), [])


class TestManifesto(unittest.TestCase):
    """Manifesto de homologacao sobre uma arvore temporaria minima."""

    def setUp(self):
        self.raiz = tempfile.mkdtemp(prefix='homologacao_')
        self.addCleanup(_remover_arvore, self.raiz)
        self.escrever('scripts/x.py', b'print(1)\n')
        self.escrever('src/pacote/a.py', b'A = 1\n')
        self.escrever('tests/test_a.py', b'import unittest\n')
        self.escrever('tests/fixtures/f.csv', b'a,b\n1,2\n')
        self.escrever('scripts/y.sh', b'echo 1\n')
        self.escrever('.claude/hooks/guarda_agentes.py', b'# hook\n')
        self.escrever('.claude/settings.json', b'{}\n')
        self.escrever('.gitattributes', b'tests/fixtures/** -text\n')
        self.total, _ = H.gravar(self.raiz)

    def escrever(self, rel, dados):
        caminho = os.path.join(self.raiz, *rel.split('/'))
        os.makedirs(os.path.dirname(caminho), exist_ok=True)
        with open(caminho, 'wb') as f:
            f.write(dados)

    def test_estado_gravado_confere(self):
        self.assertEqual(self.total, 8)
        self.assertEqual(H.diferencas(self.raiz), [])
        self.assertNotIn(H.MANIFESTO, H.ler_manifesto(self.raiz))

    def test_configuracoes_fora_das_pastas_de_codigo_entram_no_manifesto(self):
        """settings.json e .gitattributes mudam o que roda: alterou, exige nova homologacao."""
        self.escrever('.claude/settings.json', b'{"permissions": {}}\n')
        self.escrever('.gitattributes', b'* text=auto\n')
        self.assertEqual(H.diferencas(self.raiz), [('alterado', '.claude/settings.json'),
                                                   ('alterado', '.gitattributes')])
        os.remove(os.path.join(self.raiz, '.claude', 'settings.json'))
        with self.assertRaises(H.ErroHomologacao) as ctx:
            H.diferencas(self.raiz)
        self.assertIn('arquivo obrigatorio ausente', str(ctx.exception))

    def test_script_de_shell_usa_bytes_exatos(self):
        """Auditoria 4B.1 (B4): para o bash, CR e dado; o hash de *.sh nao o ignora."""
        self.escrever('scripts/y.sh', b'echo 1\r\n')
        self.assertEqual(H.diferencas(self.raiz), [('alterado', 'scripts/y.sh')])

    def test_juncao_chamada_pycache_e_recusada(self):
        """Auditoria 4B.1 (B3): link e recusado antes do filtro de __pycache__."""
        fora = tempfile.mkdtemp(prefix='homologacao_fora_')
        self.addCleanup(_remover_arvore, fora)
        motivo = _criar_juncao(fora, os.path.join(self.raiz, 'src', 'pacote', '__pycache__'))
        if motivo:
            self.skipTest(motivo)
        with self.assertRaises(H.ErroHomologacao) as ctx:
            H.diferencas(self.raiz)
        self.assertIn('src/pacote/__pycache__', str(ctx.exception))

    def test_arquivo_novo_alterado_e_removido(self):
        self.escrever('tests/test_intruso.py', b'import os\n')
        self.escrever('src/pacote/a.py', b'A = 2\n')
        os.remove(os.path.join(self.raiz, 'scripts', 'x.py'))
        self.assertEqual(H.diferencas(self.raiz), [
            ('removido', 'scripts/x.py'), ('alterado', 'src/pacote/a.py'),
            ('novo', 'tests/test_intruso.py')])

    def test_hook_alterado_e_detectado(self):
        self.escrever('.claude/hooks/guarda_agentes.py', b'# hook adulterado\n')
        self.assertEqual(H.diferencas(self.raiz), [('alterado', '.claude/hooks/guarda_agentes.py')])

    def test_crlf_nao_muda_codigo_mas_muda_fixture(self):
        self.escrever('src/pacote/a.py', b'A = 1\r\n')
        self.assertEqual(H.diferencas(self.raiz), [])
        self.escrever('tests/fixtures/f.csv', b'a,b\r\n1,2\r\n')
        self.assertEqual(H.diferencas(self.raiz), [('alterado', 'tests/fixtures/f.csv')])

    def test_cache_de_bytecode_e_ignorado_na_listagem(self):
        self.escrever('src/pacote/__pycache__/a.cpython-314.pyc', b'\x00')
        self.assertEqual(H.diferencas(self.raiz), [])

    def test_link_ou_juncao_no_conjunto_e_recusado(self):
        fora = tempfile.mkdtemp(prefix='homologacao_fora_')
        self.addCleanup(_remover_arvore, fora)
        with open(os.path.join(fora, 'test_externo.py'), 'wb') as f:
            f.write(b'import os\n')
        motivo = _criar_juncao(fora, os.path.join(self.raiz, 'tests', 'ligacao'))
        if motivo:
            self.skipTest(motivo)
        with self.assertRaises(H.ErroHomologacao) as ctx:
            H.diferencas(self.raiz)
        self.assertIn('tests/ligacao', str(ctx.exception))

    def test_manifesto_invalido(self):
        caminho = os.path.join(self.raiz, *H.MANIFESTO.split('/'))
        with open(caminho, encoding='utf-8') as f:
            linhas = [l for l in f.read().splitlines() if l and not l.startswith('#')]
        casos = {
            'malformada': 'abc  tests/test_a.py\n',
            'repetido': linhas[0] + '\n' + linhas[0] + '\n',
            'vazio': '# so comentario\n',
        }
        for trecho, conteudo in casos.items():
            with self.subTest(caso=trecho):
                with open(caminho, 'w', encoding='utf-8', newline='\n') as f:
                    f.write(conteudo)
                with self.assertRaises(H.ErroHomologacao) as ctx:
                    H.diferencas(self.raiz)
                self.assertIn(trecho, str(ctx.exception))
        os.remove(caminho)
        with self.assertRaises(H.ErroHomologacao) as ctx:
            H.diferencas(self.raiz)
        self.assertIn('ausente', str(ctx.exception))


class TestManifestoDoRepositorio(unittest.TestCase):

    def test_manifesto_do_repositorio_esta_atual(self):
        """Se falhar: o codigo mudou depois da ultima homologacao (bash scripts/homologar.sh)."""
        self.assertEqual(H.diferencas(RAIZ_REPO), [])

    def test_nucleo_e_hook_estao_no_manifesto(self):
        registrado = H.ler_manifesto(RAIZ_REPO)
        for rel in ('scripts/testar.sh', 'scripts/homologar.sh', 'scripts/lib_homologacao.sh',
                    'scripts/homologacao.py', 'scripts/validar_settings.py',
                    '.claude/hooks/guarda_agentes.py', '.claude/settings.json', '.gitattributes',
                    'tests/test_seguranca_autonomia.py', 'tests/fixtures/demo_4a/gabarito.json'):
            with self.subTest(arquivo=rel):
                self.assertIn(rel, registrado)


def _bash():
    """bash do Git for Windows (nao o do WSL) ou o bash do sistema; None se nao houver."""
    if os.name != 'nt':
        return shutil.which('bash')
    git = shutil.which('git')
    pasta = os.path.dirname(os.path.realpath(git)) if git else ''
    for _ in range(4):
        for rel in (('bin', 'bash.exe'), ('usr', 'bin', 'bash.exe')):
            candidato = os.path.join(pasta, *rel)
            if pasta and os.path.isfile(candidato):
                return candidato
        pasta = os.path.dirname(pasta)
    return None


_BASH = _bash()
_MOTIVO = None if (_BASH and shutil.which('git')) else 'bash do Git ou git nao encontrados'
VARIAVEIS_HOSTIS = {
    'PYTHONTZPATH': 'C:\\tz-hostil', 'PYTHONPATH': 'C:\\pacotes-hostis',
    'PYTHONSTARTUP': 'C:\\inicio-hostil.py', 'GUARDA_HOOK': 'C:\\hook-hostil.py',
    'GIT_DIR': 'C:\\git-hostil', 'GIT_EXTERNAL_DIFF': 'hostil', 'SEGREDO_DE_TESTE': 'x',
}


@unittest.skipIf(_MOTIVO, _MOTIVO or '')
class TestExecutor(unittest.TestCase):
    """scripts/testar.sh numa copia temporaria do repositorio (com `git init` proprio)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='executor_')
        self.addCleanup(_remover_arvore, self.tmp)
        self.copia = os.path.join(self.tmp, 'repo')
        ignorar = shutil.ignore_patterns('__pycache__')
        for pasta in ('scripts', 'src', 'tests'):
            shutil.copytree(os.path.join(RAIZ_REPO, pasta), os.path.join(self.copia, pasta),
                            ignore=ignorar)
        os.makedirs(os.path.join(self.copia, '.claude', 'hooks'))
        for rel in (('.claude', 'settings.json'), ('.claude', 'hooks', 'guarda_agentes.py'),
                    ('.gitattributes',)):
            shutil.copyfile(os.path.join(RAIZ_REPO, *rel), os.path.join(self.copia, *rel))
        subprocess.run(['git', 'init', '--quiet'], cwd=self.copia, check=True,
                       capture_output=True, timeout=60)
        self.marca = os.path.join(self.tmp, 'marca.json')

    def bash(self, script, *args, cwd=None, extra=None):
        env = dict(os.environ)
        env.update(extra or {})
        return subprocess.run([_BASH, script, *args], cwd=cwd or self.copia, env=env,
                              capture_output=True, text=True, encoding='utf-8',
                              errors='replace', timeout=300)

    def testar(self, *args, **kw):
        return self.bash('scripts/testar.sh', *args, **kw)

    def plantar_teste(self, nome='test_intruso.py'):
        """Teste novo que grava as variaveis de ambiente que enxerga em self.marca."""
        with open(os.path.join(self.copia, 'tests', nome), 'w', encoding='utf-8',
                  newline='\n') as f:
            f.write('import json, os, unittest\n\n\nclass T(unittest.TestCase):\n'
                    '    def test_marca(self):\n'
                    f'        with open({self.marca!r}, "w", encoding="utf-8") as f:\n'
                    '            json.dump(sorted(os.environ), f)\n')

    def test_copia_integra_confere(self):
        proc = self.testar('conferir')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('conjunto homologado integro', proc.stdout)

    def test_argumentos_sao_fechados(self):
        self.plantar_teste()  # se algum argumento passasse, a recusa seria pelo manifesto (3)
        for args in ([], ['motor', 'extra'], ['MOTOR'], ['-s', '/tmp'], ['motor', '-s', '/tmp'],
                     ['arquivo'], ['arquivo', '../tests/test_intruso.py'],
                     ['arquivo', 'test_intruso.py;id'], ['arquivo', '-p'],
                     ['arquivo', 'test_intruso.py', '-s', '/tmp'], ['arquivo', '$(id)'],
                     ['arquivo', 'Test_intruso.py'], ['homologar'], ['conferir', 'x']):
            with self.subTest(args=args):
                self.assertEqual(self.testar(*args).returncode, 64)
        self.assertFalse(os.path.exists(self.marca))

    def test_teste_novo_nao_homologado_nao_executa(self):
        self.plantar_teste()
        for args in (['motor'], ['arquivo', 'test_intruso.py'], ['tudo'], ['conferir']):
            with self.subTest(args=args):
                proc = self.testar(*args)
                self.assertEqual(proc.returncode, 3, proc.stderr)
                self.assertIn('novo: tests/test_intruso.py', proc.stderr)
        self.assertFalse(os.path.exists(self.marca), 'o teste nao homologado foi executado')

    def test_codigo_alterado_nao_executa(self):
        for rel, trecho in (('src/consolidacao/pipeline.py', 'alterado: src/consolidacao/pipeline.py'),
                            ('tests/_apoio_demo_4a.py', 'alterado: tests/_apoio_demo_4a.py'),
                            ('.claude/hooks/guarda_agentes.py', 'alterado: .claude/hooks/'),
                            ('scripts/homologacao.py', 'alterado (nucleo): scripts/homologacao.py')):
            with self.subTest(arquivo=rel):
                caminho = os.path.join(self.copia, *rel.split('/'))
                with open(caminho, 'rb') as f:
                    original = f.read()
                with open(caminho, 'ab') as f:
                    f.write(b'\n# alteracao nao homologada\n')
                proc = self.testar('governanca')
                self.assertEqual(proc.returncode, 3, proc.stderr)
                self.assertIn(trecho, proc.stderr)
                with open(caminho, 'wb') as f:
                    f.write(original)
        self.assertEqual(self.testar('conferir').returncode, 0)

    def test_apos_homologar_o_teste_executa_em_ambiente_limpo(self):
        self.plantar_teste()
        proc = self.bash('scripts/homologar.sh')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('novo: tests/test_intruso.py', proc.stdout)
        proc = self.testar('arquivo', 'test_intruso.py', extra=VARIAVEIS_HOSTIS)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        with open(self.marca, encoding='utf-8') as f:
            vistas = {v.upper() for v in json.load(f)}
        self.assertIn('PATH', vistas)
        self.assertEqual(vistas & set(VARIAVEIS_HOSTIS), set())
        self.assertEqual({v for v in vistas if v.startswith(('PYTHON', 'GIT_', 'CLAUDE'))}, set())

    def test_homologar_nao_aceita_argumentos(self):
        self.assertEqual(self.bash('scripts/homologar.sh', '--tudo').returncode, 64)

    def test_settings_corrompido_bloqueia_a_execucao(self):
        caminho = os.path.join(self.copia, '.claude', 'settings.json')
        with open(caminho, encoding='utf-8') as f:
            texto = f.read()
        casos = {
            'chave JSON repetida': texto.replace('"ask": [', '"ask": [],\n    "ask": [', 1),
            'INVALIDO': texto.replace('"allow": [', '"allow": [ "x" "y",', 1),
            'ask sem a regra obrigatoria Bash(python:*)': texto.replace('"Bash(python:*)",', '', 1),
        }
        self.plantar_teste()
        self.assertEqual(self.bash('scripts/homologar.sh').returncode, 0)
        for trecho, corrompido in casos.items():
            with self.subTest(caso=trecho):
                self.assertNotEqual(corrompido, texto)
                with open(caminho, 'w', encoding='utf-8') as f:
                    f.write(corrompido)
                proc = self.testar('arquivo', 'test_intruso.py')
                self.assertEqual(proc.returncode, 4, proc.stderr)
                self.assertIn(trecho, proc.stderr)
        self.assertFalse(os.path.exists(self.marca))

    def test_settings_local_amplo_bloqueia_a_execucao(self):
        with open(os.path.join(self.copia, '.claude', 'settings.local.json'), 'w',
                  encoding='utf-8') as f:
            json.dump({'permissions': {'allow': ['Bash(python:*)']}}, f)
        proc = self.testar('conferir')
        self.assertEqual(proc.returncode, 4, proc.stderr)
        self.assertIn('[local] VIOLACAO', proc.stderr)

    def test_independe_do_diretorio_atual(self):
        outro = os.path.join(self.tmp, 'outro')
        os.makedirs(outro)
        proc = self.bash(os.path.join(self.copia, 'scripts', 'testar.sh'), 'conferir', cwd=outro)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_copia_completa_fora_da_raiz_git_e_recusada(self):
        """Auditoria 4B.1 (B1): a recusa vem da checagem de raiz Git, nao de pasta ausente."""
        destino = os.path.join(self.copia, 'outputs', 'x')
        for pasta in ('scripts', 'src', 'tests', '.claude'):
            shutil.copytree(os.path.join(self.copia, pasta), os.path.join(destino, pasta))
        shutil.copyfile(os.path.join(self.copia, '.gitattributes'),
                        os.path.join(destino, '.gitattributes'))
        proc = self.bash('scripts/testar.sh', 'conferir', cwd=destino)
        self.assertEqual(proc.returncode, 70, proc.stderr)
        self.assertIn('nao esta na raiz do repositorio Git', proc.stderr)

    def test_settings_alterado_mas_valido_exige_nova_homologacao(self):
        caminho = os.path.join(self.copia, '.claude', 'settings.json')
        cfg = V.carregar(caminho)
        cfg['permissions']['ask'].append('Bash(regra-nova:*)')
        with open(caminho, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2)
        proc = self.testar('conferir')
        self.assertEqual(proc.returncode, 3, proc.stderr)
        self.assertIn('alterado: .claude/settings.json', proc.stderr)

    def test_fluxo_de_instalacao_do_perfil_autonomia(self):
        """Instalar a configuracao nova: recusa ate homologar; depois, perfil autonomia valido."""
        caminho = os.path.join(self.copia, '.claude', 'settings.json')
        for modo in (None, 'acceptEdits'):
            with self.subTest(defaultMode=modo):
                cfg = autonomia(instalada())
                if modo is None:
                    cfg['permissions'].pop('defaultMode')
                with open(caminho, 'w', encoding='utf-8', newline='\n') as f:
                    f.write(json.dumps(cfg, indent=2) + '\n')
                proc = self.testar('conferir')
                self.assertEqual(proc.returncode, 3, proc.stderr)
                self.assertIn('alterado: .claude/settings.json', proc.stderr)
                proc = self.bash('scripts/homologar.sh')
                self.assertEqual(proc.returncode, 0, proc.stderr)
                proc = self.testar('conferir')
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertIn('configuracao valida (perfil autonomia)', proc.stdout)
                self.assertNotIn('AVISO', proc.stderr)

    def test_manifesto_ausente_bloqueia(self):
        os.remove(os.path.join(self.copia, 'scripts', 'homologacao.manifest'))
        proc = self.testar('conferir')
        self.assertEqual(proc.returncode, 3, proc.stderr)
        self.assertIn('manifesto ausente', proc.stderr)

    def test_alteracao_durante_a_execucao_invalida_o_resultado(self):
        """Auditoria 4B.1 (A3): o conjunto e conferido de novo depois de cada suite."""
        with open(os.path.join(self.copia, 'tests', 'test_altera.py'), 'w', encoding='utf-8',
                  newline='\n') as f:
            f.write('import os, unittest\n\n\nclass T(unittest.TestCase):\n'
                    '    def test_altera(self):\n'
                    '        alvo = os.path.join(os.path.dirname(os.path.abspath(__file__)),\n'
                    '                            "..", "src", "consolidacao", "erros.py")\n'
                    '        with open(alvo, "ab") as f:\n'
                    '            f.write(b"\\n# alterado durante a execucao\\n")\n')
        self.assertEqual(self.bash('scripts/homologar.sh').returncode, 0)
        proc = self.testar('arquivo', 'test_altera.py')
        self.assertEqual(proc.returncode, 3, proc.stdout + proc.stderr)
        self.assertIn('DURANTE a execucao', proc.stderr)
        self.assertIn('OK', proc.stdout)  # o teste em si passou; o resultado e invalidado

    def test_bytecode_plantado_durante_a_execucao_invalida_o_resultado(self):
        """Reauditoria 4B.1 (N1): __pycache__ surgido durante a execucao e acusado."""
        with open(os.path.join(self.copia, 'tests', 'test_planta.py'), 'w', encoding='utf-8',
                  newline='\n') as f:
            f.write('import os, unittest\n\n\nclass T(unittest.TestCase):\n'
                    '    def test_planta(self):\n'
                    '        pasta = os.path.join(os.path.dirname(os.path.abspath(__file__)),\n'
                    '                             "..", "src", "consolidacao", "__pycache__")\n'
                    '        os.makedirs(pasta)\n'
                    '        with open(os.path.join(pasta, "erros.cpython-314.pyc"), "wb") as f:\n'
                    '            f.write(b"plantado")\n')
        self.assertEqual(self.bash('scripts/homologar.sh').returncode, 0)
        proc = self.testar('arquivo', 'test_planta.py')
        self.assertEqual(proc.returncode, 3, proc.stdout + proc.stderr)
        self.assertIn('bytecode em cache surgiu DURANTE a execucao', proc.stderr)

    def test_log_plantado_como_link_nao_e_seguido(self):
        """Auditoria 4B.1 (B2): um hardlink com o nome do log nao leva a escrita ao alvo."""
        alvo = os.path.join(self.tmp, 'alvo_protegido.txt')
        with open(alvo, 'wb') as f:
            f.write(b'conteudo protegido\n')
        pasta = os.path.join(self.copia, 'outputs', 'testes')
        os.makedirs(pasta)
        log = os.path.join(pasta, 'arquivo-test_guarda_plano_mock.log')
        try:
            os.link(alvo, log)
        except OSError as e:
            self.skipTest(f'hardlink indisponivel: {e!r}')
        proc = self.testar('arquivo', 'test_guarda_plano_mock.py')
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        with open(alvo, 'rb') as f:
            self.assertEqual(f.read(), b'conteudo protegido\n')
        with open(log, 'rb') as f:
            self.assertIn(b'Ran ', f.read())

    def test_python_dentro_do_repositorio_e_recusado(self):
        """Um `python` plantado no repositorio e posto na frente do PATH nao e usado."""
        pasta = os.path.join(self.copia, 'bin')
        os.makedirs(pasta)
        with open(os.path.join(pasta, 'python'), 'w', encoding='utf-8', newline='\n') as f:
            f.write(f'#!/bin/sh\necho plantado > "{self.marca}"\n')
        proc = self.testar('conferir',
                           extra={'PATH': pasta + os.pathsep + os.environ.get('PATH', '')})
        self.assertEqual(proc.returncode, 70, proc.stderr)
        self.assertIn('ferramenta dentro do repositorio', proc.stderr)
        self.assertFalse(os.path.exists(self.marca))

    def test_demo_grava_as_saidas_demonstrativas_na_propria_raiz(self):
        proc = self.testar('demo')
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn('lote: DEMO4A-cc6f21e0d609', proc.stdout)
        for camada in (('data', 'staging'), ('data', 'curated'), ('data', 'analytics'),
                       ('outputs',)):
            with self.subTest(camada='/'.join(camada)):
                self.assertTrue(os.path.isdir(os.path.join(
                    self.copia, *camada, 'demo_4a', 'DEMO4A-cc6f21e0d609')))

    def test_juncao_dentro_de_tests_e_recusada(self):
        fora = os.path.join(self.tmp, 'fora')
        os.makedirs(fora)
        motivo = _criar_juncao(fora, os.path.join(self.copia, 'tests', 'ligacao'))
        if motivo:
            self.skipTest(motivo)
        proc = self.testar('conferir')
        self.assertEqual(proc.returncode, 3, proc.stderr)
        self.assertIn('link simbolico ou juncao', proc.stderr)

    def test_bytecode_em_cache_e_removido_antes_de_executar(self):
        cache = os.path.join(self.copia, 'src', 'consolidacao', '__pycache__')
        os.makedirs(cache)
        with open(os.path.join(cache, 'pipeline.cpython-314.pyc'), 'wb') as f:
            f.write(b'\x00bytecode plantado')
        self.assertEqual(self.testar('conferir').returncode, 0)
        self.assertFalse(os.path.exists(cache))


if __name__ == '__main__':
    unittest.main()
