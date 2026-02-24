# Instalador (Inno Setup) — Gestão Inteligente

## Pré-requisitos
- Windows 10/11.
- Inno Setup 6 instalado (ISCC.exe).
- Python e dependências já configurados para o build do PyInstaller.

## Como gerar o instalador
1. Abra o PowerShell.
2. Execute:
   ```powershell
   .\installer\build_installer.ps1
   ```

O instalador gerado ficará em `dist_installer\` com o nome:
`GestaoInteligente-Setup-<versao>.exe`.

## Observações
- O instalador **não remove** dados em `%APPDATA%\RentalManager\`.
- O ícone usado é `assets/app.ico`.
- A versão é lida automaticamente de `src/rental_manager/version.py`.
