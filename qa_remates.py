"""Aquí está la lógica que usa Playwright para recorrer Próximos Remates.

La prueba oficial se respeta tal cual (incluido el texto "hundai"). Además,
corremos una búsqueda independiente con "Hyundai" como control positivo.
Las capturas y el informe se crean solos: no hace falta IA al ejecutar.

IMPORTANTE: algunas rutas del portal real ya fueron observadas en el HP Envy,
pero los cambios posteriores deben seguir verificándose allí. Una demo local
no demuestra que la web pública responda igual.
"""
from __future__ import annotations

import json
import os
import platform
import re
import time
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Locator, Page
from playwright.sync_api import sync_playwright

# Datos del enunciado: no cambiar el orden de las casas ni corregir "hundai".
URL = "https://www.proximosremates.cl"
HOUSES = ("Remates Reyco", "Remates del Río", "Remates CDR")
# Son candidatos habituales para identificar tarjetas de productos.
# No los damos por correctos hasta inspeccionar el HTML del sitio real.
RESULT_SELECTORS = (
    '[data-testid="result-card"]', '[data-testid="product-card"]',
    '[data-testid="lot-card"]', '.result-card', '.product-card',
    '.lote-card', '.remate-card', '.producto-card',
    '.resultados .card', '.results .card', '.products .card',
    '.productos .card', 'main article', 'main .card',
    # En Angular las fichas de lotes pueden ser componentes propios y no
    # enlaces clásicos. No usamos estos nombres como prueba de existencia
    # hasta comprobar que el elemento tenga contenido útil.
    'lote-card', 'app-lote-card', 'app-lote', 'lot-card',
    '.lote-item', '.lot-item', '.lot-card', '.lote',
)
# Distintas formas en que el sitio podría avisar que no hubo resultados.
# El portal presenta un contador en la búsqueda, por ejemplo:
# «9 Lote(s) encontrado(s)». Este texto puede confirmar publicaciones aun
# cuando el diseño de las tarjetas cambie y todavía no sepamos abrirlas.
LOT_COUNT_RE = re.compile(r"\b(\d+)\s+lote\s*\(\s*s\s*\)\s+encontrad[oa]\s*\(\s*s\s*\)", re.I)
SUBSCRIPTION_RE = re.compile(r"suscr[ií]bete\s+y\s+recibe\s+notificaciones", re.I)

EMPTY_RE = re.compile(
    r"no (?:se )?(?:encontraron|encontró|hay|existen) (?:resultados|productos|lotes|remates)|"
    r"sin resultados|sin productos|0 resultados|no tenemos resultados|"
    r"no hay productos publicados|ningún (?:resultado|producto|lote)", re.I,
)


def fold(value: str) -> str:
    """Ignora mayúsculas y tildes al comparar nombres de casas de remate."""
    return ''.join(c for c in unicodedata.normalize('NFD', value.lower()) if unicodedata.category(c) != 'Mn')


def slug(value: str) -> str:
    """Convierte la descripción de un paso en un nombre de PNG legible."""
    value = fold(value)
    return re.sub(r'[^a-z0-9]+', '-', value).strip('-')[:55]


def first_visible(candidates: list[Locator], limit: int = 14) -> Optional[Locator]:
    """Prueba varias maneras de encontrar un elemento sin usar uno oculto."""
    for locator in candidates:
        try:
            for i in range(min(locator.count(), limit)):
                loc = locator.nth(i)
                if loc.is_visible():
                    return loc
        except PlaywrightError:
            continue
    return None


# Guardamos pasos y resultados como datos para escribir Markdown y JSON con
# la misma información, en lugar de armar un informe a mano.
@dataclass
class Step:
    name: str
    evidence: str
    detail: str = ""


@dataclass
class Case:
    name: str
    status: str = "PENDIENTE"
    notes: list[str] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)
    required: bool = True
    evidence_folder: str = ""


