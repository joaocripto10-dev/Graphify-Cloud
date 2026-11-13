"""DEMO-4A, grupos 3 a 8: anomalias por linha, contagens, deduplicacao/conflito, segregacao,
relacionamentos, ocorrencias e historico de transformacoes. Caixa-preta, contra o gabarito.

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


def _linhas_com_status(gab, entidade, status):
    return {int(n) for n, l in gab[entidade]['linhas'].items() if l['status'] == status}


class TestAnomaliasLinhaALinha(apoio.CasoComExecucao):
    """Grupo 3: cada linha fisica de cada entidade tem o status/causas/alertas do gabarito."""

    def test_cabecalhos_exatos_do_staging(self):
        for entidade in apoio.ENTIDADES:
            with self.subTest(entidade=entidade):
                cab, _ = self.exec.staging(entidade)
                self.assertEqual(cab, apoio.cabecalho_staging(entidade))

    def test_cada_linha_fisica_aparece_exatamente_uma_vez_e_em_ordem(self):
        for entidade in apoio.ENTIDADES:
            with self.subTest(entidade=entidade):
                _, linhas = self.exec.staging(entidade)
                numeros = [int(l['linha_origem']) for l in linhas]
                recebidos = self.gab[entidade]['recebidos']
                self.assertEqual(numeros, list(range(2, recebidos + 2)))
                self.assertEqual(len(numeros), len(set(numeros)))

    def test_status_motivo_causas_e_alertas_por_linha(self):
        for entidade in apoio.ENTIDADES:
            obtidas = self.exec.staging_por_linha(entidade)
            for n, esperado in self.gab[entidade]['linhas'].items():
                with self.subTest(entidade=entidade, linha=n):
                    linha = obtidas[int(n)]
                    self.assertEqual(linha['status'], esperado['status'])
                    self.assertEqual(linha['motivo_principal'],
                                     apoio.texto(esperado['motivo_principal']))
                    self.assertEqual(linha['causas'], apoio.lista(esperado['causas']))
                    self.assertEqual(linha['alertas'], apoio.lista(esperado['alertas']))

    def test_competencia_das_vendas(self):
        obtidas = self.exec.staging_por_linha('vendas')
        for n, esperado in self.gab['vendas']['linhas'].items():
            with self.subTest(linha=n):
                self.assertEqual(obtidas[int(n)]['competencia'],
                                 apoio.texto(esperado['competencia']))

    def test_identificadores_normalizados_por_linha(self):
        vendas = self.exec.staging_por_linha('vendas')
        for n, esperado in self.gab['vendas']['linhas'].items():
            with self.subTest(entidade='vendas', linha=n):
                self.assertEqual(vendas[int(n)]['id_venda'], apoio.texto(esperado['id']))
        produtos = self.exec.staging_por_linha('produtos')
        for n, esperado in self.gab['produtos']['linhas'].items():
            with self.subTest(entidade='produtos', linha=n):
                self.assertEqual(produtos[int(n)]['codigo_produto'], esperado['codigo'])
        estoque = self.exec.staging_por_linha('estoque')
        for n, esperado in self.gab['estoque']['linhas'].items():
            with self.subTest(entidade='estoque', linha=n):
                l = estoque[int(n)]
                self.assertEqual(l['codigo_produto'], esperado['codigo'])
                self.assertEqual(l['unidade'], esperado['unidade'])
                self.assertEqual(l['data_referencia'], esperado['data_referencia'])
        unidades = self.exec.staging_por_linha('unidades')
        for n, esperado in self.gab['unidades']['linhas'].items():
            with self.subTest(entidade='unidades', linha=n):
                self.assertEqual(unidades[int(n)]['unidade'], esperado['unidade'])

    def test_rastreabilidade_do_staging(self):
        for entidade in apoio.ENTIDADES:
            sha = apoio.sha256_fixture(f'{entidade}.csv')
            _, linhas = self.exec.staging(entidade)
            for l in linhas:
                with self.subTest(entidade=entidade, linha=l['linha_origem']):
                    self.assertEqual(l['lote'], self.exec.lote)
                    self.assertEqual(l['arquivo_origem'], f'{entidade}.csv')
                    self.assertEqual(l['sha256_origem'], sha)
                    self.assertNotEqual(l['conteudo_original'], '')

    def test_linha_malformada_nao_e_interpretada(self):
        linha = self.exec.staging_por_linha('vendas')[28]
        for coluna in apoio.COLUNAS_FONTE['vendas'] + ['competencia']:
            with self.subTest(coluna=coluna):
                self.assertEqual(linha[coluna], '')
        self.assertIn('V0025', linha['conteudo_original'])
        self.assertIn('EXTRA', linha['conteudo_original'])

    def test_espacos_normalizados_e_original_preservado(self):
        linha = self.exec.staging_por_linha('vendas')[30]
        self.assertEqual(linha['codigo_produto'], 'ET01')
        self.assertIn(' ET01 ', linha['conteudo_original'])

    def test_validos_sem_causa_e_quarentena_com_causa(self):
        for entidade in apoio.ENTIDADES:
            _, linhas = self.exec.staging(entidade)
            for l in linhas:
                with self.subTest(entidade=entidade, linha=l['linha_origem']):
                    if l['status'] == 'VALIDO':
                        self.assertEqual(l['causas'], '')
                        self.assertEqual(l['motivo_principal'], '')
                    elif l['status'] == 'QUARENTENA':
                        self.assertNotEqual(l['causas'], '')
                        self.assertEqual(l['causas'].split('|')[0], l['motivo_principal'])


class TestContagensETaxa(apoio.CasoComExecucao):
    """Grupo 4: indicadores registros_* e taxa_inconsistencia por entidade = gabarito."""

    def test_status_do_staging_somam_o_gabarito(self):
        for entidade in apoio.ENTIDADES:
            _, linhas = self.exec.staging(entidade)
            for status in ('VALIDO', 'QUARENTENA', 'FORA_PERIODO', 'DUPLICATA_DESCARTADA'):
                with self.subTest(entidade=entidade, status=status):
                    obtido = sum(1 for l in linhas if l['status'] == status)
                    self.assertEqual(obtido, self.gab[entidade][status])

    def test_indicadores_de_contagem(self):
        for indicador, campo in apoio.INDICADORES_CONTAGEM.items():
            linhas = self.exec.indicadores(indicador)
            por_entidade = apoio.valores_decimais(linhas, lambda l: l['entidade'])
            for entidade in apoio.ENTIDADES:
                with self.subTest(indicador=indicador, entidade=entidade):
                    self.assertIn(entidade, por_entidade)
                    self.assertEqual(por_entidade[entidade],
                                     Decimal(self.gab[entidade][campo]))

    def test_taxa_de_inconsistencia_com_4_casas(self):
        linhas = {l['entidade']: l for l in self.exec.indicadores('taxa_inconsistencia')}
        for entidade in apoio.ENTIDADES:
            with self.subTest(entidade=entidade):
                esperado = self.gab[entidade]['taxa_inconsistencia']
                self.assertEqual(linhas[entidade]['valor'], esperado)  # texto: 4 casas fixas
                self.assertEqual(Decimal(linhas[entidade]['valor']), Decimal(esperado))

    def test_fechamento_recebidos_igual_soma_dos_status(self):
        for entidade in apoio.ENTIDADES:
            with self.subTest(entidade=entidade):
                g = self.gab[entidade]
                self.assertEqual(g['recebidos'], g['VALIDO'] + g['QUARENTENA']
                                 + g['FORA_PERIODO'] + g['DUPLICATA_DESCARTADA'])
                _, linhas = self.exec.staging(entidade)
                self.assertEqual(len(linhas), g['recebidos'])


class TestDeduplicacaoEConflito(apoio.CasoComExecucao):
    """Grupo 5: copias descartadas fora de curated; conflitos todos em quarentena."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _, cls.vendas = cls.exec.csv('curated', 'vendas_consolidadas.csv')
        _, cls.produtos = cls.exec.csv('curated', 'produtos_validos.csv')
        _, cls.estoque = cls.exec.csv('curated', 'estoque_posicao.csv')
        _, cls.quarentena = cls.exec.csv('curated', 'quarentena.csv')

    def _linhas_curated(self, linhas):
        return {int(l['linha_origem']) for l in linhas}

    def test_copias_descartadas_nao_estao_em_curated(self):
        self.assertNotIn(6, self._linhas_curated(self.vendas))
        self.assertNotIn(5, self._linhas_curated(self.produtos))
        self.assertNotIn(6, self._linhas_curated(self.estoque))

    def test_primeira_copia_segue_valida_em_curated(self):
        self.assertIn(5, self._linhas_curated(self.vendas))     # V0004
        self.assertIn(4, self._linhas_curated(self.produtos))   # AG01
        self.assertIn(5, self._linhas_curated(self.estoque))    # BETA/AG01

    def test_copias_descartadas_nao_sao_quarentena(self):
        em_quarentena = {(l['entidade'], int(l['linha_origem'])) for l in self.quarentena}
        for chave in (('vendas', 6), ('produtos', 5), ('estoque', 6)):
            with self.subTest(chave=chave):
                self.assertNotIn(chave, em_quarentena)

    def test_conflitos_todos_em_quarentena(self):
        por_chave = {(l['entidade'], int(l['linha_origem'])): l for l in self.quarentena}
        for entidade, linhas in (('vendas', (7, 8)), ('produtos', (7, 8)), ('estoque', (7, 8))):
            for n in linhas:
                with self.subTest(entidade=entidade, linha=n):
                    self.assertIn((entidade, n), por_chave)
                    l = por_chave[(entidade, n)]
                    self.assertEqual(l['motivo_principal'], 'CONFLITO_ID')
                    self.assertEqual(apoio.gravidade_normalizada(l['gravidade_maxima']), 'critica')

    def test_conflitos_ausentes_de_curated(self):
        self.assertNotIn('V0005', {l['id_venda'] for l in self.vendas})
        self.assertNotIn('SN01', {l['codigo_produto'] for l in self.produtos})
        self.assertNotIn(('BETA', 'GC01'),
                         {(l['unidade'], l['codigo_produto']) for l in self.estoque})

    def test_quarentena_csv_igual_ao_gabarito(self):
        cab, _ = self.exec.csv('curated', 'quarentena.csv')
        self.assertEqual(cab, apoio.CABECALHOS_CURATED['quarentena.csv'])
        esperado = {(e, n) for e in apoio.ENTIDADES
                    for n in _linhas_com_status(self.gab, e, 'QUARENTENA')}
        obtido = [(l['entidade'], int(l['linha_origem'])) for l in self.quarentena]
        self.assertEqual(len(obtido), len(set(obtido)), 'linha repetida na quarentena')
        self.assertEqual(set(obtido), esperado)
        self.assertEqual(obtido, sorted(obtido), 'ordenacao: entidade, linha_origem')

    def test_quarentena_motivo_causas_gravidade(self):
        for l in self.quarentena:
            e, n = l['entidade'], l['linha_origem']
            with self.subTest(entidade=e, linha=n):
                g = self.gab[e]['linhas'][n]
                self.assertEqual(l['lote'], self.exec.lote)
                self.assertEqual(l['arquivo_origem'], f'{e}.csv')
                self.assertEqual(l['motivo_principal'], g['motivo_principal'])
                self.assertEqual(l['causas'], apoio.lista(g['causas']))
                maxima = max((apoio.GRAVIDADE[c] for c in g['causas']),
                             key=apoio.ORDEM_GRAVIDADE.__getitem__)
                self.assertEqual(apoio.gravidade_normalizada(l['gravidade_maxima']), maxima)
                self.assertNotEqual(l['conteudo_original'], '')


