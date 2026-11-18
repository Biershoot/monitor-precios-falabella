"""Pruebas de la aplicación web y de la API REST.

Uso el cliente de pruebas de Flask, así que no hace falta levantar un servidor.
Los datos se arman en una carpeta temporal con los mismos HTML de ejemplo de conftest.py.
"""

import json

import pandas as pd
import pytest

from monitor_precios import __main__ as cli
from monitor_precios import analisis, extraccion, limpieza
from monitor_precios.web import create_app
from monitor_precios.web import datos as web_datos


@pytest.fixture
def carpeta_datos(tmp_path, html_busqueda, articulo):
    catalogo = limpieza.limpiar_catalogo(extraccion.parsear_busqueda(html_busqueda))
    articulo = {**articulo, "id_producto": "4"}       # el Lenovo hace de artículo
    ind = analisis.indicadores_articulo(catalogo, articulo)
    hist = analisis.agregar_historial(None, analisis.fila_historial("2026-11-09", ind))
    hist = analisis.agregar_historial(hist, analisis.fila_historial("2026-11-16", ind))
    carpeta = tmp_path / "datos"
    carpeta.mkdir()
    catalogo.to_csv(carpeta / "catalogo_ultimo.csv", index=False)
    hist.to_csv(carpeta / "historial.csv", index=False)
    (carpeta / "articulo_ultimo.json").write_text(json.dumps(articulo), encoding="utf-8")
    return carpeta


@pytest.fixture
def cliente(carpeta_datos):
    app = create_app({"TESTING": True, "DATOS_DIR": str(carpeta_datos), "COMMIT": "abc1234def",
                      "POR_PAGINA": 2})
    return app.test_client()


# ------------------------------------------------------------------ páginas HTML

def test_tablero(cliente):
    respuesta = cliente.get("/")
    assert respuesta.status_code == 200
    html = respuesta.get_data(as_text=True)
    assert "Redmi Buds 6 Play" in html
    assert "$59.900" in html
    assert "2026-11-16" in html          # fecha de la última extracción
    assert "graficaHistorial" in html
    assert "abc1234" in html             # commit desplegado en el pie de página


def test_catalogo_con_filtros_y_paginacion(cliente):
    html = cliente.get("/catalogo").get_data(as_text=True)
    assert "4 productos encontrados" in html
    assert "Página 1 de 2" in html

    html = cliente.get("/catalogo?marca=sony").get_data(as_text=True)
    assert "1 productos encontrados" in html
    assert "Sony WF-C510" in html

    html = cliente.get("/catalogo?pagina=2").get_data(as_text=True)
    assert "Página 2 de 2" in html


def test_catalogo_resalta_el_articulo(cliente):
    html = cliente.get("/catalogo?q=lenovo").get_data(as_text=True)
    assert 'class="resaltado"' in html


def test_catalogo_sin_resultados(cliente):
    html = cliente.get("/catalogo?precio_max=1000").get_data(as_text=True)
    assert "No hay productos con esos filtros" in html


def test_pagina_inexistente_responde_html(cliente):
    respuesta = cliente.get("/no-existe")
    assert respuesta.status_code == 404
    assert "Error 404" in respuesta.get_data(as_text=True)


def test_parametro_invalido_en_pagina(cliente):
    respuesta = cliente.get("/catalogo?precio_max=barato")
    assert respuesta.status_code == 400


# ------------------------------------------------------------------ API REST

def test_api_salud(cliente):
    respuesta = cliente.get("/api/salud")
    assert respuesta.status_code == 200
    cuerpo = respuesta.get_json()
    assert cuerpo["estado"] == "ok"
    assert cuerpo["commit"] == "abc1234def"
    assert cuerpo["ultima_extraccion"] == "2026-11-16"
    assert cuerpo["productos"] == 4


def test_api_salud_sin_datos(tmp_path):
    app = create_app({"TESTING": True, "DATOS_DIR": str(tmp_path / "vacia")})
    respuesta = app.test_client().get("/api/salud")
    assert respuesta.status_code == 503
    assert respuesta.get_json()["estado"] == "degradado"


def test_api_indicadores_y_articulo(cliente):
    ind = cliente.get("/api/indicadores").get_json()
    assert ind["fecha"] == "2026-11-16"
    assert ind["precio_articulo"] == 59900
    assert ind["productos_catalogo"] == 4
    assert cliente.get("/api/articulo").get_json()["marca"] == "XIAOMI"


