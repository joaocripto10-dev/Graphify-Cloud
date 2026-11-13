"""Normalização, interpretação de tipos e regras de qualidade por linha (DEMO-4A)."""

import logging
import re
import zoneinfo
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, localcontext

from . import contratos as C

LOG = logging.getLogger(__name__)

_RE_DECIMAL = re.compile(r"-?[0-9]+(?:\.([0-9]+))?")
_RE_DATA = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_RE_DATA_HORA = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}[+-][0-9]{2}:[0-9]{2}"
)

UTC_MENOS_3 = timezone(timedelta(hours=-3))
# Fim do último horário de verão em America/Sao_Paulo; limite do fallback fixo.
LIMITE_FALLBACK = datetime(2019, 2, 17, tzinfo=UTC_MENOS_3)
CENTAVO = Decimal("0.01")
_PRECISAO = 60


# ---------------------------------------------------------------- tipos base

def parse_decimal(texto):
    """Interpreta decimal estrito (``-?d+(.d+)?``). Retorna (Decimal, casas) ou None."""
    m = _RE_DECIMAL.fullmatch(texto)
    if m is None:
        return None
    casas = len(m.group(1)) if m.group(1) else 0
    return Decimal(texto), casas


def arredondar_centavos(valor):
    """Arredonda a 2 casas com ROUND_HALF_UP, sem perda por precisão de contexto."""
    with localcontext() as ctx:
        ctx.prec = _PRECISAO
        return valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def multiplicar(a, b):
    """Produto exato de dois Decimals (precisão ampliada)."""
    with localcontext() as ctx:
        ctx.prec = _PRECISAO
        return a * b


def somar(valores):
    """Soma Decimals preservando a escala (precisão ampliada)."""
    with localcontext() as ctx:
        ctx.prec = _PRECISAO
        total = Decimal(0)
        for v in valores:
            total += v
        return total


def formatar_decimal(valor):
    """Texto sem notação exponencial."""
    return format(valor, "f")


@dataclass(frozen=True)
class Fuso:
    """Fuso de competência e modo de obtenção."""

    tz: object
    modo: str
    nome: str = C.FUSO_NOME


def obter_fuso():
    """America/Sao_Paulo via zoneinfo; sem tzdata, UTC-03:00 fixo (fallback)."""
    try:
        return Fuso(zoneinfo.ZoneInfo(C.FUSO_NOME), C.MODO_ZONEINFO)
    except zoneinfo.ZoneInfoNotFoundError:
        LOG.warning("tzdata indisponível; usando UTC-03:00 fixo (fallback)")
        return Fuso(UTC_MENOS_3, C.MODO_FALLBACK)


def interpretar_data_venda(texto, fuso):
    """Retorna (competencia, convertido_iso_ou_None) ou None se a data for inválida."""
    if _RE_DATA.fullmatch(texto):
        try:
            return date.fromisoformat(texto), None
        except ValueError:
            return None
    if _RE_DATA_HORA.fullmatch(texto):
        try:
            instante = datetime.fromisoformat(texto)
        except ValueError:
            return None
        if instante.tzinfo is None or instante.utcoffset() is None:
            return None
        if fuso.modo == C.MODO_FALLBACK and instante < LIMITE_FALLBACK:
            return None
        local = instante.astimezone(fuso.tz)
        return local.date(), local.isoformat()
    return None


def interpretar_data_referencia(texto):
    """Somente AAAA-MM-DD; retorna date ou None."""
    if not _RE_DATA.fullmatch(texto):
        return None
    try:
        return date.fromisoformat(texto)
    except ValueError:
        return None


# ---------------------------------------------------------------- estruturas

@dataclass(frozen=True)
class Ocorrencia:
    """Causa ou alerta registrado para uma linha."""

    codigo: str
    campo: str = ""
    detalhe: str = ""

    @property
    def gravidade(self):
        return C.REGRA[self.codigo].gravidade

    @property
    def bloqueante(self):
        return C.REGRA[self.codigo].bloqueante


