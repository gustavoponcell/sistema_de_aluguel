@echo off
setlocal

cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" (
  call ".venv\Scripts\activate.bat"
) else (
  echo Ambiente virtual nao encontrado em .venv.
  echo Para criar e instalar as dependencias:
  echo   python -m venv .venv
  echo   .venv\Scripts\activate
  echo   pip install -r requirements.txt
  pause
  exit /b 1
)

set "PYTHONPATH=%CD%\src"
python -m rental_manager.app

endlocal
