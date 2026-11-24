#!/usr/bin/env bash
# Executor HOMOLOGADO de testes e verificacoes (FASE 4B.1, ADR-003).
#
# Unico caminho liberado sem confirmacao para executar Python neste projeto. As regras de
# permissao citam cada modalidade por extenso (sem curinga); a regra ask Bash(python:*)
# continua valendo para qualquer outro uso de python.
#
#   bash scripts/testar.sh motor            suite completa (fuso no modo do ambiente limpo)
#   bash scripts/testar.sh motor-zoneinfo   suite completa com o TZif versionado
#   bash scripts/testar.sh governanca       suite do hook guarda_agentes
#   bash scripts/testar.sh tudo             as tres acima
#   bash scripts/testar.sh conferir         so as verificacoes de integridade (nao roda testes)
#   bash scripts/testar.sh demo             saidas demonstrativas das fixtures ficticias
#   bash scripts/testar.sh arquivo test_<nome>.py   um arquivo de teste (pede confirmacao)
#
# Antes de executar qualquer coisa: argumentos fechados; raiz, ferramentas e ambiente
# conferidos; settings.json valido; conjunto identico ao manifesto homologado. Depois de cada
# suite o conjunto e conferido de novo: se mudou durante a execucao, o resultado e invalidado.
# Codigos: 0 ok; 1 teste falhou; 3 conjunto nao homologado (ou alterado durante a execucao);
# 4 configuracao invalida; 64 uso incorreto; 70 ambiente recusado.
# Testes sao codigo: isto NAO e sandbox. Uso restrito a dados demonstrativos.
set -euo pipefail

uso() {
    echo "uso: bash scripts/testar.sh {motor|motor-zoneinfo|governanca|tudo|conferir|demo|arquivo test_<nome>.py}" >&2
    exit 64
}

[ "$#" -ge 1 ] || uso
MODALIDADE="$1"
ARQUIVO=""
case "$MODALIDADE" in
    motor | motor-zoneinfo | governanca | tudo | conferir | demo)
        [ "$#" -eq 1 ] || uso ;;
    arquivo)
        [ "$#" -eq 2 ] || uso
        [[ "$2" =~ ^test_[a-z0-9_]+\.py$ ]] || uso
        ARQUIVO="$2" ;;
    *)
        uso ;;
esac

# shellcheck source=scripts/lib_homologacao.sh
source "$(dirname -- "${BASH_SOURCE[0]}")/lib_homologacao.sh"
preparar_ambiente
verificar_nucleo || exit 3      # 1o: os arquivos que fazem a propria verificacao (em shell)
verificar_settings || exit 4    # 2o: configuracao de permissoes valida (JSON estrito)
verificar_conjunto || exit 3    # 3o: todo o conjunto identico ao manifesto; nenhum link
limpar_cache                    # 4o: so o codigo-fonte conferido sera executado
if [ -n "$ARQUIVO" ]; then
    [ -f "tests/$ARQUIVO" ] && [ ! -L "tests/$ARQUIVO" ] || uso
fi

executar() {  # executar <rotulo> <comando...>: saida completa no log, resumo na tela
    local rotulo="$1" log codigo=0
    shift
    [ ! -L outputs ] && [ ! -L outputs/testes ] || falhar 70 "outputs/testes e link"
    mkdir -p outputs/testes
    log="outputs/testes/$rotulo.log"
    rm -f -- "$log"  # nunca escrever por cima de um link plantado com o nome do log
    "$@" > "$log" 2>&1 || codigo=$?
    grep -E '^(Ran [0-9]+ tests?|OK|FAILED|FAIL|ERROR|SKIP|TOTAL|lote:|reconciliacao:)' "$log" || true
    reverificar || codigo=3
    printf '[%s] codigo %d (saida completa: %s)\n' "$rotulo" "$codigo" "$log"
    return "$codigo"
}

tzpath() {  # caminho ABSOLUTO do TZif versionado, no formato do sistema
    if command -v cygpath > /dev/null 2>&1; then
        cygpath -w "$RAIZ/tests/fixtures/tzif"
    else
        printf '%s\n' "$RAIZ/tests/fixtures/tzif"
    fi
}

suite_motor() {
    executar motor "${AMBIENTE[@]}" "$PY" -I -B -m unittest discover -s tests
}

suite_motor_zoneinfo() {
    executar motor-zoneinfo "${AMBIENTE[@]}" "PYTHONTZPATH=$(tzpath)" \
        "$PY" -I -B -m unittest discover -s tests
}

suite_governanca() {
    executar governanca "${AMBIENTE[@]}" "$PY" -I -B tests/test_guarda_agentes.py
}

case "$MODALIDADE" in
    conferir)
        echo "ambiente, manifesto e configuracao conferidos" ;;
    motor)
        suite_motor ;;
    motor-zoneinfo)
        suite_motor_zoneinfo ;;
    governanca)
        suite_governanca ;;
    tudo)
        codigo=0
        suite_motor || codigo=$?
        suite_motor_zoneinfo || codigo=$?
        suite_governanca || codigo=$?
        exit "$codigo" ;;
    demo)
        executar demo "${AMBIENTE[@]}" "$PY" -I -B scripts/executar_demo_4a.py \
            --entrada tests/fixtures/demo_4a --periodo 2026-10-01:2026-10-31 ;;
    arquivo)
        executar "arquivo-${ARQUIVO%.py}" "${AMBIENTE[@]}" "$PY" -I -B -m unittest discover \
            -s tests -p "$ARQUIVO" ;;
esac
