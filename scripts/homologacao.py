"""Manifesto de homologacao do codigo executado pelas suites liberadas (FASE 4B.1, ADR-003).

O manifesto (scripts/homologacao.manifest) lista o SHA-256 de TODO arquivo sob scripts/, src/ e
tests/ (exceto __pycache__/) e do hook de governanca, que os testes executam. O executor
(scripts/testar.sh) so roda se o estado atual for identico ao manifesto: arquivo novo, alterado
ou removido, ou qualquer link simbolico/juncao, faz a execucao ser recusada. Homologar de novo
e uma acao separada (scripts/homologar.sh), que exige confirmacao do usuario.

Hash: fixtures (tests/fixtures/) e scripts de shell (*.sh) pelos bytes exatos; demais arquivos
com o CR de fim de linha removido, para o mesmo conteudo dar o mesmo hash com qualquer
core.autocrlf. Tambem entram no manifesto .claude/settings.json e .gitattributes.

Uso: python -I -B scripts/homologacao.py {verificar|gravar}
Saida: 0 = identico (ou gravado); 3 = ha diferencas; 2 = erro de uso, manifesto ou links.
Isto e controle de integridade, nao isolamento do sistema operacional.
"""
import hashlib
import os
import re
import sys

PASTAS = ('scripts', 'src', 'tests')
# Fora das pastas de codigo: o hook que os testes executam e as duas configuracoes que mudam
# o que roda (permissoes/hooks e conversao de fim de linha). Mudou, exige nova homologacao.
EXTRAS = ('.claude/hooks/guarda_agentes.py', '.claude/settings.json', '.gitattributes')
MANIFESTO = 'scripts/homologacao.manifest'
BYTES_EXATOS = 'tests/fixtures/'  # e todo *.sh: o bash trata CR como dado
CABECALHO = ('# homologacao.manifest v1 - gerado por scripts/homologar.sh; nao editar a mao\n'
             '# <sha256>  <caminho relativo>\n')
_RE_LINHA = re.compile(r'([0-9a-f]{64})  (\S(?:.*\S)?)')
_RE_CR_FIM_DE_LINHA = re.compile(rb'\r(?=\n|\Z)')


class ErroHomologacao(Exception):
    """Manifesto invalido, link no conjunto ou arquivo obrigatorio ausente."""


def raiz_padrao():
    return os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


def _eh_link(caminho):
    juncao = getattr(os.path, 'isjunction', None)
    if juncao is None:
        if os.name == 'nt':  # falha fechada: sem isjunction (Python < 3.12) nao ha como conferir
            raise ErroHomologacao('Python >= 3.12 e exigido no Windows para detectar juncoes')
        return os.path.islink(caminho)
    return os.path.islink(caminho) or juncao(caminho)


def _exigir_sem_link(raiz, rel):
    """Nenhum componente de `rel` (a partir da raiz) pode ser link ou juncao."""
    atual = raiz
    for parte in rel.split('/'):
        atual = os.path.join(atual, parte)
        if _eh_link(atual):
            raise ErroHomologacao(f'link simbolico ou juncao no conjunto: {rel}')


def arquivos_cobertos(raiz):
    """Caminhos relativos (com /) de todos os arquivos do conjunto, ordenados."""
    achados = []
    for pasta in PASTAS:
        base = os.path.join(raiz, pasta)
        _exigir_sem_link(raiz, pasta)
        if not os.path.isdir(base):
            raise ErroHomologacao(f'pasta ausente: {pasta}')
        for atual, dirs, nomes in os.walk(base):
            rel_dir = os.path.relpath(atual, raiz).replace(os.sep, '/')
            for nome in dirs + nomes:  # links sao recusados ANTES de qualquer filtro
                if _eh_link(os.path.join(atual, nome)):
                    raise ErroHomologacao(f'link simbolico ou juncao no conjunto: {rel_dir}/{nome}')
            dirs[:] = sorted(d for d in dirs if d != '__pycache__')
            achados += [f'{rel_dir}/{nome}' for nome in nomes]
    for extra in EXTRAS:
        _exigir_sem_link(raiz, extra)
        if not os.path.isfile(os.path.join(raiz, extra)):
            raise ErroHomologacao(f'arquivo obrigatorio ausente: {extra}')
        achados.append(extra)
    return sorted(a for a in set(achados) if a != MANIFESTO)


