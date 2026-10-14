@echo off
REM Se conserva este nombre para usuarios de versiones anteriores.
REM La implementacion principal esta en ejecutar-pruebas.bat.
call "%~dp0ejecutar-pruebas.bat" %*
exit /b %ERRORLEVEL%
