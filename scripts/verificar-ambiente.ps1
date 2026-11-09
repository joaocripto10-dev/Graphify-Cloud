# Verificações não destrutivas. Execute na raiz do projeto.
$ErrorActionPreference = 'Continue'
Write-Host "=== Ambiente Claude Code + Graphify ==="
Write-Host "Projeto: $(Get-Location)"
foreach ($cmd in @('git','uv','graphify','claude','python')) {
    $found = Get-Command $cmd -ErrorAction SilentlyContinue
    if ($found) { Write-Host "[OK] $cmd : $($found.Source)" }
    else { Write-Host "[AUSENTE/NÃO NO PATH] $cmd" }
}
$expected = @('CLAUDE.md','.claude/agents','.claude/skills','docs/CONTRATOS_DADOS.md')
foreach ($f in $expected) {
    if (Test-Path -LiteralPath $f) { Write-Host "[OK] $f" }
    else { Write-Host "[PENDENTE] $f" }
}
if (Get-Command git -ErrorAction SilentlyContinue) {
    git status --short 2>$null
}
Write-Host 'Nota: a extensão gráfica Claude Code do VS Code pode funcionar sem o executável claude no PATH.'
