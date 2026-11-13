"""DEMO-4A, grupos 11 (arquivos invalidos rejeitam o lote inteiro) e 12 (caminhos permitidos).

As variantes invalidas sao copias temporarias das fixtures com UM arquivo alterado.
Uso: python -I -m unittest discover -s tests
"""
import os
import sys
import tempfile
import unittest

_AQUI = os.path.dirname(os.path.abspath(__file__))
for _p in (_AQUI, os.path.join(os.path.dirname(_AQUI), 'src')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import _apoio_demo_4a as apoio  # noqa: E402

CODIGO_OK, CODIGO_REJEITADO, CODIGO_CAMINHO = 0, 2, 4


def _remove_ultima_coluna(entrada, nome):
    """Remove a ultima coluna (cabecalho e dados). Valido so para arquivos sem aspas."""
    caminho = os.path.join(entrada, nome)
    with open(caminho, encoding='utf-8', newline='') as f:
        linhas = f.read().split('\n')
    novas = [l.rsplit(',', 1)[0] if l else l for l in linhas]
    with open(caminho, 'w', encoding='utf-8', newline='') as f:
        f.write('\n'.join(novas))


def _esvazia(entrada, nome):
    open(os.path.join(entrada, nome), 'wb').close()


def _grava_bytes_nao_utf8(entrada, nome):
    caminho = os.path.join(entrada, nome)
    with open(caminho, 'rb') as f:
        dados = f.read()
    assert b'Cafe expresso' in dados
    with open(caminho, 'wb') as f:
        f.write(dados.replace(b'Cafe expresso', b'Caf\xe9 expresso'))  # latin-1, invalido em UTF-8


def _remove(entrada, nome):
    os.remove(os.path.join(entrada, nome))


VARIANTES_INVALIDAS = {
    'coluna_obrigatoria_ausente': (_remove_ultima_coluna, 'produtos.csv'),
    'arquivo_vazio': (_esvazia, 'estoque.csv'),
    'bytes_nao_utf8': (_grava_bytes_nao_utf8, 'produtos.csv'),
    'arquivo_ausente': (_remove, 'unidades.csv'),
}


class TestArquivosInvalidos(unittest.TestCase):
    """Grupo 11: arquivo ausente/vazio/nao UTF-8/cabecalho diferente -> lote rejeitado, sem saida."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix='demo4a_invalido_',
                                                ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        _, self.erros = apoio.api()

    def _preparar(self, caso):
        base = os.path.join(self._tmp.name, caso)
        entrada = apoio.copiar_fixtures(os.path.join(base, 'entrada'))
        alterar, nome = VARIANTES_INVALIDAS[caso]
        alterar(entrada, nome)
        raiz_api = os.path.join(base, 'raiz_api')
        raiz_cli = os.path.join(base, 'raiz_cli')
        os.makedirs(raiz_api)
        os.makedirs(raiz_cli)
        return base, entrada, raiz_api, raiz_cli

    def test_variante_realmente_alterou_um_unico_arquivo(self):
        for caso, (_, nome) in VARIANTES_INVALIDAS.items():
            with self.subTest(caso=caso):
                _, entrada, _, _ = self._preparar(caso)
                for outro in apoio.ARQUIVOS:
                    caminho = os.path.join(entrada, outro)
                    if outro == nome:
                        mudou = (not os.path.exists(caminho)
                                 or apoio.sha256_arquivo(caminho) != apoio.sha256_fixture(outro))
                        self.assertTrue(mudou)
                    else:
                        self.assertEqual(apoio.sha256_arquivo(caminho),
                                         apoio.sha256_fixture(outro))

    def test_api_levanta_lote_rejeitado_sem_criar_pastas(self):
        for caso in VARIANTES_INVALIDAS:
            with self.subTest(caso=caso):
                _, entrada, raiz_api, _ = self._preparar(caso)
                with self.assertRaises(self.erros.LoteRejeitado):
                    apoio.executar_api(entrada, raiz_api)
                self.assertEqual(apoio.pastas_demo_4a(raiz_api), [])

    def test_cli_retorna_codigo_2_sem_criar_pastas(self):
        for caso in VARIANTES_INVALIDAS:
            with self.subTest(caso=caso):
                base, entrada, _, raiz_cli = self._preparar(caso)
                proc = apoio.executar_cli(entrada, raiz_cli, cwd=base)
                self.assertEqual(proc.returncode, CODIGO_REJEITADO,
                                 f'stdout={proc.stdout!r} stderr={proc.stderr!r}')
                self.assertEqual(apoio.pastas_demo_4a(raiz_cli), [])

    def test_hierarquia_de_erros(self):
        e = self.erros
        for classe in (e.LoteRejeitado, e.ReconciliacaoFalhou, e.CaminhoNaoPermitido):
            with self.subTest(classe=classe.__name__):
                self.assertTrue(issubclass(classe, e.ErroPipeline))
                self.assertTrue(issubclass(classe, Exception))


class TestCaminhos(unittest.TestCase):
    """Grupo 12: entrada dentro de <raiz>/data e recusada; CLI valida termina com 0."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix='demo4a_caminhos_',
                                                ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        _, self.erros = apoio.api()

    def _raiz_com_entrada_em_data(self, nome):
        raiz = os.path.join(self._tmp.name, nome)
        entrada = apoio.copiar_fixtures(os.path.join(raiz, 'data', 'entrada_demo'))
        return raiz, entrada

    def test_api_recusa_entrada_dentro_de_data(self):
        raiz, entrada = self._raiz_com_entrada_em_data('raiz_api')
        with self.assertRaises(self.erros.CaminhoNaoPermitido):
            apoio.executar_api(entrada, raiz)
        self.assertEqual(apoio.pastas_demo_4a(raiz), [])

    def test_cli_recusa_entrada_dentro_de_data_com_codigo_4(self):
        raiz, entrada = self._raiz_com_entrada_em_data('raiz_cli')
        proc = apoio.executar_cli(entrada, raiz, cwd=self._tmp.name)
        self.assertEqual(proc.returncode, CODIGO_CAMINHO,
                         f'stdout={proc.stdout!r} stderr={proc.stderr!r}')
        self.assertEqual(apoio.pastas_demo_4a(raiz), [])

    def test_api_recusa_saida_redirecionada_para_fora_da_raiz(self):
        """Saida fora das pastas permitidas: <raiz>/data/curated/demo_4a e uma juncao (ou link
        simbolico) que aponta para fora da raiz. O pipeline deve recusar sem gravar nada la fora
        e sem publicar nenhuma camada do lote. (Lacuna declarada pelo autor dos testes; ETAPA 4A.)"""
        raiz = os.path.join(self._tmp.name, 'raiz_juncao')
        fora = os.path.join(self._tmp.name, 'fora_da_raiz')
        os.makedirs(os.path.join(raiz, 'data', 'curated'))
        os.makedirs(fora)
        juncao = os.path.join(raiz, 'data', 'curated', 'demo_4a')
        try:
            import _winapi
            _winapi.CreateJunction(fora, juncao)
        except Exception:
            try:
                os.symlink(fora, juncao, target_is_directory=True)
            except Exception as e:  # sem suporte a juncao nem symlink
                self.skipTest(f'nao foi possivel criar juncao/symlink: {e!r}')
        with self.assertRaises(self.erros.CaminhoNaoPermitido):
            apoio.executar_api(apoio.FIXTURES, raiz)
        self.assertEqual(os.listdir(fora), [], 'o pipeline gravou fora da raiz')
        for camada in (('data', 'staging'), ('data', 'analytics'), ('outputs',)):
            with self.subTest(camada='/'.join(camada)):
                self.assertFalse(os.path.exists(os.path.join(raiz, *camada, 'demo_4a')),
                                 'camada publicada apesar da recusa')

    def test_cli_com_fixtures_validas_retorna_0_e_igual_a_api(self):
        raiz_cli = os.path.join(self._tmp.name, 'raiz_cli_ok')
        raiz_api = os.path.join(self._tmp.name, 'raiz_api_ok')
        os.makedirs(raiz_cli)
        os.makedirs(raiz_api)
        proc = apoio.executar_cli(apoio.FIXTURES, raiz_cli, cwd=self._tmp.name)
        self.assertEqual(proc.returncode, CODIGO_OK,
                         f'stdout={proc.stdout!r} stderr={proc.stderr!r}')
        r_api = apoio.executar_api(apoio.FIXTURES, raiz_api)
        lote = r_api['lote']
        r_cli = {'lote': lote, 'diretorios': {
            'staging': os.path.join(raiz_cli, 'data', 'staging', 'demo_4a', lote),
            'curated': os.path.join(raiz_cli, 'data', 'curated', 'demo_4a', lote),
            'analytics': os.path.join(raiz_cli, 'data', 'analytics', 'demo_4a', lote),
            'outputs': os.path.join(raiz_cli, 'outputs', 'demo_4a', lote),
        }}
        for camada, caminho in r_cli['diretorios'].items():
            with self.subTest(camada=camada):
                self.assertTrue(os.path.isdir(caminho), f'pasta do lote ausente: {camada}')
        self.assertEqual(apoio.hashes_lote(r_cli), apoio.hashes_lote(r_api))


if __name__ == '__main__':
    unittest.main()
