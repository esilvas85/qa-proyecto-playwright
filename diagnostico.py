"""Comprobación rápida del equipo antes de probar el portal real.

Solo abre y cierra Chromium. No navega a Próximos Remates ni registra PASS.
"""
import os
import platform
import sys
from pathlib import Path

# Así podemos detectar problemas de instalación antes de culpar a un selector.
print('SO:', platform.platform())
print('Python:', sys.version.split()[0], '|', sys.executable)
print('Directorio:', Path.cwd())
try:
    import playwright
    from playwright.sync_api import sync_playwright
    print('Playwright: importación OK')
    with sync_playwright() as p:
        # En el HP Envy usaremos el navegador que descargó Playwright.
        # La variable de entorno es únicamente para otros laboratorios.
        options = {'headless': True}
        if os.environ.get('PLAYWRIGHT_CHROMIUM_PATH'):
            options['executable_path'] = os.environ['PLAYWRIGHT_CHROMIUM_PATH']
        browser = p.chromium.launch(**options)
        print('Chromium: OK | versión', browser.version)
        browser.close()
except Exception as exc:
    print('ERROR entorno Playwright/Chromium:', exc)
    sys.exit(1)
