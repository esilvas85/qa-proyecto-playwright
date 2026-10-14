"""Pruebas rápidas para revisar nuestro código sin usar datos de producción.

Estas pruebas usan páginas de ejemplo. Si pasan, sabemos que las funciones
básicas responden bien; aún faltará validarlas contra el portal verdadero.
"""
import os
import tempfile
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright
from qa_remates import Case, PortalPage, Reporter, fold, scroll_to_end, slug

DEMO = Path(__file__).resolve().parents[1] / 'demo_site'


class TextoTest(unittest.TestCase):
    """Pequeñas utilidades usadas por filtros y nombres de capturas."""
    def test_fold(self):
        self.assertEqual(fold('Remates del Río'), 'remates del rio')

    def test_slug(self):
        self.assertEqual(slug('Búsqueda ejecutada'), 'busqueda-ejecutada')


class DOMTest(unittest.TestCase):
    """Revisamos búsquedas y desplazamiento con un HTML controlado."""
    @classmethod
    def setUpClass(cls):
        cls.p = sync_playwright().start()
        args = {'headless': True}
        if os.environ.get('PLAYWRIGHT_CHROMIUM_PATH'):
            args['executable_path'] = os.environ['PLAYWRIGHT_CHROMIUM_PATH']
        cls.browser = cls.p.chromium.launch(**args)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.p.stop()

    def setUp(self):
        self.page = self.browser.new_page(viewport={'width': 1440, 'height': 900})
        self.portal = PortalPage(self.page, 'about:blank')

    def tearDown(self):
        self.page.close()

    def _homepage(self, results=False):
        # No dependemos de que alguien publique o retire remates en Internet.
        # Elegimos explícitamente si el simulador tiene dos resultados.
        html = (DEMO / 'index.html').read_text(encoding='utf-8')
        if results:
            html = html.replace("params.has('demo_resultados')", 'true')
        self.page.set_content(html)
        self.page.wait_for_timeout(100)

    def test_sin_resultados_no_es_fallo(self):
        """La palabra literal hundai debe reconocer una búsqueda vacía."""
        self._homepage()
        search = self.portal.search_input()
        search.fill('hundai')
        self.portal.set_house_filter('America Remates')
        self.portal.do_search()
        state, _, info = self.portal.results()
        self.assertEqual(state, 'EMPTY')
        self.assertIn('No se encontraron', info)

    def test_segundo_resultado_cuando_hay_dos(self):
        """El ejercicio oficial exige el segundo detalle, no el primero."""
        self._homepage(results=True)
        self.portal.search_input().fill('hundai')
        self.portal.set_house_filter('America Remates')
        self.portal.do_search()
        state, cards, info = self.portal.results()
        self.assertEqual(state, 'FOUND', info)
        self.assertEqual(self.portal.second_result(cards).locator('a').get_attribute('href'), 'detalle-2.html')

    def test_hyundai_control_positivo(self):
        """Con Hyundai bien escrito deben detectarse productos en la demo."""
        self._homepage()
        self.portal.search_input().fill('Hyundai')
        self.portal.set_house_filter('America Remates')
        self.portal.do_search()
        state, cards, info = self.portal.results()
        self.assertEqual(state, 'FOUND', info)
        self.assertEqual(
            self.portal.first_result(cards).locator('a').get_attribute('href'),
            'detalle-1.html',
        )

    def test_dropdown_personalizado_sin_combobox(self):
        """El menú real podría ser un botón + lista sin roles accesibles.

        Probamos ese tipo de HTML para no depender solo de <select>.
        Este ensayo no demuestra todavía cuál es el HTML de producción.
        """
        self.page.set_content("""
            <main>
              <input placeholder="Estoy buscando" />
              <button id="casa" type="button">Casa de Remat...</button>
              <ul id="menu" hidden><li>America Remates</li><li>Remates CDR</li></ul>
            </main>
            <script>
              document.querySelector('#casa').onclick = () =>
                document.querySelector('#menu').hidden = false;
              document.querySelectorAll('li').forEach(li => {
                li.onclick = () => {
                  document.querySelector('#casa').textContent = li.textContent;
                  document.querySelector('#menu').hidden = true;
                };
              });
            </script>
        """)
        self.portal.set_house_filter('America Remates')
        self.assertEqual(self.page.locator('#casa').inner_text(), 'America Remates')

    def test_primeng_seleccion_con_desplazamiento(self):
        """El HTML inspeccionado usa p-dropdown y una lista de 200px de alto.

        Las opciones America y CDR quedan fuera de la primera pantalla del menú.
        La prueba confirma selección y etiqueta visible, no solo un clic.
        """
        self.page.set_content("""
        <style>.p-dropdown-items-wrapper{height:200px;overflow-y:auto}
        .p-dropdown-item{height:38px;list-style:none}</style>
        <p-dropdown placeholder="Casa de Remates">
          <span class="p-dropdown-label">Casa de Remates</span>
          <div class="p-dropdown-trigger" role="button">Abrir</div>
        </p-dropdown>
        <div class="p-dropdown-panel" style="display:none">
           <div class="p-dropdown-items-wrapper"><ul class="p-dropdown-items"></ul></div>
        </div>
        <script>
          const nombres=['Remates Iñiguez','Remates JDV','Remates Lama',
            'Remates Madrid','Remates Manquehue','Remates Ossa','Remates Reyco',
            'Remates Zarate','Remates Zona Sur','Remates Dicrep','Remates Del Río',
            'Remates Andurand','America Remates','ReyTop','Superbid',
            'Remates La Calera','Tattersall','CGR Chile','Remates Macal',
            'Remates Pinto','Remate San Isidro','Remates Karkal','Remates CDR',
            'Adjudikalo'];
          const panel=document.querySelector('.p-dropdown-panel');
          const ul=document.querySelector('.p-dropdown-items');
          document.querySelector('.p-dropdown-trigger').onclick=()=>panel.style.display='block';
          for(const name of nombres){
             const li=document.createElement('li');li.className='p-dropdown-item';
             li.setAttribute('role','option');li.textContent=name;
             li.onclick=()=>{document.querySelector('.p-dropdown-label').textContent=name;
               panel.style.display='none'};
             ul.append(li);
          }
        </script>
        """)
        for name in ('America Remates', 'Remates CDR', 'Remates Del Río'):
            self.portal.set_house_filter(name)
            self.assertEqual(self.page.locator('.p-dropdown-label').inner_text(), name)

    def test_remate_card_clickable_sin_enlace(self):
        """La ficha Angular tiene span.pointer en lugar de un <a href>."""
        self.page.set_content("""
          <remate-card><div class="remate-card-title">
          <span class="pointer" onclick="location.hash='/reyco'">Remates Reyco</span>
          </div><div class="remate-card-body"><h5 class="pointer">Lote ejemplo</h5></div>
          </remate-card>
        """)
        self.portal.load = lambda: None  # Ya cargamos nuestra web de demostración.
        self.assertTrue(self.portal.open_house('Remates Reyco').endswith('#/reyco'))

    def test_popup_suscripcion_se_cierra_sin_enviar(self):
        """La X sin etiqueta también debe funcionar, sin enviar el formulario."""
        self.page.set_content("""
          <style>
            #overlay {position:fixed;inset:0;background:#0007}
            #modal {position:absolute;left:15%;top:12%;width:70%;height:60%;
              background:white;padding:20px;box-sizing:border-box}
            #x {position:absolute;right:-14px;top:-14px;background:black;
              color:white;border:0;border-radius:50%;height:32px;width:32px}
          </style>
          <main><input placeholder="Estoy buscando" /></main>
          <div id="overlay"><div id="modal">
            <h2>Suscríbete y recibe notificaciones de todos los remates de tu interés</h2>
            <input placeholder="Nombres *" />
            <button id="enviar" onclick="window.enviado=true">Enviar Suscripción</button>
            <button id="x" onclick="document.querySelector('#overlay').remove()">✖</button>
          </div></div>
        """)
        self.assertTrue(self.portal.dismiss_subscription_popup())
        self.assertEqual(self.page.locator('#overlay').count(), 0)
        self.assertFalse(self.page.evaluate('!!window.enviado'))

    def test_popup_sin_boton_cerrar_reporta_error(self):
        """Un modal que bloquea la página no debe aprobar silenciosamente."""
        self.page.set_content("""
            <style>#modal {position:absolute;left:10%;top:10%;width:65%;height:65%}</style>
            <div id="modal">
              <h2>Suscríbete y recibe notificaciones de todos los remates de tu interés</h2>
              <input placeholder="Nombres *" />
              <button>Enviar Suscripción</button>
            </div>
        """)
        with self.assertRaisesRegex(RuntimeError, 'botón de cierre'):
            self.portal.dismiss_subscription_popup()

    def test_sin_popup_continua_normal(self):
        """No debe buscar una X si el sitio no muestra ventana flotante."""
        self._homepage()
        self.assertFalse(self.portal.dismiss_subscription_popup())
        self.assertTrue(self.portal.search_input().is_visible())

    def test_titulo_oculto_fuera_de_pantalla_no_es_popup(self):
        """El sitio puede conservar el modal fuera del viewport sin abrirlo."""
        self.page.set_content("""
          <style>
            #modal {position:fixed;top:140vh;left:15%;width:70%;height:55%;
                    background:white}
          </style>
          <main><input placeholder="Estoy buscando" /></main>
          <div id="modal">
            <h2>Suscríbete y recibe notificaciones de todos los remates de tu interés</h2>
            <input placeholder="Nombres *" />
            <button>Enviar Suscripción</button>
            <button aria-label="Cerrar">×</button>
          </div>
        """)
        self.assertFalse(self.portal.dismiss_subscription_popup())
        self.assertEqual(self.page.locator('#modal').count(), 1)

    def test_texto_suscripcion_no_significa_modal(self):
        """Un título aislado en la web no autoriza a hacer clic en una X."""
        self.page.set_content("""
           <main>
             <h2>Suscríbete y recibe notificaciones de todos los remates</h2>
             <p>Aquí tienes novedades</p>
           </main>
        """)
        self.assertFalse(self.portal.dismiss_subscription_popup())

    def test_aviso_cookies_se_rechaza_por_boton(self):
        """El consentimiento no tiene relación con la suscripción del portal."""
        self.page.set_content("""
           <main><input placeholder="Estoy buscando" /></main>
           <div id="cookies" style="position:fixed;bottom:0;background:white">
            Próximos Remates emplea cookies propias y de terceros.
            <button onclick="document.querySelector('#cookies').remove()">Rechazar Cookies</button>
           </div>
        """)
        self.assertTrue(self.portal.dismiss_cookie_banner())
        self.assertEqual(self.page.locator('#cookies').count(), 0)
        self.assertFalse(self.portal.dismiss_subscription_popup())

    def test_popup_aparece_con_retraso(self):
        """Esperamos un popup tardío sin presuponer que estará siempre abierto."""
        self.page.set_content("""
          <style>
            #modal {position:fixed;left:15%;top:10%;width:70%;height:60%;
              background:white}
            #x {position:absolute;right:0;top:0;width:32px;height:32px}
          </style>
          <div id="modal" hidden>
            <h2>Suscríbete y recibe notificaciones de todos los remates de tu interés</h2>
            <input placeholder="Nombres *" />
            <button>Enviar Suscripción</button>
            <button id="x" onclick="document.querySelector('#modal').remove()">✖</button>
          </div>
          <script>setTimeout(()=>document.querySelector('#modal').removeAttribute('hidden'), 650)</script>
        """)
        self.assertTrue(self.portal.wait_for_subscription_popup(timeout_ms=2200))
        self.assertTrue(self.portal.dismiss_subscription_popup())
        self.assertEqual(self.page.locator('#modal').count(), 0)

    def test_contador_de_lotes_reales_confirma_publicaciones(self):
        """No hace falta inventar un selector de tarjeta si el portal dice 9 lotes.

        Este texto se observó en la captura real de Remates del Río.
        La existencia de lotes queda verificada, pero el detalle aún no.
        """
        self.page.set_content('''<main><h2>9 Lote(s) encontrado(s)</h2>
          <section>LOTE DE PRUEBA</section></main>''')
        state, cards, detail = self.portal.results()
        self.assertEqual(state, 'FOUND')
        self.assertIsNone(cards)
        self.assertIn('9 lote(s)', detail)

    def test_contador_cero_confirma_vacio(self):
        """Cero lotes es una prueba de estado vacío, no un error técnico."""
        self.page.set_content('<main><h2>0 Lote(s) encontrado(s)</h2></main>')
        state, cards, detail = self.portal.results()
        self.assertEqual(state, 'EMPTY')
        self.assertIsNone(cards)

    def test_cifra_no_es_el_segundo_resultado(self):
        """Un contador positivo no autoriza a fingir que abrimos un detalle."""
        self.page.set_content('''<main><h2>2 Lote(s) encontrado(s)</h2>
          <p>Hay publicaciones, pero no enlaces verificables.</p></main>''')
        state, cards, _ = self.portal.results()
        self.assertEqual(state, 'FOUND')
        self.assertIsNone(cards)

    def test_filtro_de_casa_verifica_ruta_de_consulta(self):
        """La casa elegida debe reflejarse en una consulta real de lotes."""
        self.page.set_content('<input type="text" placeholder="Estoy buscando"/>')
        self.portal.load = lambda: None
        elegidas = []
        self.portal.set_house_filter = lambda name: elegidas.append(name)
        self.portal.do_search = lambda: self.page.evaluate(
            'location.hash="/busqueda-avanzada?idCliente=35&descripcion="')
        self.assertIn('idCliente=35', self.portal.open_house_listing('America Remates'))
        self.assertEqual(elegidas, ['America Remates'])

    def test_reporte_markdown_incluye_capturas(self):
        """El informe debe enlazar los PNG reales de esta prueba local."""
        self._homepage(results=True)
        with tempfile.TemporaryDirectory() as temp:
            reporter = Reporter(Path(temp), 'Candidato de ejemplo', 'about:blank', True)
            case = Case('Caso de verificación del reporte', status='PASS', evidence_folder='validacion')
            reporter.cases.append(case)
            reporter.capture(self.page, case, 'Pantalla de prueba', 'Captura local de control.')
            reporter.write()
            markdown = (Path(temp) / 'reporte-pruebas.md').read_text(encoding='utf-8')
            self.assertIn('**Modo:** DEMOSTRACIÓN LOCAL', markdown)
            self.assertIn('![Paso 1', markdown)
            self.assertIn('evidencias/validacion/01-pantalla-de-prueba.png', markdown)
            self.assertTrue((Path(temp) / 'resultado.json').exists())

    def test_llegada_al_final(self):
        """CDR debe recorrerse hasta el pie y dejar capturas intermedias."""
        html=(DEMO / 'cdr.html').read_text(encoding='utf-8')
        self.page.set_content(html)
        with tempfile.TemporaryDirectory() as path:
            case=Case('Caso 2 - Test de desplazamiento')
            reporter=Reporter(Path(path), 'Prueba automatizada', 'about:blank', True)
            self.assertTrue(scroll_to_end(self.page, reporter, case))
            self.assertTrue(case.steps)
            self.assertTrue(all((Path(path) / item.evidence).exists() for item in case.steps))


if __name__ == '__main__':
    unittest.main()
