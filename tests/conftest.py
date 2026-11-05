"""Datos de prueba.

Armo páginas HTML falsas con la misma estructura de __NEXT_DATA__ que usa
Falabella, para que las pruebas no dependan de internet ni de los precios del día.
"""

import json

import pytest


def pagina_html(datos):
    return ("<html><head><title>Falabella</title></head><body>"
            '<script id="__NEXT_DATA__" type="application/json">'
            + json.dumps(datos, ensure_ascii=False)
            + "</script></body></html>")


def producto(pid, nombre, marca, oferta, normal=None, cmr=None, rating="0", reviews="0",
             patrocinado=False):
    precios = [{"type": "internetPrice", "price": [f"{oferta:,}".replace(",", ".")]}]
    if normal:
        precios.append({"type": "normalPrice", "price": [f"{normal:,}".replace(",", ".")]})
    if cmr:
        precios.append({"type": "cmrPrice", "price": [f"{cmr:,}".replace(",", ".")]})
    return {"productId": pid, "displayName": nombre, "brand": marca, "sellerName": "Tienda X",
            "prices": precios, "rating": rating, "totalReviews": reviews,
            "isSponsored": patrocinado, "url": f"https://www.falabella.com.co/p/{pid}"}


@pytest.fixture
def productos_busqueda():
    return [
        producto("1", "Audífonos JBL Tune", "jbl", 239900, 499900, cmr=229900,
                 rating="4.5", reviews="120", patrocinado=True),
        producto("2", "Audífonos genéricos M10", "", 25000, 50000),
        producto("3", "Audífonos Sony WF-C510", "SONY", 179900, 339900, rating="4.54",
                 reviews="904"),
        producto("4", "Audífonos Lenovo LP40", " lenovo ", 59900, 89900, rating="4.1",
                 reviews="30"),
    ]


@pytest.fixture
def html_busqueda(productos_busqueda):
    return pagina_html({"props": {"pageProps": {"results": productos_busqueda}}})


@pytest.fixture
def html_busqueda_vacia():
    return pagina_html({"props": {"pageProps": {"results": []}}})


@pytest.fixture
def html_articulo():
    datos = {"props": {"pageProps": {"productData": {
        "id": "73025565",
        "name": "Audífonos earbuds Xiaomi Bluetooth Redmi Buds 6 Play",
        "brandName": "Xiaomi",
        "variants": [{
            "prices": [{"type": "internetPrice", "price": ["59.900"]},
                       {"type": "normalPrice", "price": ["99.900"]}],
            "offerings": [{"sellerName": "FALABELLA"}],
        }],
    }}}}
    return pagina_html(datos)


@pytest.fixture
def articulo():
    return {"id_producto": "73025565", "nombre": "Redmi Buds 6 Play", "marca": "XIAOMI",
            "precio_oferta": 59900, "precio_normal": 99900}
