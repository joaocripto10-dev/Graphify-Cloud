"""Leitura das fontes: bytes, sha256, UTF-8 estrito, cabeçalho e linhas físicas."""

import csv
import hashlib
import logging
import os
import re
from dataclasses import dataclass

from .contratos import CODIFICACAO, PREFIXO_LOTE
from .erros import LoteRejeitado

LOG = logging.getLogger(__name__)

_BOM_UTF8 = b"\xef\xbb\xbf"
_TERMINADOR = re.compile(r"\r\n|\n|\r")


@dataclass(frozen=True)
class LinhaFisica:
    """Linha física de dados (o cabeçalho é a linha 1 e não aparece aqui).

    ``campos`` é None quando a linha é malformada (não interpretada).
    """

    linha: int
    conteudo_original: str
    campos: tuple = None
    detalhe_malformada: str = ""

    @property
    def malformada(self):
        return self.campos is None


@dataclass(frozen=True)
class ArquivoLido:
    """Resultado da leitura de uma fonte."""

    entidade: str
    arquivo: str
    caminho: str
    sha256: str
    bytes: int
    linhas_fisicas: int
    linhas: tuple

    @property
    def registros(self):
        """Linhas físicas de dados (sem o cabeçalho)."""
        return len(self.linhas)


def sha256_arquivo(caminho):
    """Retorna (sha256 hex, tamanho em bytes) lendo o arquivo em modo binário."""
    with open(caminho, "rb") as arq:
        dados = arq.read()
    return hashlib.sha256(dados).hexdigest(), len(dados)


def _dividir_linhas(texto):
    """Divide o texto em [(conteudo_sem_terminador, terminador)]."""
    linhas = []
    pos = 0
    for m in _TERMINADOR.finditer(texto):
        linhas.append((texto[pos:m.start()], m.group()))
        pos = m.end()
    if pos < len(texto):
        linhas.append((texto[pos:], ""))
    return linhas


def ler_fonte(diretorio, entidade):
    """Lê e valida estruturalmente a fonte de ``entidade`` em ``diretorio``.

    Levanta LoteRejeitado se o arquivo estiver ausente, vazio, fora de UTF-8
    (inclusive com BOM) ou com cabeçalho diferente do contrato.
    """
    nome = entidade.arquivo
    caminho = os.path.join(diretorio, nome)
    if not os.path.isfile(caminho):
        raise LoteRejeitado(f"{nome}: arquivo ausente")
    with open(caminho, "rb") as arq:
        dados = arq.read()
    if not dados:
        raise LoteRejeitado(f"{nome}: arquivo vazio")
    if dados.startswith(_BOM_UTF8):
        raise LoteRejeitado(f"{nome}: BOM UTF-8 não é aceito")
    try:
        texto = dados.decode(CODIFICACAO, errors="strict")
    except UnicodeDecodeError as exc:
        raise LoteRejeitado(f"{nome}: conteúdo fora de UTF-8 (byte {exc.start})") from None

    fisicas = _dividir_linhas(texto)
    leitor = csv.reader([c + t for c, t in fisicas])
    registros = []
    fim_anterior = 0
    try:
        for campos in leitor:
            fim = leitor.line_num
            registros.append((fim_anterior + 1, fim, campos))
            fim_anterior = fim
    except csv.Error:
        raise LoteRejeitado(
            f"{nome}: CSV ilegível perto da linha física {leitor.line_num}"
        ) from None

    if not registros:
        raise LoteRejeitado(f"{nome}: arquivo sem cabeçalho")
    inicio, fim, cabecalho = registros[0]
    if inicio != 1 or fim != 1 or tuple(cabecalho) != entidade.colunas:
        raise LoteRejeitado(f"{nome}: cabeçalho diferente do contrato")

    n_colunas = len(entidade.colunas)
    linhas = []
    for inicio, fim, campos in registros[1:]:
        if fim > inicio:
            for n in range(inicio, fim + 1):
                linhas.append(LinhaFisica(
                    n, fisicas[n - 1][0], None,
                    f"registro ocupa {fim - inicio + 1} linhas físicas ({inicio}-{fim})",
                ))
        elif len(campos) != n_colunas:
            linhas.append(LinhaFisica(
                inicio, fisicas[inicio - 1][0], None,
                f"{len(campos)} colunas; esperado {n_colunas}",
            ))
        else:
            linhas.append(LinhaFisica(inicio, fisicas[inicio - 1][0], tuple(campos)))
    # Defensivo: linhas físicas não consumidas pelo leitor viram malformadas.
    for n in range(fim_anterior + 1, len(fisicas) + 1):
        linhas.append(LinhaFisica(n, fisicas[n - 1][0], None, "linha não interpretável"))

    LOG.info("%s: %d linhas físicas de dados lidas", nome, len(linhas))
    return ArquivoLido(
        entidade=entidade.nome,
        arquivo=nome,
        caminho=caminho,
        sha256=hashlib.sha256(dados).hexdigest(),
        bytes=len(dados),
        linhas_fisicas=len(fisicas),
        linhas=tuple(linhas),
    )


def calcular_lote(arquivos):
    """``DEMO4A-`` + 12 hex do sha256 da lista ordenada ``nome:sha256`` (uma por linha)."""
    lista = sorted(f"{a.arquivo}:{a.sha256}" for a in arquivos)
    resumo = hashlib.sha256("\n".join(lista).encode("utf-8")).hexdigest()
    return PREFIXO_LOTE + resumo[:12]
