"""DEMO-4A, grupos 1 (leitura/manifesto) e 2 (preservacao das fontes). Caixa-preta.

Uso: python -I -m unittest discover -s tests
"""
import codecs
import os
import re
import sys
import tempfile
import unittest

_AQUI = os.path.dirname(os.path.abspath(__file__))
for _p in (_AQUI, os.path.join(os.path.dirname(_AQUI), 'src')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import _apoio_demo_4a as apoio  # noqa: E402

RE_HORARIO = re.compile(r'\d{2}:\d{2}')
CHAVES_DE_HORARIO = ('hora', 'horario', 'timestamp', 'gerado', 'executado', 'instante',
                     'duracao', 'momento')


def _textos_e_chaves(obj):
    """Percorre o JSON e devolve (todas as chaves, todos os valores string)."""
    chaves, textos = [], []
    pilha = [obj]
    while pilha:
        atual = pilha.pop()
        if isinstance(atual, dict):
            for k, v in atual.items():
                chaves.append(str(k))
                pilha.append(v)
        elif isinstance(atual, list):
            pilha.extend(atual)
        elif isinstance(atual, str):
            textos.append(atual)
    return chaves, textos


class TestLeituraManifesto(apoio.CasoComExecucao):
    """Grupo 1: manifesto.json do staging descreve as 4 fontes, sem horario."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manifesto = cls.exec.json('staging', 'manifesto.json')

    def test_retorno_da_api_segue_a_interface(self):
        r = self.exec.resultado
        self.assertIsInstance(r['lote'], str)
        self.assertRegex(r['lote'], apoio.RE_LOTE)
        self.assertEqual(set(r['diretorios']), set(apoio.CAMADAS))
        self.assertIs(r['reconciliacao_ok'], True)

    def test_contrato_lote_e_periodo(self):
        m = self.manifesto
        self.assertEqual(m['contrato'], 'DEMO-4A')
        self.assertEqual(m['lote'], self.exec.lote)
        self.assertEqual(m['periodo'], {'inicio': '2026-10-01', 'fim': '2026-10-31'})

    def test_quatro_arquivos_ordenados_por_nome(self):
        nomes = [a['arquivo'] for a in self.manifesto['arquivos']]
        self.assertEqual(nomes, list(apoio.ARQUIVOS))  # ARQUIVOS ja esta em ordem alfabetica
        self.assertEqual(nomes, sorted(nomes))

    def test_sha256_bytes_linhas_e_registros_conferem_com_as_fixtures(self):
        for item in self.manifesto['arquivos']:
            nome = item['arquivo']
            with self.subTest(arquivo=nome):
                caminho = os.path.join(apoio.FIXTURES, nome)
                with open(caminho, 'rb') as f:
                    conteudo = f.read()
                entidade = nome[:-len('.csv')]
                self.assertEqual(item['sha256'], apoio.sha256_arquivo(caminho))
                self.assertEqual(item['bytes'], len(conteudo))
                # Linha fisica: o cabecalho e a linha 1; linhas_fisicas inclui o cabecalho.
                self.assertEqual(item['linhas_fisicas'], len(conteudo.splitlines()))
                self.assertEqual(item['registros'], self.gab[entidade]['recebidos'])
                self.assertEqual(codecs.lookup(item['codificacao']).name, 'utf-8')

    def test_manifesto_sem_horario(self):
        chaves, textos = _textos_e_chaves(self.manifesto)
        # fuso.modo e um enumerado do contrato ("fallback_utc-03:00" contem um deslocamento
        # de fuso, nao um horario). So essa ocorrencia exata sai da varredura; qualquer outro
        # HH:MM no manifesto continua reprovando.
        modo = self.manifesto['fuso']['modo']
        self.assertIn(modo, (apoio.MODO_ZONEINFO, apoio.MODO_FALLBACK))
        textos.remove(modo)
        for k in chaves:
            with self.subTest(chave=k):
                self.assertFalse(any(p in k.lower() for p in CHAVES_DE_HORARIO),
                                 f'chave com cara de horario no manifesto: {k}')
        for t in textos:
            with self.subTest(valor=t):
                self.assertIsNone(RE_HORARIO.search(t), f'valor com horario no manifesto: {t}')

    def test_fuso_coerente_com_disponibilidade_de_zoneinfo(self):
        fuso = self.manifesto['fuso']
        self.assertEqual(fuso['nome'], apoio.FUSO_NOME)
        esperado = apoio.MODO_ZONEINFO if apoio.zoneinfo_disponivel() else apoio.MODO_FALLBACK
        self.assertEqual(fuso['modo'], esperado)


class TestPreservacaoFontes(unittest.TestCase):
    """Grupo 2: a entrada e so lida; nada e criado nas fixtures nem no repositorio."""

    @staticmethod
    def _foto_fixtures():
        foto = {}
        for nome in sorted(os.listdir(apoio.FIXTURES)):
            caminho = os.path.join(apoio.FIXTURES, nome)
            st = os.stat(caminho)
            sha = apoio.sha256_arquivo(caminho) if os.path.isfile(caminho) else None
            foto[nome] = (sha, st.st_mtime_ns, st.st_size)
        return foto

    @staticmethod
    def _foto_saidas_repo():
        """Conteudo atual das pastas demo_4a do repositorio (se existirem)."""
        alvos = [os.path.join(apoio.RAIZ_REPO, 'data', c, 'demo_4a')
                 for c in ('staging', 'curated', 'analytics')]
        alvos.append(os.path.join(apoio.RAIZ_REPO, 'outputs', 'demo_4a'))
        return {a: (sorted(os.listdir(a)) if os.path.isdir(a) else None) for a in alvos}

    def test_fixtures_intactas_apos_api_e_cli(self):
        antes = self._foto_fixtures()
        repo_antes = self._foto_saidas_repo()
        with tempfile.TemporaryDirectory(prefix='demo4a_preserva_',
                                         ignore_cleanup_errors=True) as tmp:
            raiz_api = os.path.join(tmp, 'raiz_api')
            raiz_cli = os.path.join(tmp, 'raiz_cli')
            os.makedirs(raiz_api)
            os.makedirs(raiz_cli)
            apoio.executar_api(apoio.FIXTURES, raiz_api)
            proc = apoio.executar_cli(apoio.FIXTURES, raiz_cli, cwd=tmp)
            self.assertEqual(proc.returncode, 0, proc.stderr)
        depois = self._foto_fixtures()
        self.assertEqual(set(depois), set(antes), 'arquivos criados/removidos nas fixtures')
        for nome, (sha, mtime, tamanho) in antes.items():
            with self.subTest(arquivo=nome):
                self.assertEqual(depois[nome][0], sha, 'sha256 mudou')
                self.assertEqual(depois[nome][1], mtime, 'mtime mudou')
                self.assertEqual(depois[nome][2], tamanho, 'tamanho mudou')
        self.assertEqual(self._foto_saidas_repo(), repo_antes,
                         'execucao com raiz temporaria alterou pastas demo_4a do repositorio')


if __name__ == '__main__':
    unittest.main()
