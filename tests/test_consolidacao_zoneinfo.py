"""FASE 4B (R4): fuso America/Sao_Paulo com zoneinfo real e fallback forcado, reproduziveis.

O arquivo de fuso vem de tests/fixtures/tzif (proveniencia em PROVENIENCIA.md) e chega ao
motor so por PYTHONTZPATH ABSOLUTO, num subprocesso da CLI com ambiente explicito. Nada e
instalado. Se o arquivo faltar ou divergir, os testes FALHAM (nao sao pulados).

Variante: fixtures + 9 vendas historicas (V0100-V0108) no fim de vendas.csv.
Uso: python -I -m unittest discover -s tests
"""
import csv
import hashlib
import importlib.util
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone

_AQUI = os.path.dirname(os.path.abspath(__file__))
for _p in (_AQUI, os.path.join(os.path.dirname(_AQUI), 'src')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import _apoio_demo_4a as apoio  # noqa: E402

DIR_TZ = os.path.join(apoio.DIR_TESTES, 'fixtures', 'tzif')
ARQ_TZ = os.path.join(DIR_TZ, 'America', 'Sao_Paulo')
SHA_TZ = '04c06744ee3fe078ef3b8b779e38eb30666bf993e67a092fcaf2fc28f63a64ce'  # PROVENIENCIA.md
LOTE_BASE = 'DEMO4A-cc6f21e0d609'
PRIMEIRA_LINHA_NOVA = 31

# (id, data na fonte, local esperado com zoneinfo, competencia, aceita no fallback?)
CASOS = [
    ('V0100', '2000-01-01T12:00:00+00:00', '2000-01-01T10:00:00-02:00', '2000-01-01', False),
    ('V0101', '2018-11-04T02:59:59+00:00', '2018-11-03T23:59:59-03:00', '2018-11-03', False),
    ('V0102', '2018-11-04T03:00:00+00:00', '2018-11-04T01:00:00-02:00', '2018-11-04', False),
    ('V0103', '2018-12-15T12:00:00+00:00', '2018-12-15T10:00:00-02:00', '2018-12-15', False),
    ('V0104', '2019-02-17T01:59:59+00:00', '2019-02-16T23:59:59-02:00', '2019-02-16', False),
    ('V0105', '2019-02-17T02:00:00+00:00', '2019-02-16T23:00:00-03:00', '2019-02-16', False),
    ('V0106', '2019-02-17T02:59:59+00:00', '2019-02-16T23:59:59-03:00', '2019-02-16', False),
    ('V0107', '2019-02-17T03:00:00+00:00', '2019-02-17T00:00:00-03:00', '2019-02-17', True),
    ('V0108', '2019-02-16T23:30:00-02:00', '2019-02-16T23:30:00-02:00', '2019-02-16', False),
]
ACEITOS_PRA_COMPARAR = ('manifesto.json', 'relatorio_qualidade.md', 'execucao.json')


def _sha(caminho):
    with open(caminho, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def ler_tzif(caminho):
    """Le o bloco v2 (64 bits) de um TZif: [(instante UTC, deslocamento s, isdst)]."""
    with open(caminho, 'rb') as f:
        dados = f.read()
    if dados[:4] != b'TZif' or dados[4:5] not in (b'2', b'3', b'4'):
        raise ValueError('nao e TZif v2+')

    def cabecalho(pos):
        return struct.unpack('>6l', dados[pos + 20:pos + 44])

    isut, isstd, leap, tempos, tipos, chars = cabecalho(0)
    pos = 44 + tempos * 5 + tipos * 6 + chars + leap * 8 + isstd + isut
    if dados[pos:pos + 4] != b'TZif':
        raise ValueError('bloco v2 ausente')
    isut, isstd, leap, tempos, tipos, chars = cabecalho(pos)
    pos += 44
    instantes = struct.unpack(f'>{tempos}q', dados[pos:pos + 8 * tempos])
    pos += 8 * tempos
    indices = dados[pos:pos + tempos]
    pos += tempos
    info = [struct.unpack('>lBB', dados[pos + 6 * i:pos + 6 * i + 6]) for i in range(tipos)]
    # Segundos inteiros: o TZif pode ter um instante sentinela fora da faixa de datetime.
    return [(t, info[i][0], info[i][1]) for t, i in zip(instantes, indices)]


def _ambiente(tzpath):
    if not os.path.isabs(tzpath):
        raise AssertionError(f'PYTHONTZPATH precisa ser absoluto: {tzpath!r}')
    env = dict(os.environ)
    env['PYTHONTZPATH'] = tzpath
    env['PYTHONIOENCODING'] = 'utf-8'
    return env


def executar_cli_com_tz(entrada, raiz, tzpath, cwd):
    comando = [sys.executable, '-I', '-B', apoio.SCRIPT_CLI, '--entrada', str(entrada),
               '--periodo', apoio.PERIODO_CLI, '--raiz', str(raiz)]
    proc = subprocess.run(comando, capture_output=True, text=True, encoding='utf-8',
                          errors='replace', timeout=300, cwd=cwd, env=_ambiente(tzpath))
    if proc.returncode != 0:
        raise AssertionError(f'CLI terminou com {proc.returncode}: {proc.stderr}')
    lote = next(l.split(': ', 1)[1] for l in proc.stdout.splitlines()
                if l.startswith('lote: '))
    return apoio.Execucao(raiz, {'lote': lote, 'diretorios': {
        'staging': os.path.join(raiz, 'data', 'staging', 'demo_4a', lote),
        'curated': os.path.join(raiz, 'data', 'curated', 'demo_4a', lote),
        'analytics': os.path.join(raiz, 'data', 'analytics', 'demo_4a', lote),
        'outputs': os.path.join(raiz, 'outputs', 'demo_4a', lote)}}), proc


def montar_variante(destino):
    entrada = apoio.copiar_fixtures(destino)
    caminho = os.path.join(entrada, 'vendas.csv')
    with open(caminho, 'rb') as f:
        original = f.read()
    assert original.endswith(b'\n') and len(original.splitlines()) == PRIMEIRA_LINHA_NOVA - 1
    with open(caminho, 'ab') as f:
        for ident, data, *_ in CASOS:
            f.write(f'EMP01,ALFA,{ident},{data},AG01,1,3.50,3.50\n'.encode('ascii'))
    return entrada


def conversoes(execucao):
    """{linha: valor_depois} das transformacoes CONVERTE_FUSO de vendas."""
    _, linhas = execucao.csv('curated', 'transformacoes.csv')
    return {int(l['linha_origem']): (l['valor_antes'], l['valor_depois']) for l in linhas
            if l['entidade'] == 'vendas' and l['regra'] == 'CONVERTE_FUSO'}


class TestArquivoTZif(unittest.TestCase):
    """O arquivo versionado existe, tem o hash registrado e as transicoes conhecidas."""

    def test_arquivo_presente_e_com_hash_da_proveniencia(self):
        self.assertTrue(os.path.isfile(ARQ_TZ), f'arquivo de fuso ausente: {ARQ_TZ}')
        self.assertEqual(_sha(ARQ_TZ), SHA_TZ)
        self.assertTrue(os.path.isfile(os.path.join(DIR_TZ, 'PROVENIENCIA.md')))

    def test_transicoes_de_2018_e_2019_lidas_sem_zoneinfo(self):
        trans = ler_tzif(ARQ_TZ)
        porinstante = {t: (off, dst) for t, off, dst in trans}
        inicio = int(datetime(2018, 11, 4, 3, 0, tzinfo=timezone.utc).timestamp())
        fim = int(datetime(2019, 2, 17, 2, 0, tzinfo=timezone.utc).timestamp())
        self.assertEqual(porinstante.get(inicio), (-7200, 1))
        self.assertEqual(porinstante.get(fim), (-10800, 0))
        self.assertEqual(trans[-1][0], fim, 'a ultima transicao deve ser o fim de 2019')


class _CasoTZ(unittest.TestCase):
    tzpath = None  # definido pela subclasse

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix='demo4a_tz_')
        try:
            tz = cls.preparar_tzpath()
            cls.variante, cls.proc_var = executar_cli_com_tz(
                montar_variante(os.path.join(cls._tmp, 'entrada')),
                cls.nova_raiz('raiz_var'), tz, cls._tmp)
            cls.fixtures, _ = executar_cli_com_tz(apoio.FIXTURES, cls.nova_raiz('raiz_fix'), tz,
                                                  cls._tmp)
        except BaseException:
            shutil.rmtree(cls._tmp, ignore_errors=True)
            raise

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._tmp, ignore_errors=True)

    @classmethod
    def nova_raiz(cls, nome):
        raiz = os.path.join(cls._tmp, nome)
        os.makedirs(raiz)
        return raiz

    def linha(self, n):
        return self.variante.staging_por_linha('vendas')[n]


