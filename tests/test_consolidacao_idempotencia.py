"""DEMO-4A, grupo 10 (idempotencia) e formato fisico das saidas. Caixa-preta.

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

ARQUIVOS_ESPERADOS = {
    'staging': {'manifesto.json', 'unidades.csv', 'produtos.csv', 'vendas.csv', 'estoque.csv'},
    'curated': set(apoio.CABECALHOS_CURATED),
    'analytics': {'indicadores.csv'},
    'outputs': {'reconciliacao.json', 'relatorio_qualidade.md', 'execucao.json'},
}


class TestIdempotencia(unittest.TestCase):
    """Grupo 10: mesma entrada -> arquivos de dados identicos byte a byte (exceto execucao.json)."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(prefix='demo4a_idem_', ignore_cleanup_errors=True)
        cls.raiz_a = os.path.join(cls._tmp.name, 'raiz_a')
        cls.raiz_b = os.path.join(cls._tmp.name, 'raiz_b')
        os.makedirs(cls.raiz_a)
        os.makedirs(cls.raiz_b)
        try:
            cls.r1 = apoio.executar_api(apoio.FIXTURES, cls.raiz_a)
            cls.h1 = apoio.hashes_lote(cls.r1)
            # Arquivo estranho no lote: a reexecucao deve substituir o conteudo por inteiro.
            cls.lixo = os.path.join(cls.r1['diretorios']['staging'], 'lixo_de_teste.txt')
            with open(cls.lixo, 'w', encoding='utf-8') as f:
                f.write('nao deve sobreviver a reexecucao\n')
            cls.r2 = apoio.executar_api(apoio.FIXTURES, cls.raiz_a)
            cls.h2 = apoio.hashes_lote(cls.r2)
            cls.r3 = apoio.executar_api(apoio.FIXTURES, cls.raiz_b)
            cls.h3 = apoio.hashes_lote(cls.r3)
        except BaseException:
            cls._tmp.cleanup()
            raise

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_lote_estavel_e_no_formato(self):
        self.assertRegex(self.r1['lote'], apoio.RE_LOTE)
        self.assertEqual(self.r1['lote'], self.r2['lote'])
        self.assertEqual(self.r1['lote'], self.r3['lote'])

    def test_mesma_raiz_reexecutada_gera_arquivos_identicos(self):
        self.assertEqual(self.h2, self.h1)

    def test_outra_raiz_gera_arquivos_identicos(self):
        self.assertEqual(self.h3, self.h1)

    def test_reexecucao_substitui_o_conteudo_do_lote(self):
        self.assertFalse(os.path.exists(self.lixo), 'arquivo antigo sobreviveu a reexecucao')

    def test_pastas_do_lote_seguem_a_interface(self):
        lote = self.r1['lote']
        esperado = {
            'staging': os.path.join(self.raiz_a, 'data', 'staging', 'demo_4a', lote),
            'curated': os.path.join(self.raiz_a, 'data', 'curated', 'demo_4a', lote),
            'analytics': os.path.join(self.raiz_a, 'data', 'analytics', 'demo_4a', lote),
            'outputs': os.path.join(self.raiz_a, 'outputs', 'demo_4a', lote),
        }
        for camada, caminho in esperado.items():
            with self.subTest(camada=camada):
                self.assertTrue(apoio.mesmo_caminho(self.r2['diretorios'][camada], caminho))
                self.assertEqual(os.listdir(os.path.dirname(caminho)), [lote],
                                 'mais de um lote na pasta demo_4a')

    def test_conjunto_de_arquivos_por_camada(self):
        for camada, nomes in ARQUIVOS_ESPERADOS.items():
            with self.subTest(camada=camada):
                presentes = set(os.listdir(self.r2['diretorios'][camada]))
                self.assertEqual(presentes, nomes)

    def test_execucao_json_e_o_unico_com_horario(self):
        execucao = apoio.ler_json(os.path.join(self.r2['diretorios']['outputs'], 'execucao.json'))
        self.assertIn('inicio', execucao)
        self.assertIn('fim', execucao)
        self.assertNotIn(('outputs', 'execucao.json'), self.h1)


class TestFormatoDasSaidas(apoio.CasoComExecucao):
    """Esquema das saidas: UTF-8 sem BOM, terminador \\n, arquivo_origem sem caminho."""

    def _arquivos(self):
        for camada in apoio.CAMADAS:
            base = self.exec.dirs[camada]
            for nome in sorted(os.listdir(base)):
                yield camada, nome, os.path.join(base, nome)

    def test_utf8_sem_bom_e_terminador_lf(self):
        for camada, nome, caminho in self._arquivos():
            with self.subTest(camada=camada, arquivo=nome):
                with open(caminho, 'rb') as f:
                    dados = f.read()
                self.assertFalse(dados.startswith(b'\xef\xbb\xbf'), 'BOM presente')
                self.assertNotIn(b'\r', dados, 'terminador diferente de \\n')
                dados.decode('utf-8')
                if nome.endswith('.csv'):
                    self.assertTrue(dados.endswith(b'\n'))

    def test_arquivo_origem_e_so_o_nome_e_sem_caminhos_absolutos(self):
        caminhos_proibidos = [apoio.FIXTURES, apoio.FIXTURES.replace('\\', '/'), self.exec.raiz,
                              self.exec.raiz.replace('\\', '/')]
        for camada, nome, caminho in self._arquivos():
            if nome == 'execucao.json':
                continue
            with self.subTest(camada=camada, arquivo=nome):
                with open(caminho, encoding='utf-8') as f:
                    conteudo = f.read()
                for proibido in caminhos_proibidos:
                    self.assertNotIn(proibido, conteudo, 'caminho absoluto em arquivo de dados')
                if nome.endswith('.csv'):
                    _, linhas = apoio.ler_csv(caminho)
                    for l in linhas:
                        if 'arquivo_origem' in l:
                            self.assertIn(l['arquivo_origem'], apoio.ARQUIVOS)

    def test_relatorio_qualidade_nao_vazio(self):
        with open(self.exec.caminho('outputs', 'relatorio_qualidade.md'), encoding='utf-8') as f:
            self.assertNotEqual(f.read().strip(), '')


if __name__ == '__main__':
    unittest.main()
