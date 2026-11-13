"""Utilitarios dos testes caixa-preta do pipeline DEMO-4A (FASE 4A, dados 100% ficticios).

Fontes de verdade: docs/CONTRATOS_DADOS.md (secao "Pipeline DEMO-4A"), docs/DICIONARIO_DADOS.md
(secao "KPIs DEMONSTRATIVOS do pipeline DEMO-4A"), tests/fixtures/demo_4a/gabarito.json e as
fixtures CSV. Este modulo NAO le a implementacao; so a executa pela interface publica.

Regras deste apoio:
- toda execucao usa uma raiz temporaria (nunca data/ ou outputs/ do repositorio);
- dinheiro e quantidade sao comparados como Decimal, nunca float;
- as fixtures nunca sao alteradas; variantes sao copias em diretorio temporario.
"""
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import unittest
from datetime import date
from decimal import Decimal

DIR_TESTES = os.path.dirname(os.path.abspath(__file__))
RAIZ_REPO = os.path.dirname(DIR_TESTES)
DIR_SRC = os.path.join(RAIZ_REPO, 'src')
FIXTURES = os.path.join(DIR_TESTES, 'fixtures', 'demo_4a')
SCRIPT_CLI = os.path.join(RAIZ_REPO, 'scripts', 'executar_demo_4a.py')

for _p in (DIR_SRC,):
    if _p not in sys.path:
        sys.path.insert(0, _p)

INICIO = date(2026, 10, 1)
FIM = date(2026, 10, 31)
PERIODO_CLI = '2026-10-01:2026-10-31'

ARQUIVOS = ('estoque.csv', 'produtos.csv', 'unidades.csv', 'vendas.csv')
ENTIDADES = ('estoque', 'produtos', 'unidades', 'vendas')
CAMADAS = ('staging', 'curated', 'analytics', 'outputs')

FUSO_NOME = 'America/Sao_Paulo'
MODO_ZONEINFO = 'zoneinfo'
MODO_FALLBACK = 'fallback_utc-03:00'

RE_LOTE = re.compile(r'DEMO4A-[0-9a-f]{12}')
RE_DINHEIRO = re.compile(r'-?\d+\.\d{2}')
RE_DECIMAL_SEM_EXPOENTE = re.compile(r'-?\d+(\.\d+)?')

# Colunas de cada fonte, na ordem do contrato.
COLUNAS_FONTE = {
    'unidades': ['empresa', 'unidade', 'nome'],
    'produtos': ['empresa', 'codigo_produto', 'descricao', 'categoria', 'unidade_medida',
                 'status_cadastral'],
    'vendas': ['empresa', 'unidade', 'id_venda', 'data', 'codigo_produto', 'quantidade',
               'preco_unitario', 'valor_calculado'],
    'estoque': ['empresa', 'unidade', 'codigo_produto', 'data_referencia',
                'quantidade_disponivel'],
}

PREFIXO_STAGING = ['lote', 'arquivo_origem', 'linha_origem', 'sha256_origem', 'status',
                   'motivo_principal', 'causas', 'alertas', 'conteudo_original']


def cabecalho_staging(entidade):
    extra = ['competencia'] if entidade == 'vendas' else []
    return PREFIXO_STAGING + COLUNAS_FONTE[entidade] + extra


CABECALHOS_CURATED = {
    'vendas_consolidadas.csv': [
        'lote', 'empresa', 'unidade', 'id_venda', 'competencia', 'data_original',
        'codigo_produto', 'descricao', 'categoria', 'unidade_medida', 'status_cadastral',
        'quantidade', 'preco_unitario', 'valor', 'alertas', 'arquivo_origem', 'linha_origem',
        'sha256_origem'],
    'produtos_validos.csv': [
        'lote', 'empresa', 'codigo_produto', 'descricao', 'categoria', 'unidade_medida',
        'status_cadastral', 'arquivo_origem', 'linha_origem'],
    'estoque_posicao.csv': [
        'lote', 'empresa', 'unidade', 'codigo_produto', 'data_referencia',
        'quantidade_disponivel', 'unidade_medida', 'alertas', 'arquivo_origem', 'linha_origem'],
    'quarentena.csv': [
        'lote', 'entidade', 'arquivo_origem', 'linha_origem', 'motivo_principal', 'causas',
        'gravidade_maxima', 'conteudo_original'],
    'ocorrencias.csv': [
        'lote', 'entidade', 'arquivo_origem', 'linha_origem', 'codigo', 'gravidade',
        'bloqueante', 'principal', 'campo', 'detalhe'],
    'transformacoes.csv': [
        'lote', 'entidade', 'arquivo_origem', 'linha_origem', 'campo', 'valor_antes',
        'valor_depois', 'regra'],
}