class TestZoneinfoReal(_CasoTZ):
    """Modo zoneinfo com o TZif versionado: horario de verao historico e fevereiro de 2019."""

    @classmethod
    def preparar_tzpath(cls):
        if _sha(ARQ_TZ) != SHA_TZ:
            raise AssertionError('arquivo de fuso divergente da proveniencia')
        return os.path.abspath(DIR_TZ)

    def test_manifesto_registra_zoneinfo(self):
        for ex in (self.variante, self.fixtures):
            with self.subTest(lote=ex.lote):
                fuso = ex.json('staging', 'manifesto.json')['fuso']
                self.assertEqual(fuso, {'nome': apoio.FUSO_NOME, 'modo': apoio.MODO_ZONEINFO})
        self.assertNotIn('fallback', self.proc_var.stderr)

    def test_conversoes_historicas(self):
        conv = conversoes(self.variante)
        for i, (ident, data, local, comp, _) in enumerate(CASOS):
            n = PRIMEIRA_LINHA_NOVA + i
            with self.subTest(id=ident, data=data):
                linha = self.linha(n)
                self.assertEqual(linha['id_venda'], ident)
                self.assertEqual(linha['status'], 'FORA_PERIODO')
                self.assertEqual(linha['causas'], '')
                self.assertEqual(linha['competencia'], comp)
                self.assertEqual(conv.get(n), (data, local))

    def test_fixtures_aprovadas_iguais_ao_fallback(self):
        """Nao regressao: nas fixtures (2026, sem horario de verao) zoneinfo = fallback."""
        self.assertEqual(self.fixtures.lote, LOTE_BASE)
        with tempfile.TemporaryDirectory(prefix='demo4a_tz_vazio_') as base:
            vazio = os.path.join(base, 'tz_vazio')
            raiz = os.path.join(base, 'raiz')
            os.makedirs(vazio)
            os.makedirs(raiz)
            fb, _ = executar_cli_com_tz(apoio.FIXTURES, raiz, os.path.abspath(vazio), base)
            self.assertEqual(fb.json('staging', 'manifesto.json')['fuso']['modo'],
                             apoio.MODO_FALLBACK)
            h_zi = apoio.hashes_lote(self.fixtures.resultado, ignorar=ACEITOS_PRA_COMPARAR)
            h_fb = apoio.hashes_lote(fb.resultado, ignorar=ACEITOS_PRA_COMPARAR)
            self.assertEqual(len(h_zi), 12)
            self.assertEqual(h_zi, h_fb)
            m_zi = self.fixtures.json('staging', 'manifesto.json')
            m_fb = fb.json('staging', 'manifesto.json')
            m_fb['fuso']['modo'] = apoio.MODO_ZONEINFO
            self.assertEqual(m_zi, m_fb)


