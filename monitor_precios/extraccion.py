"""Extracción de datos de Falabella Colombia.

Retomo la lógica de la Evidencia 1: en vez de leer las clases CSS (que cambian
seguido porque las genera Next.js), leo el JSON que viene en la etiqueta
<script id="__NEXT_DATA__">. Aquí lo dejé separado en funciones pequeñas
para poder probar cada una con pytest sin tener que conectarme a internet.
"""

import json
import time
from urllib import robotparser

import requests
from bs4 import BeautifulSoup

BASE = "https://www.falabella.com.co"
URL_BUSQUEDA = BASE + "/falabella-co/search?Ntt={busqueda}&page={pagina}"
URL_ARTICULO = (BASE + "/falabella-co/product/73025565/"
                "Audifonos-earbuds-Xiaomi-Bluetooth-Redmi-Buds-6-Play-Ng")

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"),
    "Accept-Language": "es-CO,es;q=0.9",
}


def a_numero(texto):
    """Convierte un precio como '$ 59.900' en el entero 59900."""
    if texto is None:
        return None
    digitos = "".join(c for c in str(texto) if c.isdigit())
    return int(digitos) if digitos else None


def extraer_next_data(html):
    """Devuelve el diccionario que viene dentro de <script id="__NEXT_DATA__">."""
    soup = BeautifulSoup(html, "html.parser")
    etiqueta = soup.find("script", id="__NEXT_DATA__")
    if etiqueta is None or not etiqueta.string:
        raise ValueError("La página no trae el bloque __NEXT_DATA__")
    return json.loads(etiqueta.string)


def leer_precios(lista_precios):
    """Pasa la lista de precios de Falabella a un diccionario {tipo: valor}.

    Falabella maneja internetPrice (oferta), normalPrice (tachado),
    cmrPrice (con tarjeta CMR) y a veces eventPrice.
    """
    precios = {}
    for precio in lista_precios or []:
        valores = precio.get("price") or []
        if valores:
            precios[precio.get("type")] = a_numero(valores[0])
    return precios


def precio_oferta(precios):
    """El precio de oferta es el menor de los que no son el precio normal.

    Dejo por fuera el precio CMR porque solo aplica a quien tiene la tarjeta.
    """
    ofertas = [v for k, v in precios.items() if k not in ("normalPrice", "cmrPrice") and v]
    if ofertas:
        return min(ofertas)
    return precios.get("normalPrice")


def parsear_busqueda(html, pagina=1):
    """Saca la lista de productos de una página de resultados de búsqueda."""
    datos = extraer_next_data(html)
    resultados = datos.get("props", {}).get("pageProps", {}).get("results", []) or []
    productos = []
    for posicion, p in enumerate(resultados, start=1):
        precios = leer_precios(p.get("prices"))
        oferta = precio_oferta(precios)
        productos.append({
            "pagina": pagina,
            "posicion": posicion,
            "id_producto": p.get("productId"),
            "nombre": p.get("displayName"),
            "marca": (p.get("brand") or "").strip().upper(),
            "vendedor": p.get("sellerName"),
            "precio_oferta": oferta,
            "precio_normal": precios.get("normalPrice") or oferta,
            "precio_cmr": precios.get("cmrPrice"),
            "calificacion": float(p.get("rating") or 0),
            "num_resenas": int(p.get("totalReviews") or 0),
            "patrocinado": bool(p.get("isSponsored", False)),
            "url": p.get("url"),
        })
    return productos


def parsear_articulo(html, url=URL_ARTICULO):
    """Saca los datos principales de la ficha de un producto."""
    producto = extraer_next_data(html)["props"]["pageProps"]["productData"]
    variante = producto["variants"][0]
    precios = leer_precios(variante.get("prices"))
    ofertas = variante.get("offerings") or []
    return {
        "id_producto": producto.get("id"),
        "nombre": producto.get("name"),
        "marca": (producto.get("brandName") or "").strip().upper(),
        "vendedor": ofertas[0].get("sellerName") if ofertas else None,
        "precio_oferta": precio_oferta(precios),
        "precio_normal": precios.get("normalPrice"),
        "url": url,
    }


def puede_rastrear(url, user_agent="*"):
    """Revisa el robots.txt antes de scrapear (lo mismo que hice en la EA1)."""
    rp = robotparser.RobotFileParser()
    rp.set_url(BASE + "/robots.txt")
    rp.read()
    return rp.can_fetch(user_agent, url)


def descargar(url, sesion=None, timeout=30):
    """Descarga una página y la devuelve como texto en UTF-8."""
    sesion = sesion or requests.Session()
    respuesta = sesion.get(url, headers=HEADERS, timeout=timeout)
    respuesta.raise_for_status()
    # Si dejo que requests adivine la codificación, las tildes salen dañadas
    return respuesta.content.decode("utf-8", errors="replace")


def scrapear_catalogo(busqueda="audifonos inalambricos", paginas=5, pausa=1.5, descargar_fn=None):
    """Recorre varias páginas de la búsqueda y junta todos los productos.

    descargar_fn se puede reemplazar en las pruebas para no usar internet.
    """
    descargar_fn = descargar_fn or descargar
    productos = []
    for pagina in range(1, paginas + 1):
        url = URL_BUSQUEDA.format(busqueda=busqueda.replace(" ", "+"), pagina=pagina)
        html = descargar_fn(url)
        nuevos = parsear_busqueda(html, pagina)
        if not nuevos:  # si una página viene vacía ya no hay más resultados
            break
        productos.extend(nuevos)
        if pausa:
            time.sleep(pausa)  # pausa para no saturar el servidor
    return productos
