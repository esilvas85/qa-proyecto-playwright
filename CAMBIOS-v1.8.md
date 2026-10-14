# Versión 1.8 — Preparación de entrega (sin cambios funcionales)

Se conserva **íntegro** el comportamiento de `qa_remates.py` y `run.py` de la versión 1.7.

- `ejecutar-pruebas.bat`: inicia los escenarios reales mediante doble clic en Windows.
- `validar_entrega.py`: revisa que los estados obligatorios sean PASS, que el reporte y el JSON concuerden y que las imágenes PNG existan y sean válidas.
- `preparar_entrega.py` y `preparar-entrega.bat`: generan el ZIP final integrando **las capturas reales del HP Envy**, nunca capturas fabricadas o provenientes de DEMO.
- `README.md`: documentación breve, reproducible y orientada al evaluador.
- `AUDITORIA-v1.8.md`: evaluación documentada de la ejecución de las 17:44 del 14/10/2026 y limitaciones de lo revisado.
- `tests/test_empaquetado.py`: pruebas locales de las comprobaciones de entrega.

**Hyundai no se modificó**: sigue siendo un control adicional y no altera el estado global de la evaluación oficial.

La versión 1.8 no afirma que se hayan inspeccionado visualmente capturas de la última corrida: el paquete final se genera únicamente en el equipo que tiene esas imágenes.
