"""FASE 4B (ADR-002): estabilidade das quebras de linha das fixtures DEMO-4A.

A ancora de integridade sao os blobs do commit aprovado 1f70e76, lidos do proprio Git.
Nenhum hash esperado e digitado aqui: se uma fixture mudar, o teste falha, e a correcao
e restaurar a fixture (nunca trocar a ancora).

Cobre: (1) arvore = blobs do commit-base; (2) nenhuma fixture com CR; (3) hashes preservados
apos novo checkout; (4) lote DEMO4A-cc6f21e0d609; (5) clone temporario com core.autocrlf=true
gera as mesmas saidas; (6) detector acusa fixture convertida para CRLF.
Uso: python -I -m unittest discover -s tests
"""
import hashlib
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

_AQUI = os.path.dirname(os.path.abspath(__file__))
for _p in (_AQUI, os.path.join(os.path.dirname(_AQUI), 'src')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import _apoio_demo_4a as apoio  # noqa: E402

COMMIT_BASE = '1f70e7620edea9477bbc127d0e32a8a60151fcf2'
LOTE_BASE = 'DEMO4A-cc6f21e0d609'
DIR_REL = 'tests/fixtures/demo_4a'
CONTROLE_TEXTO = 'src/consolidacao/pipeline.py'  # sem atributo: o autocrlf converte


def _git(*args, cwd=apoio.RAIZ_REPO, check=True):
    return subprocess.run(['git', *args], cwd=cwd, capture_output=True, check=check,
                          timeout=180)


def _sha(dados):
    return hashlib.sha256(dados).hexdigest()


def _ler(caminho):
    with open(caminho, 'rb') as f:
        return f.read()


def _motivo_sem_git():
    """None se o Git e o commit-base estao disponiveis; senao, o motivo do skip."""
    if shutil.which('git') is None:
        return 'git nao encontrado no PATH'
    try:
        _git('rev-parse', '--is-inside-work-tree')
        _git('cat-file', '-e', COMMIT_BASE + '^{commit}')
    except (subprocess.CalledProcessError, OSError) as e:
        return f'repositorio Git ou commit-base {COMMIT_BASE[:7]} indisponivel: {e!r}'
    return None


def nomes_base():
    """Arquivos de tests/fixtures/demo_4a no commit-base (ordenados)."""
    saida = _git('ls-tree', '-r', '--name-only', COMMIT_BASE, DIR_REL + '/').stdout
    return sorted(os.path.basename(l) for l in saida.decode('utf-8').splitlines() if l)


def blob_base(nome):
    return _git('show', f'{COMMIT_BASE}:{DIR_REL}/{nome}').stdout


def problemas_eol(diretorio, nomes):
    """[(nome, detalhe)] para cada arquivo com CR (CRLF ou CR isolado)."""
    achados = []
    for nome in nomes:
        dados = _ler(os.path.join(diretorio, nome))
        if b'\r' in dados:
            achados.append((nome, f'{dados.count(b"\r\n")} CRLF, {dados.count(b"\r")} CR'))
    return achados


def _remover_arvore(caminho):
    def _forcar(funcao, alvo, _exc):
        os.chmod(alvo, stat.S_IWRITE)
        funcao(alvo)
    if os.path.exists(caminho):
        shutil.rmtree(caminho, onexc=_forcar)


_MOTIVO = _motivo_sem_git()


@unittest.skipIf(_MOTIVO, _MOTIVO or '')
class TestFixturesContraCommitBase(unittest.TestCase):
    """(1), (2) e (4) na arvore de trabalho deste repositorio."""

    def test_lista_de_fixtures_e_a_do_commit_base(self):
        rastreados = _git('ls-files', DIR_REL + '/').stdout.decode('utf-8').split()
        self.assertEqual(sorted(os.path.basename(r) for r in rastreados), nomes_base())

    def test_fixtures_iguais_aos_blobs_do_commit_base(self):
        for nome in nomes_base():
            with self.subTest(arquivo=nome):
                atual = _ler(os.path.join(apoio.FIXTURES, nome))
                base = blob_base(nome)
                self.assertEqual(
                    (_sha(atual), len(atual)), (_sha(base), len(base)),
                    f'{nome} difere do blob de {COMMIT_BASE[:7]}: restaure a fixture '
                    '(git checkout); nao atualize a ancora')

    def test_nenhuma_fixture_tem_cr(self):
        self.assertEqual(problemas_eol(apoio.FIXTURES, nomes_base()), [])

    def test_atributo_desliga_conversao_nas_fixtures(self):
        caminhos = [f'{DIR_REL}/{n}' for n in nomes_base()]
        saida = _git('check-attr', 'text', '--', *caminhos).stdout.decode('utf-8')
        for linha in saida.splitlines():
            with self.subTest(linha=linha):
                self.assertTrue(linha.endswith(': text: unset'), linha)
        self.assertEqual(len(saida.splitlines()), len(caminhos))

    def test_atributo_nao_e_global(self):
        saida = _git('check-attr', 'text', '--', CONTROLE_TEXTO).stdout.decode('utf-8')
        self.assertTrue(saida.strip().endswith(': text: unspecified'), saida)

    def test_lote_das_fixtures_e_o_aprovado(self):
        with tempfile.TemporaryDirectory(prefix='demo4a_eol_lote_',
                                         ignore_cleanup_errors=True) as tmp:
            self.assertEqual(apoio.executar_api(apoio.FIXTURES, tmp)['lote'], LOTE_BASE)


@unittest.skipIf(_MOTIVO, _MOTIVO or '')
class TestDetectorCRLF(unittest.TestCase):
    """(6) Uma copia com uma fixture convertida para CRLF e acusada; o lote muda."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(prefix='demo4a_eol_crlf_',
                                               ignore_cleanup_errors=True)
        cls.entrada = apoio.copiar_fixtures(os.path.join(cls._tmp.name, 'entrada'))
        caminho = os.path.join(cls.entrada, 'vendas.csv')
        dados = _ler(caminho)
        with open(caminho, 'wb') as f:
            f.write(dados.replace(b'\n', b'\r\n'))

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_detector_acusa_somente_o_arquivo_convertido(self):
        achados = problemas_eol(self.entrada, apoio.ARQUIVOS)
        self.assertEqual([n for n, _ in achados], ['vendas.csv'])

    def test_conversao_quebra_a_igualdade_com_o_blob(self):
        self.assertNotEqual(_sha(_ler(os.path.join(self.entrada, 'vendas.csv'))),
                            _sha(blob_base('vendas.csv')))

    def test_crlf_muda_o_identificador_do_lote(self):
        """Prova de sensibilidade: sem a regra -text, o lote dependeria da maquina."""
        raiz = os.path.join(self._tmp.name, 'raiz')
        os.makedirs(raiz)
        self.assertNotEqual(apoio.executar_api(self.entrada, raiz)['lote'], LOTE_BASE)


@unittest.skipIf(_MOTIVO, _MOTIVO or '')
class TestCloneAutocrlf(unittest.TestCase):
    """(3) e (5) Clone temporario com core.autocrlf=true, com o .gitattributes desta arvore.

    Enquanto o .gitattributes nao estiver commitado, o clone recebe a copia da arvore de
    trabalho e as fixtures sao extraidas de novo; depois do commit, a copia e identica.
    """

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix='demo4a_eol_clone_')
        try:
            cls.clone = os.path.join(cls._tmp, 'clone')
            _git('-c', 'core.autocrlf=true', 'clone', '--no-local', '--quiet',
                 '-c', 'core.autocrlf=true', apoio.RAIZ_REPO, cls.clone, cwd=cls._tmp)
            atributos = _ler(os.path.join(apoio.RAIZ_REPO, '.gitattributes'))
            destino = os.path.join(cls.clone, '.gitattributes')
            cls.atributos_copiados = (not os.path.exists(destino)
                                      or _ler(destino) != atributos)
            if cls.atributos_copiados:
                with open(destino, 'wb') as f:
                    f.write(atributos)
            cls._reextrair()
            cls.dir_fix = os.path.join(cls.clone, *DIR_REL.split('/'))
        except BaseException:
            _remover_arvore(cls._tmp)
            raise

    @classmethod
    def tearDownClass(cls):
        _remover_arvore(cls._tmp)

    @classmethod
    def _reextrair(cls):
        dir_fix = os.path.join(cls.clone, *DIR_REL.split('/'))
        for nome in os.listdir(dir_fix):
            os.remove(os.path.join(dir_fix, nome))
        _git('checkout', '--', DIR_REL, cwd=cls.clone)

    def test_controle_autocrlf_ativo_no_clone(self):
        """Sem este controle, um clone sem conversao passaria o teste por acaso."""
        valor = _git('config', 'core.autocrlf', cwd=self.clone).stdout.decode().strip()
        self.assertEqual(valor, 'true')
        self.assertIn(b'\r\n', _ler(os.path.join(self.clone, *CONTROLE_TEXTO.split('/'))))

    def test_fixtures_do_clone_iguais_aos_blobs(self):
        nomes = nomes_base()
        self.assertEqual(problemas_eol(self.dir_fix, nomes), [])
        for nome in nomes:
            with self.subTest(arquivo=nome):
                self.assertEqual(_sha(_ler(os.path.join(self.dir_fix, nome))),
                                 _sha(blob_base(nome)))

    def test_novo_checkout_preserva_hashes(self):
        type(self)._reextrair()
        _git('checkout', 'HEAD', '--', DIR_REL, cwd=self.clone)
        for nome in nomes_base():
            with self.subTest(arquivo=nome):
                self.assertEqual(_sha(_ler(os.path.join(self.dir_fix, nome))),
                                 _sha(blob_base(nome)))
        status = _git('status', '--porcelain', '--', DIR_REL, cwd=self.clone).stdout
        self.assertEqual(status, b'')

    def test_saidas_do_clone_identicas_as_do_repositorio(self):
        raiz_clone = os.path.join(self._tmp, 'raiz_clone')
        raiz_repo = os.path.join(self._tmp, 'raiz_repo')
        os.makedirs(raiz_clone)
        os.makedirs(raiz_repo)
        r_clone = apoio.executar_api(self.dir_fix, raiz_clone)
        r_repo = apoio.executar_api(apoio.FIXTURES, raiz_repo)
        self.assertEqual(r_clone['lote'], LOTE_BASE)
        self.assertEqual(r_repo['lote'], LOTE_BASE)
        h_clone, h_repo = apoio.hashes_lote(r_clone), apoio.hashes_lote(r_repo)
        self.assertEqual(len(h_repo), 14)
        self.assertEqual(h_clone, h_repo)


if __name__ == '__main__':
    unittest.main()
