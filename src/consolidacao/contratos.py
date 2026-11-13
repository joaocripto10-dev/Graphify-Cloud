"""Constantes do contrato DEMO-4A: fontes, grão, regras e esquema das saídas.

Fonte única: docs/CONTRATOS_DADOS.md, seção "Pipeline DEMO-4A".
"""

from dataclasses import dataclass

CONTRATO = "DEMO-4A"
PREFIXO_LOTE = "DEMO4A-"
SUBPASTA = "demo_4a"
CODIFICACAO = "utf-8"

FUSO_NOME = "America/Sao_Paulo"
MODO_ZONEINFO = "zoneinfo"
MODO_FALLBACK = "fallback_utc-03:00"

# Status (precedência: DUPLICATA_DESCARTADA > QUARENTENA > FORA_PERIODO > VALIDO).
DUPLICATA_DESCARTADA = "DUPLICATA_DESCARTADA"
QUARENTENA = "QUARENTENA"
FORA_PERIODO = "FORA_PERIODO"
VALIDO = "VALIDO"
STATUS = (VALIDO, QUARENTENA, FORA_PERIODO, DUPLICATA_DESCARTADA)

# Regras de transformação registradas em transformacoes.csv.
NORMALIZA_ESPACOS = "NORMALIZA_ESPACOS"
CONVERTE_FUSO = "CONVERTE_FUSO"
DESCARTA_DUPLICATA = "DESCARTA_DUPLICATA"
EXCLUI_FORA_PERIODO = "EXCLUI_FORA_PERIODO"
EXCLUI_QUARENTENA = "EXCLUI_QUARENTENA"

UNIDADES_MEDIDA = frozenset({"L", "UN", "KG"})
STATUS_CADASTRAL = frozenset({"ATIVO", "INATIVO"})
UNIDADE_MEDIDA_INTEIRA = "UN"
STATUS_INATIVO = "INATIVO"

CASAS_MAX_QUANTIDADE = 3
CASAS_MAX_PRECO = 3
CASAS_MAX_VALOR = 2

OBRIGATORIOS = frozenset({
    "empresa", "unidade", "id_venda", "data", "codigo_produto", "quantidade",
    "descricao", "categoria", "unidade_medida", "status_cadastral",
    "data_referencia", "quantidade_disponivel", "nome",
})


@dataclass(frozen=True)
class Entidade:
    """Descrição de uma fonte: arquivo, colunas (ordem exata) e chave do grão."""

    nome: str
    arquivo: str
    colunas: tuple
    chave: tuple
    campos_quantidade: tuple = ()

    @property
    def obrigatorios(self):
        """Campos obrigatórios desta entidade, na ordem das colunas."""
        return tuple(c for c in self.colunas if c in OBRIGATORIOS)


UNIDADES = Entidade(
    "unidades", "unidades.csv",
    ("empresa", "unidade", "nome"),
    ("empresa", "unidade"),
)
PRODUTOS = Entidade(
    "produtos", "produtos.csv",
    ("empresa", "codigo_produto", "descricao", "categoria", "unidade_medida",
     "status_cadastral"),
    ("empresa", "codigo_produto"),
)
VENDAS = Entidade(
    "vendas", "vendas.csv",
    ("empresa", "unidade", "id_venda", "data", "codigo_produto", "quantidade",
     "preco_unitario", "valor_calculado"),
    ("empresa", "unidade", "id_venda"),
    ("quantidade",),
)
ESTOQUE = Entidade(
    "estoque", "estoque.csv",
    ("empresa", "unidade", "codigo_produto", "data_referencia",
     "quantidade_disponivel"),
    ("empresa", "unidade", "codigo_produto", "data_referencia"),
    ("quantidade_disponivel",),
)

# Ordem de processamento (cadastros antes dos fatos).
ENTIDADES = (UNIDADES, PRODUTOS, VENDAS, ESTOQUE)
POR_NOME = {e.nome: e for e in ENTIDADES}


@dataclass(frozen=True)
class Regra:
    """Regra de qualidade por linha."""

    codigo: str
    gravidade: str
    bloqueante: bool


