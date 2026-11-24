#!/usr/bin/env bash
# Homologa o conjunto de codigo atual (FASE 4B.1, ADR-003): grava scripts/homologacao.manifest.
#
# ESTE COMANDO EXIGE CONFIRMACAO DO USUARIO (regra ask). Depois dele, as suites liberadas de
# scripts/testar.sh voltam a rodar sem confirmacao sobre o conjunto recem-homologado.
# Antes de aprovar, revise o que mudou:
#   bash scripts/testar.sh conferir    lista os arquivos novos, alterados e removidos
#   git status / git diff              mostra o conteudo das mudancas
#
# Uso: bash scripts/homologar.sh   (sem argumentos)
set -euo pipefail

[ "$#" -eq 0 ] || { echo "uso: bash scripts/homologar.sh (sem argumentos)" >&2; exit 64; }

# shellcheck source=scripts/lib_homologacao.sh
source "$(dirname -- "${BASH_SOURCE[0]}")/lib_homologacao.sh"
preparar_ambiente
verificar_settings || exit 4    # nao se homologa por cima de uma configuracao invalida
"${AMBIENTE[@]}" "$PY" -I -B scripts/homologacao.py gravar
