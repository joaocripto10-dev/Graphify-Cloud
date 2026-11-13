"""DEMO-4A, grupo 9: reconciliacao financeira e de registros (indicadores.csv e
reconciliacao.json) contra o gabarito, ao centavo, em Decimal. Caixa-preta.

Uso: python -I -m unittest discover -s tests
"""
import os
import sys
import unittest
from decimal import Decimal

_AQUI = os.path.dirname(os.path.abspath(__file__))
for _p in (_AQUI, os.path.join(os.path.dirname(_AQUI), 'src')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import _apoio_demo_4a as apoio  # noqa: E402

ZERO = Decimal('0')


class TestReconciliacaoFinanceiraERegistros(apoio.CasoComExecucao):
    """Grupo 9: faturamento, quantidade vendida e estoque = gabarito; reconciliacao ok."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fat = cls.gab['faturamento']

    def _conferir_mapa(self, obtido, esperado, rotulo):
        """Chaves do gabarito batem ao centavo; chaves extras so sao toleradas com valor zero."""
        for chave, valor in esperado.items():
            with self.subTest(indicador=rotulo, chave=chave):
                self.assertIn(chave, obtido)
                self.assertEqual(obtido[chave], Decimal(valor))
        for chave in set(obtido) - set(esperado):
            with self.subTest(indicador=rotulo, chave_extra=chave):
                self.assertEqual(obtido[chave], ZERO, 'valor fora do gabarito')

    def test_cabecalho_exato_e_ordenacao_dos_indicadores(self):
        cab, linhas = self.exec.csv('analytics', 'indicadores.csv')
        self.assertEqual(cab, apoio.CABECALHO_INDICADORES)
        chaves = [(l['indicador'], l['entidade'], l['empresa'], l['unidade'],
                   l['codigo_produto'], l['data_referencia']) for l in linhas]
        self.assertEqual(chaves, sorted(chaves))
        self.assertEqual(len(chaves), len(set(chaves)), 'indicador repetido no mesmo grao')
        for l in linhas:
            with self.subTest(linha=l):
                self.assertEqual(l['lote'], self.exec.lote)
                self.assertRegex(l['valor'], apoio.RE_DECIMAL_SEM_EXPOENTE)

    def test_faturamento_bruto_valido_por_empresa(self):
        linhas = self.exec.indicadores('faturamento_bruto_valido')
        obtido = apoio.valores_decimais(linhas, lambda l: l['empresa'])
        esperado = {emp: v['total'] for emp, v in self.fat.items()}
        self._conferir_mapa(obtido, esperado, 'faturamento_bruto_valido')

    def test_faturamento_por_unidade(self):
        linhas = self.exec.indicadores('faturamento_por_unidade')
        obtido = apoio.valores_decimais(linhas, lambda l: (l['empresa'], l['unidade']))
        esperado = {(emp, u): v for emp, d in self.fat.items() for u, v in d['por_unidade'].items()}
        self._conferir_mapa(obtido, esperado, 'faturamento_por_unidade')

    def test_faturamento_por_produto(self):
        linhas = self.exec.indicadores('faturamento_por_produto')
        obtido = apoio.valores_decimais(linhas, lambda l: (l['empresa'], l['codigo_produto']))
        esperado = {(emp, p): v for emp, d in self.fat.items() for p, v in d['por_produto'].items()}
        self._conferir_mapa(obtido, esperado, 'faturamento_por_produto')

    def test_dinheiro_com_duas_casas_e_periodo_declarado(self):
        for nome in ('faturamento_bruto_valido', 'faturamento_por_unidade',
                     'faturamento_por_produto'):
            for l in self.exec.indicadores(nome):
                with self.subTest(indicador=nome, empresa=l['empresa'], unidade=l['unidade'],
                                  produto=l['codigo_produto']):
                    self.assertRegex(l['valor'], apoio.RE_DINHEIRO)
                    self.assertEqual(l['periodo_inicio'], '2026-10-01')
                    self.assertEqual(l['periodo_fim'], '2026-10-31')

    def test_soma_por_unidade_igual_soma_por_produto_igual_total(self):
        totais = apoio.valores_decimais(self.exec.indicadores('faturamento_bruto_valido'),
                                        lambda l: l['empresa'])
        for empresa, total in totais.items():
            with self.subTest(empresa=empresa):
                por_unidade = sum((Decimal(l['valor'])
                                   for l in self.exec.indicadores('faturamento_por_unidade')
                                   if l['empresa'] == empresa), ZERO)
                por_produto = sum((Decimal(l['valor'])
                                   for l in self.exec.indicadores('faturamento_por_produto')
                                   if l['empresa'] == empresa), ZERO)
                self.assertEqual(por_unidade, total)
                self.assertEqual(por_produto, total)
        # Conferencia independente do gabarito (sanidade da propria referencia).
        for empresa, d in self.fat.items():
            with self.subTest(gabarito=empresa):
                total = Decimal(d['total'])
                self.assertEqual(sum(map(Decimal, d['por_unidade'].values()), ZERO), total)
                self.assertEqual(sum(map(Decimal, d['por_produto'].values()), ZERO), total)

    def test_faturamento_curated_igual_ao_total(self):
        _, vendas = self.exec.csv('curated', 'vendas_consolidadas.csv')
        for empresa, d in self.fat.items():
            with self.subTest(empresa=empresa):
                soma = sum((Decimal(l['valor']) for l in vendas if l['empresa'] == empresa), ZERO)
                self.assertEqual(soma, Decimal(d['total']))
        staging = self.exec.staging_por_linha('vendas')
        soma_staging = sum((Decimal(l['valor_calculado']) for l in staging.values()
                            if l['status'] == 'VALIDO'), ZERO)
        soma_curated = sum((Decimal(l['valor']) for l in vendas), ZERO)
        self.assertEqual(soma_curated, soma_staging)

    def test_quantidade_vendida_com_unidade_de_medida(self):
        linhas = self.exec.indicadores('quantidade_vendida')
        obtido = {}
        for l in linhas:
            chave = (l['empresa'], l['codigo_produto'])
            self.assertNotIn(chave, obtido, 'mesmo produto com mais de uma linha/unidade')
            obtido[chave] = (Decimal(l['valor']), l['unidade_medida'])
        esperado = {(emp, p): (Decimal(v['quantidade']), v['unidade_medida'])
                    for emp, d in self.gab['quantidade_vendida'].items() for p, v in d.items()}
        for chave, (qtd, um) in esperado.items():
            with self.subTest(chave=chave):
                self.assertIn(chave, obtido)
                self.assertEqual(obtido[chave], (qtd, um))
        for chave in set(obtido) - set(esperado):
            with self.subTest(chave_extra=chave):
                self.assertEqual(obtido[chave][0], ZERO)

    def test_estoque_disponivel_com_data_de_referencia(self):
        linhas = self.exec.indicadores('estoque_disponivel')
        obtido = {}
        for l in linhas:
            chave = (l['empresa'], l['unidade'], l['codigo_produto'], l['data_referencia'])
            self.assertNotIn(chave, obtido, f'foto de estoque repetida: {chave}')
            self.assertNotEqual(l['data_referencia'], '', 'estoque sem data de referencia')
            obtido[chave] = (Decimal(l['valor']), l['unidade_medida'])
        esperado = {(e['empresa'], e['unidade'], e['codigo_produto'], e['data_referencia']):
                    (Decimal(e['quantidade']), e['unidade_medida'])
                    for e in self.gab['estoque_disponivel']}
        self.assertEqual(obtido, esperado)

    def test_reconciliacao_json_ok(self):
        rec = self.exec.json('outputs', 'reconciliacao.json')
        self.assertIs(rec['ok'], True)
        verificacoes = rec['verificacoes']
        self.assertGreater(len(verificacoes), 0)
        ids = [v['id'] for v in verificacoes]
        self.assertEqual(ids, sorted(ids), 'verificacoes ordenadas por id')
        self.assertEqual(len(ids), len(set(ids)))
        for v in verificacoes:
            with self.subTest(id=v.get('id')):
                for campo in ('id', 'descricao', 'esperado', 'obtido', 'ok'):
                    self.assertIn(campo, v)
                self.assertIs(v['ok'], True)


if __name__ == '__main__':
    unittest.main()
