"""Fotografía técnica del formulario de Próximos Remates.

¿Por qué existe? En el primer ensayo REAL los tres casos se bloquearon porque
nuestros selectores suponían etiquetas HTML que aún no habíamos visto.
Este script NO marca casos como PASS: solo reúne evidencias del DOM real para
corregirlos con datos, no con adivinanzas.

Uso en Windows:
    .\\.venv\\Scripts\\python.exe inspeccionar_portal.py

Comparte los archivos `elementos.json` y `dropdown-abierto.png` resultantes.
No captures contraseñas ni cookies; el script se limita a elementos públicos.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright
from qa_remates import URL, PortalPage

HERE = Path(__file__).resolve().parent

# JavaScript de lectura: extrae estructura, etiquetas y textos visibles.
# No ejecuta comandos que modifiquen datos del portal ni recopila cookies.
INSPECT_JS = r"""() => {
 const shown=e=>{
   const b=e.getBoundingClientRect(), s=getComputedStyle(e);
   return !!(b.width && b.height && s.visibility!=='hidden' && s.display!=='none');
 };
 const short=(t,n=220)=>String(t||'').trim().replace(/\s+/g,' ').slice(0,n);
 const info=(e)=>({tag:e.tagName.toLowerCase(),id:e.id||'',clase:String(e.className||'').slice(0,160),
   role:e.getAttribute('role'),aria:e.getAttribute('aria-label'),placeholder:e.getAttribute('placeholder'),
   title:e.getAttribute('title'),texto:short(e.innerText||e.textContent),
   html:e.outerHTML.slice(0,1200),rect:(()=>{const r=e.getBoundingClientRect();return {x:Math.round(r.x),y:Math.round(r.y),w:Math.round(r.width),h:Math.round(r.height)}})()});
 const all=[...document.querySelectorAll('input,select,button,[role="button"],[role="combobox"],[role="listbox"],[role="option"],[role="menuitem"],a[href]')];
 const relevant=all.filter(e=>shown(e)).map(info);
 const matching=[...document.querySelectorAll('body *')].filter(e=>shown(e)&&
   /america\s*remates|casa\s+de\s+remat|remates\s+(reyco|del\s+r[ií]o|cdr)/i.test(short(e.innerText||e.textContent,240)) &&
   (e.children.length < 5 || /^(INPUT|BUTTON|A|SELECT|LI)$/.test(e.tagName)));
 // Limitar los resultados evita un archivo enorme en sitios con muchas tarjetas.
 const samples=matching.slice(0,90).map(e=>{
   const p=e.closest('button,a,[role="button"],[role="combobox"],li')||e.parentElement;
   return {elemento:info(e),ancestro_candidato:p?info(p):null};
 });
 return {titulo:document.title,url:location.href,
   inputs:relevant.filter(x=>x.tag==='input'),
   selects:[...document.querySelectorAll('select')].map(e=>({ ...info(e), opciones:[...e.options].map(o=>({texto:short(o.textContent),valor:o.value}))})),
   botones:relevant.filter(x=>x.tag==='button'||x.role==='button'),
   combos:relevant.filter(x=>x.role==='combobox'||x.role==='listbox'),
   opciones:relevant.filter(x=>x.role==='option'||x.role==='menuitem'),
   enlaces:relevant.filter(x=>x.tag==='a').slice(0,160),
   coincidencias:samples,
   resumen_visible:short(document.body.innerText,2800)};
}"""


def pick_trigger(page):
    """Busca el desplegable de casas sin asumir que sea un <select> nativo."""
    candidates = [
        page.get_by_role('combobox'),
        page.locator('input[placeholder*="casa" i]'),
        page.locator('[aria-label*="casa" i]'),
        page.locator('button').filter(has_text=re.compile(r'casa\s+de\s+remat', re.I)),
        page.get_by_text(re.compile(r'casa\s+de\s+remat', re.I)),
    ]
    for candidate in candidates:
        try:
            for index in range(min(candidate.count(), 30)):
                element = candidate.nth(index)
                if not element.is_visible():
                    continue
                # Un select nativo ya expone sus opciones; no lo abrimos.
                if element.evaluate('(e)=>e.tagName.toLowerCase()') == 'select':
                    return None
                box = element.bounding_box()
                # Ignoramos bloques enormes (por ejemplo un contenedor de toda la página).
                if box and box['width'] < 500 and box['height'] < 180:
                    return element
        except Exception:
            continue
    return None


def main():
    parser = argparse.ArgumentParser(description='Inspección de DOM real sin alterar las pruebas')
    parser.add_argument('--url', default=URL)
    parser.add_argument('--headless', action='store_true')
    args = parser.parse_args()
    out = HERE / 'salidas' / ('diagnostico_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        launch_options = {'headless': args.headless}
        # Útil si otro laboratorio usa un Chromium propio. En el Envy no
        # hace falta: Playwright ya tiene su navegador instalado.
        if os.environ.get('PLAYWRIGHT_CHROMIUM_PATH'):
            launch_options['executable_path'] = os.environ['PLAYWRIGHT_CHROMIUM_PATH']
        browser = playwright.chromium.launch(**launch_options)
        page = browser.new_page(viewport={'width':1440,'height':900},locale='es-CL',timezone_id='America/Santiago')
        page.set_default_timeout(12000)
        data={'estado':'SIN_INICIAR','url_solicitada':args.url,'momento':datetime.now().astimezone().isoformat()}
        try:
            response=page.goto(args.url,wait_until='domcontentloaded',timeout=45000)
            page.locator('body').wait_for(state='visible',timeout=15000)
            data['http_status']=response.status if response else None
            portal = PortalPage(page, args.url)
            # Guardamos el DOM antes de cambiar nada. Esto permite corregir
            # localizadores incluso cuando falla el manejo de una ventana.
            data['dom_inicial']=page.evaluate(INSPECT_JS)
            page.screenshot(path=str(out/'estado-inicial.png'),animations='disabled')
            # Algunas ventanas se abren unos segundos después de cargar.
            # Aguardamos su presencia REAL, no solamente un título oculto.
            data['popup_visible_tras_espera']=portal.wait_for_subscription_popup(timeout_ms=5000)
            if data['popup_visible_tras_espera']:
                page.screenshot(path=str(out/'popup-detectado.png'),animations='disabled')
            data['popup_cerrado']=portal.dismiss_subscription_popup()
            # Esta barra es distinta al formulario de suscripción.
            data['cookies_rechazadas']=portal.dismiss_cookie_banner()
            data['popup_cerrado']=portal.dismiss_subscription_popup() or data['popup_cerrado']
            data['antes_de_abrir']=page.evaluate(INSPECT_JS)
            page.screenshot(path=str(out/'inicio.png'),animations='disabled')
            print('Página:',data['antes_de_abrir']['titulo'],'| URL:',page.url)
            target=pick_trigger(page)
            if target is None:
                data['desplegable']='No se identificó un control personalizado; revisar selects y coincidencias.'
            else:
                data['desplegable']='Intento de apertura con Playwright'
                data['control_html']=target.evaluate('(e)=>e.outerHTML.slice(0,2500)')
                print('Abriendo desplegable de casas…')
                target.click(timeout=7000)
                page.wait_for_timeout(800)
                data['despues_de_abrir']=page.evaluate(INSPECT_JS)
                page.screenshot(path=str(out/'dropdown-abierto.png'),animations='disabled')
                print('Captura del menú abierto guardada.')
            data['estado']='INSPECCION_REALIZADA'
        except Exception as exc:
            data['estado']='ERROR_DIAGNOSTICO'
            data['error']=f'{type(exc).__name__}: {exc}'
            try:
                page.screenshot(path=str(out/'error-diagnostico.png'),animations='disabled')
            except Exception:
                pass
        finally:
            (out/'elementos.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
            print('Archivos de diagnóstico:',out)
            print('Estado:',data['estado'])
            browser.close()

if __name__ == '__main__':
    main()