class TestSegregacaoEmpresas(apoio.CasoComExecucao):
    """Grupo 6: nada da EMP02 se mistura a EMP01; nenhum indicador soma empresas."""

    def test_vendas_curated_sem_emp02(self):
        _, vendas = self.exec.csv('curated', 'vendas_consolidadas.csv')
        self.assertNotIn('EMP02', {l['empresa'] for l in vendas})
        self.assertEqual({l['empresa'] for l in vendas}, {'EMP01'})
        self.assertNotIn('V0010', {l['id_venda'] for l in vendas})

    def test_ds01_so_existe_sob_emp02(self):
        _, produtos = self.exec.csv('curated', 'produtos_validos.csv')
        ds01 = [l for l in produtos if l['codigo_produto'] == 'DS01']
        self.assertEqual(len(ds01), 1)
        self.assertEqual(ds01[0]['empresa'], 'EMP02')

    def test_v0020_produto_sem_cadastro_na_emp01(self):
        linha = self.exec.staging_por_linha('vendas')[23]
        self.assertEqual(linha['id_venda'], 'V0020')
        self.assertEqual(linha['status'], 'QUARENTENA')
        self.assertIn('PRODUTO_SEM_CADASTRO', linha['causas'].split('|'))

    def test_v0010_empresa_unidade_inconsistente(self):
        linha = self.exec.staging_por_linha('vendas')[13]
        self.assertEqual(linha['causas'].split('|'),
                         ['EMPRESA_UNIDADE_INCONSISTENTE', 'PRODUTO_SEM_CADASTRO'])

    def test_nenhum_indicador_de_faturamento_soma_empresas(self):
        empresas_conhecidas = {'EMP01', 'EMP02'}
        for nome in ('faturamento_bruto_valido', 'faturamento_por_unidade',
                     'faturamento_por_produto', 'quantidade_vendida'):
            for l in self.exec.indicadores(nome):
                with self.subTest(indicador=nome, linha=l):
                    self.assertIn(l['empresa'], empresas_conhecidas,
                                  'indicador sem empresa (total entre empresas?)')
        totais = [l['empresa'] for l in self.exec.indicadores('faturamento_bruto_valido')]
        self.assertEqual(len(totais), len(set(totais)), 'mais de um total por empresa')


