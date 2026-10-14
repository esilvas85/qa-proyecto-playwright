@echo off
setlocal
REM Inicia los escenarios del portal real sin abrir ChatGPT ni usar una API de IA.
REM Trabajamos desde la carpeta donde esta este archivo para evitar errores de rutas.
cd /d "%~dp0"
set "PYTHON=.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo ERROR: falta .venv. Sigue las instrucciones de README.md.
  pause
  exit /b 2
)
REM El resultado adicional Hyundai se ejecuta y documenta, pero no determina
REM el codigo de salida de los dos ejercicios obligatorios.
"%PYTHON%" run.py --nombre "Emilio Silva" %*
set "RESULTADO=%ERRORLEVEL%"
echo.
if "%RESULTADO%"=="0" (
  echo Ejercicios obligatorios: ejecucion finalizada con PASS.
) else (
  echo ATENCION: hubo un caso obligatorio no aprobado o un error tecnico.
)
echo Consulta reporte-pruebas.md y resultado.json en la ultima carpeta salidas.
pause
exit /b %RESULTADO%
