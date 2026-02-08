$ErrorActionPreference = "Stop"

$projectRoot = $PSScriptRoot
Set-Location $projectRoot

$python = Join-Path $PSScriptRoot ".venv\\Scripts\\python.exe"
if (-not (Test-Path $python)) {
  & python -m venv .venv
}
if (-not (Test-Path $python)) {
  throw "Python do venv não encontrado em $python. Verifique a criação da virtualenv."
}

& $python -m pip install -r requirements.txt

$iconPath = Join-Path $projectRoot "assets\\app.ico"
$versionFile = Join-Path $projectRoot "tools\\windows_version_info.txt"
$appVersionFile = Join-Path $projectRoot "src\\rental_manager\\version.py"
$entrypoint = Join-Path $projectRoot "src\\rental_manager\\__main__.py"
if (-not (Test-Path $iconPath)) {
  $iconDir = Split-Path $iconPath -Parent
  if (-not (Test-Path $iconDir)) {
    New-Item -ItemType Directory -Path $iconDir | Out-Null
  }
  $iconBase64 = "AAABAAEAAQEAAAEAIABGAAAAFgAAAIlQTkcNChoKAAAADUlIRFIAAAABAAAAAQgGAAAAHxXEiQAAAA1JREFUCJljYGBg+A8AAQQBAHmeZPUAAAAASUVORK5CYII="
  [IO.File]::WriteAllBytes($iconPath, [Convert]::FromBase64String($iconBase64))
}
if (-not (Test-Path $versionFile)) {
  throw "Arquivo de versão não encontrado em $versionFile. Verifique tools\\windows_version_info.txt."
}
if (-not (Test-Path $appVersionFile)) {
  throw "Arquivo de versão não encontrado em $appVersionFile."
}

$versionMatch = Select-String -Path $appVersionFile -Pattern '__version__\s*=\s*"([^"]+)"' -AllMatches
if (-not $versionMatch.Matches) {
  throw "Não foi possível extrair a versão em $appVersionFile."
}
$appVersion = $versionMatch.Matches[0].Groups[1].Value
$versionParts = $appVersion.Split(".")
if ($versionParts.Count -lt 3) {
  throw "Versão inválida em $appVersionFile. Use o formato X.Y.Z."
}
$fileVersion = "$($versionParts[0]), $($versionParts[1]), $($versionParts[2]), 0"
$versionInfo = Get-Content $versionFile -Raw
$versionInfo = $versionInfo -replace "filevers=\([^\)]*\)", "filevers=($fileVersion)"
$versionInfo = $versionInfo -replace "prodvers=\([^\)]*\)", "prodvers=($fileVersion)"
$versionInfo = $versionInfo -replace "StringStruct\('FileVersion', '[^']*'\)", "StringStruct('FileVersion', '$appVersion')"
$versionInfo = $versionInfo -replace "StringStruct\('ProductVersion', '[^']*'\)", "StringStruct('ProductVersion', '$appVersion')"
$versionInfo = $versionInfo -replace "StringStruct\('ProductName', '[^']*'\)", "StringStruct('ProductName', 'Gestão Inteligente')"
$versionInfo = $versionInfo -replace "StringStruct\('FileDescription', '[^']*'\)", "StringStruct('FileDescription', 'Gestão Inteligente')"
$versionInfo = $versionInfo -replace "StringStruct\('CompanyName', '[^']*'\)", "StringStruct('CompanyName', 'Gestão Inteligente')"
$versionInfo = $versionInfo -replace "StringStruct\('InternalName', '[^']*'\)", "StringStruct('InternalName', 'GestaoInteligente')"
$versionInfo = $versionInfo -replace "StringStruct\('OriginalFilename', '[^']*'\)", "StringStruct('OriginalFilename', 'GestaoInteligente.exe')"
Set-Content -Path $versionFile -Value $versionInfo -Encoding UTF8

& $python -m PyInstaller `
  --noconsole `
  --name GestaoInteligente `
  --icon assets/app.ico `
  --version-file tools/windows_version_info.txt `
  --add-data "assets;assets" `
  --paths "src" `
  --clean `
  --noconfirm `
  $entrypoint

$builtExe = Join-Path $projectRoot "dist\\GestaoInteligente\\GestaoInteligente.exe"
if (-not (Test-Path $builtExe)) {
  throw "Build concluído, mas o executável não foi encontrado em $builtExe."
}
