# Preambulo comum de scripts/testar.sh e scripts/homologar.sh (FASE 4B.1, ADR-003).
# Carregado com `source`; nao executar diretamente.
#
# Garante, antes de qualquer execucao homologada:
#   - raiz fisica do repositorio derivada do local do executor (nao do diretorio atual);
#   - nenhum link simbolico/juncao no executor nem nas pastas de codigo;
#   - python, git e utilitarios resolvidos FORA do repositorio, por caminho absoluto;
#   - ambiente limpo: so as variaveis de VARS_PERMITIDAS chegam aos processos filhos;
#   - nenhum bytecode em cache (so o codigo-fonte conferido pelo manifesto e executado).
# Isto NAO e isolamento do sistema operacional: testes sao codigo e rodam com as permissoes
# do usuario. O ambiente continua restrito a dados demonstrativos.

MANIFESTO="scripts/homologacao.manifest"
NUCLEO=(scripts/testar.sh scripts/homologar.sh scripts/lib_homologacao.sh
        scripts/homologacao.py scripts/validar_settings.py)
PASTAS_CODIGO=(scripts src tests)
VARS_PERMITIDAS=(PATH HOME USERPROFILE HOMEDRIVE HOMEPATH SYSTEMROOT SYSTEMDRIVE WINDIR COMSPEC
                 PATHEXT TEMP TMP TMPDIR APPDATA LOCALAPPDATA PROGRAMDATA PROGRAMFILES
                 ALLUSERSPROFILE NUMBER_OF_PROCESSORS PROCESSOR_ARCHITECTURE OS LANG LC_ALL
                 TERM MSYSTEM)

falhar() {  # falhar <codigo> <mensagem>
    local codigo="$1"
    shift
    printf 'ERRO: %s\n' "$*" >&2
    exit "$codigo"
}

ferramenta() {  # caminho fisico absoluto de um programa; recusa o que estiver no repositorio
    local p d
    p="$(command -v -- "$1")" || falhar 70 "ferramenta ausente: $1"
    case "$p" in
        /*) ;;
        *) falhar 70 "ferramenta sem caminho absoluto: $1 -> $p" ;;
    esac
    d="$(cd -P -- "$(dirname -- "$p")" && pwd -P)"
    case "${d,,}/" in
        "${RAIZ,,}/"*) falhar 70 "ferramenta dentro do repositorio: $p" ;;
    esac
    printf '%s/%s\n' "$d" "$(basename -- "$p")"
}

preparar_ambiente() {  # define RAIZ, PY, GIT e AMBIENTE; muda para a raiz
    local executor="${BASH_SOURCE[1]}" aqui topo f v
    [ ! -L "$executor" ] || falhar 70 "o executor e um link simbolico"
    aqui="$(cd -P -- "$(dirname -- "$executor")" && pwd -P)"
    [ "$(basename -- "$aqui")" = scripts ] || falhar 70 "executor fora da pasta scripts/"
    RAIZ="$(cd -P -- "$aqui/.." && pwd -P)"
    cd -- "$RAIZ"
    for f in "${PASTAS_CODIGO[@]}" .claude .claude/hooks; do
        [ -d "$f" ] || falhar 70 "pasta ausente: $f"
        [ ! -L "$f" ] || falhar 70 "pasta e link simbolico ou juncao: $f"
    done
    GIT="$(ferramenta git)"
    PY="$(ferramenta python)"
    ENV_BIN="$(ferramenta env)"
    for f in find sed sha256sum grep cut rm mkdir; do
        ferramenta "$f" > /dev/null
    done
    AMBIENTE=("$ENV_BIN" -i)
    for v in "${VARS_PERMITIDAS[@]}"; do
        if [ -n "${!v+x}" ]; then
            AMBIENTE+=("$v=${!v}")
        fi
    done
    # O git do proprio executor tambem roda no ambiente limpo (GIT_DIR etc. nao o desviam).
    topo="$("${AMBIENTE[@]}" "$GIT" -C "$RAIZ" rev-parse --show-toplevel 2> /dev/null)" ||
        falhar 70 "a raiz do executor nao e um repositorio Git"
    [ "$topo" -ef "$RAIZ" ] || falhar 70 "o executor nao esta na raiz do repositorio Git"
}

limpar_cache() {  # remove __pycache__ das pastas de codigo (artefato derivado, fora do Git)
    # Chamado SO depois de o manifesto conferir: a essa altura nao ha link nem juncao nas
    # pastas de codigo (homologacao.py recusa). Ainda assim, links nunca sao seguidos.
    local d
    while IFS= read -r d; do
        [ -d "$d" ] && [ ! -L "$d" ] || falhar 70 "__pycache__ inesperado (link): $d"
        rm -rf -- "$d"
    done < <(find "${PASTAS_CODIGO[@]}" -name __pycache__ -prune -print)
}

hash_nucleo() {  # mesmo criterio de scripts/homologacao.py: *.sh por bytes exatos
    case "$1" in
        *.sh) sha256sum < "$1" ;;
        *) sed 's/\r$//' "$1" | sha256sum ;;
    esac | cut -d' ' -f1
}

verificar_nucleo() {  # confere em shell os arquivos que fazem a propria verificacao
    local f esperado atual
    [ -f "$MANIFESTO" ] && [ ! -L "$MANIFESTO" ] || {
        echo "manifesto ausente ou link: $MANIFESTO" >&2
        return 3
    }
    for f in "${NUCLEO[@]}"; do
        [ -f "$f" ] && [ ! -L "$f" ] || { echo "nucleo ausente ou link: $f" >&2; return 3; }
        esperado="$(sed 's/\r$//' "$MANIFESTO" | grep -x -- "[0-9a-f]\{64\}  $f" | cut -d' ' -f1 || true)"
        atual="$(hash_nucleo "$f")"
        [ -n "$esperado" ] && [ "$esperado" = "$atual" ] || {
            echo "alterado (nucleo): $f" >&2
            return 3
        }
    done
}

verificar_conjunto() {  # conjunto completo, em Python (o nucleo ja foi conferido em shell)
    "${AMBIENTE[@]}" "$PY" -I -B scripts/homologacao.py verificar || return 3
}

reverificar() {  # depois de cada suite: o conjunto nao pode ter mudado DURANTE a execucao
    if ! { verificar_nucleo && verificar_conjunto > /dev/null; }; then
        echo "conjunto alterado DURANTE a execucao: resultado invalidado" >&2
        return 3
    fi
    # Tudo roda com -B: bytecode em cache so aparece se algo o plantou durante a execucao.
    if [ -n "$(find "${PASTAS_CODIGO[@]}" -name __pycache__ -print -quit)" ]; then
        echo "bytecode em cache surgiu DURANTE a execucao: resultado invalidado" >&2
        return 3
    fi
}

verificar_settings() {  # validador estrito sobre a configuracao instalada (e a local, se houver)
    local alvos=(.claude/settings.json)
    [ ! -e .claude/settings.local.json ] || alvos+=(.claude/settings.local.json)
    "${AMBIENTE[@]}" "$PY" -I -B scripts/validar_settings.py "${alvos[@]}" || return 4
}
