r"""Este es el archivo que debes ejecutar para iniciar la automatización.

Ejemplo: .\.venv\Scripts\python.exe run.py --nombre "Nombre Apellido"
La ejecución real y la demostración local usan el mismo flujo, pero sus resultados
quedan separados para no confundir una simulación con evidencia del portal.
"""
import argparse
import sys
import threading
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from qa_remates import URL, execute

# Tomamos la ubicación del archivo, no la carpeta actual de PowerShell.
# Así el proyecto funciona aunque lo ejecuten desde otro directorio.
HERE = Path(__file__).resolve().parent


class DemoHandler(SimpleHTTPRequestHandler):
    """Servidor sencillo para ensayar los escenarios sin depender de Internet."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(HERE / 'demo_site'), **kwargs)

    def log_message(self, format, *args):
        # No llenamos la consola con cada petición de imágenes, CSS, etc.
        pass


def main():
    # Todos los parámetros son opcionales: una ejecución sin --demo prueba
    # el sitio real y también incluye el control adicional de Hyundai.
    parser = argparse.ArgumentParser(description='Automatización QA Senior Próximos Remates')
    parser.add_argument('--nombre', default='Candidato QA Senior')
    parser.add_argument('--demo', action='store_true', help='Usar sitio simulado local; NO valida producción')
    parser.add_argument('--demo-con-resultados', action='store_true', help='En demo, crear 2 resultados en ejercicio 1')
    parser.add_argument('--solo-oficial', action='store_true', help='Ejecuta solo los ejercicios obligatorios, sin control adicional Hyundai')
    parser.add_argument('--headless', action='store_true', help='Ejecutar sin mostrar el navegador')
    parser.add_argument('--slowmo', type=int, default=100, help='Retardo entre acciones, ms')
    parser.add_argument('--url', help='URL del portal (por defecto: proximosremates.cl)')
    parser.add_argument('--output', type=Path, help='Destino de evidencias e informe')
    opts = parser.parse_args()
    # Estos chequeos evitan que alguien presente por error una DEMO como REAL.
    if opts.demo and opts.url:
        parser.error('No combinar --demo con --url')
    if opts.demo_con_resultados and not opts.demo:
        parser.error('--demo-con-resultados requiere --demo')
    suffix = 'DEMO' if opts.demo else 'REAL'
    output = opts.output or (HERE / 'salidas' / f'{datetime.now():%Y%m%d_%H%M%S}_{suffix}')
    server = None
    if opts.demo:
        # Levantamos un sitio de ejemplo en el equipo. No es proximosremates.cl.
        # El sistema elige un puerto libre y lo cerramos al terminar.
        server = ThreadingHTTPServer(('127.0.0.1', 0), DemoHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f'http://127.0.0.1:{server.server_port}/index.html'
        if opts.demo_con_resultados:
            url += '?demo_resultados=1'
    else:
        url = opts.url or URL
    print(f'Iniciando {suffix} | URL: {url}\nResultados: {output}', flush=True)
    try:
        result = execute(output, opts.nombre, url, opts.demo, opts.headless, opts.slowmo, include_hyundai=not opts.solo_oficial)
    except Exception as exc:
        print(f'ERROR al iniciar la ejecución: {exc}', file=sys.stderr)
        return 2
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
    # El caso extra Hyundai se informa, pero no determina la aprobación
    # de los dos ejercicios que realmente pide la empresa.
    for case in result.cases:
        print(f'{case.name}: {case.status}')
    print(f'Reporte: {output / "reporte-pruebas.md"}')
    return 0 if all(c.status == 'PASS' for c in result.cases if c.required) else 1


if __name__ == '__main__':
    sys.exit(main())
