"""Crea el ZIP final SOLO con código y evidencias reales que pasen auditoría.

No reutilizamos capturas de simulación ni generamos imágenes de ejemplo. Se toma
una ejecución realizada previamente en el HP Envy y se mantienen sus rutas
relativas para que reporte-pruebas.md muestre todas las imágenes al abrirlo.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from validar_entrega import print_validation, real_run_folder, validate_run

ROOT = Path(__file__).resolve().parent
SOURCE_FILES = (
    ".gitignore", "README.md", "GUIA-DE-CODIGO.md", "AUDITORIA-v1.8.md",
    "CAMBIOS-v1.8.md", "requirements.txt", "run.py", "qa_remates.py",
    "inspeccionar_portal.py", "diagnostico.py", "ejecutar-pruebas.bat",
    "ejecutar_windows.bat", "preparar-entrega.bat", "preparar_entrega.py",
    "validar_entrega.py", "tests/test_automatizacion.py",
    "tests/test_empaquetado.py",
)


def create_package(folder: Path, output: Path) -> Path:
    check = validate_run(folder)
    print_validation(check)
    if not check.ok:
        raise RuntimeError("No se prepara la entrega si faltan PNG o hay casos obligatorios sin PASS.")
    output.parent.mkdir(parents=True, exist_ok=True)
    prefix = "QA-Senior-Remates/"
    with ZipFile(output, "w", ZIP_DEFLATED, compresslevel=8) as archive:
        for filename in SOURCE_FILES:
            path = ROOT / filename
            if not path.is_file():
                raise FileNotFoundError(f"Archivo de la solución faltante: {filename}")
            archive.write(path, prefix + filename)
        for path in sorted((ROOT / "demo_site").glob("*")):
            if path.is_file():
                archive.write(path, prefix + path.relative_to(ROOT).as_posix())
        # El reporte conserva ./evidencias/... relativo a su propia carpeta.
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                relative = path.relative_to(folder).as_posix()
                if relative in ("resultado.json", "reporte-pruebas.md") or (
                    relative.startswith("evidencias/") and path.suffix.lower() == ".png"
                ):
                    archive.write(path, prefix + f"entrega_evidencias/{folder.name}/" + relative)
        note = (
            "Esta entrega fue empaquetada con evidencias de una ejecución REAL del portal.\n"
            f"Carpeta de ejecución utilizada: {folder.name}\n"
            f"Fecha de empaquetado: {datetime.now().astimezone().isoformat(timespec='seconds')}\n"
            f"PNG verificados: {check.captures}\n"
            "La revisión automatizada no sustituye la inspección visual de las capturas.\n"
        )
        archive.writestr(prefix + "entrega_evidencias/LEEME.txt", note)
    with ZipFile(output) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise RuntimeError(f"Archivo comprimido corrupto: {bad}")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Preparar entrega de prueba QA Senior")
    parser.add_argument("--carpeta", type=Path,
                        help="Carpeta _REAL a incorporar; por defecto, la más reciente")
    parser.add_argument("--destino", type=Path, help="Ruta del ZIP de salida")
    args = parser.parse_args()
    try:
        folder = real_run_folder(ROOT, args.carpeta)
        dest = args.destino or ROOT / "entregas" / f"QA-Senior-Remates-ENTREGA-{folder.name}.zip"
        output = create_package(folder, dest)
    except (FileNotFoundError, RuntimeError, OSError) as exc:
        print(f"NO SE PUDO CREAR EL ZIP: {exc}")
        return 1
    print(f"ZIP final validado: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
