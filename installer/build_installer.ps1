$ErrorActionPreference = "Stop"

try {
  $scriptRoot = $PSScriptRoot
  $projectRoot = Resolve-Path (Join-Path $scriptRoot "..")
  Set-Location $projectRoot

  $buildScript = Join-Path $projectRoot "build_windows.ps1"
  & $buildScript

  $appVersionFile = Join-Path $projectRoot "src\\rental_manager\\version.py"
  $versionMatch = Select-String -Path $appVersionFile -Pattern '__version__\s*=\s*"([^"]+)"' -AllMatches
  if (-not $versionMatch.Matches) {
    throw "Não foi possível extrair a versão em $appVersionFile."
  }
  $appVersion = $versionMatch.Matches[0].Groups[1].Value

  $distInstaller = Join-Path $projectRoot "dist_installer"
  if (-not (Test-Path $distInstaller)) {
    New-Item -ItemType Directory -Path $distInstaller | Out-Null
  }

  $innoCompiler = $env:INNO_SETUP_COMPILER
  if (-not $innoCompiler) {
    $innoCompiler = "C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe"
  }
  if (-not (Test-Path $innoCompiler)) {
    throw "ISCC.exe não encontrado. Instale o Inno Setup e verifique se o ISCC.exe está em '$innoCompiler' ou defina INNO_SETUP_COMPILER."
  }

  $issPath = Join-Path $scriptRoot "GestaoInteligente.iss"
  & $innoCompiler /DAppVersion=$appVersion $issPath
} catch {
  Write-Error $_
  Read-Host "Erro durante o build. Pressione Enter para sair"
  throw
}