class Reporter:
    """Centraliza las capturas, los estados y el informe final de ejecución."""

    def __init__(self, output_dir: Path, name: str, url: str, demo: bool):
        self.output = output_dir
        self.output.mkdir(parents=True, exist_ok=True)
        self.name = name
        self.url = url
        self.demo = demo
        self.started = datetime.now().astimezone()
        self.cases: list[Case] = []
        self.browser = "Chromium (Playwright)"
        self.version = ""

    def capture(self, page: Page, case: Case, title: str, detail: str = ""):
        # La imagen se guarda apenas ocurre el paso: así tenemos pruebas de
        # lo que realmente vio el navegador, no una captura preparada después.
        folder = self.output / "evidencias" / (case.evidence_folder or ("caso-1" if case.name.startswith("Caso 1") else "caso-2"))
        folder.mkdir(parents=True, exist_ok=True)
        filename = f"{len(case.steps) + 1:02d}-{slug(title)}.png"
        path = folder / filename
        try:
            page.screenshot(path=str(path), full_page=False, animations="disabled", timeout=15000)
            relative = path.relative_to(self.output).as_posix()
        except Exception as exc:
            # No escondemos fallas de captura. Más adelante impedimos declarar
            # PASS a un caso que perdió una de sus evidencias.
            relative = ""
            case.notes.append(f"No se pudo capturar '{title}': {exc}")
        case.steps.append(Step(title, relative, detail))

    def write(self):
        """Escribe el informe .md y el JSON al terminar los escenarios."""
        finished = datetime.now().astimezone()
        lines = [
            "# Informe de automatización — QA Senior", "",
            f"**Nombre:** {self.name}",
            f"**Fecha/hora inicio:** {self.started.isoformat(timespec='seconds')}",
            f"**Fecha/hora término:** {finished.isoformat(timespec='seconds')}",
            "**Herramienta:** Python + Playwright + reportería propia (sin IA en runtime)",
            f"**Navegador:** {self.browser} {self.version}",
            f"**Sistema operativo:** {platform.platform()}",
            f"**URL probada:** {self.url}",
            f"**Modo:** {'DEMOSTRACIÓN LOCAL — no valida el portal real' if self.demo else 'SITIO REAL'}",
            "",
            "## Resumen", "",
            "| Caso | Estado | Evidencias |", "| --- | --- | ---: |",
        ]
        for case in self.cases:
            group = "Obligatorio" if case.required else "Adicional (no evaluable)"
            lines.append(f"| {case.name} ({group}) | **{case.status}** | {sum(bool(s.evidence) for s in case.steps)} |")
        lines += ["", "**Criterios:** PASS exige verificar todos los pasos previstos. "
                  "Una búsqueda sin resultados es PASS solo si se detecta inequívocamente el estado vacío. "
                  "INCONCLUSO y BLOQUEADO no se presentan como aprobados. "
                  "El caso Hyundai es adicional; si no hay publicaciones se marca SIN_DATOS, "
                  "nunca PASS ficticio ni fallo del ejercicio obligatorio.", ""]
        for case in self.cases:
            lines += [f"## {case.name}", "", f"**Estado:** {case.status}", ""]
            if case.notes:
                lines += ["### Observaciones", ""]
                lines += [f"- {note.replace(chr(10), ' ')}" for note in case.notes]
                lines.append("")
            lines += ["### Evidencias", ""]
            if not case.steps:
                lines.append("No se generaron evidencias.")
            for i, step in enumerate(case.steps, 1):
                lines.append(f"**Paso {i} — {step.name}**")
                lines.append("")
                if step.detail:
                    lines += [step.detail, ""]
                if step.evidence:
                    lines += [f"![Paso {i} — {step.name}](./{step.evidence})", ""]
                else:
                    lines += ["*Captura no disponible*", ""]
        lines += ["## Alcance y limitaciones", "",
                  "La presencia de productos o remates puede variar entre ejecuciones. "
                  "Los errores de conectividad, localizadores y estados no verificables "
                  "se informan explícitamente. El modo DEMO no prueba el sitio de producción.", ""]
        (self.output / "reporte-pruebas.md").write_text("\n".join(lines), encoding="utf-8")
        data = {
            "started_at": self.started.isoformat(), "finished_at": finished.isoformat(),
            "name": self.name, "url": self.url, "demo": self.demo,
            "browser": self.browser, "browser_version": self.version,
            "cases": [asdict(case) for case in self.cases],
        }
        (self.output / "resultado.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


class PortalPage:
    """Acciones compartidas sobre la web: carga, filtros y resultados."""

    def __init__(self, page: Page, url: str):
        self.page = page
        self.url = url

    def _subscription_geometry(self):
        """Distingue un modal *abierto* de contenido oculto en el DOM.

        Un texto puede seguir en la página aun cuando su ventana esté fuera de
        pantalla. Playwright puede reportar ese texto como visible; por eso
        comprobamos que el formulario completo esté realmente en el viewport.
        """
        for i in range(min(self.page.get_by_text(SUBSCRIPTION_RE).count(), 15)):
            heading = self.page.get_by_text(SUBSCRIPTION_RE).nth(i)
            try:
                if not heading.is_visible():
                    continue
                info = heading.evaluate(r"""heading => {
                    function onScreen(el) {
                        const r = el.getBoundingClientRect();
                        if (r.width < 8 || r.height < 8 || r.right <= 0 ||
                            r.bottom <= 0 || r.left >= innerWidth ||
                            r.top >= innerHeight) return false;
                        for (let p=el; p && p!==document; p=p.parentElement) {
                            const st=getComputedStyle(p);
                            if (st.display==='none' || st.visibility==='hidden' ||
                                Number(st.opacity)===0) return false;
                        }
                        return true;
                    }
                    // No confundimos la palabra 'Suscríbete' del HTML con
                    // una ventana abierta: necesitamos el formulario visible.
                    if (!onScreen(heading)) return null;
                    let root=heading;
                    while (root && root!==document.body) {
                        const r=root.getBoundingClientRect();
                        const txt=root.innerText||'';
                        const hasName=Array.from(root.querySelectorAll('input'))
                          .some(el=>onScreen(el));
                        if (r.width>340 && r.height>220 &&
                            r.width<innerWidth*.96 && r.height<innerHeight*.98 &&
                            /enviar\s+suscripci[oó]n/i.test(txt) && hasName &&
                            onScreen(root)) break;
                        root=root.parentElement;
                    }
                    if (!root || root===document.body) return null;
                    const box=root.getBoundingClientRect();
                    // Buscamos la X también en elementos adyacentes: algunos
                    // sitios la sitúan fuera del borde con posición absoluta.
                    const nodes=Array.from(document.querySelectorAll(
                      'button,a,[role="button"],[onclick],img,svg,'+
                      '[class*="close" i],[id*="close" i],'+
                      '[class*="cerrar" i],[id*="cerrar" i],'+
                      '[class*="times" i],i,span'
                    ));
                    const candidates=nodes.map(el=>{
                        if (!onScreen(el)) return null;
                        const r=el.getBoundingClientRect();
                        const x=r.x+r.width/2,y=r.y+r.height/2;
                        if (x<box.right-135 || x>box.right+65 ||
                            y<box.top-75 || y>box.top+115 ||
                            r.width<12 || r.height<12 ||
                            r.width>105 || r.height>105) return null;
                        const label=[el.getAttribute('aria-label'),el.title,
                           el.id,el.className?.baseVal||el.className,
                           el.alt,el.innerText].filter(Boolean).join(' ').slice(0,150);
                        const close=/close|cerrar|cerr|×|✕|✖|\bx\b/i.test(label);
                        const semantic=el.matches('button,a,[role="button"],[onclick]');
                        const pointer=getComputedStyle(el).cursor==='pointer';
                        // Evitamos tocar imágenes o elementos decorativos al azar.
                        if (!close && !semantic && !pointer) return null;
                        return {x,y,score:(close?100:0)+(semantic?18:0)+
                          (pointer?10:0)-(Math.abs(x-box.right)+
                          Math.abs(y-box.top))/10};
                    }).filter(Boolean).sort((a,b)=>b.score-a.score);
                    return {root:{x:box.x,y:box.y,w:box.width,h:box.height},
                            candidates};
                }""")
                if info:
                    return info
            except PlaywrightError:
                continue
        return None

    def wait_for_subscription_popup(self, timeout_ms: int = 2500) -> bool:
        """Da tiempo a ventanas diferidas, sin asumir que siempre aparecen."""
        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            if self._subscription_geometry():
                return True
            self.page.wait_for_timeout(150)
        return bool(self._subscription_geometry())

    def dismiss_subscription_popup(self) -> bool:
        """Cierra con un clic real la X de la ventana, si realmente está abierta.

        No rellenamos formularios ni damos por presente una ventana solo porque
        su encabezado permanezca en un componente oculto de la página.
        """
        geometry = self._subscription_geometry()
        if geometry is None:
            return False
        if not geometry['candidates']:
            raise RuntimeError('Popup de suscripción visible, pero no se identificó su botón de cierre.')
        for target in geometry['candidates'][:5]:
            self.page.mouse.click(target['x'], target['y'])
            # Esperamos al cambio real de estado, no un retardo fijo de éxito.
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                if self._subscription_geometry() is None:
                    return True
                self.page.wait_for_timeout(150)
        raise RuntimeError('Se intentó cerrar el popup, pero el formulario sigue visible.')

    def dismiss_cookie_banner(self) -> bool:
        """Rechaza cookies opcionales si el aviso interfiere con la prueba.

        El aviso de cookies y el popup de suscripción son dos elementos
        distintos. Usamos el botón que el sitio ofrece, sin eliminar HTML.
        """
        reject = first_visible([
            self.page.get_by_role('button', name=re.compile(r'^\s*Rechazar Cookies\s*$', re.I)),
            self.page.get_by_text(re.compile(r'^\s*Rechazar Cookies\s*$', re.I)),
        ])
        if reject is None:
            return False
        reject.click(timeout=6000)
        try:
            reject.wait_for(state='hidden', timeout=3500)
        except PlaywrightError as exc:
            raise RuntimeError('Se hizo clic en Rechazar Cookies pero el aviso continúa visible.') from exc
        return True

    def prepare_overlays(self, wait_for_popup: bool = False) -> bool:
        """Resuelve modales en orden y vuelve a comprobar si reaparecieron."""
        if wait_for_popup:
            self.wait_for_subscription_popup(timeout_ms=3000)
        popup_closed = self.dismiss_subscription_popup()
        self.dismiss_cookie_banner()
        # En ciertos sitios el popup surge cuando se termina con las cookies.
        return self.dismiss_subscription_popup() or popup_closed

    def load(self):
        response = self.page.goto(self.url, wait_until="domcontentloaded", timeout=45000)
        if response is not None and response.status >= 400:
            raise RuntimeError(f"El portal respondió HTTP {response.status}")
        self.page.locator('body').wait_for(state='visible', timeout=15000)
        # Esperamos un popup tardío solo después de navegar a una página nueva.
        return self.prepare_overlays(wait_for_popup=True)

    def search_input(self) -> Locator:
        self.prepare_overlays()
        # Preferimos el rol accesible. Los selectores alternativos nos ayudan
        # si el portal no implementó correctamente las etiquetas HTML.
        return first_visible([
            self.page.get_by_role('searchbox'),
            self.page.locator('input[type="search"]'),
            self.page.locator('input[placeholder*="buscar" i]'),
            self.page.locator('input[placeholder*="búsq" i]'),
            self.page.locator('input[name*="buscar" i], input[name*="search" i]'),
            self.page.locator('input[type="text"]'),
        ]) or self._missing("campo de búsqueda")

    def _missing(self, text: str):
        raise RuntimeError(f"No se encontró {text}; se requiere inspeccionar el DOM real")

    def set_house_filter(self, name: str):
        """Selecciona una casa incluso cuando el menú es un componente visual.

        En la primera ejecución real detectamos que el portal no exponía un
        <select> ni un combobox que nuestros selectores reconocieran. Por eso
        agregamos un tercer camino para los desplegables personalizados.
        No adivinamos un resultado: si no se verifica la selección, fallamos.
        """
        self.prepare_overlays()
        # 0) Selector verificado contra el DOM del 14-10-2026.
        # El portal usa PrimeNG: p-dropdown con opciones <li role="option">.
        # El campo combobox interno es invisible, por eso no se debe clicar.
        prime = self.page.locator('p-dropdown[placeholder="Casa de Remates"]')
        if prime.count():
            campo = prime.first
            trigger = campo.locator('.p-dropdown-trigger')
            trigger.click(timeout=10000)
            panel = self.page.locator('.p-dropdown-panel:visible')
            panel.wait_for(state='visible', timeout=7000)
            # La mayoría de opciones está FUERA de los 200px visibles del menú.
            # El desplazamiento debe hacerse dentro de ese menú, no en la página.
            opciones = panel.locator('li.p-dropdown-item[role="option"]')
            destino = None
            for indice in range(opciones.count()):
                opcion = opciones.nth(indice)
                if fold(opcion.inner_text().strip()) == fold(name):
                    destino = opcion
                    break
            if destino is None:
                labels = opciones.all_inner_texts()
                raise RuntimeError(f"La casa {name!r} no figura en el desplegable. "
                                   f"Opciones disponibles: {labels!r}")
            destino.scroll_into_view_if_needed(timeout=10000)
            destino.click(timeout=10000)
            # No verificamos el texto del trigger: es solo una flecha.
            # Lo que debe cambiar es la etiqueta del propio p-dropdown.
            etiqueta = campo.locator('.p-dropdown-label').inner_text(timeout=5000).strip()
            if fold(etiqueta) != fold(name):
                raise RuntimeError(f"La casa seleccionada no coincide: "
                                   f"esperada={name!r}; visible={etiqueta!r}")
            return

        # 1) Controles HTML clásicos. Son los más fáciles de inspeccionar.
        for i in range(self.page.locator('select').count()):
            item = self.page.locator('select').nth(i)
            if not item.is_visible():
                continue
            opts = item.locator('option').all_text_contents()
            for label in opts:
                if fold(name) in fold(label.strip()):
                    item.select_option(label=label)
                    return

        # 2) Componentes accesibles: <div role="combobox">, entre otros.
        # Hay portales que implementan el control sin semántica accesible;
        # en ese caso pasamos a los candidatos visuales.
        combos = self.page.get_by_role('combobox')
        for i in range(min(combos.count(), 8)):
            combo = combos.nth(i)
            if not combo.is_visible():
                continue
            try:
                combo.click(timeout=3000)
                if self._select_open_option(name, combo):
                    return
                self.page.keyboard.press('Escape')
            except PlaywrightError:
                continue

        # 3) Fallback basado en el texto que ve una persona. En la captura
        # del Envy el desplegable aparece como "Casa de Remat...".
        # No asumimos todavía qué framework JavaScript renderiza la página.
        triggers = [
            self.page.locator('input[placeholder*="casa" i]'),
            self.page.locator('[aria-label*="casa" i]'),
            self.page.locator('button').filter(has_text=re.compile(r'casa\s+de\s+remat', re.I)),
            self.page.get_by_text(re.compile(r'casa\s+de\s+remat', re.I)),
        ]
        for candidates in triggers:
            for i in range(min(candidates.count(), 15)):
                trigger = candidates.nth(i)
                try:
                    if not trigger.is_visible():
                        continue
                    rect = trigger.bounding_box()
                    # No clicar en un gran bloque que solo contiene el texto.
                    if not rect or rect['height'] > 180 or rect['width'] > 500:
                        continue
                    trigger.click(timeout=4000)
                    self.page.wait_for_timeout(350)
                    if self._select_open_option(name, trigger):
                        return
                    self.page.keyboard.press('Escape')
                except PlaywrightError:
                    continue
        raise RuntimeError(f"No se pudo seleccionar y comprobar la casa {name!r}. "
                           "Ejecuta inspeccionar_portal.py para obtener el DOM real del desplegable.")

    def _select_open_option(self, name: str, trigger: Locator) -> bool:
        """Escoge una opción visible del menú abierto, sin tocar otros remates.

        Primero buscamos roles/etiquetas de listas. Si el portal omite esas
        etiquetas, limitamos los textos exactos al área cercana al control.
        """
        target = re.compile(r'^\s*' + re.escape(name) + r'\s*$', re.I)
        # Algunos frameworks construyen options como <li> o <div role=option>.
        options = [
            self.page.get_by_role('option', name=target),
            self.page.get_by_role('menuitem', name=target),
            self.page.locator('li').filter(has_text=target),
            self.page.locator('mat-option').filter(has_text=target),
            self.page.locator('[class*="option" i], [class*="item" i]').filter(has_text=target),
        ]
        origin = trigger.bounding_box() or {'x': 0, 'y': 0, 'width': 0, 'height': 0}
        # Guardamos el elemento original: después de elegir America Remates,
        # el selector basado en "Casa de Remat..." ya no coincidirá.
        trigger_handle = trigger.element_handle()
        # Este último candidato es intencionalmente más amplio; la distancia
        # impide escoger una tarjeta del catálogo en vez de la opción del menú.
        options.append(self.page.get_by_text(target))
        for group in options:
            for i in range(min(group.count(), 50)):
                option = group.nth(i)
                try:
                    if not option.is_visible():
                        continue
                    r = option.bounding_box()
                    if not r:
                        continue
                    # El desplegable debe abrirse cerca del campo de casas.
                    dist = abs(r['x'] - origin['x']) + abs(r['y'] - origin['y'])
                    if dist > 850:
                        continue
                    option.click(timeout=3500)
                    self.page.wait_for_timeout(200)
                    # Verificamos el cambio que puede observarse en pantalla.
                    # Algunos controles dejan el valor en el propio trigger;
                    # otros lo muestran en un elemento padre o input asociado.
                    if not trigger_handle:
                        continue
                    control_text = trigger_handle.evaluate('(e) => (e.value || e.innerText || e.textContent || "").trim()')
                    parent_text = trigger_handle.evaluate('(e) => (e.parentElement?.innerText || "").trim()')
                    if fold(name) in fold(control_text) or fold(name) in fold(parent_text[:220]):
                        return True
                    # Si la opción es un <option> accesible y desaparece al
                    # seleccionarla, puede ser el nuevo valor. Inspeccionar
                    # el resultado en la ejecución real antes de aprobar.
                except PlaywrightError:
                    continue
        return False

    def do_search(self):
        self.prepare_overlays()
        # No enviamos Enter por comodidad: el enunciado pide pulsar Buscar.
        button = first_visible([
            self.page.get_by_role('button', name=re.compile(r'^\s*buscar\s*$', re.I)),
            self.page.locator('button[type="submit"], input[type="submit"]'),
            self.page.get_by_text('Buscar', exact=True),
        ])
        if button is None:
            self._missing("botón Buscar")
        button.click(timeout=15000)
        self.page.wait_for_load_state('domcontentloaded', timeout=15000)
        self.page.wait_for_timeout(1000)

    def results(self, allow_remate_cards: bool = False) -> tuple[str, Optional[Locator], str]:
        """Distingue resultados publicados, búsquedas vacías y casos inciertos.

        Una frase «9 Lote(s) encontrado(s)» es evidencia positiva del propio
        portal. Para abrir un detalle todavía necesitamos encontrar una tarjeta
        clicable, así que dejamos diferenciadas esas dos comprobaciones.
        """
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            # Nunca convertimos una página en blanco en «cero resultados».
            empty = first_visible([
                self.page.locator('.no-results, .empty-state, [data-testid="empty-results"]'),
                self.page.get_by_text(EMPTY_RE),
            ])
            if empty:
                return "EMPTY", None, empty.inner_text(timeout=3000)[:220]

            counter = None
            try:
                # innerText del body nos permite leer el contador aunque esté
                # en un h2, div o span diferente según la pantalla.
                visible_text = self.page.locator('body').inner_text(timeout=3000)
                match = LOT_COUNT_RE.search(visible_text)
                if match:
                    counter = int(match.group(1))
                    if counter == 0:
                        return "EMPTY", None, "El portal indica 0 Lote(s) encontrado(s)."
            except PlaywrightError:
                pass

            selectors = (*RESULT_SELECTORS, 'remate-card') if allow_remate_cards else RESULT_SELECTORS
            for selector in selectors:
                cards = self.page.locator(selector)
                try:
                    usable = []
                    for idx in range(min(cards.count(), 250)):
                        card = cards.nth(idx)
                        if (card.is_visible() and
                                self._card_target(card) is not None and
                                len(card.inner_text().strip()) >= 3):
                            usable.append(idx)
                    if usable:
                        prefix = f"El portal anuncia {counter} lote(s). " if counter is not None else ""
                        return "FOUND", cards, (prefix +
                            f"Se localizaron {len(usable)} tarjetas clicables con '{selector}'.")
                except PlaywrightError:
                    continue

            if counter is not None and counter > 0:
                # El contador demuestra que sí existen lotes, pero no
                # afirmamos haber encontrado el enlace de sus detalles.
                return "FOUND", None, (f"El portal informa {counter} lote(s) encontrado(s). "
                    "Aún no se identificó una tarjeta clicable para abrir detalles.")
            self.page.wait_for_timeout(300)
        return "UNKNOWN", None, ("Tras esperar la actualización del portal, no hubo "
            "mensaje de estado vacío, contador de lotes ni tarjetas reconocibles.")

    def open_house_listing(self, name: str) -> str:
        """Consulta el listado real de lotes asociado a una casa.

        En el calendario hay tarjetas que representan REMATES, no productos.
        Un clic en una de ellas puede llevar a la web externa sin mostrar lotes.
        Para comprobar publicaciones primero filtramos la búsqueda del portal
        por casa y verificamos que efectivamente se cargue esa consulta.
        """
        self.load()
        self.search_input().fill("")
        self.set_house_filter(name)
        self.do_search()
        # El portal Angular utiliza una ruta #/busqueda-avanzada?idCliente=...
        # y solo se da por visitado el listado si ocurrió la navegación.
        url = self.page.url
        if 'busqueda-avanzada' not in url or 'idCliente=' not in url:
            # El simulador local no utiliza hash routes; allí probamos la
            # navegación tradicional con tarjetas HTML.
            if '127.0.0.1' in self.url or 'localhost' in self.url:
                return self.open_house(name)
            raise RuntimeError(f'No se verificó el listado de {name}: URL {url}')
        return url

    def _card_target(self, card: Locator) -> Optional[Locator]:
        """Identifica qué se debe pulsar para abrir un detalle de verdad.

        Algunas tarjetas de Angular navegan mediante un controlador de clic,
        no con enlaces <a>. Preferimos el nombre del remate si existe.
        """
        return first_visible([
            card.locator('a[href]'),
            card.locator('.remate-card-body h5.pointer'),
            card.locator('.remate-card-body .pointer'),
        ])

    def first_result(self, cards: Locator) -> Locator:
        for idx in range(min(cards.count(), 250)):
            card = cards.nth(idx)
            if card.is_visible() and self._card_target(card) is not None and len(card.inner_text().strip()) >= 3:
                return card
        raise ValueError('Se detectaron cero resultados utilizables; no existe primer resultado.')

    def second_result(self, cards: Locator) -> Locator:
        # Tomamos el segundo resultado *visible y utilizable*, no la segunda
        # tarjeta del DOM: a veces hay tarjetas ocultas para diseño responsivo.
        valid = []
        for idx in range(min(cards.count(), 250)):
            card = cards.nth(idx)
            if card.is_visible() and self._card_target(card) is not None and len(card.inner_text().strip()) >= 3:
                valid.append(card)
        if len(valid) < 2:
            raise ValueError(f"Se detectaron solo {len(valid)} resultados utilizables; no existe segundo resultado.")
        return valid[1]

    def open_house(self, name: str) -> str:
        """Abre un remate de la casa solicitada, sin confundirlo con testimonios.

        El DOM del portal muestra <remate-card> y títulos clicables como
        <span class="pointer">Remates Reyco</span>. Por eso intentamos primero
        una tarjeta auténtica. Si no hay tarjeta semanal, buscamos por la casa
        mediante el desplegable validado. Que exista una casa en el filtro no
        demuestra que tenga lotes: eso se comprueba después.
        """
        self.load()
        original_url = self.page.url
        original_text = self.page.locator('body').inner_text(timeout=5000)

        def tarjetas_de_casa():
            # La etiqueta exacta evita que "Reyco" coincida con un testimonio
            # o con el texto de una tarjeta diferente.
            loc = self.page.locator('remate-card .remate-card-title span.pointer')
            return [loc.nth(i) for i in range(min(loc.count(), 200))
                    if fold(loc.nth(i).inner_text().strip()) == fold(name)]

        links = tarjetas_de_casa()
        if not links:
            # La casa puede no tener eventos en el calendario inicial y sí
            # aparecer como opción en el buscador. Probamos esa ruta.
            self.set_house_filter(name)
            self.do_search()
            links = tarjetas_de_casa()

        if not links:
            raise RuntimeError(
                f"No se identificó una tarjeta clicable de {name} "
                "en el calendario ni en la búsqueda por casa. "
                "La selección del filtro no equivale a visitar su detalle."
            )

        original_pages = list(self.page.context.pages)
        selected = next((loc for loc in links if loc.is_visible()), links[0])
        selected.scroll_into_view_if_needed(timeout=10000)
        selected.click(timeout=12000)
        self.page.wait_for_timeout(1200)
        nuevas = [pg for pg in self.page.context.pages if pg not in original_pages]
        if nuevas:
            self.page = nuevas[-1]
        self.page.wait_for_load_state('domcontentloaded', timeout=15000)
        self.page.locator('body').wait_for(state='visible', timeout=10000)
        if self.page.url == original_url and self.page.locator('body').inner_text(timeout=5000) == original_text:
            raise RuntimeError(f'No se verificó navegación hacia {name}: URL y contenido no cambiaron')
        return self.page.url


def run_search_case(portal: PortalPage, report: Reporter, *, term: str, extra: bool = False):
    """Escenario de búsqueda reutilizable. No confundir el obligatorio con el bonus.

    - hundai: requisito literal; EMPTY es un resultado aceptado.
    - Hyundai: control positivo adicional; PASS requiere un resultado y navegación
      al detalle. SIN_DATOS significa que el portal no permite comprobar el positivo.
    """
    if extra:
        case = Case('Caso 1B - Control positivo Hyundai (adicional)',
                    required=False, evidence_folder='caso-1b-hyundai')
    else:
        case = Case('Caso 1 - Búsqueda y filtrado (hundai)',
                    required=True, evidence_folder='caso-1-hundai')
    report.cases.append(case)
    try:
        popup_closed = portal.load()
        report.capture(portal.page, case, 'Sitio cargado', portal.page.url)
        if popup_closed:
            report.capture(portal.page, case, 'Ventana de suscripcion cerrada',
                           'Se cerró el popup sin enviar información.')
        search = portal.search_input()
        search.fill(term)
        if search.input_value() != term:
            raise RuntimeError(f'El campo no conservó exactamente {term!r}')
        report.capture(portal.page, case, f'Busqueda {term} ingresada',
                       f'Valor exacto: `{term}`.')
        # Mantenemos el filtro fijo en ambos casos para comparar la misma casa.
        portal.set_house_filter('America Remates')
        report.capture(portal.page, case, 'America Remates seleccionada')
        portal.do_search()
        report.capture(portal.page, case, 'Busqueda ejecutada', portal.page.url)
        state, cards, info = portal.results(allow_remate_cards=True)
        report.capture(portal.page, case, 'Estado de resultados',
                       f'Término: `{term}`. Detección: {state}. {info}')
        if state == 'EMPTY':
            # Solo "hundai" puede aprobar sin datos, porque así lo autoriza el
            # enunciado. "Hyundai" busca un resultado positivo y queda SIN_DATOS.
            if extra:
                case.status = 'SIN_DATOS'
                case.notes.append('La búsqueda con Hyundai no devolvió publicaciones. '
                                  'No se puede validar un control positivo sin datos, '
                                  'pero esto no invalida el ejercicio 1.')
            else:
                case.status = 'PASS'
                case.notes.append('Ruta válida: búsqueda hundai sin resultados; '
                                  'evidencia del estado vacío registrada.')
            return
        if state != 'FOUND' or cards is None:
            # Si no podemos determinar qué muestra el portal, no es correcto
            # reportar PASS ni afirmar que la búsqueda está vacía.
            case.status = 'INCONCLUSO'
            case.notes.append(info)
            return
        # En el ejercicio oficial ES OBLIGATORIO abrir el segundo resultado.
        # En el control positivo extra basta con abrir uno: segundo cuando exista,
        # primero si hay solo una publicación; nunca fabricar resultados.
        try:
            if extra:
                try:
                    chosen = portal.second_result(cards)
                    ordinal = 'Segundo'
                except ValueError:
                    chosen = portal.first_result(cards)
                    ordinal = 'Primer'
            else:
                chosen = portal.second_result(cards)
                ordinal = 'Segundo'
        except ValueError as exc:
            case.status = 'BLOQUEADO'
            case.notes.append(str(exc))
            return
        initial_pages = list(portal.page.context.pages)
        old_url = portal.page.url
        old_text = portal.page.locator('body').inner_text(timeout=5000)
        target = portal._card_target(chosen)
        if target is None:
            raise RuntimeError('El resultado seleccionado no tiene detalle clicable.')
        target.click(timeout=12000)
        portal.page.wait_for_timeout(1100)
        current_page = next((p for p in portal.page.context.pages if p not in initial_pages), portal.page)
        current_page.wait_for_load_state('domcontentloaded', timeout=15000)
        report.capture(current_page, case, f'{ordinal} resultado abierto', current_page.url)
        if current_page.url == old_url and current_page.locator('body').inner_text(timeout=5000) == old_text:
            raise RuntimeError('No se verificó apertura del resultado (URL y contenido sin cambios).')
        case.status = 'PASS'
        case.notes.append(f'Búsqueda literal `{term}`: publicación encontrada, '
                          f'{ordinal.lower()} resultado abierto y detalle capturado.')
    except Exception as exc:
        case.status = 'ERROR'
        case.notes.append(f'{type(exc).__name__}: {exc}')
        try:
            report.capture(portal.page, case, f'Error buscando {term}', str(exc))
        except Exception:
            pass


def run_first(portal: PortalPage, report: Reporter):
    """Caso obligatorio de la prueba v1.1."""
    return run_search_case(portal, report, term='hundai')


def run_positive_hyundai(portal: PortalPage, report: Reporter):
    """Caso adicional propuesto: control positivo, nunca reemplaza a hundai."""
    return run_search_case(portal, report, term='Hyundai', extra=True)


def scroll_to_end(page: Page, report: Reporter, case: Case) -> bool:
    """Desplaza la página por tramos y confirma que llegó al pie."""
    # Evitamos saltar de golpe con End: el ejercicio solicita un avance
    # progresivo y algunas webs van agregando contenido al bajar.
    was_bottom = False
    for i in range(1, 35):
        before = page.evaluate('({y:window.scrollY, doc:document.documentElement.scrollHeight, h:innerHeight})')
        page.evaluate('window.scrollBy(0, Math.max(320, Math.floor(innerHeight * 0.72)))')
        page.wait_for_timeout(320)
        after = page.evaluate('({y:window.scrollY, doc:document.documentElement.scrollHeight, h:innerHeight})')
        if i in (1, 4, 9):
            report.capture(page, case, f'Scroll progresivo {i}', f"Posición: {int(after['y'])} px")
        if after['y'] + after['h'] >= after['doc'] - 5:
            page.wait_for_timeout(700)
            check = page.evaluate('({y:window.scrollY, doc:document.documentElement.scrollHeight, h:innerHeight})')
            if check['y'] + check['h'] >= check['doc'] - 5:
                was_bottom = True
                break
    return was_bottom


def run_second(portal: PortalPage, report: Reporter):
    """Comprueba lotes por orden y finaliza en la página externa de CDR.

    No confundimos tarjetas del calendario con productos disponibles: el
    contador de lotes en la búsqueda filtrada permite verificar cada casa.
    """
    case = Case('Caso 2 - Casas de remates y desplazamiento')
    report.cases.append(case)
    found_house: Optional[str] = None
    uncertainties: list[str] = []
    seen: dict[str, str] = {}
    for house in HOUSES:
        try:
            if report.demo:
                # En la demo las casas se visitan por sus enlaces HTML.
                destination = portal.open_house(house)
            else:
                # En producción priorizamos la consulta real de lotes de la
                # casa, no una tarjeta promocional del calendario semanal.
                destination = portal.open_house_listing(house)
            report.capture(portal.page, case, f'Listado consultado {house}', destination)
            state, cards, info = portal.results()
            seen[house] = state
            report.capture(portal.page, case, f'Lotes verificados {house}',
                           f"Detección: {state}. {info}")
            if state == 'FOUND':
                found_house = house
                case.notes.append(f"Primera casa con lotes confirmados: {house}. {info}")
                break
            if state == 'UNKNOWN':
                uncertainties.append(f"{house}: resultados no verificables ({info})")
        except Exception as exc:
            uncertainties.append(f"{house}: {type(exc).__name__}: {exc}")
            try:
                report.capture(portal.page, case, f'Error consultando {house}', str(exc))
            except Exception:
                pass
    if found_house is None:
        case.notes.append('No se confirmó una casa con lotes en las consultas realizadas.')

    # Aun si otra casa tiene productos, el enunciado solicita situarnos
    # específicamente en Remates CDR y bajar hasta el pie de su web.
    try:
        if report.demo:
            portal.open_house('Remates CDR')
        else:
            portal.open_house('Remates CDR')
        if 'cdr' not in fold(portal.page.url):
            raise RuntimeError('No se verificó la URL de Remates CDR.')
        report.capture(portal.page, case, 'Ubicados en Remates CDR', portal.page.url)
        at_end = scroll_to_end(portal.page, report, case)
        report.capture(portal.page, case, 'Final de pagina Remates CDR',
                       f"¿Llegó al pie? {at_end}")
        if not at_end:
            case.status = 'INCONCLUSO'
            case.notes.append('No se verificó el final de página tras los desplazamientos.')
        elif uncertainties:
            case.status = 'INCONCLUSO'
            case.notes.append('No se puede afirmar que se encontró la primera casa '
                              'con lotes: existen consultas no verificadas previamente.')
        else:
            case.status = 'PASS'
    except Exception as exc:
        case.status = 'ERROR'
        case.notes.append(f'No se completó el desplazamiento en CDR: '
                          f'{type(exc).__name__}: {exc}')
        try:
            report.capture(portal.page, case, 'Error al finalizar en CDR', str(exc))
        except Exception:
            pass
    case.notes.extend(uncertainties)
    case.notes.append('Orden de evaluación: ' + ', '.join(
        f'{house}: {seen.get(house, "NO VERIFICADO")}' for house in HOUSES))
    if not report.demo:
        case.notes.append('La disponibilidad se verificó en los listados filtrados de '
                          'Próximos Remates; el cierre se documentó en la web externa CDR.')


def execute(output: Path, name: str, url: str, demo: bool, headless: bool = False, slowmo: int = 100, include_hyundai: bool = True):
    """Prepara Chromium y ejecuta todos los escenarios solicitados."""
    reporter = Reporter(output, name, url, demo)
    with sync_playwright() as p:
        launch_opts = {'headless': headless, 'slow_mo': slowmo}
        executable = os.getenv('PLAYWRIGHT_CHROMIUM_PATH')
        if executable:
            launch_opts['executable_path'] = executable
        browser = p.chromium.launch(**launch_opts)
        reporter.version = browser.version
        # Una ventana con medidas estables hace las capturas comparables.
        # Fijamos además el idioma y la zona horaria de Chile.
        context = browser.new_context(viewport={'width': 1440, 'height': 900}, locale='es-CL', timezone_id='America/Santiago', accept_downloads=False)
        page = context.new_page()
        page.set_default_timeout(12000)
        portal = PortalPage(page, url)
        try:
            # Ejecutamos primero lo pedido por la empresa, después el control
            # adicional y finalmente la navegación entre casas.
            run_first(portal, reporter)
            if include_hyundai:
                run_positive_hyundai(portal, reporter)
            run_second(portal, reporter)
        finally:
            # Las capturas son obligatorias; un PASS sin evidencia no se entrega como PASS.
            for case in reporter.cases:
                if case.status == 'PASS' and any(not step.evidence for step in case.steps):
                    case.status = 'INCONCLUSO'
                    case.notes.append('Se perdió al menos una captura obligatoria.')
            reporter.write()
            context.close()
            browser.close()
    return reporter
