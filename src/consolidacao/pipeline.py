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


def _reler_sha(arquivos):
    obtidos = {}
    for a in arquivos:
        try:
            obtidos[a.arquivo] = ingestao.sha256_arquivo(a.caminho)[0]
        except OSError:
            obtidos[a.arquivo] = ""
    return obtidos


def _reconciliar(arquivos, avaliadas, contagens, juncao_vendas, juncao_estoque,
                 indice, inds):
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
                                 juncao_estoque, indice, inds)
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

    taxas = {e.nome: indicadores.taxa_inconsistencia(
        contagens[e.nome][C.QUARENTENA], contagens[e.nome]["recebidos"])
        for e in C.ENTIDADES}
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