@unittest.skipIf(importlib.util.find_spec('tzdata') is not None,
                 'pacote tzdata instalado: o fallback nao pode ser forcado por PYTHONTZPATH')
class TestFallbackForcado(_CasoTZ):
    """PYTHONTZPATH aponta para pasta vazia: fallback UTC-03:00 deterministico."""

    @classmethod
    def preparar_tzpath(cls):
        vazio = os.path.join(cls._tmp, 'tz_vazio')
        os.makedirs(vazio)
        return os.path.abspath(vazio)

    def test_manifesto_registra_fallback(self):
        fuso = self.variante.json('staging', 'manifesto.json')['fuso']
        self.assertEqual(fuso['modo'], apoio.MODO_FALLBACK)
        self.assertEqual(self.fixtures.lote, LOTE_BASE)

    def test_limite_conservador_do_fallback(self):
        conv = conversoes(self.variante)
        for i, (ident, data, _, comp, aceito) in enumerate(CASOS):
            n = PRIMEIRA_LINHA_NOVA + i
            with self.subTest(id=ident, data=data):
                linha = self.linha(n)
                self.assertEqual(linha['id_venda'], ident)
                if aceito:
                    self.assertEqual(linha['status'], 'FORA_PERIODO')
                    self.assertEqual(linha['competencia'], comp)
                    self.assertEqual(conv.get(n), (data, '2019-02-17T00:00:00-03:00'))
                else:
                    self.assertEqual(linha['status'], 'QUARENTENA')
                    self.assertEqual(linha['causas'], 'DATA_INVALIDA')
                    self.assertEqual(linha['competencia'], '')
                    self.assertNotIn(n, conv)


if __name__ == '__main__':
    unittest.main()
