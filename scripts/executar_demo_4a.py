"""Executa o pipeline DEMONSTRATIVO DEMO-4A (somente dados fictícios).

Uso:
    python -I scripts/executar_demo_4a.py --entrada DIR --periodo AAAA-MM-DD:AAAA-MM-DD [--raiz DIR]

Códigos de saída: 0 ok; 2 LoteRejeitado; 3 ReconciliacaoFalhou;
4 CaminhoNaoPermitido; 1 outro erro (inclusive argumentos inválidos).
"""

import argparse
import logging
import os
import re
import sys
from datetime import date

RAIZ_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# python -I não inclui o diretório do script nem o cwd em sys.path.
sys.path.insert(0, os.path.join(RAIZ_REPO, "src"))

from consolidacao.erros import (  # noqa: E402
    CaminhoNaoPermitido,
    ErroPipeline,
    LoteRejeitado,
    ReconciliacaoFalhou,
)
from consolidacao.pipeline import executar  # noqa: E402

_RE_PERIODO = re.compile(r"([0-9]{4}-[0-9]{2}-[0-9]{2}):([0-9]{4}-[0-9]{2}-[0-9]{2})")
_CODIGOS = ((LoteRejeitado, 2), (ReconciliacaoFalhou, 3), (CaminhoNaoPermitido, 4))


class _ErroArgumentos(Exception):
    """Argumentos de linha de comando inválidos."""


class _Parser(argparse.ArgumentParser):
    """Parser que não usa o código 2 (reservado a LoteRejeitado)."""

    def error(self, message):
        raise _ErroArgumentos(message)


def _periodo(texto):
    m = _RE_PERIODO.fullmatch(texto)
    if m is None:
        raise argparse.ArgumentTypeError("use AAAA-MM-DD:AAAA-MM-DD")
    try:
        inicio, fim = date.fromisoformat(m.group(1)), date.fromisoformat(m.group(2))
    except ValueError:
        raise argparse.ArgumentTypeError("data inexistente no período") from None
    if inicio > fim:
        raise argparse.ArgumentTypeError("início posterior ao fim")
    return inicio, fim


def _argumentos(argv):
    parser = _Parser(description="Pipeline DEMONSTRATIVO DEMO-4A (dados fictícios).")
    parser.add_argument("--entrada", required=True, help="diretório com os 4 CSVs")
    parser.add_argument("--periodo", required=True, type=_periodo,
                        help="AAAA-MM-DD:AAAA-MM-DD (intervalo fechado)")
    parser.add_argument("--raiz", default=RAIZ_REPO,
                        help="raiz onde ficam data/ e outputs/ (padrão: repositório)")
    return parser.parse_args(argv)


def main(argv=None):
    """Ponto de entrada; retorna o código de saída."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    try:
        args = _argumentos(argv)
    except _ErroArgumentos as exc:
        print(f"erro de argumentos: {exc}", file=sys.stderr)
        return 1
    inicio, fim = args.periodo
    try:
        resultado = executar(args.entrada, inicio, fim, args.raiz)
    except ErroPipeline as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        for classe, codigo in _CODIGOS:
            if isinstance(exc, classe):
                return codigo
        return 1
    except Exception as exc:  # noqa: BLE001 - código 1 para qualquer outro erro
        print(f"erro inesperado: {type(exc).__name__}", file=sys.stderr)
        return 1
    print(f"lote: {resultado['lote']}")
    for camada in ("staging", "curated", "analytics", "outputs"):
        print(f"{camada}: {resultado['diretorios'][camada]}")
    print("reconciliacao: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
