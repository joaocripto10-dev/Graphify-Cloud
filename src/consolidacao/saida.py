"""Segurança de caminhos, renderização determinística e publicação atômica do lote."""

import csv
import io
import json
import logging
import os
import re
import secrets
import shutil
import tempfile

from . import contratos as C
from .erros import CaminhoNaoPermitido

LOG = logging.getLogger(__name__)

# camada -> partes relativas à raiz (a pasta do lote fica em <base>/demo_4a/<lote>).
CAMADAS = (
    ("staging", ("data", "staging")),
    ("curated", ("data", "curated")),
    ("analytics", ("data", "analytics")),
    ("outputs", ("outputs",)),
)
_RE_LOTE = re.compile(r"DEMO4A-[0-9a-f]{12}")


# ---------------------------------------------------------------- caminhos

def _norm(caminho):
    return os.path.normcase(os.path.abspath(caminho))


def _contido(caminho, base):
    """True se ``caminho`` é ``base`` ou está dentro dele (comparação normalizada)."""
    c, b = _norm(caminho), _norm(base)
    try:
        return os.path.commonpath([c, b]) == b
    except ValueError:  # discos diferentes no Windows
        return False


def verificar_raiz(raiz):
    """A raiz precisa ser um diretório existente; retorna o caminho real."""
    real = os.path.realpath(raiz)
    if not os.path.isdir(real):
        raise CaminhoNaoPermitido("raiz inexistente ou não é diretório")
    return real


def verificar_entrada(entrada, raiz_real):
    """Recusa entrada dentro de <raiz>/data (inclusive via link simbólico)."""
    entrada_real = os.path.realpath(entrada)
    data = os.path.join(raiz_real, "data")
    if _contido(entrada_real, data) or _contido(entrada_real, os.path.realpath(data)):
        raise CaminhoNaoPermitido("entrada dentro de <raiz>/data não é permitida")
    return entrada_real


def destinos(raiz, lote):
    """Pastas do lote por camada (na forma absoluta da raiz informada).

    A validação usa o caminho real: um link simbólico que leve para fora da
    base permitida é recusado.
    """
    if not _RE_LOTE.fullmatch(lote):
        raise CaminhoNaoPermitido("identificador de lote inválido")
    raiz_abs = os.path.abspath(raiz)
    raiz_real = os.path.realpath(raiz)
    resultado = {}
    for camada, partes in CAMADAS:
        destino = os.path.join(raiz_abs, *partes, C.SUBPASTA, lote)
        base_real = os.path.join(raiz_real, *partes)
        if not _contido(os.path.realpath(destino), base_real):
            raise CaminhoNaoPermitido(f"saída fora de {'/'.join(partes)}")
        resultado[camada] = destino
    return resultado


def verificar_entrada_fora_destinos(entrada_real, pastas):
    """A entrada não pode ficar dentro de uma pasta que será substituída."""
    for destino in pastas.values():
        if _contido(entrada_real, os.path.realpath(destino)):
            raise CaminhoNaoPermitido("entrada dentro de uma pasta de saída do lote")


# ---------------------------------------------------------------- renderização

def _texto(valor):
    return "" if valor is None else str(valor)


