# QA Proyecto Playwright | Automatización web QA Senior

**Proyecto de portafolio QA** que automatiza escenarios de búsqueda, filtrado y navegación en el portal chileno [Próximos Remates](https://www.proximosremates.cl/). La solución registra evidencias por paso y genera automáticamente un informe Markdown y un JSON estructurado. La ejecución no utiliza modelos de IA ni claves API.

> Proyecto independiente basado en una prueba técnica. No está afiliado a Próximos Remates ni a las casas de remates mencionadas. Los nombres y capturas pertenecen a sus respectivos titulares. Los datos de publicación pueden variar de una ejecución a otra.

## Resultado documentado | 14 de octubre de 2026

| Escenario | Estado | Evidencia |
|---|---|---|
| **1 · Búsqueda `hundai` (obligatorio)** | **PASS** | Filtro de America Remates y mensaje «No se encontraron lotes» |
| **1B · Búsqueda `Hyundai` (complementario)** | **INCONCLUSO** | Se detectaron 2 lotes, pero no se abrió un detalle; no afecta el resultado obligatorio |
| **2 · Casas de remates (obligatorio)** | **PASS** | 158 lotes informados para Reyco y recorrido final hasta el pie de CDR |
| **3 · Reporte automático (obligatorio)** | **GENERADO** | Markdown, JSON y 16 capturas PNG |

**Alcance del caso 2:** la disponibilidad de lotes de Reyco se comprobó mediante el contador del listado filtrado de Próximos Remates, **no abriendo el sitio externo de Reyco ni un detalle de producto**. Después se abrió el sitio de CDR y se llegó progresivamente al final. Estos resultados corresponden a una ejecución puntual; no equivalen a disponibilidad permanente de lotes.

### Capturas de la ejecución real

| Búsqueda literal sin resultados | Lotes publicados en Reyco | Llegada al final de CDR |
|---|---|---|
| ![Búsqueda hundai sin lotes](entrega_evidencias/20261014_174424_REAL/evidencias/caso-1-hundai/05-estado-de-resultados.png) | ![158 lotes de Reyco](entrega_evidencias/20261014_174424_REAL/evidencias/caso-2/02-lotes-verificados-remates-reyco.png) | ![Final de la página de CDR](entrega_evidencias/20261014_174424_REAL/evidencias/caso-2/06-final-de-pagina-remates-cdr.png) |

[Ver el informe Markdown completo](entrega_evidencias/20261014_174424_REAL/reporte-pruebas.md) · [Ver los datos JSON](entrega_evidencias/20261014_174424_REAL/resultado.json) · [Leer decisiones técnicas](GUIA-DE-CODIGO.md)

## Tecnologías y criterios de diseño

- **Python y Playwright (Chromium)**: navegación, acciones y esperas condicionadas.
- **PrimeNG**: automatización del selector de casa de remates con lista de desplazamiento interno.
- **Detección de popups**: control separado para suscripción y aviso de cookies.
- **Comprobación dinámica**: se distinguen resultados encontrados, ausencia confirmada y estados no verificables. Se evita fabricar `PASS` ante la falta de evidencia.
- **Reporterías reproducibles**: un directorio por ejecución con capturas paso a paso, Markdown y JSON.
- **Sin IA en ejecución**: la IA apoyó la elaboración y depuración del proyecto, pero el programa no llama a servicios de IA.

## Instalación en Windows

Requisitos: **Python compatible**, conexión a Internet y Git (solo si se desea clonar). La ejecución real se ha validado en **Windows 11, Python 3.14.6 y Playwright 1.64.0**.

```powershell
# Desde la raíz del proyecto
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
```

## Cómo ejecutar

```powershell
# Escenarios reales, con el navegador visible
.\.venv\Scripts\python.exe run.py --nombre "Emilio Silva"

# Solo los ejercicios obligatorios
.\.venv\Scripts\python.exe run.py --nombre "Emilio Silva" --solo-oficial

# Modo demostración local (NO cuenta como ejecución de producción)
.\.venv\Scripts\python.exe run.py --demo

# Pruebas automatizadas de regresión
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Alternativamente, `ejecutar-pruebas.bat` inicia los escenarios reales con doble clic, una vez instalado el entorno. Los resultados se crean en `salidas/AAAAmmdd_HHMMSS_REAL/` (excluido de Git).

## Estructura del proyecto

```text
run.py                      # Punto de entrada
qa_remates.py               # Navegación y reglas de evaluación
inspeccionar_portal.py      # Diagnóstico de selectores reales
tests/                      # 27 pruebas locales de regresión y empaquetado
demo_site/                  # HTML simulado para pruebas controladas
validar_entrega.py          # Comprueba rutas, estados y archivos de evidencia
preparar_entrega.py         # Genera un ZIP entregable con resultados reales
entrega_evidencias/         # Ejecución real preservada (16 PNG + MD + JSON)
.github/workflows/ci.yml    # CI: ejecuta solo los tests locales
GUIA-DE-CODIGO.md           # Explicación de funciones y decisiones técnicas
AUDITORIA-v1.8.md           # Limitaciones de la ejecución registrada
```

## Qué valida la integración continua

El workflow de GitHub Actions instala Python, Playwright y Chromium y ejecuta **solo las pruebas locales** con HTML simulado. No consulta ni modifica el portal real, no publica credenciales y no vuelve a generar evidencias del sitio productivo. El flujo real se ejecuta manualmente en un equipo configurado.

## Limitaciones conocidas

- Los listados de remates cambian; cada nueva corrida se evalúa con el contenido disponible en ese momento.
- El control complementario `Hyundai` permanece `INCONCLUSO` y no se maquilla como aprobado.
- La identificación de lotes puede basarse en el contador visible de resultados; no implica que se haya abierto una ficha detallada.
- Una modificación de la estructura del portal puede requerir revisar selectores mediante `inspeccionar_portal.py`.
- La disponibilidad del sitio externo de CDR, sus imágenes y su mapa dependen de terceros.

Para las instrucciones completas del paquete de evaluación y el empaquetador, consulta [la guía técnica](GUIA-DE-CODIGO.md) y [la auditoría](AUDITORIA-v1.8.md).

## Publicación en GitHub

Repositorio público sugerido: `esilvas85/qa-proyecto-playwright`.

Crea un repositorio **Public** y vacío en GitHub, sin inicializar con README, `.gitignore` ni licencia. Luego ejecuta, desde el directorio descomprimido:

```powershell
git init -b main
git add .
git commit -m "Publicación inicial del portafolio QA con Playwright"
git remote add origin https://github.com/esilvas85/qa-proyecto-playwright.git
git push -u origin main
```

La publicación es independiente de la ejecución de las pruebas sobre el portal real. GitHub Actions ejecutará las pruebas locales usando páginas simuladas.
