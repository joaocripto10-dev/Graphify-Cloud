"""Consolidação DEMO-4A: produtos válidos, junção vendas x produtos e posição de estoque."""

import logging
from dataclasses import dataclass

from . import contratos as C
from .erros import ReconciliacaoFalhou
from .qualidade import arredondar_centavos, formatar_decimal, parse_decimal

LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResultadoJuncao:
    """Linhas consolidadas e contagens antes/depois da junção."""

    linhas: list
    antes: int
    depois: int


def indexar_produtos_validos(produtos):
    """Índice (empresa, codigo_produto) -> linha VALIDO, com verificação de unicidade."""
    indice = {}
    for la in produtos:
        if la.status != C.VALIDO:
            continue
        chave = (la.valores["empresa"], la.valores["codigo_produto"])
        if chave in indice:
            raise ReconciliacaoFalhou(
                "produtos_validos: chave (empresa, codigo_produto) repetida")
        indice[chave] = la
    return indice


def produtos_validos(indice, lote):
    """Linhas de curated/produtos_validos.csv, ordenadas por empresa e código."""
    linhas = []
    for (empresa, codigo), la in sorted(indice.items()):
        v = la.valores
        linhas.append({
            "lote": lote, "empresa": empresa, "codigo_produto": codigo,
            "descricao": v["descricao"], "categoria": v["categoria"],
            "unidade_medida": v["unidade_medida"],
            "status_cadastral": v["status_cadastral"],
            "arquivo_origem": la.arquivo, "linha_origem": la.linha,
        })
    return linhas


def consolidar_vendas(vendas, indice, lote):
    """Junção N:1 das vendas VALIDO com o produto válido da mesma empresa."""
    validas = [la for la in vendas if la.status == C.VALIDO]
    linhas = []
    for la in validas:
        v = la.valores
        produto = indice.get((v["empresa"], v["codigo_produto"]))
        if produto is None:
            continue  # contagem depois != antes: a reconciliação acusa a falha
        p = produto.valores
        valor = arredondar_centavos(parse_decimal(v["valor_calculado"])[0])
        linhas.append({
            "lote": lote, "empresa": v["empresa"], "unidade": v["unidade"],
            "id_venda": v["id_venda"], "competencia": la.competencia,
            "data_original": v["data"], "codigo_produto": v["codigo_produto"],
            "descricao": p["descricao"], "categoria": p["categoria"],
            "unidade_medida": p["unidade_medida"],
            "status_cadastral": p["status_cadastral"],
            "quantidade": v["quantidade"], "preco_unitario": v["preco_unitario"],
            "valor": formatar_decimal(valor),
            "alertas": C.SEPARADOR_LISTA.join(la.alertas),
            "arquivo_origem": la.arquivo, "linha_origem": la.linha,
            "sha256_origem": la.sha256,
        })
    linhas.sort(key=lambda r: (r["empresa"], r["unidade"], r["id_venda"]))
    LOG.info("vendas consolidadas: %d de %d válidas", len(linhas), len(validas))
    return ResultadoJuncao(linhas, len(validas), len(linhas))


def posicao_estoque(estoque, indice, lote):
    """Posição de estoque das linhas VALIDO com a unidade de medida do produto."""
    validas = [la for la in estoque if la.status == C.VALIDO]
    linhas = []
    for la in validas:
        v = la.valores
        produto = indice.get((v["empresa"], v["codigo_produto"]))
        if produto is None:
            continue
        linhas.append({
            "lote": lote, "empresa": v["empresa"], "unidade": v["unidade"],
            "codigo_produto": v["codigo_produto"],
            "data_referencia": v["data_referencia"],
            "quantidade_disponivel": v["quantidade_disponivel"],
            "unidade_medida": produto.valores["unidade_medida"],
            "alertas": C.SEPARADOR_LISTA.join(la.alertas),
            "arquivo_origem": la.arquivo, "linha_origem": la.linha,
        })
    linhas.sort(key=lambda r: (r["empresa"], r["unidade"], r["codigo_produto"],
                               r["data_referencia"]))
    return ResultadoJuncao(linhas, len(validas), len(linhas))
