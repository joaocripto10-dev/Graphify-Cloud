"""FASE 4B: P17 SIMULADO, com link simbolico de arquivo emulado por mock de os.path.realpath.

NAO substitui o P17 real de tests/test_guarda_agentes.py. Aquele exige criar um symlink de
verdade, o que este Windows recusa (WinError 1314). O P17 real continua PENDENTE ate rodar
num ambiente autorizado com privilegio de symlink.

O hook e carregado do TEXTO-FONTE com compile/exec em memoria: nao ha import, nao se grava
bytecode e nada e criado em .claude/hooks/. O hook nao e alterado. A prova de mutacao tambem
roda em memoria: sem a checagem de pasta, os cenarios P17 passam a ser permitidos e o teste
acusa.
Uso: python -I -m unittest discover -s tests
"""
import contextlib
import hashlib
import io
import json
import os
import shutil
import tempfile
import types
import unittest
from unittest import mock

RAIZ_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.environ.get('GUARDA_HOOK') or os.path.join(RAIZ_REPO, '.claude', 'hooks',
                                                     'guarda_agentes.py')
NEGA, SEGUE = 2, 0
# Trecho do hook que a mutacao remove (checagem de que o alvo real esta na pasta de planos).
TRECHO_PASTA = 'os.path.normcase(os.path.dirname(alvo)) == pasta\n            and '


def _ler_fonte():
    with open(HOOK, encoding='utf-8') as f:
        return f.read()


