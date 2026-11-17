"""FASE 4B: falhas de reconciliacao provocadas de proposito (R3) e deteccao de indicadores
adulterados (R1 taxa de inconsistencia; R2 chaves e valores por empresa, unidade e produto).

A falha e injetada por mock em consolidacao.indicadores.calcular: o resultado verdadeiro e
adulterado depois de calculado. Toda prova exige que o mock tenha sido chamado exatamente uma
vez e que a verificacao esperada seja a que falhou (sem falso verde).
Uso: python -I -m unittest discover -s tests
"""
import os
import subprocess
import sys
import tempfile
import unittest
from decimal import ROUND_HALF_UP, Decimal, localcontext
from unittest import mock

_AQUI = os.path.dirname(os.path.abspath(__file__))
for _p in (_AQUI, os.path.join(os.path.dirname(_AQUI), 'src')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import _apoio_demo_4a as apoio  # noqa: E402

CODIGO_RECONCILIACAO = 3
LOTE_BASE = 'DEMO4A-cc6f21e0d609'
IDS_NOVOS_4B = {
    'indicadores_catalogo', 'indicadores_metadados',
    'indicadores_chaves_estoque_disponivel', 'indicadores_chaves_faturamento_bruto_valido',
    'indicadores_chaves_faturamento_por_produto', 'indicadores_chaves_faturamento_por_unidade',
    'indicadores_chaves_quantidade_vendida',
    'indicadores_taxa_estoque', 'indicadores_taxa_produtos', 'indicadores_taxa_unidades',
    'indicadores_taxa_vendas',
}


# ---------------------------------------------------------------- utilitarios

def _modulo_indicadores():
    import consolidacao.indicadores as indicadores
    return indicadores


def _uma(linhas, **filtro):
    achadas = [r for r in linhas if all(r[k] == v for k, v in filtro.items())]
    assert len(achadas) == 1, (filtro, len(achadas))
    return achadas[0]


def _somar_texto(texto, delta):
    return str(Decimal(texto) + Decimal(delta))


def instantaneo(raiz):
    """{caminho relativo: (sha256, bytes, mtime_ns)} e lista de pastas sob `raiz`."""
    arquivos, pastas = {}, []
    for atual, dirs, nomes in os.walk(raiz):
        for d in dirs:
            pastas.append(os.path.relpath(os.path.join(atual, d), raiz))
        for n in nomes:
            c = os.path.join(atual, n)
            st = os.stat(c)
            arquivos[os.path.relpath(c, raiz)] = (apoio.sha256_arquivo(c), st.st_size,
                                                  st.st_mtime_ns)
    return arquivos, sorted(pastas)


def residuos(raiz):
    """Nomes de temporarios de publicacao (.tmp- / .old-) deixados sob `raiz`."""
    achados = []
    for atual, dirs, nomes in os.walk(raiz):
        achados += [n for n in dirs + nomes if '.tmp-' in n or '.old-' in n]
    return achados


class _Adulterador:
    """Envolve indicadores.calcular: chama o original e aplica `alterar` nas linhas."""

    def __init__(self, alterar):
        self.alterar = alterar
        self.chamadas = 0
        self.original = _modulo_indicadores().calcular

    def __call__(self, *args, **kwargs):
        self.chamadas += 1
        linhas = self.original(*args, **kwargs)
        return self.alterar(linhas) or linhas


class _CasoFalha(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix='demo4a_falha_',
                                                ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        _, self.erros = apoio.api()

    def nova_raiz(self, nome='raiz'):
        raiz = os.path.join(self._tmp.name, nome)
        os.makedirs(raiz)
        return raiz

    def executar_adulterado(self, alterar, raiz, entrada=apoio.FIXTURES):
        """Executa a API com o adulterador; devolve (ids que falharam, adulterador)."""
        adulterador = _Adulterador(alterar)
        with mock.patch.object(_modulo_indicadores(), 'calcular', adulterador):
            with self.assertRaises(self.erros.ReconciliacaoFalhou) as ctx:
                apoio.executar_api(entrada, raiz)
        self.assertEqual(adulterador.chamadas, 1, 'a falha simulada nao foi executada')
        mensagem = str(ctx.exception)
        self.assertTrue(mensagem.startswith('reconciliação falhou: '), mensagem)
        return set(mensagem.split(': ', 1)[1].split(', ')), adulterador

    def assert_nada_publicado(self, raiz):
        self.assertEqual(apoio.pastas_demo_4a(raiz), [])
        self.assertEqual(residuos(raiz), [])

    def assert_falha(self, alterar, *ids_esperados, ids_que_passam=()):
        raiz = self.nova_raiz()
        falharam, _ = self.executar_adulterado(alterar, raiz)
        for ident in ids_esperados:
            self.assertIn(ident, falharam)
        for ident in ids_que_passam:
            self.assertNotIn(ident, falharam)
        self.assert_nada_publicado(raiz)
        return falharam


# ---------------------------------------------------------------- R3

def _fatura_999(linhas):
    _uma(linhas, indicador='faturamento_bruto_valido', empresa='EMP01')['valor'] = '999.99'


class TestR3FalhaNaApi(_CasoFalha):
    """R3: ReconciliacaoFalhou e levantada antes de publicar qualquer camada."""

    def test_sem_adulteracao_o_mock_passa_e_publica(self):
        """Controle: o envoltorio sozinho nao provoca falha (o teste nao e verde por acaso)."""
        raiz = self.nova_raiz()
        adulterador = _Adulterador(lambda linhas: None)
        with mock.patch.object(_modulo_indicadores(), 'calcular', adulterador):
            r = apoio.executar_api(apoio.FIXTURES, raiz)
        self.assertEqual(adulterador.chamadas, 1)
        self.assertEqual(r['lote'], LOTE_BASE)
        rec = apoio.ler_json(os.path.join(r['diretorios']['outputs'], 'reconciliacao.json'))
        self.assertTrue(rec['ok'])
        ids = {x['id'] for x in rec['verificacoes']}
        self.assertTrue(IDS_NOVOS_4B <= ids, IDS_NOVOS_4B - ids)
        self.assertEqual(len(rec['verificacoes']), 32)
        self.assertTrue(all(x['ok'] for x in rec['verificacoes']))

    def test_falha_levanta_excecao_sem_publicar(self):
        falharam = self.assert_falha(_fatura_999, 'faturamento_indicador_EMP01')
        self.assertIn('faturamento_recorte_EMP01', falharam)

    def test_lote_anterior_fica_intacto(self):
        raiz = self.nova_raiz()
        apoio.executar_api(apoio.FIXTURES, raiz)
        antes = instantaneo(raiz)
        self.assertEqual(len(antes[0]), 15)
        self.executar_adulterado(_fatura_999, raiz)
        self.assertEqual(instantaneo(raiz), antes)
        self.assertEqual(residuos(raiz), [])


_WRAPPER_CLI = r'''
import runpy, sys
sys.path.insert(0, {src!r})
from unittest import mock
import consolidacao.indicadores as I
original = I.calcular
chamadas = []
def adulterado(*a, **k):
    chamadas.append(1)
    linhas = original(*a, **k)
    for r in linhas:
        if r["indicador"] == "faturamento_bruto_valido" and r["empresa"] == "EMP01":
            r["valor"] = "999.99"
    return linhas
codigo = None
with mock.patch.object(I, "calcular", adulterado):
    sys.argv = [{script!r}] + sys.argv[1:]
    try:
        runpy.run_path({script!r}, run_name="__main__")
    except SystemExit as e:
        codigo = e.code
sys.stderr.write("CHAMADAS=%d CODIGO=%r\n" % (len(chamadas), codigo))
sys.exit(codigo if isinstance(codigo, int) else 99)
'''


class TestR3FalhaNaCli(_CasoFalha):
    """R3: a CLI real (caminho __main__) devolve 3 e nao publica."""

    def _executar_cli_adulterada(self, raiz):
        wrapper = os.path.join(self._tmp.name, 'cli_adulterada.py')
        with open(wrapper, 'w', encoding='utf-8') as f:
            f.write(_WRAPPER_CLI.format(src=apoio.DIR_SRC, script=apoio.SCRIPT_CLI))
        comando = [sys.executable, '-I', '-B', wrapper, '--entrada', apoio.FIXTURES,
                   '--periodo', apoio.PERIODO_CLI, '--raiz', raiz]
        return subprocess.run(comando, capture_output=True, text=True, encoding='utf-8',
                              errors='replace', timeout=300, cwd=self._tmp.name)

    def test_cli_retorna_3_sem_publicar(self):
        raiz = self.nova_raiz()
        proc = self._executar_cli_adulterada(raiz)
        self.assertEqual(proc.returncode, CODIGO_RECONCILIACAO, proc.stderr)
        self.assertIn('CHAMADAS=1 CODIGO=3', proc.stderr)
        self.assertIn('ReconciliacaoFalhou', proc.stderr)
        self.assertIn('faturamento_indicador_EMP01', proc.stderr)
        self.assertNotIn('lote:', proc.stdout)
        self.assert_nada_publicado(raiz)

    def test_cli_preserva_lote_anterior(self):
        raiz = self.nova_raiz()
        ok = apoio.executar_cli(apoio.FIXTURES, raiz, cwd=self._tmp.name)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        antes = instantaneo(raiz)
        proc = self._executar_cli_adulterada(raiz)
        self.assertEqual(proc.returncode, CODIGO_RECONCILIACAO, proc.stderr)
        self.assertIn('CHAMADAS=1 CODIGO=3', proc.stderr)
        self.assertEqual(instantaneo(raiz), antes)
        self.assertEqual(residuos(raiz), [])


# ---------------------------------------------------------------- R1

class TestR1TaxaInconsistencia(_CasoFalha):
    """R1: a taxa publicada e reconciliada contra quarentena / recebidos."""

    def test_taxa_adulterada(self):
        def alterar(linhas):
            _uma(linhas, indicador='taxa_inconsistencia', entidade='vendas')['valor'] = '0.5863'
        self.assert_falha(alterar, 'indicadores_taxa_vendas',
                          ids_que_passam=('indicadores_taxa_estoque', 'indicadores_catalogo'))

    def test_taxa_com_outra_representacao_textual(self):
        def alterar(linhas):
            _uma(linhas, indicador='taxa_inconsistencia', entidade='vendas')['valor'] = '0.58620'
        self.assert_falha(alterar, 'indicadores_taxa_vendas')

    def test_taxa_ausente(self):
        def alterar(linhas):
            linhas.remove(_uma(linhas, indicador='taxa_inconsistencia', entidade='produtos'))
        self.assert_falha(alterar, 'indicadores_taxa_produtos', 'indicadores_catalogo')

    def test_taxa_duplicada(self):
        def alterar(linhas):
            linhas.append(dict(_uma(linhas, indicador='taxa_inconsistencia', entidade='estoque')))
        self.assert_falha(alterar, 'indicadores_taxa_estoque', 'indicadores_catalogo')

    def test_taxa_zero_trocada_por_indisponivel(self):
        def alterar(linhas):
            _uma(linhas, indicador='taxa_inconsistencia',
                 entidade='unidades')['valor'] = 'indisponível'
        self.assert_falha(alterar, 'indicadores_taxa_unidades')

    def test_arquivo_so_com_cabecalho_publica_taxa_indisponivel(self):
        """Borda executada: recebidos = 0 -> 'indisponível' (nao 0), reconciliado e publicado."""
        entrada = apoio.copiar_fixtures(os.path.join(self._tmp.name, 'entrada'))
        caminho = os.path.join(entrada, 'estoque.csv')
        with open(caminho, 'rb') as f:
            cabecalho = f.read().split(b'\n', 1)[0] + b'\n'
        with open(caminho, 'wb') as f:
            f.write(cabecalho)
        r = apoio.executar_api(entrada, self.nova_raiz())
        ex = apoio.Execucao(None, r)
        taxa = ex.indicadores('taxa_inconsistencia')
        self.assertEqual([l['valor'] for l in taxa if l['entidade'] == 'estoque'],
                         ['indisponível'])
        self.assertEqual(ex.indicadores('estoque_disponivel'), [])
        rec = ex.json('outputs', 'reconciliacao.json')
        por_id = {x['id']: x for x in rec['verificacoes']}
        self.assertTrue(por_id['indicadores_taxa_estoque']['ok'])
        self.assertEqual(por_id['indicadores_taxa_estoque']['obtido'], ['indisponível'])
        self.assertEqual(por_id['indicadores_chaves_estoque_disponivel']['esperado'], [])
        with open(ex.caminho('outputs', 'relatorio_qualidade.md'), encoding='utf-8') as f:
            self.assertIn('indisponível', f.read())

    def test_formula_inteira_igual_a_decimal_half_up(self):
        """O recalculo por inteiros coincide com Decimal ROUND_HALF_UP em 0 <= q <= r <= 300."""
        from consolidacao.pipeline import _taxa_por_inteiros
        self.assertEqual(_taxa_por_inteiros(0, 0), 'indisponível')
        with localcontext() as ctx:
            ctx.prec = 60
            for r in range(1, 301):
                for q in range(0, r + 1):
                    esperado = format((Decimal(q) / Decimal(r)).quantize(
                        Decimal('0.0001'), rounding=ROUND_HALF_UP), 'f')
                    if _taxa_por_inteiros(q, r) != esperado:
                        self.fail(f'q={q} r={r}: {_taxa_por_inteiros(q, r)} != {esperado}')


# ---------------------------------------------------------------- R2

def _copia_com(linhas, base, **mudancas):
    nova = dict(base)
    nova.update(mudancas)
    linhas.append(nova)


class TestR2Faturamento(_CasoFalha):
    """R2/B12: chaves e valores do faturamento, nao so somatorios."""

    def test_empresa_extra_com_valor_zero(self):
        """B12: empresa sem venda valida nao tem linha; um 0.00 publicado e indevido."""
        def alterar(linhas):
            _copia_com(linhas, _uma(linhas, indicador='faturamento_bruto_valido',
                                    empresa='EMP01'), empresa='EMP02', valor='0.00')
        self.assert_falha(alterar, 'indicadores_chaves_faturamento_bruto_valido',
                          'indicadores_catalogo')

    def test_empresa_extra_com_valor(self):
        def alterar(linhas):
            _copia_com(linhas, _uma(linhas, indicador='faturamento_bruto_valido',
                                    empresa='EMP01'), empresa='EMP99', valor='10.00')
        self.assert_falha(alterar, 'indicadores_chaves_faturamento_bruto_valido')

    def test_empresa_ausente(self):
        def alterar(linhas):
            linhas.remove(_uma(linhas, indicador='faturamento_bruto_valido', empresa='EMP01'))
        self.assert_falha(alterar, 'indicadores_chaves_faturamento_bruto_valido',
                          'indicadores_catalogo')

    def test_chave_repetida_por_unidade(self):
        def alterar(linhas):
            linhas.append(dict(_uma(linhas, indicador='faturamento_por_unidade',
                                    unidade='ALFA')))
        self.assert_falha(alterar, 'indicadores_chaves_faturamento_por_unidade')

    def test_unidade_extra_com_zero(self):
        def alterar(linhas):
            _copia_com(linhas, _uma(linhas, indicador='faturamento_por_unidade',
                                    unidade='BETA'), unidade='GAMA', valor='0.00')
        self.assert_falha(alterar, 'indicadores_chaves_faturamento_por_unidade',
                          ids_que_passam=('faturamento_recorte_EMP01',))

    def test_unidades_adulteradas_preservando_a_soma(self):
        """A verificacao 4A (somatorios) passa; a nova (chave a chave) acusa."""
        def alterar(linhas):
            alfa = _uma(linhas, indicador='faturamento_por_unidade', unidade='ALFA')
            beta = _uma(linhas, indicador='faturamento_por_unidade', unidade='BETA')
            alfa['valor'] = _somar_texto(alfa['valor'], '1.00')
            beta['valor'] = _somar_texto(beta['valor'], '-1.00')
        falharam = self.assert_falha(alterar, 'indicadores_chaves_faturamento_por_unidade',
                                     ids_que_passam=('faturamento_recorte_EMP01',
                                                     'faturamento_indicador_EMP01'))
        self.assertEqual(falharam, {'indicadores_chaves_faturamento_por_unidade'})

    def test_produtos_adulterados_preservando_a_soma(self):
        def alterar(linhas):
            gc = _uma(linhas, indicador='faturamento_por_produto', codigo_produto='GC01')
            et = _uma(linhas, indicador='faturamento_por_produto', codigo_produto='ET01')
            gc['valor'] = _somar_texto(gc['valor'], '0.01')
            et['valor'] = _somar_texto(et['valor'], '-0.01')
        falharam = self.assert_falha(alterar, 'indicadores_chaves_faturamento_por_produto')
        self.assertEqual(falharam, {'indicadores_chaves_faturamento_por_produto'})

    def test_venda_atribuida_a_outra_empresa(self):
        """Segregacao: a mesma chave de produto movida para EMP02 e acusada."""
        def alterar(linhas):
            _uma(linhas, indicador='faturamento_por_produto',
                 codigo_produto='CF01')['empresa'] = 'EMP02'
        self.assert_falha(alterar, 'indicadores_chaves_faturamento_por_produto')


class TestR2QuantidadeEstoque(_CasoFalha):
    """R2: quantidade vendida e estoque disponivel ganharam verificacao propria."""

    def test_quantidade_alterada(self):
        def alterar(linhas):
            r = _uma(linhas, indicador='quantidade_vendida', codigo_produto='GC01')
            r['valor'] = _somar_texto(r['valor'], '1')
        self.assert_falha(alterar, 'indicadores_chaves_quantidade_vendida')

    def test_unidade_de_medida_trocada(self):
        def alterar(linhas):
            r = _uma(linhas, indicador='quantidade_vendida', codigo_produto='GC01')
            r['unidade_medida'] = r['unidade_valor'] = 'UN'
        self.assert_falha(alterar, 'indicadores_chaves_quantidade_vendida')

    def test_quantidade_ausente(self):
        def alterar(linhas):
            linhas.remove(_uma(linhas, indicador='quantidade_vendida', codigo_produto='PB01'))
        self.assert_falha(alterar, 'indicadores_chaves_quantidade_vendida',
                          'indicadores_catalogo')

    def _uma_posicao(self, linhas):
        return sorted((r for r in linhas if r['indicador'] == 'estoque_disponivel'),
                      key=lambda r: (r['unidade'], r['codigo_produto']))[0]

    def test_estoque_alterado(self):
        def alterar(linhas):
            r = self._uma_posicao(linhas)
            r['valor'] = _somar_texto(r['valor'], '1')
        self.assert_falha(alterar, 'indicadores_chaves_estoque_disponivel')

    def test_estoque_duplicado(self):
        def alterar(linhas):
            linhas.append(dict(self._uma_posicao(linhas)))
        self.assert_falha(alterar, 'indicadores_chaves_estoque_disponivel',
                          'indicadores_catalogo')

    def test_estoque_ausente(self):
        def alterar(linhas):
            linhas.remove(self._uma_posicao(linhas))
        self.assert_falha(alterar, 'indicadores_chaves_estoque_disponivel',
                          'indicadores_catalogo')

    def test_estoque_com_outra_data_de_referencia(self):
        def alterar(linhas):
            self._uma_posicao(linhas)['data_referencia'] = '2026-10-30'
        self.assert_falha(alterar, 'indicadores_chaves_estoque_disponivel')

    def test_indicador_desconhecido(self):
        def alterar(linhas):
            _copia_com(linhas, _uma(linhas, indicador='faturamento_bruto_valido',
                                    empresa='EMP01'), indicador='margem_bruta')
        self.assert_falha(alterar, 'indicadores_catalogo')

    def test_contagem_duplicada(self):
        """A verificacao 4A (dict por nome) nao via repeticao; o catalogo ve."""
        def alterar(linhas):
            linhas.append(dict(_uma(linhas, indicador='registros_validos', entidade='vendas')))
        falharam = self.assert_falha(alterar, 'indicadores_catalogo')
        self.assertEqual(falharam, {'indicadores_catalogo'})


class TestIdentidadeEMetadados(_CasoFalha):
    """Auditoria 4B (D1/D2): falsos negativos A5, A6, A12, A13 e A15 do auditor independente."""

    def test_contagem_com_empresa_preenchida(self):  # A6
        def alterar(linhas):
            _uma(linhas, indicador='registros_validos', entidade='vendas')['empresa'] = 'EMP01'
        self.assertEqual(self.assert_falha(alterar, 'indicadores_catalogo'),
                         {'indicadores_catalogo'})

    def test_taxa_com_empresa_preenchida(self):  # A15
        def alterar(linhas):
            _uma(linhas, indicador='taxa_inconsistencia', entidade='vendas')['empresa'] = 'EMP02'
        self.assertEqual(self.assert_falha(alterar, 'indicadores_catalogo'),
                         {'indicadores_catalogo'})

    def test_unidade_do_valor_trocada_no_total(self):
        def alterar(linhas):
            _uma(linhas, indicador='faturamento_bruto_valido',
                 empresa='EMP01')['unidade_valor'] = 'BRL'
        self.assert_falha(alterar, 'indicadores_catalogo')

    def test_periodo_adulterado(self):  # A5
        def alterar(linhas):
            _uma(linhas, indicador='faturamento_por_produto',
                 codigo_produto='GC01')['periodo_inicio'] = '2026-09-01'
        self.assertEqual(self.assert_falha(alterar, 'indicadores_catalogo'),
                         {'indicadores_catalogo'})

    def test_estoque_com_periodo_de_vendas(self):
        """A posicao de estoque e foto: periodo preenchido e indevido."""
        def alterar(linhas):
            r = sorted((x for x in linhas if x['indicador'] == 'estoque_disponivel'),
                       key=lambda x: (x['unidade'], x['codigo_produto']))[0]
            r['periodo_inicio'], r['periodo_fim'] = '2026-10-01', '2026-10-31'
        self.assert_falha(alterar, 'indicadores_catalogo')

    def test_lote_de_uma_linha_adulterado(self):  # A13
        def alterar(linhas):
            _uma(linhas, indicador='registros_recebidos',
                 entidade='produtos')['lote'] = 'DEMO4A-000000000000'
        self.assertEqual(self.assert_falha(alterar, 'indicadores_catalogo'),
                         {'indicadores_catalogo'})

    def test_formula_de_uma_linha_adulterada(self):  # A12
        def alterar(linhas):
            _uma(linhas, indicador='faturamento_por_unidade',
                 unidade='ALFA')['formula'] = 'Σ valor bruto com impostos'
        self.assertEqual(self.assert_falha(alterar, 'indicadores_metadados'),
                         {'indicadores_metadados'})

    def test_fonte_vazia_mesmo_que_uniforme(self):
        def alterar(linhas):
            for r in linhas:
                if r['indicador'] == 'quantidade_vendida':
                    r['fonte'] = ''
        self.assertEqual(self.assert_falha(alterar, 'indicadores_metadados'),
                         {'indicadores_metadados'})


if __name__ == '__main__':
    unittest.main()
