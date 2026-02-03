$ErrorActionPreference = "Stop"

$projectRoot = $PSScriptRoot
Set-Location $projectRoot

$iconPath = Join-Path $projectRoot "assets\\icon.ico"
$versionFile = Join-Path $projectRoot "tools\\windows_version_info.txt"
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

pyinstaller `
  --noconsole `
  --name RentalManager `
  --icon assets/icon.ico `
  --version-file tools/windows_version_info.txt `
  --add-data "assets;assets" `
  --paths "src" `
  --clean `
  --noconfirm `
  $entrypoint