def hash_arquivo(raiz, rel):
    with open(os.path.join(raiz, *rel.split('/')), 'rb') as f:
        dados = f.read()
    if not (rel.startswith(BYTES_EXATOS) or rel.endswith('.sh')):
        dados = _RE_CR_FIM_DE_LINHA.sub(b'', dados)
    return hashlib.sha256(dados).hexdigest()


def estado(raiz):
    return {rel: hash_arquivo(raiz, rel) for rel in arquivos_cobertos(raiz)}


def ler_manifesto(raiz):
    caminho = os.path.join(raiz, *MANIFESTO.split('/'))
    _exigir_sem_link(raiz, MANIFESTO)
    if not os.path.isfile(caminho):
        raise ErroHomologacao(f'manifesto ausente: {MANIFESTO} (rode scripts/homologar.sh)')
    registrado = {}
    with open(caminho, encoding='utf-8', newline='') as f:
        for numero, linha in enumerate(f.read().splitlines(), start=1):
            if not linha or linha.startswith('#'):
                continue
            m = _RE_LINHA.fullmatch(linha)
            if m is None:
                raise ErroHomologacao(f'manifesto: linha {numero} malformada')
            if m.group(2) in registrado:
                raise ErroHomologacao(f'manifesto: caminho repetido na linha {numero}')
            registrado[m.group(2)] = m.group(1)
    if not registrado:
        raise ErroHomologacao('manifesto vazio')
    return registrado


def diferencas(raiz, registrado=None):
    """[(tipo, caminho)], tipo em novo / alterado / removido, em relacao ao manifesto."""
    registrado = ler_manifesto(raiz) if registrado is None else registrado
    atual = estado(raiz)
    difs = [('novo', r) for r in atual if r not in registrado]
    difs += [('alterado', r) for r in atual if r in registrado and registrado[r] != atual[r]]
    difs += [('removido', r) for r in registrado if r not in atual]
    return sorted(difs, key=lambda d: (d[1], d[0]))


def gravar(raiz):
    """Grava o manifesto do estado atual; devolve (total, diferencas sobre o anterior)."""
    try:
        anteriores = diferencas(raiz)
    except ErroHomologacao:
        anteriores = None  # sem manifesto anterior valido
    atual = estado(raiz)
    caminho = os.path.join(raiz, *MANIFESTO.split('/'))
    with open(caminho, 'w', encoding='utf-8', newline='\n') as f:
        f.write(CABECALHO)
        for rel in sorted(atual):
            f.write(f'{atual[rel]}  {rel}\n')
    return len(atual), anteriores


def main(argv):
    if len(argv) != 2 or argv[1] not in ('verificar', 'gravar'):
        print(__doc__, file=sys.stderr)
        return 2
    raiz = raiz_padrao()
    try:
        if argv[1] == 'gravar':
            total, anteriores = gravar(raiz)
            for tipo, rel in anteriores or []:
                print(f'{tipo}: {rel}')
            print(f'manifesto gravado: {total} arquivos homologados'
                  + ('' if anteriores is not None else ' (primeira homologacao)'))
            return 0
        difs = diferencas(raiz)
    except ErroHomologacao as e:
        print(f'ERRO de homologacao: {e}', file=sys.stderr)
        return 2
    if difs:
        for tipo, rel in difs:
            print(f'{tipo}: {rel}', file=sys.stderr)
        print(f'conjunto NAO homologado: {len(difs)} diferenca(s). Revise as mudancas e rode '
              '"bash scripts/homologar.sh" (exige confirmacao).', file=sys.stderr)
        return 3
    print(f'conjunto homologado integro: {len(ler_manifesto(raiz))} arquivos')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
