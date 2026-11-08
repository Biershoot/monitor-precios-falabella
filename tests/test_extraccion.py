import pytest

from monitor_precios import extraccion


@pytest.mark.parametrize("texto, esperado", [
    ("$ 59.900", 59900),
    ("1.299.900", 1299900),
    ("99900", 99900),
    ("", None),
    (None, None),
    ("sin precio", None),
])
def test_a_numero(texto, esperado):
    assert extraccion.a_numero(texto) == esperado


def test_extraer_next_data_sin_bloque_lanza_error():
    with pytest.raises(ValueError):
        extraccion.extraer_next_data("<html><body>Hola</body></html>")


def test_leer_precios_y_oferta():
    precios = extraccion.leer_precios([
        {"type": "internetPrice", "price": ["120.990"]},
        {"type": "normalPrice", "price": ["150.000"]},
        {"type": "cmrPrice", "price": ["99.990"]},
        {"type": "eventPrice", "price": []},
    ])
    assert precios == {"internetPrice": 120990, "normalPrice": 150000, "cmrPrice": 99990}
    # el precio CMR no cuenta como oferta porque solo aplica con la tarjeta
    assert extraccion.precio_oferta(precios) == 120990


def test_precio_oferta_solo_normal():
    assert extraccion.precio_oferta({"normalPrice": 80000}) == 80000


def test_parsear_busqueda(html_busqueda):
    productos = extraccion.parsear_busqueda(html_busqueda, pagina=2)
    assert len(productos) == 4
    primero = productos[0]
    assert primero["pagina"] == 2
    assert primero["posicion"] == 1
    assert primero["marca"] == "JBL"
    assert primero["precio_oferta"] == 239900
    assert primero["precio_normal"] == 499900
    assert primero["precio_cmr"] == 229900
    assert primero["calificacion"] == 4.5
    assert primero["num_resenas"] == 120
    assert primero["patrocinado"] is True
    assert productos[3]["marca"] == "LENOVO"


def test_parsear_busqueda_vacia(html_busqueda_vacia):
    assert extraccion.parsear_busqueda(html_busqueda_vacia) == []


def test_parsear_articulo(html_articulo):
    art = extraccion.parsear_articulo(html_articulo)
    assert art["id_producto"] == "73025565"
    assert art["marca"] == "XIAOMI"
    assert art["vendedor"] == "FALABELLA"
    assert art["precio_oferta"] == 59900
    assert art["precio_normal"] == 99900


def test_scrapear_catalogo_se_detiene_en_pagina_vacia(html_busqueda, html_busqueda_vacia):
    urls = []

    def falso_descargar(url):
        urls.append(url)
        return html_busqueda if len(urls) <= 2 else html_busqueda_vacia

    productos = extraccion.scrapear_catalogo("audifonos inalambricos", paginas=5, pausa=0,
                                             descargar_fn=falso_descargar)
    assert len(productos) == 8          # 2 páginas x 4 productos
    assert len(urls) == 3               # la tercera viene vacía y se detiene
    assert "Ntt=audifonos+inalambricos&page=1" in urls[0]


class SesionFalsa:
    """Reemplaza requests.Session para no salir a internet."""

    def __init__(self, texto):
        self.texto = texto

    def get(self, url, headers=None, timeout=None):
        sesion = self

        class Respuesta:
            text = sesion.texto
            content = sesion.texto.encode("utf-8")

            def raise_for_status(self):
                pass

        return Respuesta()


def test_puede_rastrear_respeta_robots():
    robots = "User-agent: *\nDisallow: /cgi-bin/\n"
    sesion = SesionFalsa(robots)
    url_ok = extraccion.URL_BUSQUEDA.format(busqueda="audifonos", pagina=1)
    assert extraccion.puede_rastrear(url_ok, sesion=sesion) is True
    url_carrito = extraccion.BASE + "/cgi-bin/prueba"
    assert extraccion.puede_rastrear(url_carrito, sesion=sesion) is False


def test_descargar_decodifica_utf8():
    assert extraccion.descargar("https://x", sesion=SesionFalsa("Audífonos")) == "Audífonos"


def test_respaldo_usa_categoria_si_la_busqueda_falla(html_busqueda, html_busqueda_vacia):
    """Si la búsqueda no trae productos (statusCode 500 del 8-nov) se usa la categoría."""
    urls = []

    def falso_descargar(url):
        urls.append(url)
        if "/search?" in url:
            return html_busqueda_vacia
        return html_busqueda if "page=1" in url else html_busqueda_vacia

    productos, fuente = extraccion.scrapear_con_respaldo(paginas=3, pausa=0,
                                                         descargar_fn=falso_descargar)
    assert fuente == "categoria"
    assert len(productos) == 4
    assert "/category/cat50670/" in urls[1]


def test_respaldo_no_se_usa_si_la_busqueda_funciona(html_busqueda, html_busqueda_vacia):
    paginas = iter([html_busqueda, html_busqueda_vacia])
    productos, fuente = extraccion.scrapear_con_respaldo(paginas=3, pausa=0,
                                                         descargar_fn=lambda url: next(paginas))
    assert fuente == "busqueda"
    assert len(productos) == 4