class TestRelacionamentos(apoio.CasoComExecucao):
    """Grupo 7: juncao vendas x produtos sem multiplicacao e com rastreabilidade."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fonte_vendas = apoio.linhas_fonte('vendas.csv')
        cls.fonte_produtos = apoio.linhas_fonte('produtos.csv')
        cls.fonte_estoque = apoio.linhas_fonte('estoque.csv')
        validos = _linhas_com_status(cls.gab, 'produtos', 'VALIDO')
        cls.cadastro = {(cls.fonte_produtos[n]['empresa'], cls.fonte_produtos[n]['codigo_produto']):
                        (n, cls.fonte_produtos[n]) for n in validos}

    def test_cabecalhos_exatos_do_curated(self):
        for nome, esperado in apoio.CABECALHOS_CURATED.items():
            with self.subTest(arquivo=nome):
                cab, _ = self.exec.csv('curated', nome)
                self.assertEqual(cab, esperado)

    def test_produtos_validos_sem_chave_duplicada_e_igual_ao_gabarito(self):
        _, produtos = self.exec.csv('curated', 'produtos_validos.csv')
        chaves = [(l['empresa'], l['codigo_produto']) for l in produtos]
        self.assertEqual(len(chaves), len(set(chaves)), 'chave duplicada em produtos_validos')
        self.assertEqual(set(chaves), set(self.cadastro))
        self.assertEqual(chaves, sorted(chaves))
        for l in produtos:
            chave = (l['empresa'], l['codigo_produto'])
            with self.subTest(chave=chave):
                n, fonte = self.cadastro[chave]
                self.assertEqual(l['lote'], self.exec.lote)
                self.assertEqual(int(l['linha_origem']), n)
                self.assertEqual(l['arquivo_origem'], 'produtos.csv')
                for c in ('descricao', 'categoria', 'unidade_medida', 'status_cadastral'):
                    self.assertEqual(l[c], fonte[c])

    def test_vendas_consolidadas_tem_exatamente_as_linhas_validas(self):
        _, vendas = self.exec.csv('curated', 'vendas_consolidadas.csv')
        esperado = _linhas_com_status(self.gab, 'vendas', 'VALIDO')
        self.assertEqual(len(esperado), 9)
        obtido = [int(l['linha_origem']) for l in vendas]
        self.assertEqual(len(obtido), len(esperado), 'juncao multiplicou ou perdeu linhas')
        self.assertEqual(set(obtido), esperado)
        chaves = [(l['empresa'], l['unidade'], l['id_venda']) for l in vendas]
        self.assertEqual(chaves, sorted(chaves), 'ordenacao: empresa, unidade, id_venda')

    def test_vendas_consolidadas_atributos_e_rastreabilidade(self):
        _, vendas = self.exec.csv('curated', 'vendas_consolidadas.csv')
        sha = apoio.sha256_fixture('vendas.csv')
        for l in vendas:
            n = int(l['linha_origem'])
            with self.subTest(linha=n):
                g = self.gab['vendas']['linhas'][str(n)]
                fonte = self.fonte_vendas[n]
                _, produto = self.cadastro[(fonte['empresa'], fonte['codigo_produto'])]
                self.assertEqual(l['lote'], self.exec.lote)
                self.assertEqual(l['arquivo_origem'], 'vendas.csv')
                self.assertEqual(l['sha256_origem'], sha)
                self.assertEqual(l['id_venda'], g['id'])
                self.assertEqual(l['empresa'], fonte['empresa'])
                self.assertEqual(l['unidade'], fonte['unidade'])
                self.assertEqual(l['codigo_produto'], fonte['codigo_produto'])
                self.assertEqual(l['competencia'], g['competencia'])
                self.assertEqual(l['data_original'], fonte['data'])
                for c in ('descricao', 'categoria', 'unidade_medida', 'status_cadastral'):
                    self.assertEqual(l[c], produto[c], c)
                self.assertEqual(Decimal(l['quantidade']), Decimal(fonte['quantidade']))
                self.assertEqual(Decimal(l['preco_unitario']), Decimal(fonte['preco_unitario']))
                self.assertRegex(l['valor'], apoio.RE_DINHEIRO)
                self.assertEqual(Decimal(l['valor']), Decimal(g['valor']))
                self.assertEqual(l['alertas'], apoio.lista(g['alertas']))

    def test_estoque_posicao_tem_as_linhas_validas_com_unidade_de_medida(self):
        _, estoque = self.exec.csv('curated', 'estoque_posicao.csv')
        esperado = _linhas_com_status(self.gab, 'estoque', 'VALIDO')
        obtido = [int(l['linha_origem']) for l in estoque]
        self.assertEqual(len(obtido), len(esperado))
        self.assertEqual(set(obtido), esperado)
        chaves = [(l['empresa'], l['unidade'], l['codigo_produto'], l['data_referencia'])
                  for l in estoque]
        self.assertEqual(chaves, sorted(chaves))
        for l in estoque:
            n = int(l['linha_origem'])
            with self.subTest(linha=n):
                g = self.gab['estoque']['linhas'][str(n)]
                fonte = self.fonte_estoque[n]
                _, produto = self.cadastro[(fonte['empresa'], fonte['codigo_produto'])]
                self.assertEqual(l['lote'], self.exec.lote)
                self.assertEqual(l['arquivo_origem'], 'estoque.csv')
                self.assertEqual(l['data_referencia'], g['data_referencia'])
                self.assertEqual(Decimal(l['quantidade_disponivel']),
                                 Decimal(fonte['quantidade_disponivel']))
                self.assertEqual(l['unidade_medida'], produto['unidade_medida'])
                self.assertEqual(l['alertas'], apoio.lista(g['alertas']))


class TestOcorrenciasEHistorico(apoio.CasoComExecucao):
    """Grupo 8: ocorrencias.csv lista todas as causas/alertas; transformacoes.csv o historico."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _, cls.ocorrencias = cls.exec.csv('curated', 'ocorrencias.csv')
        _, cls.transformacoes = cls.exec.csv('curated', 'transformacoes.csv')

    def test_ocorrencias_contem_exatamente_causas_e_alertas_do_gabarito(self):
        esperado = set()
        for e in apoio.ENTIDADES:
            for n, g in self.gab[e]['linhas'].items():
                for codigo in g['causas'] + g['alertas']:
                    esperado.add((e, int(n), codigo))
        obtido = {(l['entidade'], int(l['linha_origem']), l['codigo']) for l in self.ocorrencias}
        self.assertEqual(obtido - esperado, set(), 'ocorrencias a mais')
        self.assertEqual(esperado - obtido, set(), 'ocorrencias faltando')

    def test_principal_sim_so_no_motivo_principal(self):
        for l in self.ocorrencias:
            e, n, codigo = l['entidade'], l['linha_origem'], l['codigo']
            with self.subTest(entidade=e, linha=n, codigo=codigo):
                g = self.gab[e]['linhas'][n]
                esperado = 'sim' if codigo == g['motivo_principal'] else 'nao'
                self.assertEqual(l['principal'], esperado)
        for e in apoio.ENTIDADES:
            for n, g in self.gab[e]['linhas'].items():
                if g['motivo_principal'] is None:
                    continue
                with self.subTest(entidade=e, linha=n):
                    principais = [l for l in self.ocorrencias if l['entidade'] == e
                                  and int(l['linha_origem']) == int(n) and l['principal'] == 'sim']
                    self.assertEqual({l['codigo'] for l in principais}, {g['motivo_principal']})

    def test_gravidade_bloqueante_e_rastreabilidade(self):
        for l in self.ocorrencias:
            codigo = l['codigo']
            with self.subTest(entidade=l['entidade'], linha=l['linha_origem'], codigo=codigo):
                self.assertEqual(l['lote'], self.exec.lote)
                self.assertEqual(l['arquivo_origem'], f"{l['entidade']}.csv")
                self.assertEqual(apoio.gravidade_normalizada(l['gravidade']),
                                 apoio.GRAVIDADE[codigo])
                self.assertIn(l['bloqueante'], ('sim', 'nao'))
                if codigo == 'PRODUTO_INATIVO':
                    self.assertEqual(l['bloqueante'], 'nao')
                    self.assertEqual(l['principal'], 'nao')
                elif codigo != 'DUPLICATA_EXATA':  # "descarta a copia": nao fixado pelo contrato
                    self.assertEqual(l['bloqueante'], 'sim')

    def test_ordenacao_das_ocorrencias(self):
        chaves = [(l['entidade'], int(l['linha_origem']), apoio.ORDEM_CODIGOS.index(l['codigo']))
                  for l in self.ocorrencias]
        self.assertEqual(chaves, sorted(chaves), 'ordenacao: entidade, linha_origem, codigo')

    def _transformacoes(self, regra):
        return [l for l in self.transformacoes if l['regra'] == regra]

    def test_regras_de_transformacao_no_dominio(self):
        permitidas = {'NORMALIZA_ESPACOS', 'CONVERTE_FUSO', 'DESCARTA_DUPLICATA',
                      'EXCLUI_FORA_PERIODO', 'EXCLUI_QUARENTENA'}
        self.assertEqual({l['regra'] for l in self.transformacoes} - permitidas, set())
        for l in self.transformacoes:
            with self.subTest(linha=l):
                self.assertEqual(l['lote'], self.exec.lote)
                self.assertEqual(l['arquivo_origem'], f"{l['entidade']}.csv")

    def test_normaliza_espacos(self):
        linhas = self._transformacoes('NORMALIZA_ESPACOS')
        self.assertEqual([(l['entidade'], int(l['linha_origem']), l['campo']) for l in linhas],
                         [('vendas', 30, 'codigo_produto')])
        self.assertEqual(linhas[0]['valor_antes'], ' ET01 ')
        self.assertEqual(linhas[0]['valor_depois'], 'ET01')

    def test_converte_fuso(self):
        fonte = apoio.linhas_fonte('vendas.csv')
        linhas = self._transformacoes('CONVERTE_FUSO')
        self.assertEqual(sorted((l['entidade'], int(l['linha_origem'])) for l in linhas),
                         [('vendas', 24), ('vendas', 25), ('vendas', 26)])
        for l in linhas:
            n = int(l['linha_origem'])
            with self.subTest(linha=n):
                self.assertEqual(l['valor_antes'], fonte[n]['data'])
                self.assertIn(self.gab['vendas']['linhas'][str(n)]['competencia'],
                              l['valor_depois'])

    def test_descarta_duplicata(self):
        obtido = sorted((l['entidade'], int(l['linha_origem']))
                        for l in self._transformacoes('DESCARTA_DUPLICATA'))
        self.assertEqual(obtido, [('estoque', 6), ('produtos', 5), ('vendas', 6)])

    def test_exclui_fora_periodo(self):
        obtido = sorted((l['entidade'], int(l['linha_origem']))
                        for l in self._transformacoes('EXCLUI_FORA_PERIODO'))
        self.assertEqual(obtido, [('vendas', 22), ('vendas', 26)])

    def test_exclui_quarentena_para_cada_linha_em_quarentena(self):
        esperado = sorted((e, n) for e in apoio.ENTIDADES
                          for n in _linhas_com_status(self.gab, e, 'QUARENTENA'))
        obtido = sorted((l['entidade'], int(l['linha_origem']))
                        for l in self._transformacoes('EXCLUI_QUARENTENA'))
        self.assertEqual(obtido, esperado)

    def test_ordenacao_das_transformacoes(self):
        chaves = [(l['entidade'], int(l['linha_origem']), l['campo'], l['regra'])
                  for l in self.transformacoes]
        self.assertEqual(chaves, sorted(chaves), 'ordenacao: entidade, linha_origem, campo, regra')


if __name__ == '__main__':
    unittest.main()
