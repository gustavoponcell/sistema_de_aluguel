@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ==============================
REM RentalManager launcher (Windows)
REM - Vai para a pasta do projeto
REM - Cria/ativa venv automaticamente
REM - Instala requirements quando mudarem
REM - Roda o app
REM ==============================

REM 1) Ir para a pasta onde este .bat está (raiz do projeto)
cd /d "%~dp0"

REM 2) Caminhos (reais) baseados na pasta do projeto
set "PROJ_DIR=%CD%"
set "VENV_DIR=%PROJ_DIR%\.venv"
set "REQ_FILE=%PROJ_DIR%\requirements.txt"
set "SRC_DIR=%PROJ_DIR%\src"
set "HASH_FILE=%VENV_DIR%\requirements.sha256"

REM 3) Checagens
if not exist "%REQ_FILE%" (
  echo [ERRO] requirements.txt nao encontrado em:
  echo   %REQ_FILE%
  pause
  exit /b 1
)

if not exist "%SRC_DIR%" (
  echo [ERRO] Pasta src nao encontrada em:
  echo   %SRC_DIR%
  pause
  exit /b 1
)

REM 4) Garantir que python existe
where python >nul 2>&1
if errorlevel 1 (
  echo [ERRO] Python nao encontrado no PATH.
  echo Instale o Python e marque "Add Python to PATH".
  pause
  exit /b 1
)

REM 5) Criar venv se nao existir
if not exist "%VENV_DIR%\Scripts\python.exe" (
  echo [INFO] Criando ambiente virtual em "%VENV_DIR%"...
  python -m venv "%VENV_DIR%"
  if errorlevel 1 (
    echo [ERRO] Falha ao criar o ambiente virtual.
    pause
    exit /b 1
  )
)

REM 6) Ativar venv
call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
  echo [ERRO] Falha ao ativar o ambiente virtual.
  pause
  exit /b 1
)

REM 7) Calcular hash do requirements.txt (para instalar deps apenas quando mudar)
set "REQ_HASH="
for /f "usebackq delims=" %%H in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-FileHash -Algorithm SHA256 '%REQ_FILE%').Hash"`) do set "REQ_HASH=%%H"

if "%REQ_HASH%"=="" (
  echo [ERRO] Nao foi possivel calcular o hash do requirements.txt.
  pause
  exit /b 1
)

set "OLD_HASH="
if exist "%HASH_FILE%" (
  set /p OLD_HASH=<"%HASH_FILE%"
)

if /I not "%REQ_HASH%"=="%OLD_HASH%" (
  echo [INFO] Instalando/atualizando dependencias (requirements mudou ou primeira execucao)...
  python -m pip install --upgrade pip
  if errorlevel 1 (
    echo [AVISO] Nao foi possivel atualizar o pip. Continuando...
  )

  pip install -r "%REQ_FILE%"
  if errorlevel 1 (
    echo [ERRO] Falha ao instalar dependencias.
    echo Verifique sua internet ou permissao de instalacao.
    pause
    exit /b 1
  )

  echo %REQ_HASH%>"%HASH_FILE%"
) else (
  echo [INFO] Dependencias OK (requirements.txt nao mudou).
)

REM 8) Rodar app (layout src)
set "PYTHONPATH=%SRC_DIR%"
python -m rental_manager.app

endlocal

