# Guía para entender la automatización — QA Senior

Esta guía complementa los comentarios que están dentro de los archivos. La idea es que puedas abrir el proyecto en VS Code, seguir el recorrido y explicar con tus palabras qué hace cada parte.

## Actualización 1.7 — ¿por qué contamos lotes antes de abrir una casa?

En la captura real de Remates del Río se leyó «9 Lote(s) encontrado(s)».
No era correcto registrar `UNKNOWN` cuando el portal mostraba un contador
explícito. Ahora `PortalPage.results()` lo reconoce como señal positiva, pero
mantiene separada la localización del enlace de detalle.

La función `open_house_listing()` abre una búsqueda filtrada por casa y valida
que navegamos a `#/busqueda-avanzada` con `idCliente`. `run_second()` usa esa
consulta para decidir cuál es la primera casa con lotes, en vez de suponer que
una tarjeta del calendario representa inventario publicado. La navegación
final a la web de CDR sigue siendo independiente y obligatoria.

Si el portal no informa cantidad, no presenta tarjetas ni da un mensaje vacío,
el estado será `UNKNOWN/INCONCLUSO`. Esperar no equivale a inventar datos.


## Cómo fluye una ejecución

1. Se ejecuta **`run.py`**. El archivo interpreta los parámetros (`--demo`, `--headless`, `--nombre`) y elige la carpeta para las evidencias.
2. `run.py` llama a **`execute()`** de `qa_remates.py`, que abre Chromium y prepara la sesión de Playwright.
3. `run_first()` ejecuta la búsqueda oficial con **`hundai`** (exactamente como aparece en el documento de la prueba).
4. `run_positive_hyundai()` ejecuta una búsqueda **adicional** con **`Hyundai`**. Este control no reemplaza la prueba oficial.
5. `run_second()` visita las casas en el orden requerido y, sin importar dónde encuentre productos, termina en **Remates CDR** para recorrer su página hasta el final.
6. `Reporter` guarda las capturas y genera **`reporte-pruebas.md`** y **`resultado.json`**.

## Las decisiones QA que conviene saber explicar

**¿Por qué no corregimos `hundai`?** Porque es el dato exacto solicitado por la empresa. Un test automatizado debe probar los valores definidos, no adivinar qué quiso decir el usuario.

**¿Para qué añadimos `Hyundai`?** Como control positivo complementario. Si hay productos visibles, comprobamos que la búsqueda permite abrir un detalle. Como el contenido del portal cambia, si no hay publicaciones se registra `SIN_DATOS`, no un PASS inventado.

**¿Por qué una búsqueda vacía puede ser PASS?** El enunciado lo permite para el caso `hundai`, siempre que hayamos comprobado de verdad que no se encontraron resultados y guardado evidencia.

**¿Y si aparece solo una publicación?** En la prueba oficial no cumplimos la instrucción de abrir el segundo resultado. Registramos `BLOQUEADO` en vez de abrir el primero para aparentar que funcionó.

**¿Por qué el caso 2 acaba en CDR aunque encuentre productos antes?** Porque el paso final de la prueba lo pide expresamente.

**¿Qué aporta el reporte automático?** Muestra lo que ocurrió durante esa ejecución, con hora, estados, notas y capturas por paso. No se redacta después ni depende de ChatGPT al ejecutarse.

## Qué revisar si falla la ejecución real

Primero mira `salidas/..._REAL/reporte-pruebas.md` y `resultado.json`. Si no se encuentra un campo, botón o enlace, usa `inspeccionar_portal.py` para revisar los elementos actuales del sitio. En `qa_remates.py`, la clase `PortalPage` concentra los localizadores: normalmente ese será el lugar que habrá que ajustar.

Los scripts de `tests/` y `demo_site/` solo verifican la lógica local. **Nunca se deben adjuntar capturas `DEMO` como evidencia del portal real**.


## Diagnóstico tras la primera ejecución real (v1.3)

El primer ensayo confirmó que los casos de prueba funcionan en el HTML simulado, pero no reconocen los selectores del portal real. No confundimos este error de automatización con una caída del servidor: Chrome abre el portal y la conexión TCP a 443 funciona.

En `set_house_filter()` ahora probamos tres tipos de menú: `<select>` nativo, control accesible `role=combobox` y menú personalizado que una persona identifica por el texto visible «Casa de Remat...». También conservamos el elemento antes de hacer clic, porque su texto cambia y el selector anterior podría dejar de coincidir.

`inspeccionar_portal.py` es nuestro apoyo para analizar el DOM de producción. Toma una captura antes, intenta abrir el menú de casas y captura después. Su archivo `elementos.json` registra qué etiquetas y atributos existen realmente; con eso ajustaremos los selectores definitivos. El script es de solo lectura (salvo abrir visualmente el menú), no modifica publicaciones ni genera informes PASS.

La navegación hacia Reyco, Remates del Río y CDR sigue pendiente de ajuste hasta observar el HTML del portal; no vamos a inventar su comportamiento.

## Ventana emergente de suscripción (v1.4)

En el HP Envy se observó un formulario de suscripción superpuesto al buscador. No pertenece a los pasos del examen: es una interferencia visual del propio portal. En `PortalPage.dismiss_subscription_popup()` revisamos si está visible y localizamos un botón de cierre en la esquina superior derecha de la ventana. Se hace un clic normal y se espera a que el formulario desaparezca.

No rellenamos «Nombres», «Correo Electrónico» ni presionamos «Enviar Suscripción». Si no aparece la ventana, continuamos. Si aparece y no podemos cerrarla, el caso informa el bloqueo; no eliminamos elementos HTML para forzar un resultado. El inspector guarda además `popup-detectado.png` como apoyo para corregir los selectores reales si falla esta primera implementación.

## Distinguir ventanas superpuestas (versión 1.5)

La captura real del Envy nos mostró un aviso de **cookies**, no el formulario grande de **suscripción**. El inspector anterior buscaba el título de suscripción en el HTML y podía confundir una ventana oculta con una abierta. No es correcto declarar un error de cierre sin haber visto el modal completo.

Ahora `_subscription_geometry()` exige que el recuadro y sus controles estén realmente en pantalla. Cuando la ventana tarda en aparecer, `wait_for_subscription_popup()` la espera durante un tiempo acotado. Por separado, `dismiss_cookie_banner()` pulsa **Rechazar Cookies**; no acepta permisos opcionales ni envía el formulario de suscripción. `prepare_overlays()` coordina ambos cierres.

En el inspector guardamos `estado-inicial.png` y `dom_inicial` antes de interactuar: aun si falla algún selector, queda la estructura del sitio para ajustar el código con evidencia. Esto evita intentar adivinar el DOM a partir de una sola captura.

## Qué aprendimos del DOM real (versión 1.6)

El filtro del portal no es un `<select>`: es un `p-dropdown` de PrimeNG. El elemento accesible con rol `combobox` está oculto; por eso el clic real se hace en `.p-dropdown-trigger`. Una vez abierto, recorremos las opciones del panel, desplazamos la opción elegida a la parte visible y confirmamos el texto del control. Seleccionar **America Remates** (situada fuera de los primeros elementos visibles) es una prueba útil del scroll interno.

La web también usa tarjetas personalizadas `<remate-card>` y zonas `span.pointer` en vez de enlaces convencionales. Los localizadores de navegación ahora priorizan esas zonas de tarjeta, para evitar clicar un texto repetido en un testimonio. Las pruebas locales demuestran la lógica del código; la ejecución en el portal vivo debe confirmar qué pantalla y qué lotes aparecen después de cada clic.
