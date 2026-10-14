"""Tests del validador y el empaquetado (sin acceder al portal)."""
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from zipfile import ZipFile

from preparar_entrega import create_package
from validar_entrega import valid_png, validate_run


def chunk(kind, payload):
    return (struct.pack('>I', len(payload)) + kind + payload +
            struct.pack('>I', zlib.crc32(kind + payload) & 0xffffffff))


def tiny_png():
    ihdr = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
    pixels = zlib.compress(b'\x00\x20\x30\x40')
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', pixels) + chunk(b'IEND', b'')


class AuditTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name) / '20261014_174424_REAL'
        self.folder.mkdir()
        self.cases = [
            {'name': 'Caso 1 - Búsqueda y filtrado (hundai)', 'status': 'PASS', 'required': True,
             'steps': [
                 {'name':'Busqueda hundai ingresada', 'evidence':'evidencias/caso-1/01.png', 'detail':'Valor exacto: `hundai`.'},
                 {'name':'Busqueda ejecutada', 'evidence':'evidencias/caso-1/02.png', 'detail':'descripcion=hundai'}
             ]},
            {'name': 'Caso 1B - Control positivo Hyundai (adicional)', 'status': 'INCONCLUSO', 'required': False,
             'steps': [{'name':'Estado de resultados', 'evidence':'evidencias/caso-1b/01.png', 'detail':'2 lotes sin abrir'}]},
            {'name': 'Caso 2 - Casas de remates y desplazamiento', 'status': 'PASS', 'required': True,
             'notes': ['Primera casa con lotes: Remates Reyco. Aún no se identificó una tarjeta clicable'],
             'steps': [
                 {'name':'Ubicados en Remates CDR', 'evidence':'evidencias/caso-2/01.png', 'detail':'https://www.rematescdr.cl/'},
                 {'name':'Scroll progresivo 1', 'evidence':'evidencias/caso-2/02.png', 'detail':'648px'},
                 {'name':'Final de pagina Remates CDR', 'evidence':'evidencias/caso-2/03.png', 'detail':'¿Llegó al pie? True'},
             ]}
        ]
        self.save()

    def save(self):
        data = {'demo': False, 'started_at': '2026-10-14T17:44:24-03:00',
                'browser_version': '156.0.8078.4', 'cases': self.cases}
        (self.folder / 'resultado.json').write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        lines=['# Informe de automatización', 'Modo: SITIO REAL']
        for case in self.cases:
            lines += [f"## {case['name']}", f"**Estado:** {case['status']}"]
            for step in case['steps']:
                evidence = step['evidence']
                path = self.folder / evidence
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(tiny_png())
                lines.append(f"![{step['name']}](./{evidence})")
        (self.folder / 'reporte-pruebas.md').write_text('\n'.join(lines), encoding='utf-8')

    def test_validacion_correcta(self):
        info = validate_run(self.folder)
        self.assertTrue(info.ok, info.errors)
        self.assertEqual(info.captures, 6)

    def test_zip_incluye_evidencias_verdaderas(self):
        result = create_package(self.folder, Path(self.tmp.name) / 'entrega.zip')
        with ZipFile(result) as archive:
            files = archive.namelist()
            self.assertTrue(any('entrega_evidencias/20261014_174424_REAL/evidencias/caso-2/03.png' in p for p in files))
            self.assertTrue(any(p.endswith('qa_remates.py') for p in files))
            self.assertIsNone(archive.testzip())

    def test_falta_png_detiene_entrega(self):
        (self.folder / 'evidencias/caso-2/03.png').unlink()
        info = validate_run(self.folder)
        self.assertFalse(info.ok)
        self.assertTrue(any('PNG faltante' in s for s in info.errors))

    def test_caso_obligatorio_en_error_detiene_entrega(self):
        self.cases[0]['status'] = 'ERROR'
        self.save()
        info = validate_run(self.folder)
        self.assertFalse(info.ok)
        self.assertTrue(any('obligatorio' in s for s in info.errors))

    def test_integridad_png(self):
        path = self.folder / 'evidencias/caso-2/03.png'
        self.assertTrue(valid_png(path))
        path.write_bytes(tiny_png()[:35])
        self.assertFalse(valid_png(path))

    def test_modo_demo_no_es_entrega(self):
        data = json.loads((self.folder / 'resultado.json').read_text(encoding='utf-8'))
        data['demo'] = True
        (self.folder / 'resultado.json').write_text(json.dumps(data), encoding='utf-8')
        self.assertFalse(validate_run(self.folder).ok)


if __name__ == '__main__':
    unittest.main()
