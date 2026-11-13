"""DEMO-4A, grupo 13: fuso America/Sao_Paulo e fallback UTC-03:00 sem tzdata. Caixa-preta.

Variante temporaria: as fixtures + UMA venda nova no fim de vendas.csv (linha fisica 31),
com hora anterior a 2019-02-17 (fim do ultimo horario de verao).
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

LINHA_NOVA = b'EMP01,ALFA,V0028,2019-01-10T10:00:00-02:00,AG01,1,3.50,3.50\n'
NUMERO_LINHA_NOVA = 31


class TestFusoFallback(unittest.TestCase):
    """Grupo 13: com fallback, instante anterior a 2019-02-17 vira DATA_INVALIDA."""

    @classmethod
    def setUpClass(cls):
        cls.zoneinfo_ok = apoio.zoneinfo_disponivel()
        cls._tmp = tempfile.TemporaryDirectory(prefix='demo4a_fuso_', ignore_cleanup_errors=True)
        try:
            entrada = apoio.copiar_fixtures(os.path.join(cls._tmp.name, 'entrada'))
            caminho = os.path.join(entrada, 'vendas.csv')
            with open(caminho, 'rb') as f:
                original = f.read()
            assert original.endswith(b'\n') and len(original.splitlines()) == NUMERO_LINHA_NOVA - 1
            with open(caminho, 'ab') as f:
                f.write(LINHA_NOVA)
            raiz = os.path.join(cls._tmp.name, 'raiz')
            os.makedirs(raiz)
            cls.exec = apoio.Execucao(raiz, apoio.executar_api(entrada, raiz))
        except BaseException:
            cls._tmp.cleanup()
            raise

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_manifesto_registra_o_modo_de_fuso(self):
        fuso = self.exec.json('staging', 'manifesto.json')['fuso']
        self.assertEqual(fuso['nome'], apoio.FUSO_NOME)
        esperado = apoio.MODO_ZONEINFO if self.zoneinfo_ok else apoio.MODO_FALLBACK
        self.assertEqual(fuso['modo'], esperado)

    def test_fallback_marca_data_anterior_a_2019_02_17_como_invalida(self):
        if self.zoneinfo_ok:
            self.skipTest('zoneinfo resolve America/Sao_Paulo neste ambiente: o fallback '
                          'UTC-03:00 nao e usado, entao a regra de DATA_INVALIDA pre-2019-02-17 '
                          'nao se aplica aqui.')
        linha = self.exec.staging_por_linha('vendas')[NUMERO_LINHA_NOVA]
        self.assertEqual(linha['id_venda'], 'V0028')
        self.assertEqual(linha['status'], 'QUARENTENA')
        self.assertEqual(linha['motivo_principal'], 'DATA_INVALIDA')
        self.assertEqual(linha['causas'], 'DATA_INVALIDA')
        self.assertEqual(linha['competencia'], '')

    def test_zoneinfo_converte_horario_de_verao_e_exclui_por_periodo(self):
        if not self.zoneinfo_ok:
            self.skipTest('zoneinfo nao resolve America/Sao_Paulo (sem tzdata): o pipeline usa o '
                          'fallback UTC-03:00; a conversao com horario de verao nao se aplica.')
        linha = self.exec.staging_por_linha('vendas')[NUMERO_LINHA_NOVA]
        self.assertEqual(linha['id_venda'], 'V0028')
        self.assertEqual(linha['status'], 'FORA_PERIODO')
        self.assertEqual(linha['causas'], '')
        self.assertEqual(linha['competencia'], '2019-01-10')

    def test_linhas_originais_nao_mudam_com_a_variante(self):
        gab = apoio.carregar_gabarito()
        obtidas = self.exec.staging_por_linha('vendas')
        for n, esperado in gab['vendas']['linhas'].items():
            with self.subTest(linha=n):
                self.assertEqual(obtidas[int(n)]['status'], esperado['status'])
                self.assertEqual(obtidas[int(n)]['causas'], apoio.lista(esperado['causas']))


if __name__ == '__main__':
    unittest.main()
