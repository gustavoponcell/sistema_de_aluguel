$ErrorActionPreference = "Stop"

$projectRoot = $PSScriptRoot
Set-Location $projectRoot

$iconPath = Join-Path $projectRoot "assets\\icon.ico"
if (-not (Test-Path $iconPath)) {
  $iconDir = Split-Path $iconPath -Parent
  if (-not (Test-Path $iconDir)) {
    New-Item -ItemType Directory -Path $iconDir | Out-Null
  }
  $iconBase64 = "AAABAAEAAQEAAAEAIABGAAAAFgAAAIlQTkcNChoKAAAADUlIRFIAAAABAAAAAQgGAAAAHxXEiQAAAA1JREFUCJljYGBg+A8AAQQBAHmeZPUAAAAASUVORK5CYII="
  [IO.File]::WriteAllBytes($iconPath, [Convert]::FromBase64String($iconBase64))
}

pyinstaller `
  --noconsole `
  --name RentalManager `
  --icon assets/icon.ico `
  --add-data "assets;assets" `
  --paths "src" `
  --clean `
  --noconfirm `
  src/rental_manager/app.py
