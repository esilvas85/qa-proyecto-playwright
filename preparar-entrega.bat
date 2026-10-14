@echo off
setlocal
REM Solo empaqueta un resultado REAL y con evidencias PNG verificadas.
cd /d "%~dp0"
set "PYTHON=.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo ERROR: falta .venv. Revisa README.md.
  pause
  exit /b 2
)
"%PYTHON%" preparar_entrega.py %*
set "RESULTADO=%ERRORLEVEL%"
pause
exit /b %RESULTADO%