@dataclass(frozen=True)
class Transformacao:
    """Alteração registrada em transformacoes.csv."""

    campo: str
    valor_antes: str
    valor_depois: str
    regra: str


@dataclass
class LinhaAvaliada:
    """Linha física avaliada: valores normalizados, ocorrências e status."""

    entidade: str
    arquivo: str
    sha256: str
    linha: int
    conteudo_original: str
    valores: dict
    malformada: bool = False
    ocorrencias: list = field(default_factory=list)
    transformacoes: list = field(default_factory=list)
    status: str = ""
    competencia: str = ""

    @property
    def causas(self):
        """Códigos bloqueantes, na ordem da tabela."""
        return [o.codigo for o in self.ocorrencias if o.bloqueante]

    @property
    def alertas(self):
        """Códigos não bloqueantes, na ordem da tabela."""
        return [o.codigo for o in self.ocorrencias if not o.bloqueante]

    @property
    def motivo_principal(self):
        causas = self.causas
        return causas[0] if causas else ""

    @property
    def gravidade_maxima(self):
        gravs = [o.gravidade for o in self.ocorrencias if o.bloqueante]
        return max(gravs, key=C.PESO_GRAVIDADE.__getitem__) if gravs else ""


@dataclass(frozen=True)
class Cadastros:
    """Domínios usados pelas regras de relacionamento de vendas e estoque."""

    pares_unidade: frozenset
    unidades: frozenset
    produtos_existentes: frozenset
    produtos_validos: dict


def montar_cadastros(unidades, produtos, produtos_validos):
    """Unidades: só linhas VALIDO. Existência de produto: qualquer linha não malformada."""
    pares = frozenset(
        (la.valores["empresa"], la.valores["unidade"])
        for la in unidades if la.status == C.VALIDO
    )
    existentes = frozenset(
        (la.valores["empresa"], la.valores["codigo_produto"])
        for la in produtos if not la.malformada
    )
    return Cadastros(pares, frozenset(u for _, u in pares), existentes, produtos_validos)


# ---------------------------------------------------------------- avaliação

def _ordenar(ocorrencias):
    """Remove códigos repetidos e ordena pela ordem da tabela de regras."""
    vistos = {}
    for o in ocorrencias:
        vistos.setdefault(o.codigo, o)
    return sorted(vistos.values(), key=lambda o: C.ORDEM_REGRA[o.codigo])


def _assinatura(entidade, valores):
    """Conteúdo normalizado comparável; quantidades comparadas pelo valor Decimal."""
    partes = []
    for col in entidade.colunas:
        texto = valores[col]
        if col in entidade.campos_quantidade:
            num = parse_decimal(texto)
            if num is not None:
                partes.append(("D", num[0]))
                continue
        partes.append(("T", texto))
    return tuple(partes)


def _classificar_duplicidade(linhas, entidade):
    """Retorna (linhas em conflito, {linha_copia: linha_original})."""
    grupos = {}
    for la in linhas:
        if not la.malformada:
            chave = tuple(la.valores[c] for c in entidade.chave)
            grupos.setdefault(chave, []).append(la)
    conflitos = set()
    copias = {}
    for grupo in grupos.values():
        if len(grupo) < 2:
            continue
        if len({_assinatura(entidade, la.valores) for la in grupo}) > 1:
            conflitos.update(la.linha for la in grupo)
        else:
            for la in grupo[1:]:
                copias[la.linha] = grupo[0].linha
    return conflitos, copias