def _sha_hook():
    with open(HOOK, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def carregar_hook(fonte, nome='guarda_agentes_simulado'):
    """Executa o texto do hook num modulo novo, sem import e sem bytecode."""
    modulo = types.ModuleType(nome)
    modulo.__file__ = HOOK
    exec(compile(fonte, HOOK, 'exec'), modulo.__dict__)  # __name__ != '__main__': main() nao roda
    return modulo


class _Ambiente:
    """Projeto e pasta pessoal falsos; links simbolicos emulados no realpath."""

    def __init__(self, tmp):
        self.proj = os.path.join(tmp, 'projeto')
        self.casa = os.path.join(tmp, 'casa')
        self.planos = os.path.join(self.casa, '.claude', 'plans')
        self.fora = os.path.join(tmp, 'fora')
        self.outra = os.path.join(tmp, 'planos-reais')
        for d in (self.proj, self.planos, self.fora, self.outra):
            os.makedirs(d)
        self.links = {}
        self.consultas = []

    def chave(self, p):
        return os.path.normcase(os.path.abspath(str(p)))

    def realpath_falso(self, original):
        def realpath(p, *a, **k):
            atual = self.chave(p)
            self.consultas.append(atual)
            for _ in range(10):  # cadeias de links
                if atual in self.links:
                    atual = self.chave(self.links[atual])
                    continue
                pai, base = os.path.split(atual)
                if pai in self.links:  # o proprio diretorio e um link
                    atual = self.chave(os.path.join(self.links[pai], base))
                    continue
                break
            return original(atual, *a, **k)
        return realpath

    def evento(self, caminho, agente=''):
        e = {'tool_name': 'Write', 'tool_input': {'file_path': caminho.replace('\\', '/'),
                                                  'content': 'x'},
             'cwd': self.proj, 'session_id': 'teste-p17-simulado'}
        if agente:
            e['agent_type'] = agente
        return e

    def decidir(self, modulo, evento, links):
        self.links = {self.chave(k): v for k, v in links.items()}
        self.consultas = []
        env = {'CLAUDE_PROJECT_DIR': self.proj, 'USERPROFILE': self.casa, 'HOME': self.casa}
        with mock.patch.dict(os.environ, env), \
                mock.patch('os.path.realpath', self.realpath_falso(os.path.realpath)), \
                contextlib.redirect_stderr(io.StringIO()):
            try:
                modulo.decidir(evento)
                return SEGUE
            except SystemExit as e:
                return e.code


def cenarios(amb):
    """(nome, evento, links emulados, esperado, caminho que o realpath deve consultar)."""
    pl, fora, outra = amb.planos, amb.fora, amb.outra
    link = os.path.join(pl, 'link.md')
    return [
        ('C0 controle: plano comum sem link', amb.evento(os.path.join(pl, 'plano-a.md')), {},
         SEGUE, None),
        ('S1 P17: link.md -> fora/alvo.md (nome valido)', amb.evento(link),
         {link: os.path.join(fora, 'alvo.md')}, NEGA, link),
        ('S2 link.md -> settings do projeto', amb.evento(link),
         {link: os.path.join(amb.proj, '.claude', 'settings.json')}, NEGA, link),
        ('S3 cadeia a.md -> b.md -> fora/c.md', amb.evento(os.path.join(pl, 'a.md')),
         {os.path.join(pl, 'a.md'): os.path.join(pl, 'b.md'),
          os.path.join(pl, 'b.md'): os.path.join(fora, 'c.md')}, NEGA, os.path.join(pl, 'a.md')),
        ('S4 link.md -> subpasta de plans', amb.evento(link),
         {link: os.path.join(pl, 'sub', 'plano.md')}, NEGA, link),
        ('S5 link.md -> outro plano valido em plans', amb.evento(link),
         {link: os.path.join(pl, 'outro-plano.md')}, SEGUE, link),
        ('S6 a pasta plans inteira e um link', amb.evento(os.path.join(pl, 'plano-b.md')),
         {pl: outra}, SEGUE, os.path.join(pl, 'plano-b.md')),
        ('S7 subagente com link para plano valido', amb.evento(link, agente='Plan'),
         {link: os.path.join(pl, 'outro-plano.md')}, NEGA, None),
        ('S8 juncao de pasta (como P16) -> fora', amb.evento(os.path.join(pl, 'juncao.md')),
         {os.path.join(pl, 'juncao.md'): fora}, NEGA, os.path.join(pl, 'juncao.md')),
    ]


class TestP17Simulado(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='guarda_p17_sim_')
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.amb = _Ambiente(self.tmp)
        self.fonte = _ler_fonte()
        self.sha_hook = _sha_hook()
        self.cache_antes = os.path.exists(os.path.join(os.path.dirname(HOOK), '__pycache__'))

    def tearDown(self):
        self.assertEqual(_sha_hook(), self.sha_hook, 'o hook mudou durante o teste')
        self.assertEqual(os.path.exists(os.path.join(os.path.dirname(HOOK), '__pycache__')),
                         self.cache_antes, '__pycache__ criado em .claude/hooks/')

    def resultados(self, modulo):
        saida = {}
        for nome, evento, links, esperado, consultado in cenarios(self.amb):
            obtido = self.amb.decidir(modulo, evento, links)
            if consultado is not None:  # o mock foi realmente usado (sem falso verde)
                self.assertIn(self.amb.chave(consultado), self.amb.consultas, nome)
            saida[nome] = (obtido, esperado)
        return saida

    def test_cenarios_de_link_no_hook_instalado(self):
        for nome, (obtido, esperado) in self.resultados(carregar_hook(self.fonte)).items():
            with self.subTest(cenario=nome):
                self.assertEqual(obtido, esperado)

    def test_hook_grava_so_o_log_no_projeto_falso(self):
        self.resultados(carregar_hook(self.fonte))
        self.assertEqual(os.listdir(self.amb.fora), [])
        self.assertEqual(os.listdir(self.amb.planos), [])
        log = os.path.join(self.amb.proj, 'outputs', 'governanca', 'hook_guarda_log.jsonl')
        with open(log, encoding='utf-8') as f:
            decisoes = [json.loads(l)['decisao'] for l in f]
        self.assertIn('permitido_plano', decisoes)

    @unittest.skipIf(os.environ.get('GUARDA_HOOK'), 'GUARDA_HOOK aponta outro hook candidato')
    def test_hook_instalado_e_o_aprovado(self):
        """Auditoria 4B (D7): o hook avaliado e o aprovado na ETAPA 3H (candidato B)."""
        self.assertEqual(self.sha_hook,
                         '3c5531628558629df8bf82a75ee27240db084dccb49c77b2283df9208f68872a')

    def test_mutacao_sem_checagem_de_pasta_e_detectada(self):
        """Prova de mutacao: so os cenarios cuja defesa e a checagem de pasta mudam."""
        self.assertEqual(self.fonte.count(TRECHO_PASTA), 1,
                         'trecho da checagem de pasta nao encontrado: revisar a mutacao')
        mutante = carregar_hook(self.fonte.replace(TRECHO_PASTA, ''), 'guarda_mutante')
        divergentes = sorted(n for n, (obtido, esperado) in self.resultados(mutante).items()
                             if obtido != esperado)
        self.assertEqual(divergentes, ['S1 P17: link.md -> fora/alvo.md (nome valido)',
                                       'S3 cadeia a.md -> b.md -> fora/c.md',
                                       'S4 link.md -> subpasta de plans'])


if __name__ == '__main__':
    unittest.main()