CABECALHO_INDICADORES = [
    'lote', 'indicador', 'entidade', 'empresa', 'unidade', 'codigo_produto', 'data_referencia',
    'unidade_medida', 'valor', 'unidade_valor', 'formula', 'grao', 'filtro', 'periodo_inicio',
    'periodo_fim', 'fonte']

# Ordem da tabela de regras do contrato (define motivo principal e ordem das listas).
ORDEM_CODIGOS = [
    'LINHA_MALFORMADA', 'CAMPO_OBRIGATORIO_AUSENTE', 'CONFLITO_ID', 'DATA_INVALIDA',
    'EMPRESA_UNIDADE_INCONSISTENTE', 'UNIDADE_FORA_DOMINIO', 'PRODUTO_SEM_CADASTRO',
    'CHAVE_RELACIONAMENTO_INVALIDA', 'UNIDADE_MEDIDA_FORA_DOMINIO', 'STATUS_CADASTRAL_INVALIDO',
    'QUANTIDADE_INVALIDA', 'UNIDADE_MEDIDA_DIVERGENTE', 'PRECO_AUSENTE', 'PRECO_INVALIDO',
    'VALOR_AUSENTE', 'VALOR_INVALIDO', 'VALOR_DIVERGENTE', 'PRODUTO_INATIVO', 'DUPLICATA_EXATA']

# Gravidade por codigo (tabela do contrato), ja normalizada sem acento e em minusculas.
GRAVIDADE = {codigo: 'alta' for codigo in ORDEM_CODIGOS}
GRAVIDADE.update({
    'CONFLITO_ID': 'critica', 'EMPRESA_UNIDADE_INCONSISTENTE': 'critica',
    'VALOR_DIVERGENTE': 'critica', 'DUPLICATA_EXATA': 'critica',
    'STATUS_CADASTRAL_INVALIDO': 'media', 'PRODUTO_INATIVO': 'baixa',
})
ORDEM_GRAVIDADE = {'baixa': 0, 'media': 1, 'alta': 2, 'critica': 3}

# Indicadores de contagem -> campo correspondente no gabarito.
INDICADORES_CONTAGEM = {
    'registros_recebidos': 'recebidos',
    'registros_validos': 'VALIDO',
    'registros_quarentena': 'QUARENTENA',
    'registros_fora_periodo': 'FORA_PERIODO',
    'duplicatas_descartadas': 'DUPLICATA_DESCARTADA',
}


# ---------------------------------------------------------------- leitura de referencia

def carregar_gabarito():
    with open(os.path.join(FIXTURES, 'gabarito.json'), encoding='utf-8') as f:
        return json.load(f)


def sha256_arquivo(caminho):
    h = hashlib.sha256()
    with open(caminho, 'rb') as f:
        for bloco in iter(lambda: f.read(65536), b''):
            h.update(bloco)
    return h.hexdigest()


def sha256_fixture(nome_arquivo):
    return sha256_arquivo(os.path.join(FIXTURES, nome_arquivo))


def linhas_fonte(nome_arquivo, diretorio=FIXTURES):
    """Le uma fonte CSV e devolve {linha_fisica: {coluna: valor com strip()}}.

    Ignora registros com numero de colunas diferente do cabecalho (malformados).
    Nas fixtures cada registro ocupa exatamente uma linha fisica.
    """
    with open(os.path.join(diretorio, nome_arquivo), encoding='utf-8', newline='') as f:
        leitor = csv.reader(f)
        cab = next(leitor)
        saida = {}
        for registro in leitor:
            if len(registro) == len(cab):
                saida[leitor.line_num] = {c: v.strip() for c, v in zip(cab, registro)}
        return saida


def lista(valores):
    return '|'.join(valores or [])


def texto(valor):
    return '' if valor is None else valor


def gravidade_normalizada(valor):
    sem_acento = unicodedata.normalize('NFKD', valor)
    sem_acento = ''.join(c for c in sem_acento if not unicodedata.combining(c))
    return sem_acento.strip().casefold()


def zoneinfo_disponivel():
    """True se zoneinfo resolve America/Sao_Paulo neste interpretador."""
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo(FUSO_NOME)
        return True
    except Exception:  # ImportError, ZoneInfoNotFoundError, ValueError...
        return False


# ---------------------------------------------------------------- execucao

def api():
    """Importa a API publica so quando necessario (falha clara se o pacote nao existir)."""
    from consolidacao.pipeline import executar
    from consolidacao import erros
    return executar, erros