def _regras_relacionamento(entidade, v, cadastros, data_ok):
    """Regras de vendas e estoque (data, unidade, produto, quantidade, preço, valor)."""
    oc = []
    eh_venda = entidade.nome == C.VENDAS.nome
    campo_data = "data" if eh_venda else "data_referencia"
    if v[campo_data] and not data_ok:
        oc.append(Ocorrencia("DATA_INVALIDA", campo_data, "fora do formato aceito ou data inexistente"))

    empresa, unidade, codigo = v["empresa"], v["unidade"], v["codigo_produto"]
    if unidade:
        if unidade not in cadastros.unidades:
            oc.append(Ocorrencia("UNIDADE_FORA_DOMINIO", "unidade",
                                 "unidade inexistente no cadastro"))
        elif empresa and (empresa, unidade) not in cadastros.pares_unidade:
            oc.append(Ocorrencia("EMPRESA_UNIDADE_INCONSISTENTE", "empresa|unidade",
                                 "unidade cadastrada em outra empresa"))

    produto = None
    if empresa and codigo:
        chave = (empresa, codigo)
        if chave not in cadastros.produtos_existentes:
            oc.append(Ocorrencia("PRODUTO_SEM_CADASTRO", "codigo_produto",
                                 "código inexistente no cadastro da empresa"))
        elif chave not in cadastros.produtos_validos:
            oc.append(Ocorrencia("CHAVE_RELACIONAMENTO_INVALIDA", "codigo_produto",
                                 "produto existe na empresa, mas sem cadastro válido"))
        else:
            produto = cadastros.produtos_validos[chave].valores

    campo_qtd = entidade.campos_quantidade[0]
    qtd = None
    if v[campo_qtd]:
        num = parse_decimal(v[campo_qtd])
        if num is None or num[1] > C.CASAS_MAX_QUANTIDADE:
            ok = False
        else:
            ok = num[0] > 0 if eh_venda else num[0] >= 0
        if ok:
            qtd = num[0]
        else:
            regra = "> 0" if eh_venda else ">= 0"
            oc.append(Ocorrencia("QUANTIDADE_INVALIDA", campo_qtd,
                                 f"exige decimal com até 3 casas e {regra}"))

    if produto is not None and qtd is not None:
        if (produto["unidade_medida"] == C.UNIDADE_MEDIDA_INTEIRA
                and qtd != qtd.to_integral_value()):
            oc.append(Ocorrencia("UNIDADE_MEDIDA_DIVERGENTE", campo_qtd,
                                 "quantidade não inteira para produto em UN"))
        if produto["status_cadastral"] == C.STATUS_INATIVO:
            oc.append(Ocorrencia("PRODUTO_INATIVO", "codigo_produto",
                                 "produto com status INATIVO"))

    if eh_venda:
        oc.extend(_regras_preco_valor(v, qtd))
    return oc


def _regras_preco_valor(v, qtd):
    """Preço, valor e divergência valor x (quantidade x preço)."""
    oc = []
    preco = valor = None
    if v["preco_unitario"] == "":
        oc.append(Ocorrencia("PRECO_AUSENTE", "preco_unitario", "preço vazio (nunca vira zero)"))
    else:
        num = parse_decimal(v["preco_unitario"])
        if num is None or num[1] > C.CASAS_MAX_PRECO or num[0] <= 0:
            oc.append(Ocorrencia("PRECO_INVALIDO", "preco_unitario",
                                 "exige decimal com ponto, até 3 casas e > 0"))
        else:
            preco = num[0]
    if v["valor_calculado"] == "":
        oc.append(Ocorrencia("VALOR_AUSENTE", "valor_calculado", "valor vazio"))
    else:
        num = parse_decimal(v["valor_calculado"])
        if num is None or num[1] > C.CASAS_MAX_VALOR:
            oc.append(Ocorrencia("VALOR_INVALIDO", "valor_calculado",
                                 "exige decimal com ponto e até 2 casas"))
        else:
            valor = num[0]
    if qtd is not None and preco is not None and valor is not None:
        esperado = arredondar_centavos(multiplicar(qtd, preco))
        if esperado != valor:
            oc.append(Ocorrencia("VALOR_DIVERGENTE", "valor_calculado",
                                 f"esperado {formatar_decimal(esperado)}"))
    return oc