def test_api_historial(cliente):
    historial = cliente.get("/api/historial").get_json()
    assert [f["fecha"] for f in historial] == ["2026-11-09", "2026-11-16"]


def test_api_marcas(cliente):
    marcas = cliente.get("/api/marcas?top=2").get_json()
    assert len(marcas) == 2
    assert {"marca", "productos", "precio_mediano"} <= set(marcas[0])


@pytest.mark.parametrize("consulta, esperados", [
    ("", ["2", "4", "3", "1"]),                          # más barato primero
    ("?orden=precio_desc", ["1", "3", "4", "2"]),
    ("?orden=resenas", ["3", "1", "4", "2"]),
    ("?precio_min=50000&precio_max=200000", ["4", "3"]),
    ("?q=jbl", ["1"]),
    ("?marca=SIN MARCA", ["2"]),
])
def test_api_catalogo_filtros(cliente, consulta, esperados):
    cuerpo = cliente.get("/api/catalogo" + consulta).get_json()
    assert [p["id_producto"] for p in cuerpo["productos"]] == esperados
    assert cuerpo["total"] == len(esperados)


def test_api_catalogo_limite_y_desde(cliente):
    cuerpo = cliente.get("/api/catalogo?limite=2&desde=1").get_json()
    assert cuerpo["total"] == 4
    assert [p["id_producto"] for p in cuerpo["productos"]] == ["4", "3"]


@pytest.mark.parametrize("consulta", ["?precio_max=abc", "?limite=0", "?orden=nombre"])
def test_api_catalogo_parametros_invalidos(cliente, consulta):
    respuesta = cliente.get("/api/catalogo" + consulta)
    assert respuesta.status_code == 400
    assert "error" in respuesta.get_json()


def test_api_ruta_inexistente(cliente):
    respuesta = cliente.get("/api/precios")
    assert respuesta.status_code == 404
    assert respuesta.get_json()["error"].startswith("No existe")


def test_api_sin_datos_responde_503(tmp_path):
    app = create_app({"TESTING": True, "DATOS_DIR": str(tmp_path)})
    cliente = app.test_client()
    assert cliente.get("/api/indicadores").status_code == 503
    assert cliente.get("/").status_code == 503


# ------------------------------------------------------------------ módulo de datos

def test_cache_se_actualiza_cuando_cambian_los_archivos(carpeta_datos):
    primero = web_datos.cargar(carpeta_datos)
    assert web_datos.cargar(carpeta_datos) is primero          # sin cambios: misma copia

    hist = pd.read_csv(carpeta_datos / "historial.csv")
    hist.loc[len(hist)] = hist.iloc[-1]
    hist.loc[len(hist) - 1, "fecha"] = "2026-11-23"
    hist.to_csv(carpeta_datos / "historial.csv", index=False)

    segundo = web_datos.cargar(carpeta_datos)
    assert segundo is not primero
    assert segundo.historial["fecha"].iloc[-1] == "2026-11-23"


def test_historial_sin_columna_fuente(carpeta_datos):
    hist = pd.read_csv(carpeta_datos / "historial.csv").drop(columns="fuente")
    hist.to_csv(carpeta_datos / "historial.csv", index=False)
    assert set(web_datos.cargar(carpeta_datos).historial["fuente"]) == {"busqueda"}


def test_histograma_vacio():
    vacio = pd.DataFrame({"precio_oferta": pd.Series(dtype=float)})
    assert web_datos.histograma(vacio) == {"rangos": [], "conteos": []}


def test_configuracion_desde_entorno(monkeypatch):
    monkeypatch.setenv("RENDER_GIT_COMMIT", "f00baa")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("LIMITE_MAXIMO", "20")
    app = create_app()
    assert app.config["COMMIT"] == "f00baa"
    assert app.config["APP_ENV"] == "production"
    assert app.config["LIMITE_MAXIMO"] == 20


def test_comando_servidor(monkeypatch):
    llamadas = {}
    monkeypatch.setattr("flask.Flask.run", lambda self, **kw: llamadas.update(kw))
    assert cli.main(["servidor", "--puerto", "8080"]) == 0
    assert llamadas == {"host": "127.0.0.1", "port": 8080, "debug": False}
