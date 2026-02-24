@echo off
setlocal EnableExtensions EnableDelayedExpansion

call :main > "%~dp0run_app.log" 2>&1
set "EXIT_CODE=%errorlevel%"
if not "%EXIT_CODE%"=="0" (
  echo [ERRO] A execucao falhou. Consulte o log em "%~dp0run_app.log".
  echo [ERRO] A execucao falhou. Consulte o log em "%~dp0run_app.log".>>"%~dp0run_app.log"
  pause
)
exit /b %EXIT_CODE%

:main
REM ==============================
REM RentalManager launcher (Windows)
REM - Vai para a pasta do projeto
REM - Cria/ativa venv automaticamente
REM - Instala requirements quando mudarem
REM - Roda o app
REM ==============================

echo [ETAPA] Indo para a raiz do projeto...
cd /d "%~dp0"

REM Caminhos (reais) baseados na pasta do projeto
set "PROJ_DIR=%~dp0"
set "VENV_DIR=%PROJ_DIR%.venv"
set "REQ_FILE=%PROJ_DIR%requirements.txt"
set "SRC_DIR=%PROJ_DIR%src"
set "PKG_DIR=%SRC_DIR%\rental_manager"
set "INIT_FILE=%PKG_DIR%\__init__.py"
set "APP_FILE=%PKG_DIR%\app.py"
set "HASH_FILE=%VENV_DIR%\requirements.sha256"

echo [ETAPA] Validando arquivos e pastas obrigatorios...
if not exist "%REQ_FILE%" (
  echo [ERRO] requirements.txt nao encontrado em:
  echo   %REQ_FILE%
  exit /b 1
)

if not exist "%SRC_DIR%" (
  echo [ERRO] Pasta src nao encontrada em:
  echo   %SRC_DIR%
  exit /b 1
)

if not exist "%PKG_DIR%" (
  echo [ERRO] Pasta src\rental_manager nao encontrada em:
  echo   %PKG_DIR%
  exit /b 1
)

if not exist "%INIT_FILE%" (
  echo [AVISO] __init__.py nao encontrado. Criando arquivo vazio em:
  echo   %INIT_FILE%
  type NUL > "%INIT_FILE%"
)

if not exist "%INIT_FILE%" (
  echo [ERRO] Falha ao criar %INIT_FILE%.
  exit /b 1
)

if not exist "%APP_FILE%" (
  echo [ERRO] app.py nao encontrado em:
  echo   %APP_FILE%
  exit /b 1
)

echo [ETAPA] Verificando Python no PATH...
where python >nul 2>&1
if errorlevel 1 (
  echo [ERRO] Python nao encontrado no PATH.
  echo Instale o Python e marque "Add Python to PATH".
  exit /b 1
)

echo [ETAPA] Criando ambiente virtual (se necessario)...
if not exist "%VENV_DIR%\Scripts\python.exe" (
  python -m venv "%VENV_DIR%"
  if errorlevel 1 (
    echo [ERRO] Falha ao criar o ambiente virtual.
    exit /b 1
  )
)

echo [ETAPA] Ativando ambiente virtual...
call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
  echo [ERRO] Falha ao ativar o ambiente virtual.
  exit /b 1
)

echo [ETAPA] Diagnosticos do ambiente...
set "PYTHONPATH=%SRC_DIR%"
python --version
where python
pip --version
python -c "import sys; print(sys.path)"
python -c "import os; print(os.getcwd())"
python -c "import rental_manager; print('OK import rental_manager', rental_manager.__file__)"

echo [ETAPA] Verificando dependencias (requirements.txt)...
set "REQ_HASH="
for /f "usebackq delims=" %%H in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-FileHash -Algorithm SHA256 '%REQ_FILE%').Hash"`) do set "REQ_HASH=%%H"

if "%REQ_HASH%"=="" (
  echo [ERRO] Nao foi possivel calcular o hash do requirements.txt.
  exit /b 1
)

set "OLD_HASH="
if exist "%HASH_FILE%" set /p OLD_HASH=<"%HASH_FILE%"

if /I "%REQ_HASH%"=="%OLD_HASH%" goto :run
goto :install

:install
echo [INFO] Entrando em :install
python -m pip install --upgrade pip
if errorlevel 1 (
  echo [AVISO] Nao foi possivel atualizar o pip. Continuando...
)
pip install -r "%REQ_FILE%"
if errorlevel 1 (
  echo [ERRO] Falha ao instalar dependencias.
  echo Verifique sua internet ou permissao de instalacao.
  exit /b 1
)
echo %REQ_HASH%>"%HASH_FILE%"
goto :run

:run
python -m rental_manager.app
if errorlevel 1 (
  echo [ERRO] App falhou. Veja run_app.log
  pause
  exit /b 1
)
exit /b 0