def csv_texto(colunas, linhas):
    """CSV com cabeçalho, terminador '\\n' e aspas mínimas."""
    buf = io.StringIO(newline="")
    escritor = csv.writer(buf, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    escritor.writerow(colunas)
    for linha in linhas:
        escritor.writerow([_texto(linha[c]) for c in colunas])
    return buf.getvalue()


def json_texto(obj):
    """JSON determinístico (chaves ordenadas, UTF-8 legível, '\\n' final)."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, indent=2) + "\n"


def _tabela(cabecalho, linhas):
    saida = ["| " + " | ".join(cabecalho) + " |",
             "|" + "|".join("---" for _ in cabecalho) + "|"]
    saida.extend("| " + " | ".join(_texto(c) for c in linha) + " |" for linha in linhas)
    return saida


def relatorio_qualidade(lote, inicio, fim, fuso, arquivos, contagens, taxas,
                        motivos, faturamento, reconciliacao):
    """Relatório Markdown determinístico (sem horário)."""
    ok = reconciliacao["ok"]
    n = len(reconciliacao["verificacoes"])
    md = [
        "# Relatório de qualidade DEMO-4A",
        "",
        "> DEMONSTRATIVO: dados 100% fictícios; não aplicar a dados reais.",
        "",
        f"- Lote: `{lote}`",
        f"- Contrato: {C.CONTRATO}",
        f"- Período declarado: {inicio.isoformat()} a {fim.isoformat()} (intervalo fechado)",
        f"- Fuso de competência: {fuso.nome} (modo `{fuso.modo}`)",
        f"- Reconciliação: {'OK' if ok else 'FALHOU'} ({n} verificações)",
        "",
        "## Arquivos de origem",
        "",
    ]
    md += _tabela(("Arquivo", "SHA-256", "Bytes", "Linhas físicas", "Registros"),
                  [(a.arquivo, a.sha256, a.bytes, a.linhas_fisicas, a.registros)
                   for a in sorted(arquivos, key=lambda a: a.arquivo)])
    md += ["", "## Contagens por entidade", ""]
    md += _tabela(
        ("Entidade", "Recebidos", "Válidos", "Quarentena", "Fora do período",
         "Duplicatas descartadas", "Taxa de inconsistência"),
        [(e.nome, contagens[e.nome]["recebidos"], contagens[e.nome][C.VALIDO],
          contagens[e.nome][C.QUARENTENA], contagens[e.nome][C.FORA_PERIODO],
          contagens[e.nome][C.DUPLICATA_DESCARTADA], taxas[e.nome])
         for e in C.ENTIDADES])
    md += ["", "## Motivos principais", "",
           "Contagem pelo motivo principal; todas as causas estão em `ocorrencias.csv`.", ""]
    md += _tabela(("Entidade", "Status", "Motivo principal", "Registros"), motivos)
    md += ["", "## Faturamento bruto válido por empresa (R$)", "",
           "Sem total entre empresas.", ""]
    md += _tabela(("Empresa", "Faturamento"), faturamento)
    md += ["", "## Verificações de reconciliação", ""]
    md += _tabela(("Verificação", "Resultado"),
                  [(v["id"], "ok" if v["ok"] else "FALHOU")
                   for v in reconciliacao["verificacoes"]])
    return "\n".join(md) + "\n"


# ---------------------------------------------------------------- publicação

def _remover(caminho):
    if os.path.isdir(caminho) and not os.path.islink(caminho):
        shutil.rmtree(caminho, ignore_errors=True)
    elif os.path.lexists(caminho):
        try:
            os.remove(caminho)
        except OSError:
            LOG.warning("não foi possível remover um temporário do lote")


def publicar(pastas, conteudos):
    """Grava tudo em temporários irmãos e só então substitui as pastas do lote.

    ``pastas``: camada -> destino; ``conteudos``: camada -> {nome_arquivo: texto}.
    Em erro, restaura as pastas antigas e remove os temporários.
    """
    temporarios, antigos, movidas = {}, {}, []
    try:
        for camada, destino in pastas.items():
            pai = os.path.dirname(destino)
            os.makedirs(pai, exist_ok=True)
            nome = os.path.basename(destino)
            tmp = tempfile.mkdtemp(prefix=f".{nome}.tmp-", dir=pai)
            temporarios[camada] = tmp
            for arquivo, texto in sorted(conteudos[camada].items()):
                with open(os.path.join(tmp, arquivo), "w", encoding="utf-8",
                          newline="") as saida:
                    saida.write(texto)
        for camada, destino in pastas.items():
            if os.path.lexists(destino):
                antigo = os.path.join(
                    os.path.dirname(destino),
                    f".{os.path.basename(destino)}.old-{secrets.token_hex(8)}")
                os.replace(destino, antigo)
                antigos[camada] = antigo
            os.replace(temporarios[camada], destino)
            del temporarios[camada]
            movidas.append(camada)
    except BaseException:
        for camada in movidas:
            _remover(pastas[camada])
        for camada, antigo in antigos.items():
            try:
                os.replace(antigo, pastas[camada])
            except OSError:
                LOG.error("falha ao restaurar a pasta anterior da camada %s", camada)
        for tmp in temporarios.values():
            _remover(tmp)
        raise
    for antigo in antigos.values():
        _remover(antigo)
    LOG.info("lote publicado em %d camadas", len(pastas))