# Na ordem da tabela do contrato: define motivo principal e ordem das listas.
REGRAS = (
    Regra("LINHA_MALFORMADA", "Alta", True),
    Regra("CAMPO_OBRIGATORIO_AUSENTE", "Alta", True),
    Regra("CONFLITO_ID", "Crítica", True),
    Regra("DATA_INVALIDA", "Alta", True),
    Regra("EMPRESA_UNIDADE_INCONSISTENTE", "Crítica", True),
    Regra("UNIDADE_FORA_DOMINIO", "Alta", True),
    Regra("PRODUTO_SEM_CADASTRO", "Alta", True),
    Regra("CHAVE_RELACIONAMENTO_INVALIDA", "Alta", True),
    Regra("UNIDADE_MEDIDA_FORA_DOMINIO", "Alta", True),
    Regra("STATUS_CADASTRAL_INVALIDO", "Média", True),
    Regra("QUANTIDADE_INVALIDA", "Alta", True),
    Regra("UNIDADE_MEDIDA_DIVERGENTE", "Alta", True),
    Regra("PRECO_AUSENTE", "Alta", True),
    Regra("PRECO_INVALIDO", "Alta", True),
    Regra("VALOR_AUSENTE", "Alta", True),
    Regra("VALOR_INVALIDO", "Alta", True),
    Regra("VALOR_DIVERGENTE", "Crítica", True),
    Regra("PRODUTO_INATIVO", "Baixa", False),
    Regra("DUPLICATA_EXATA", "Crítica", True),
)
REGRA = {r.codigo: r for r in REGRAS}
ORDEM_REGRA = {r.codigo: i for i, r in enumerate(REGRAS)}
PESO_GRAVIDADE = {"Baixa": 1, "Média": 2, "Alta": 3, "Crítica": 4}

# Esquema das saídas (colunas na ordem do contrato).
COLUNAS_STAGING_PREFIXO = (
    "lote", "arquivo_origem", "linha_origem", "sha256_origem", "status",
    "motivo_principal", "causas", "alertas", "conteudo_original",
)
COLUNAS_VENDAS_CONSOLIDADAS = (
    "lote", "empresa", "unidade", "id_venda", "competencia", "data_original",
    "codigo_produto", "descricao", "categoria", "unidade_medida",
    "status_cadastral", "quantidade", "preco_unitario", "valor", "alertas",
    "arquivo_origem", "linha_origem", "sha256_origem",
)
COLUNAS_PRODUTOS_VALIDOS = (
    "lote", "empresa", "codigo_produto", "descricao", "categoria",
    "unidade_medida", "status_cadastral", "arquivo_origem", "linha_origem",
)
COLUNAS_ESTOQUE_POSICAO = (
    "lote", "empresa", "unidade", "codigo_produto", "data_referencia",
    "quantidade_disponivel", "unidade_medida", "alertas", "arquivo_origem",
    "linha_origem",
)
COLUNAS_QUARENTENA = (
    "lote", "entidade", "arquivo_origem", "linha_origem", "motivo_principal",
    "causas", "gravidade_maxima", "conteudo_original",
)
COLUNAS_OCORRENCIAS = (
    "lote", "entidade", "arquivo_origem", "linha_origem", "codigo",
    "gravidade", "bloqueante", "principal", "campo", "detalhe",
)
COLUNAS_TRANSFORMACOES = (
    "lote", "entidade", "arquivo_origem", "linha_origem", "campo",
    "valor_antes", "valor_depois", "regra",
)
COLUNAS_INDICADORES = (
    "lote", "indicador", "entidade", "empresa", "unidade", "codigo_produto",
    "data_referencia", "unidade_medida", "valor", "unidade_valor", "formula",
    "grao", "filtro", "periodo_inicio", "periodo_fim", "fonte",
)

SEPARADOR_LISTA = "|"
TAXA_INDISPONIVEL = "indisponível"


def colunas_staging(entidade):
    """Colunas do staging da entidade (vendas recebe 'competencia' no fim)."""
    extra = ("competencia",) if entidade.nome == VENDAS.nome else ()
    return COLUNAS_STAGING_PREFIXO + entidade.colunas + extra
