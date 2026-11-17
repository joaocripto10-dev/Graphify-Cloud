"""Pipeline DEMO-4A: ingestão -> qualidade -> consolidação -> indicadores -> reconciliação -> saída.

Interface estável: ``executar(entrada, inicio, fim, raiz) -> dict``.
"""

import logging
import os
import platform
import time
from datetime import date, datetime, timezone

from . import consolida, indicadores, ingestao, qualidade, saida
from . import contratos as C
from .erros import ReconciliacaoFalhou
from .qualidade import arredondar_centavos, formatar_decimal, parse_decimal, somar

LOG = logging.getLogger(__name__)


def _validar_periodo(inicio, fim):
    for nome, valor in (("inicio", inicio), ("fim", fim)):
        if isinstance(valor, datetime) or not isinstance(valor, date):
            raise TypeError(f"{nome} deve ser datetime.date")
    if inicio > fim:
        raise ValueError("inicio posterior a fim")


# ---------------------------------------------------------------- linhas de saída

def _linhas_staging(lote, linhas, entidade):
    resultado = []
    for la in sorted(linhas, key=lambda x: x.linha):
        r = {
            "lote": lote, "arquivo_origem": la.arquivo, "linha_origem": la.linha,
            "sha256_origem": la.sha256, "status": la.status,
            "motivo_principal": la.motivo_principal,
            "causas": C.SEPARADOR_LISTA.join(la.causas),
            "alertas": C.SEPARADOR_LISTA.join(la.alertas),
            "conteudo_original": la.conteudo_original,
        }
        r.update(la.valores)
        if entidade.nome == C.VENDAS.nome:
            r["competencia"] = la.competencia
        resultado.append(r)
    return resultado


def _todas(avaliadas):
    for entidade in C.ENTIDADES:
        yield from avaliadas[entidade.nome]


def _linhas_quarentena(lote, avaliadas):
    linhas = [{
        "lote": lote, "entidade": la.entidade, "arquivo_origem": la.arquivo,
        "linha_origem": la.linha, "motivo_principal": la.motivo_principal,
        "causas": C.SEPARADOR_LISTA.join(la.causas),
        "gravidade_maxima": la.gravidade_maxima,
        "conteudo_original": la.conteudo_original,
    } for la in _todas(avaliadas) if la.status == C.QUARENTENA]
    linhas.sort(key=lambda r: (r["entidade"], r["linha_origem"]))
    return linhas


def _linhas_ocorrencias(lote, avaliadas):
    linhas = []
    for la in _todas(avaliadas):
        principal = la.motivo_principal
        for o in la.ocorrencias:
            linhas.append({
                "lote": lote, "entidade": la.entidade, "arquivo_origem": la.arquivo,
                "linha_origem": la.linha, "codigo": o.codigo, "gravidade": o.gravidade,
                "bloqueante": "sim" if o.bloqueante else "nao",
                "principal": "sim" if o.bloqueante and o.codigo == principal else "nao",
                "campo": o.campo, "detalhe": o.detalhe,
            })
    linhas.sort(key=lambda r: (r["entidade"], r["linha_origem"], C.ORDEM_REGRA[r["codigo"]]))
    return linhas


def _linhas_transformacoes(lote, avaliadas):
    linhas = [{
        "lote": lote, "entidade": la.entidade, "arquivo_origem": la.arquivo,
        "linha_origem": la.linha, "campo": t.campo, "valor_antes": t.valor_antes,
        "valor_depois": t.valor_depois, "regra": t.regra,
    } for la in _todas(avaliadas) for t in la.transformacoes]
    linhas.sort(key=lambda r: (r["entidade"], r["linha_origem"], r["campo"], r["regra"]))
    return linhas


def _manifesto(lote, fuso, inicio, fim, arquivos):
    return {
        "lote": lote,
        "contrato": C.CONTRATO,
        "fuso": {"nome": fuso.nome, "modo": fuso.modo},
        "periodo": {"inicio": inicio.isoformat(), "fim": fim.isoformat()},
        "arquivos": [{
            "arquivo": a.arquivo, "sha256": a.sha256, "bytes": a.bytes,
            "linhas_fisicas": a.linhas_fisicas, "registros": a.registros,
            "codificacao": C.CODIFICACAO,
        } for a in sorted(arquivos, key=lambda a: a.arquivo)],
    }


