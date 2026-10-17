param([string]$RepositoryName = 'rrg-kiko')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
if ($RepositoryName -notmatch '^[a-zA-Z0-9_.-]+$') { throw 'Nombre de repositorio inválido.' }
& gh auth status
if ($LASTEXITCODE -ne 0) { throw 'Reconecta GitHub con: gh auth login --hostname github.com' }
$login = & gh api user --jq .login
if ($LASTEXITCODE -ne 0) { throw 'No se pudo obtener el usuario autenticado.' }
$origin = & git remote get-url origin 2>$null
if ($origin) { throw "Este repositorio ya tiene un remoto ($origin). Revísalo antes de publicar." }
$existing = & gh repo view "$login/$RepositoryName" --json name 2>$null
if ($LASTEXITCODE -eq 0) { throw 'Ya existe un repositorio con ese nombre; el script no lo modificará.' }
$files = & git ls-files
if ($files -match '(^|/)(ENCARGO_CODEX_RRG_KIKO.md|NAVEGABILIDAD_RRG.md|market.json|refresh-status.json|\.env)$') {
    throw 'Hay notas personales, datos o secretos potenciales en el índice. Revisar antes de publicar.'
}
& gh repo create $RepositoryName --public --source . --remote origin --push --description 'Explorador de rotación relativa de índices y sectores'
if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear/subir el repositorio.' }
& gh api --method POST "repos/$login/$RepositoryName/pages" -f build_type=workflow
if ($LASTEXITCODE -ne 0) { Write-Warning 'Configura Settings → Pages → GitHub Actions en el repositorio.' }
Write-Output "Código publicado: https://github.com/$login/$RepositoryName"
Write-Output 'El workflow prepara los datos y despliega el prototipo personal solicitado.'
Write-Output 'No se ha verificado una URL pública funcional por ejecutar este script.'
