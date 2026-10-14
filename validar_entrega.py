"""Revisa una ejecución REAL antes de publicarla o entregarla.

Los JSON y Markdown son solo el índice: para entregar hay que disponer de
cada imagen citada en ellos. Este validador NO inventa capturas ni cambia
resultados; si falta algo, detiene la preparación del paquete.

Ejemplo (desde la raíz del proyecto):
  .\\.venv\\Scripts\\python.exe validar_entrega.py --carpeta salidas\\20261014_174424_REAL
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
IMAGE_RE = re.compile(r'!\[[^\]]*\]\(([^)]+\.png)\)', re.IGNORECASE)


@dataclass
class Validation:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    captures: int = 0
    name: str = ""

    @property
    def ok(self) -> bool:
        return not self.errors


def real_run_folder(project: Path, selected: Path | None = None) -> Path:
    """Elige una corrida REAL; las carpetas DEMO no son evidencia evaluable."""
    if selected is not None:
        folder = selected if selected.is_absolute() else (project / selected)
        return folder.resolve()
    options = sorted((project / "salidas").glob("*_REAL"), reverse=True)
    if not options:
        raise FileNotFoundError("No se encontraron ejecuciones *_REAL en salidas/.")
    return options[0].resolve()


def valid_png(path: Path) -> bool:
    """Lee los bloques PNG y sus CRC: detecta capturas incompletas o corruptas."""
    try:
        if path.stat().st_size > 40 * 1024 * 1024:
            return False
        with path.open("rb") as stream:
            if stream.read(8) != PNG_SIGNATURE:
                return False
            saw_ihdr = False
            saw_idat = False
            while True:
                header = stream.read(8)
                if len(header) != 8:
                    return False
                length, kind = struct.unpack(">I4s", header)
                if length > 40 * 1024 * 1024:
                    return False
                payload = stream.read(length)
                crc = stream.read(4)
                if len(payload) != length or len(crc) != 4:
                    return False
                if (zlib.crc32(kind + payload) & 0xffffffff) != struct.unpack(">I", crc)[0]:
                    return False
                if kind == b"IHDR":
                    if saw_ihdr or length != 13:
                        return False
                    width, height = struct.unpack(">II", payload[:8])
                    if width <= 0 or height <= 0:
                        return False
                    saw_ihdr = True
                elif kind == b"IDAT":
                    saw_idat = True
                elif kind == b"IEND":
                    return saw_ihdr and saw_idat and length == 0 and stream.read(1) == b""
    except (OSError, struct.error):
        return False


def relative_file(folder: Path, value: str) -> Path | None:
    """Evita rutas absolutas y ../ fuera de la carpeta de evidencias."""
    if not value or re.match(r"^[a-zA-Z]:", value):
        return None
    base = folder.resolve()
    target = (base / value.removeprefix("./").replace("\\", "/")).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        return None
    return target


def validate_run(folder: Path) -> Validation:
    result = Validation()
    folder = folder.resolve()
    result.name = folder.name
    if not folder.is_dir() or not folder.name.endswith("_REAL"):
        result.errors.append("La carpeta elegida debe existir y terminar en _REAL.")
        return result
    js = folder / "resultado.json"
    md = folder / "reporte-pruebas.md"
    if not js.is_file() or not md.is_file():
        result.errors.append("Falta resultado.json o reporte-pruebas.md.")
        return result
    try:
        data = json.loads(js.read_text(encoding="utf-8-sig"))
        report = md.read_text(encoding="utf-8-sig")
    except (UnicodeError, json.JSONDecodeError, OSError) as exc:
        result.errors.append(f"No se pudo leer el informe: {exc}")
        return result
    if data.get("demo") is not False or "SITIO REAL" not in report:
        result.errors.append("La ejecución no está identificada como SITIO REAL.")
    if not data.get("started_at") or not data.get("browser_version"):
        result.errors.append("Falta fecha de inicio o versión del navegador.")
    cases = data.get("cases", [])
    if not isinstance(cases, list) or not cases:
        result.errors.append("No se encontraron casos en resultado.json.")
        return result
    compulsory = [c for c in cases if c.get("required") is True]
    if len(compulsory) != 2:
        result.errors.append(f"Se esperaban 2 casos obligatorios; encontrados: {len(compulsory)}.")
    for case in compulsory:
        if case.get("status") != "PASS":
            result.errors.append(f"El caso obligatorio '{case.get('name')}' no es PASS.")
    bonus = next((c for c in cases if c.get("required") is False and "Hyundai" in c.get("name", "")), None)
    if bonus:
        result.notes.append(f"Hyundai adicional: {bonus.get('status')} (no altera el resultado oficial).")
    visited_png: set[str] = set()
    for case in cases:
        name = str(case.get("name", "sin nombre"))
        if f"## {name}" not in report:
            result.errors.append(f"El caso '{name}' no aparece en el Markdown.")
        if f"**Estado:** {case.get('status')}" not in report:
            result.errors.append(f"No consta el estado de '{name}' en el Markdown.")
        for step in case.get("steps", []):
            filename = step.get("evidence", "")
            if not filename:
                result.errors.append(f"Falta captura en '{name}' / {step.get('name')}.")
                continue
            target = relative_file(folder, filename)
            if target is None or target.suffix.lower() != ".png":
                result.errors.append(f"Ruta de captura inválida: {filename}")
                continue
            if not valid_png(target):
                result.errors.append(f"PNG faltante o no válido: {filename}")
            else:
                result.captures += 1
            if f"(./{filename.replace('\\', '/')})" not in report:
                result.errors.append(f"La captura no está enlazada en Markdown: {filename}")
            visited_png.add(filename.replace("\\", "/"))
    md_pngs = IMAGE_RE.findall(report)
    for ref in md_pngs:
        path = ref.removeprefix("./")
        if path not in visited_png:
            result.errors.append(f"Markdown referencia un PNG no registrado en JSON: {path}")
        target = relative_file(folder, path)
        if target is None or not valid_png(target):
            result.errors.append(f"Enlace del Markdown a PNG ausente o inválido: {path}")
    if len(md_pngs) != len(visited_png):
        result.errors.append("El número de imágenes del Markdown y del JSON no coincide.")
    first = next((c for c in cases if c.get("name", "").startswith("Caso 1 -")), None)
    if first:
        texts = " ".join(s.get("detail", "") for s in first.get("steps", []))
        if "descripcion=hundai" not in texts or "Valor exacto: `hundai`" not in texts:
            result.errors.append("No está trazada la búsqueda literal 'hundai'.")
    second = next((c for c in cases if c.get("name", "").startswith("Caso 2 -")), None)
    if second:
        steps = second.get("steps", [])
        if not any("Ubicados en Remates CDR" in s.get("name", "") and
                   "cdr" in s.get("detail", "").lower() for s in steps):
            result.errors.append("Falta la navegación final identificada como Remates CDR.")
        if not any("Final de pagina Remates CDR" in s.get("name", "") and
                   "True" in s.get("detail", "") for s in steps):
            result.errors.append("Falta comprobación del pie de página en CDR.")
        if not any("Scroll progresivo" in s.get("name", "") for s in steps):
            result.errors.append("Falta evidencia del desplazamiento progresivo.")
        if any("sin identificó" in s for s in second.get("notes", [])):
            result.warnings.append("Revisar observaciones del ejercicio 2.")
        if any("Aún no se identificó una tarjeta clicable" in s for s in second.get("notes", [])):
            result.warnings.append("Hay lotes confirmados por contador, pero no se abrió el detalle de un producto.")
    result.notes.append("Este control comprueba archivos, estados y trazabilidad; no reemplaza la revisión visual humana.")
    return result


def print_validation(report: Validation) -> None:
    print(f"Validando: {report.name}")
    for text in report.notes:
        print(f"  NOTA: {text}")
    for text in report.warnings:
        print(f"  ADVERTENCIA: {text}")
    for text in report.errors:
        print(f"  ERROR: {text}")
    print(f"Capturas PNG válidas: {report.captures}")
    print("Resultado:", "VALIDADO PARA EMPAQUETAR" if report.ok else "ENTREGA DETENIDA")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validar reporte y evidencias reales")
    parser.add_argument("--carpeta", type=Path, help="Carpeta de la ejecución _REAL a auditar")
    args = parser.parse_args()
    try:
        folder = real_run_folder(Path(__file__).resolve().parent, args.carpeta)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        return 2
    result = validate_run(folder)
    print_validation(result)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