# ---------------------------------------------------------------- reconciliação

def _verificacao(ident, descricao, esperado, obtido, ok=None):
    return {"id": ident, "descricao": descricao, "esperado": esperado,
            "obtido": obtido, "ok": bool(esperado == obtido if ok is None else ok)}


def _soma_indicador(inds, indicador, empresa):
    return somar(parse_decimal(r["valor"])[0] for r in inds
                 if r["indicador"] == indicador and r["empresa"] == empresa)


# Fase 4B (R1, R2): esperados recalculados por caminho independente de indicadores.calcular
# e de consolida (staging VALIDO + índice de produtos válidos; taxa só com inteiros).
_INDICADORES_CONTAGEM = ("registros_recebidos", "registros_validos", "registros_quarentena",
                         "registros_fora_periodo", "duplicatas_descartadas")
_CAMPOS_INDICADOR = ("empresa", "unidade", "codigo_produto", "data_referencia",
                     "unidade_medida", "unidade_valor", "valor")


def _taxa_por_inteiros(quarentena, recebidos):
    """quarentena ÷ recebidos, 4 casas, ROUND_HALF_UP; 'indisponível' se recebidos = 0."""
    if recebidos == 0:
        return C.TAXA_INDISPONIVEL
    inteiro, fracao = divmod((2 * quarentena * 10000 + recebidos) // (2 * recebidos), 10000)
    return f"{inteiro}.{fracao:04d}"


def _esperados_por_indicador(avaliadas, indice):
    """{indicador: [linha esperada]} dos indicadores de valor, nos campos _CAMPOS_INDICADOR.

    B12: empresa ou recorte sem venda VALIDO não tem linha (ausência não é zero).
    """
    def medida(empresa, codigo):
        produto = indice.get((empresa, codigo))
        return produto.valores["unidade_medida"] if produto is not None else ""

    def dinheiro(valores):
        return formatar_decimal(arredondar_centavos(somar(valores)))

    fat, uni, prod, qtd = {}, {}, {}, {}
    for la in avaliadas[C.VENDAS.nome]:
        if la.status != C.VALIDO:
            continue
        v = la.valores
        emp, codigo = v["empresa"], v["codigo_produto"]
        valor = parse_decimal(v["valor_calculado"])[0]
        fat.setdefault(emp, []).append(valor)
        uni.setdefault((emp, v["unidade"]), []).append(valor)
        prod.setdefault((emp, codigo), []).append(valor)
        qtd.setdefault((emp, codigo, medida(emp, codigo)), []).append(
            parse_decimal(v["quantidade"])[0])
    estoque = []
    for la in avaliadas[C.ESTOQUE.nome]:
        if la.status != C.VALIDO:
            continue
        v = la.valores
        um = medida(v["empresa"], v["codigo_produto"])
        estoque.append((v["empresa"], v["unidade"], v["codigo_produto"], v["data_referencia"],
                        um, um, formatar_decimal(parse_decimal(v["quantidade_disponivel"])[0])))
    return {
        "faturamento_bruto_valido": [(e, "", "", "", "", "R$", dinheiro(vs))
                                     for e, vs in fat.items()],
        "faturamento_por_unidade": [(e, u, "", "", "", "R$", dinheiro(vs))
                                    for (e, u), vs in uni.items()],
        "faturamento_por_produto": [(e, "", c, "", "", "R$", dinheiro(vs))
                                    for (e, c), vs in prod.items()],
        "quantidade_vendida": [(e, "", c, "", um, um, formatar_decimal(somar(vs)))
                               for (e, c, um), vs in qtd.items()],
        "estoque_disponivel": estoque,
    }


_ENTIDADE_INDICADOR = {"faturamento_bruto_valido": C.VENDAS.nome,
                       "faturamento_por_unidade": C.VENDAS.nome,
                       "faturamento_por_produto": C.VENDAS.nome,
                       "quantidade_vendida": C.VENDAS.nome,
                       "estoque_disponivel": C.ESTOQUE.nome}


# Identidade de cada linha de indicador (auditoria 4B, D1/D2): chaves, unidade do valor,
# lote e período. Linhas de entidade (contagens e taxa) têm chaves de recorte vazias.
_IDENTIDADE = ("indicador", "entidade", "empresa", "unidade", "codigo_produto",
               "data_referencia", "unidade_medida", "unidade_valor", "lote",
               "periodo_inicio", "periodo_fim")
_METADADOS = ("formula", "grao", "filtro", "fonte")


def _verificacoes_indicadores(avaliadas, indice, inds, lote, inicio, fim):
    """R1 (taxa por entidade), R2 (chaves e valores por indicador) e catálogo completo."""
    v = []
    for e in C.ENTIDADES:
        quarentena = sum(1 for la in avaliadas[e.nome] if la.status == C.QUARENTENA)
        publicadas = [r["valor"] for r in inds
                      if r["indicador"] == "taxa_inconsistencia" and r["entidade"] == e.nome]
        v.append(_verificacao(
            f"indicadores_taxa_{e.nome}",
            "taxa_inconsistencia publicada uma única vez = quarentena ÷ recebidos "
            "(4 casas, ROUND_HALF_UP; 'indisponível' se recebidos = 0)",
            [_taxa_por_inteiros(quarentena, len(avaliadas[e.nome]))], publicadas))
    esperados = _esperados_por_indicador(avaliadas, indice)
    for nome, linhas in sorted(esperados.items()):
        obtidas = [tuple(r[c] for c in _CAMPOS_INDICADOR) for r in inds
                   if r["indicador"] == nome]
        v.append(_verificacao(
            f"indicadores_chaves_{nome}",
            f"linhas de {nome} (chaves {', '.join(_CAMPOS_INDICADOR[:-1])} e valor) = "
            "recálculo pelo staging VALIDO; sem chave extra, ausente ou repetida",
            [list(x) for x in sorted(linhas)], [list(x) for x in sorted(obtidas)]))
    periodo = (inicio.isoformat(), fim.isoformat())
    catalogo = [(n, e.nome, "", "", "", "", "", "registros", lote) + periodo
                for e in C.ENTIDADES for n in _INDICADORES_CONTAGEM]
    catalogo += [("taxa_inconsistencia", e.nome, "", "", "", "", "", "proporção", lote) + periodo
                 for e in C.ENTIDADES]
    for n, linhas in esperados.items():
        # A posição de estoque é foto (data de referência), sem período de vendas.
        per = ("", "") if n == "estoque_disponivel" else periodo
        catalogo += [(n, _ENTIDADE_INDICADOR[n]) + tuple(x[:-1]) + (lote,) + per
                     for x in linhas]
    v.append(_verificacao(
        "indicadores_catalogo",
        "cada linha publicada é esperada e aparece exatamente uma vez, com identidade completa "
        "(" + ", ".join(_IDENTIDADE) + ")",
        [list(x) for x in sorted(catalogo)],
        [list(x) for x in sorted(tuple(r[c] for c in _IDENTIDADE) for r in inds)]))
    combinacoes = {}
    for r in inds:  # a fonte das contagens e da taxa é o arquivo da própria entidade
        combinacoes.setdefault(f'{r["indicador"]}/{r["entidade"]}', set()).add(
            tuple(r[c] for c in _METADADOS))
    v.append(_verificacao(
        "indicadores_metadados",
        "cada (indicador, entidade) publicado tem uma única combinação de fórmula, grão, "
        "filtro e fonte, sem campo vazio",
        {n: 1 for n in sorted(combinacoes)},
        {n: len(c) + (100 if any("" in x for x in c) else 0)
         for n, c in sorted(combinacoes.items())}))
    return v


def taxa_publicada(inds, entidade):
    """Taxa de inconsistência publicada (já reconciliada) de uma entidade."""
    return next(r["valor"] for r in inds
                if r["indicador"] == "taxa_inconsistencia" and r["entidade"] == entidade)


def _reler_sha(arquivos):
    obtidos = {}
    for a in arquivos:
        try:
            obtidos[a.arquivo] = ingestao.sha256_arquivo(a.caminho)[0]
        except OSError:
            obtidos[a.arquivo] = ""
    return obtidos


def _reconciliar(arquivos, avaliadas, contagens, juncao_vendas, juncao_estoque,
                 indice, inds, lote, inicio, fim):
    v = []
    for e in C.ENTIDADES:
        cont = contagens[e.nome]
        soma = sum(cont[s] for s in C.STATUS)
        v.append(_verificacao(
            f"contagens_{e.nome}",
            "recebidos = válidos + quarentena + fora do período + duplicatas descartadas",
            cont["recebidos"], soma))
        # Auditoria 4A (B2): os indicadores de contagem publicados precisam bater com o
        # status de cada linha avaliada (contagem refeita aqui, sem passar por contar_status).
        por_status = {s: sum(1 for la in avaliadas[e.nome] if la.status == s) for s in C.STATUS}
        mapa = {"registros_recebidos": len(avaliadas[e.nome]),
                "registros_validos": por_status[C.VALIDO],
                "registros_quarentena": por_status[C.QUARENTENA],
                "registros_fora_periodo": por_status[C.FORA_PERIODO],
                "duplicatas_descartadas": por_status[C.DUPLICATA_DESCARTADA]}
        publicados = {r["indicador"]: r["valor"] for r in inds
                      if r["entidade"] == e.nome and r["indicador"] in mapa}
        v.append(_verificacao(
            f"indicadores_contagens_{e.nome}",
            "indicadores de contagem publicados = contagem por status das linhas avaliadas",
            {k: str(n) for k, n in sorted(mapa.items())},
            {k: publicados.get(k, "") for k in sorted(mapa)}))
        n_fisicas = arquivos[e.nome].linhas_fisicas
        linhas = sorted(la.linha for la in avaliadas[e.nome])
        v.append(_verificacao(
            f"linhas_fisicas_{e.nome}",
            "cada linha física de dados aparece exatamente uma vez no staging",
            n_fisicas - 1, len(linhas), ok=linhas == list(range(2, n_fisicas + 1))))

    vendas_validas = [la for la in avaliadas[C.VENDAS.nome] if la.status == C.VALIDO]
    empresas = sorted({la.valores["empresa"] for la in vendas_validas}
                      | {r["empresa"] for r in juncao_vendas.linhas})
    for empresa in empresas:
        total = _soma_indicador(inds, "faturamento_bruto_valido", empresa)
        s_uni = _soma_indicador(inds, "faturamento_por_unidade", empresa)
        s_prod = _soma_indicador(inds, "faturamento_por_produto", empresa)
        v.append(_verificacao(
            f"faturamento_recorte_{empresa}",
            "Σ por unidade = total da empresa = Σ por produto",
            formatar_decimal(arredondar_centavos(total)),
            {"por_unidade": formatar_decimal(arredondar_centavos(s_uni)),
             "por_produto": formatar_decimal(arredondar_centavos(s_prod))},
            ok=total == s_uni == s_prod))
        stg = somar(parse_decimal(la.valores["valor_calculado"])[0]
                    for la in vendas_validas if la.valores["empresa"] == empresa)
        cur = somar(parse_decimal(r["valor"])[0]
                    for r in juncao_vendas.linhas if r["empresa"] == empresa)
        v.append(_verificacao(
            f"faturamento_camadas_{empresa}",
            "Σ valor em curated = Σ valor_calculado das vendas VALIDO em staging",
            formatar_decimal(arredondar_centavos(stg)),
            formatar_decimal(arredondar_centavos(cur)), ok=stg == cur))
        # Auditoria 4A (B1): o indicador publicado precisa bater com a soma do curated.
        v.append(_verificacao(
            f"faturamento_indicador_{empresa}",
            "faturamento_bruto_valido publicado = Σ valor das linhas em curated",
            formatar_decimal(arredondar_centavos(cur)),
            formatar_decimal(arredondar_centavos(total)), ok=total == cur))

    v.append(_verificacao("juncao_vendas_produtos",
                          "contagem de vendas VALIDO antes = depois da junção N:1",
                          juncao_vendas.antes, juncao_vendas.depois))
    v.append(_verificacao("juncao_estoque_produtos",
                          "contagem de estoque VALIDO antes = depois da junção N:1",
                          juncao_estoque.antes, juncao_estoque.depois))
    n_prod_validos = sum(1 for la in avaliadas[C.PRODUTOS.nome] if la.status == C.VALIDO)
    v.append(_verificacao("produtos_validos_chave_unica",
                          "cada (empresa, codigo_produto) aparece uma vez em produtos_validos",
                          n_prod_validos, len(indice)))
    v.append(_verificacao("rastreabilidade_validos",
                          "linhas VALIDO sem causa bloqueante", 0,
                          sum(1 for la in _todas(avaliadas)
                              if la.status == C.VALIDO and la.causas)))
    v.append(_verificacao("rastreabilidade_quarentena",
                          "linhas em QUARENTENA com pelo menos uma causa bloqueante", 0,
                          sum(1 for la in _todas(avaliadas)
                              if la.status == C.QUARENTENA and not la.causas)))
    lidos = list(arquivos.values())
    v.append(_verificacao("entrada_inalterada",
                          "sha256 das fontes relido no fim do pipeline é igual ao inicial",
                          {a.arquivo: a.sha256 for a in lidos}, _reler_sha(lidos)))
    v.extend(_verificacoes_indicadores(avaliadas, indice, inds, lote, inicio, fim))
    v.sort(key=lambda x: x["id"])
    return {"ok": all(x["ok"] for x in v), "verificacoes": v}


# ---------------------------------------------------------------- execução

def executar(entrada, inicio, fim, raiz):
    """Executa o DEMO-4A e publica as 4 pastas do lote. Ver docs/CONTRATOS_DADOS.md."""
    instante_inicio = datetime.now(timezone.utc)
    relogio = time.monotonic()
    _validar_periodo(inicio, fim)

    raiz_real = saida.verificar_raiz(os.fspath(raiz))
    entrada_real = saida.verificar_entrada(os.fspath(entrada), raiz_real)

    arquivos = {}
    for entidade in sorted(C.ENTIDADES, key=lambda e: e.arquivo):
        arquivos[entidade.nome] = ingestao.ler_fonte(entrada_real, entidade)
    lote = ingestao.calcular_lote(arquivos.values())
    pastas = saida.destinos(os.fspath(raiz), lote)
    saida.verificar_entrada_fora_destinos(entrada_real, pastas)
    LOG.info("lote %s: fontes lidas", lote)

    fuso = qualidade.obter_fuso()
    unidades = qualidade.avaliar_entidade(arquivos["unidades"], C.UNIDADES, fuso, inicio, fim)
    produtos = qualidade.avaliar_entidade(arquivos["produtos"], C.PRODUTOS, fuso, inicio, fim)
    indice = consolida.indexar_produtos_validos(produtos)
    cadastros = qualidade.montar_cadastros(unidades, produtos, indice)
    vendas = qualidade.avaliar_entidade(arquivos["vendas"], C.VENDAS, fuso, inicio, fim,
                                        cadastros)
    estoque = qualidade.avaliar_entidade(arquivos["estoque"], C.ESTOQUE, fuso, inicio, fim,
                                         cadastros)
    avaliadas = {"unidades": unidades, "produtos": produtos, "vendas": vendas,
                 "estoque": estoque}

    juncao_vendas = consolida.consolidar_vendas(vendas, indice, lote)
    juncao_estoque = consolida.posicao_estoque(estoque, indice, lote)
    inds = indicadores.calcular(lote, avaliadas, juncao_vendas.linhas,
                                juncao_estoque.linhas, inicio, fim)
    contagens = {nome: indicadores.contar_status(linhas) for nome, linhas in avaliadas.items()}

    reconciliacao = _reconciliar(arquivos, avaliadas, contagens, juncao_vendas,
                                 juncao_estoque, indice, inds, lote, inicio, fim)
    if not reconciliacao["ok"]:
        falhas = [x["id"] for x in reconciliacao["verificacoes"] if not x["ok"]]
        LOG.error("lote %s: reconciliação falhou (%s)", lote, ", ".join(falhas))
        raise ReconciliacaoFalhou("reconciliação falhou: " + ", ".join(falhas))

    conteudos = _conteudos(lote, fuso, inicio, fim, arquivos, avaliadas, contagens,
                           juncao_vendas, juncao_estoque, indice, inds, reconciliacao)
    instante_fim = datetime.now(timezone.utc)
    conteudos["outputs"]["execucao.json"] = saida.json_texto({
        "lote": lote,
        "inicio": instante_inicio.isoformat(),
        "fim": instante_fim.isoformat(),
        "duracao_segundos": round(time.monotonic() - relogio, 3),
        "versao_python": platform.python_version(),
    })
    saida.publicar(pastas, conteudos)
    return {"lote": lote, "diretorios": dict(pastas), "reconciliacao_ok": True}


def _conteudos(lote, fuso, inicio, fim, arquivos, avaliadas, contagens, juncao_vendas,
               juncao_estoque, indice, inds, reconciliacao):
    """Textos de todos os arquivos determinísticos, por camada."""
    staging = {"manifesto.json": saida.json_texto(
        _manifesto(lote, fuso, inicio, fim, arquivos.values()))}
    for e in C.ENTIDADES:
        staging[e.arquivo] = saida.csv_texto(
            C.colunas_staging(e), _linhas_staging(lote, avaliadas[e.nome], e))

    curated = {
        "vendas_consolidadas.csv": saida.csv_texto(
            C.COLUNAS_VENDAS_CONSOLIDADAS, juncao_vendas.linhas),
        "produtos_validos.csv": saida.csv_texto(
            C.COLUNAS_PRODUTOS_VALIDOS, consolida.produtos_validos(indice, lote)),
        "estoque_posicao.csv": saida.csv_texto(
            C.COLUNAS_ESTOQUE_POSICAO, juncao_estoque.linhas),
        "quarentena.csv": saida.csv_texto(
            C.COLUNAS_QUARENTENA, _linhas_quarentena(lote, avaliadas)),
        "ocorrencias.csv": saida.csv_texto(
            C.COLUNAS_OCORRENCIAS, _linhas_ocorrencias(lote, avaliadas)),
        "transformacoes.csv": saida.csv_texto(
            C.COLUNAS_TRANSFORMACOES, _linhas_transformacoes(lote, avaliadas)),
    }
    analytics = {"indicadores.csv": saida.csv_texto(C.COLUNAS_INDICADORES, inds)}

    # Fase 4B (R1): fonte única, a taxa publicada em indicadores.csv e já reconciliada.
    taxas = {e.nome: taxa_publicada(inds, e.nome) for e in C.ENTIDADES}
    motivos = []
    for e in C.ENTIDADES:
        cont = {}
        for la in avaliadas[e.nome]:
            if la.status in (C.QUARENTENA, C.DUPLICATA_DESCARTADA):
                chave = (la.status, la.motivo_principal)
                cont[chave] = cont.get(chave, 0) + 1
        for (status, motivo), n in sorted(
                cont.items(), key=lambda kv: (kv[0][0], C.ORDEM_REGRA[kv[0][1]])):
            motivos.append((e.nome, status, motivo, n))
    faturamento = [(r["empresa"], r["valor"]) for r in inds
                   if r["indicador"] == "faturamento_bruto_valido"]
    outputs = {
        "reconciliacao.json": saida.json_texto(reconciliacao),
        "relatorio_qualidade.md": saida.relatorio_qualidade(
            lote, inicio, fim, fuso, arquivos.values(), contagens, taxas, motivos,
            faturamento, reconciliacao),
    }
    return {"staging": staging, "curated": curated, "analytics": analytics,
            "outputs": outputs}