def executar_api(entrada, raiz, inicio=INICIO, fim=FIM):
    executar, _ = api()
    return executar(str(entrada), inicio, fim, str(raiz))


def executar_cli(entrada, raiz, periodo=PERIODO_CLI, cwd=None):
    comando = [sys.executable, '-I', SCRIPT_CLI, '--entrada', str(entrada),
               '--periodo', periodo, '--raiz', str(raiz)]
    return subprocess.run(comando, capture_output=True, text=True, encoding='utf-8',
                          errors='replace', timeout=300, cwd=cwd or tempfile.gettempdir())


def copiar_fixtures(destino):
    """Copia somente os 4 CSVs das fixtures para `destino` (criado se preciso)."""
    os.makedirs(destino, exist_ok=True)
    for nome in ARQUIVOS:
        shutil.copyfile(os.path.join(FIXTURES, nome), os.path.join(destino, nome))
    return destino


def pastas_demo_4a(raiz):
    """Lista todas as pastas chamadas demo_4a sob `raiz`."""
    achadas = []
    for atual, dirs, _ in os.walk(raiz):
        for d in dirs:
            if d == 'demo_4a':
                achadas.append(os.path.join(atual, d))
    return achadas


def mesmo_caminho(a, b):
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def ler_csv(caminho):
    """Devolve (cabecalho, linhas como dict). Falha se alguma linha tiver aridade diferente."""
    with open(caminho, encoding='utf-8', newline='') as f:
        registros = list(csv.reader(f))
    if not registros:
        raise AssertionError(f'CSV sem cabecalho: {os.path.basename(caminho)}')
    cab = registros[0]
    linhas = []
    for i, r in enumerate(registros[1:], start=2):
        if len(r) != len(cab):
            raise AssertionError(
                f'{os.path.basename(caminho)} linha {i}: {len(r)} colunas, cabecalho tem {len(cab)}')
        linhas.append(dict(zip(cab, r)))
    return cab, linhas


def ler_json(caminho):
    with open(caminho, encoding='utf-8') as f:
        return json.load(f)


def hashes_lote(resultado, ignorar=('execucao.json',)):
    """{(camada, caminho relativo): sha256} de todos os arquivos das 4 pastas do lote."""
    saida = {}
    for camada in CAMADAS:
        base = resultado['diretorios'][camada]
        for atual, _, arquivos in os.walk(base):
            for nome in arquivos:
                if nome in ignorar:
                    continue
                caminho = os.path.join(atual, nome)
                rel = os.path.relpath(caminho, base).replace('\\', '/')
                saida[(camada, rel)] = sha256_arquivo(caminho)
    return saida


class Execucao:
    """Resultado de uma execucao da API com acesso tipado as saidas."""

    def __init__(self, raiz, resultado):
        self.raiz = raiz
        self.resultado = resultado
        self.lote = resultado['lote']
        self.dirs = resultado['diretorios']

    def caminho(self, camada, nome):
        return os.path.join(self.dirs[camada], nome)

    def csv(self, camada, nome):
        return ler_csv(self.caminho(camada, nome))

    def json(self, camada, nome):
        return ler_json(self.caminho(camada, nome))

    def staging(self, entidade):
        return self.csv('staging', f'{entidade}.csv')

    def staging_por_linha(self, entidade):
        _, linhas = self.staging(entidade)
        return {int(l['linha_origem']): l for l in linhas}

    def indicadores(self, nome=None):
        _, linhas = self.csv('analytics', 'indicadores.csv')
        if nome is None:
            return linhas
        return [l for l in linhas if l['indicador'] == nome]


class CasoComExecucao(unittest.TestCase):
    """Base: uma execucao da API sobre as fixtures originais, em raiz temporaria propria.

    Cada subclasse tem sua propria raiz, entao nao ha dependencia de ordem entre classes.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._tmp = tempfile.TemporaryDirectory(prefix='demo4a_teste_', ignore_cleanup_errors=True)
        raiz = os.path.join(cls._tmp.name, 'raiz')
        os.makedirs(raiz)
        try:
            resultado = executar_api(FIXTURES, raiz)
        except BaseException:
            cls._tmp.cleanup()
            raise
        cls.exec = Execucao(raiz, resultado)
        cls.gab = carregar_gabarito()

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()
        super().tearDownClass()


def valores_decimais(linhas, chave, coluna='valor'):
    """Mapeia chave(linha) -> Decimal(linha[coluna]); falha em chave repetida."""
    saida = {}
    for l in linhas:
        k = chave(l)
        if k in saida:
            raise AssertionError(f'chave repetida em indicadores: {k}')
        saida[k] = Decimal(l[coluna])
    return saida
