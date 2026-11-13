"""Indicadores DEMONSTRATIVOS do DEMO-4A (docs/DICIONARIO_DADOS.md).

Nenhum indicador soma empresas diferentes.
"""

from decimal import ROUND_HALF_UP, Decimal, localcontext

from . import contratos as C
from .qualidade import arredondar_centavos, formatar_decimal, parse_decimal, somar

_QUATRO_CASAS = Decimal("0.0001")
_CHAVE_ORDEM = ("indicador", "entidade", "empresa", "unidade", "codigo_produto",
                "data_referencia")

_CONTAGENS = (
    ("registros_recebidos", None, "contagem de linhas físicas sem o cabeçalho", "nenhum"),
    ("registros_validos", C.VALIDO, "contagem de status VALIDO", "status = VALIDO"),
    ("registros_quarentena", C.QUARENTENA, "contagem de status QUARENTENA",
     "status = QUARENTENA"),
    ("registros_fora_periodo", C.FORA_PERIODO, "contagem de status FORA_PERIODO",
     "status = FORA_PERIODO"),
    ("duplicatas_descartadas", C.DUPLICATA_DESCARTADA,
     "contagem de status DUPLICATA_DESCARTADA", "status = DUPLICATA_DESCARTADA"),
)


def taxa_inconsistencia(quarentena, recebidos):
    """quarentena / recebidos com 4 casas (ROUND_HALF_UP); 'indisponível' se recebidos = 0."""
    if recebidos == 0:
        return C.TAXA_INDISPONIVEL
    with localcontext() as ctx:
        ctx.prec = 60
        taxa = (Decimal(quarentena) / Decimal(recebidos)).quantize(
            _QUATRO_CASAS, rounding=ROUND_HALF_UP)
    return formatar_decimal(taxa)


def contar_status(linhas):
    """Contagens por status e total recebido de uma entidade."""
    contagem = {s: 0 for s in C.STATUS}
    for la in linhas:
        contagem[la.status] += 1
    contagem["recebidos"] = len(linhas)
    return contagem


def _linha(base, indicador, valor, unidade_valor, formula, grao, filtro, fonte,
           com_periodo=True, **chaves):
    linha = {c: "" for c in C.COLUNAS_INDICADORES}
    linha.update(base if com_periodo else {"lote": base["lote"]})
    linha.update(chaves)
    linha.update({
        "indicador": indicador, "valor": valor, "unidade_valor": unidade_valor,
        "formula": formula, "grao": grao, "filtro": filtro, "fonte": fonte,
    })
    return linha


def calcular(lote, avaliadas, vendas_consolidadas, estoque_posicao, inicio, fim):
    """Lista ordenada de linhas de analytics/indicadores.csv."""
    base = {"lote": lote, "periodo_inicio": inicio.isoformat(),
            "periodo_fim": fim.isoformat()}
    linhas = []

    for entidade in C.ENTIDADES:
        cont = contar_status(avaliadas[entidade.nome])
        for indicador, status, formula, filtro in _CONTAGENS:
            valor = cont["recebidos"] if status is None else cont[status]
            linhas.append(_linha(base, indicador, str(valor), "registros", formula,
                                 "entidade × lote", filtro, entidade.arquivo,
                                 entidade=entidade.nome))
        linhas.append(_linha(
            base, "taxa_inconsistencia",
            taxa_inconsistencia(cont[C.QUARENTENA], cont["recebidos"]), "proporção",
            "registros_quarentena ÷ registros_recebidos (4 casas, ROUND_HALF_UP)",
            "entidade × lote", "nenhum", entidade.arquivo, entidade=entidade.nome))

    por_empresa, por_unidade, por_produto, quantidades = {}, {}, {}, {}
    for r in vendas_consolidadas:
        valor = parse_decimal(r["valor"])[0]
        qtd = parse_decimal(r["quantidade"])[0]
        por_empresa.setdefault(r["empresa"], []).append(valor)
        por_unidade.setdefault((r["empresa"], r["unidade"]), []).append(valor)
        por_produto.setdefault((r["empresa"], r["codigo_produto"]), []).append(valor)
        quantidades.setdefault(
            (r["empresa"], r["codigo_produto"], r["unidade_medida"]), []).append(qtd)

    formula_fat = "Σ valor_calculado das vendas VALIDO (2 casas, arredondado por linha)"
    filtro_val = "status = VALIDO"
    for empresa, valores in por_empresa.items():
        linhas.append(_linha(base, "faturamento_bruto_valido", _dinheiro(valores), "R$",
                             formula_fat, "empresa × período", filtro_val, C.VENDAS.arquivo,
                             entidade=C.VENDAS.nome, empresa=empresa))
    for (empresa, unidade), valores in por_unidade.items():
        linhas.append(_linha(base, "faturamento_por_unidade", _dinheiro(valores), "R$",
                             formula_fat, "empresa × unidade × período", filtro_val,
                             C.VENDAS.arquivo, entidade=C.VENDAS.nome,
                             empresa=empresa, unidade=unidade))
    for (empresa, codigo), valores in por_produto.items():
        linhas.append(_linha(base, "faturamento_por_produto", _dinheiro(valores), "R$",
                             formula_fat, "empresa × produto × período", filtro_val,
                             C.VENDAS.arquivo, entidade=C.VENDAS.nome,
                             empresa=empresa, codigo_produto=codigo))
    for (empresa, codigo, um), qtds in quantidades.items():
        linhas.append(_linha(base, "quantidade_vendida", formatar_decimal(somar(qtds)), um,
                             "Σ quantidade das vendas VALIDO",
                             "empresa × produto × unidade de medida × período", filtro_val,
                             f"{C.VENDAS.arquivo}; {C.PRODUTOS.arquivo}",
                             entidade=C.VENDAS.nome, empresa=empresa,
                             codigo_produto=codigo, unidade_medida=um))
    for r in estoque_posicao:
        qtd = parse_decimal(r["quantidade_disponivel"])[0]
        linhas.append(_linha(base, "estoque_disponivel", formatar_decimal(qtd),
                             r["unidade_medida"],
                             "quantidade_disponivel da linha de estoque VALIDO (foto, não aditiva no tempo)",
                             "empresa × unidade × produto × data de referência", filtro_val,
                             f"{C.ESTOQUE.arquivo}; {C.PRODUTOS.arquivo}", com_periodo=False,
                             entidade=C.ESTOQUE.nome, empresa=r["empresa"],
                             unidade=r["unidade"], codigo_produto=r["codigo_produto"],
                             data_referencia=r["data_referencia"],
                             unidade_medida=r["unidade_medida"]))

    linhas.sort(key=lambda r: tuple(r[c] for c in _CHAVE_ORDEM))
    return linhas


def _dinheiro(valores):
    """Soma de valores monetários com 2 casas fixas."""
    return formatar_decimal(arredondar_centavos(somar(valores)))
