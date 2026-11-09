# Executar na raiz do projeto; requer uv instalado e PowerShell interativo.
param([switch]$Reinstalar)
$ErrorActionPreference = 'Stop'
$projeto = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $projeto
try {
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        throw 'uv não encontrado. Instale uv (winget install --id astral-sh.uv -e), reinicie o terminal e repita.'
    }
    Write-Host "Projeto: $projeto"
    Write-Host 'Este processo instala/atualiza uma ferramenta em seu perfil e registra a skill Graphify no projeto.'
    Write-Host 'Ele poderá criar/alterar arquivos em .claude/ e configurações de hooks; revise o diff antes do commit.'
    if (Test-Path '.env') { Write-Warning 'Existe .env. Revise os arquivos a indexar e não envie segredos a backend externo.' }
    $confirm = Read-Host 'Digite INSTALAR para continuar; qualquer outra resposta cancela'
    if ($confirm -cne 'INSTALAR') { Write-Host 'Cancelado pelo usuário.'; exit 0 }
    $exists = [bool](Get-Command graphify -ErrorAction SilentlyContinue)
    if (-not $exists -or $Reinstalar) {
        $uvArgs = @('tool','install')
        if ($Reinstalar) { $uvArgs += '--reinstall' }
        $uvArgs += 'graphifyy[office,pdf,sql,postgres]'
        & uv @uvArgs
        if ($LASTEXITCODE -ne 0) { throw "Falha no uv (código $LASTEXITCODE)." }
    } else {
        Write-Host '[INFO] Graphify já está instalado. Não alterei dependências. Para reinstalar extras, execute com -Reinstalar.'
    }
    if (-not (Get-Command graphify -ErrorAction SilentlyContinue)) {
        Write-Warning 'Graphify pode não estar no PATH. Execute uv tool update-shell, reinicie PowerShell e tente novamente.'
        exit 1
    }
    # Comando oficial (docs.graphify.com): copia a skill para .claude/skills/graphify/,
    # grava a seção graphify no CLAUDE.md e registra hooks em .claude/settings.json.
    & graphify install --project --platform claude
    if ($LASTEXITCODE -ne 0) { throw 'A integração oficial do Graphify não concluiu. Confira a ajuda: graphify --help' }
    Write-Host 'Integração solicitada. Reinicie o Claude Code se a skill não aparecer; execute /graphify . após revisar privacidade.'
    if (Get-Command git -ErrorAction SilentlyContinue) { & git status --short }
} finally {
    Pop-Location
}