def _aplicar_regras(entidade, v, conflito, cadastros, data_ok):
    """Todas as causas aplicáveis, respeitando a regra de dependência."""
    oc = []
    ausentes = [c for c in entidade.obrigatorios if v[c] == ""]
    if ausentes:
        oc.append(Ocorrencia("CAMPO_OBRIGATORIO_AUSENTE", C.SEPARADOR_LISTA.join(ausentes),
                             "campo obrigatório vazio"))
    if conflito:
        oc.append(Ocorrencia("CONFLITO_ID", C.SEPARADOR_LISTA.join(entidade.chave),
                             "mesma chave com conteúdo normalizado diferente"))
    if entidade.nome == C.PRODUTOS.nome:
        if v["unidade_medida"] and v["unidade_medida"] not in C.UNIDADES_MEDIDA:
            oc.append(Ocorrencia("UNIDADE_MEDIDA_FORA_DOMINIO", "unidade_medida",
                                 "fora de {KG, L, UN}"))
        if v["status_cadastral"] and v["status_cadastral"] not in C.STATUS_CADASTRAL:
            oc.append(Ocorrencia("STATUS_CADASTRAL_INVALIDO", "status_cadastral",
                                 "fora de {ATIVO, INATIVO}"))
    elif entidade.nome in (C.VENDAS.nome, C.ESTOQUE.nome):
        oc.extend(_regras_relacionamento(entidade, v, cadastros, data_ok))
    return _ordenar(oc)


def _transformacao_status(status):
    regra = {
        C.DUPLICATA_DESCARTADA: C.DESCARTA_DUPLICATA,
        C.QUARENTENA: C.EXCLUI_QUARENTENA,
        C.FORA_PERIODO: C.EXCLUI_FORA_PERIODO,
    }.get(status)
    return Transformacao("status", "", status, regra) if regra else None


def avaliar_entidade(arquivo, entidade, fuso, inicio, fim, cadastros=None):
    """Avalia todas as linhas físicas de uma fonte e define o status de cada uma."""
    eh_venda = entidade.nome == C.VENDAS.nome
    linhas = []
    for lf in arquivo.linhas:
        la = LinhaAvaliada(
            entidade=entidade.nome, arquivo=arquivo.arquivo, sha256=arquivo.sha256,
            linha=lf.linha, conteudo_original=lf.conteudo_original,
            valores={c: "" for c in entidade.colunas}, malformada=lf.malformada,
        )
        if lf.malformada:
            la.ocorrencias = [Ocorrencia("LINHA_MALFORMADA", "", lf.detalhe_malformada)]
        else:
            for col, bruto in zip(entidade.colunas, lf.campos):
                norm = bruto.strip()
                la.valores[col] = norm
                if norm != bruto:
                    la.transformacoes.append(
                        Transformacao(col, bruto, norm, C.NORMALIZA_ESPACOS))
        linhas.append(la)

    conflitos, copias = _classificar_duplicidade(linhas, entidade)

    for la in linhas:
        if not la.malformada:
            data_ok = True
            if eh_venda:
                data_ok = False
                if la.valores["data"]:
                    interp = interpretar_data_venda(la.valores["data"], fuso)
                    if interp is not None:
                        data_ok = True
                        la.competencia = interp[0].isoformat()
                        if interp[1] is not None:
                            la.transformacoes.append(Transformacao(
                                "data", la.valores["data"], interp[1], C.CONVERTE_FUSO))
            elif entidade.nome == C.ESTOQUE.nome:
                data_ok = interpretar_data_referencia(la.valores["data_referencia"]) is not None

            if la.linha in copias:
                la.ocorrencias = [Ocorrencia(
                    "DUPLICATA_EXATA", C.SEPARADOR_LISTA.join(entidade.chave),
                    f"cópia da linha {copias[la.linha]}")]
            else:
                la.ocorrencias = _aplicar_regras(
                    entidade, la.valores, la.linha in conflitos, cadastros, data_ok)

        if la.linha in copias:
            la.status = C.DUPLICATA_DESCARTADA
        elif la.causas:
            la.status = C.QUARENTENA
        elif eh_venda and not (inicio <= date.fromisoformat(la.competencia) <= fim):
            la.status = C.FORA_PERIODO
        else:
            la.status = C.VALIDO
        trans = _transformacao_status(la.status)
        if trans is not None:
            la.transformacoes.append(trans)

    LOG.info("%s: %d linhas avaliadas", entidade.nome, len(linhas))
    return linhas
