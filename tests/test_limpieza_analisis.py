import pandas as pd
import pytest

from monitor_precios import analisis, extraccion, limpieza


@pytest.fixture
def catalogo(html_busqueda):
    productos = extraccion.parsear_busqueda(html_busqueda)
    productos.append(dict(productos[0]))                                   # repetido
    productos.append({**productos[1], "id_producto": "99", "precio_oferta": None})  # sin precio
    return limpieza.limpiar_catalogo(productos)


def test_limpieza_quita_repetidos_y_sin_precio(catalogo):
    assert len(catalogo) == 4
    assert catalogo["id_producto"].is_unique


def test_limpieza_marca_vacia(catalogo):
    assert "SIN MARCA" in catalogo["marca"].values
    assert "LENOVO" in catalogo["marca"].values


def test_limpieza_calcula_descuento(catalogo):
    sony = catalogo[catalogo["marca"] == "SONY"].iloc[0]
    assert sony["descuento_pct"] == pytest.approx(47.1, abs=0.1)


def test_limpieza_corrige_precio_normal_menor():
    df = limpieza.limpiar_catalogo([{"id_producto": 1, "precio_oferta": 50000,
                                     "precio_normal": 40000}])
    assert df.loc[0, "precio_normal"] == 50000
    assert df.loc[0, "descuento_pct"] == 0


def test_indicadores_articulo(catalogo, articulo):
    ind = analisis.indicadores_articulo(catalogo, articulo)
    assert ind["productos_catalogo"] == 4
    assert ind["precio_articulo"] == 59900
    assert ind["descuento_articulo"] == pytest.approx(40.0, abs=0.1)
    assert ind["pct_mas_baratos_que_articulo"] == 25.0   # solo el genérico de $25.000
    assert ind["precio_mediano_catalogo"] == pytest.approx(119900)
    assert ind["pct_patrocinados"] == 25.0


def test_indicadores_catalogo_vacio(articulo):
    with pytest.raises(ValueError):
        analisis.indicadores_articulo(pd.DataFrame(), articulo)


def test_resumen_marcas(catalogo):
    resumen = analisis.resumen_marcas(catalogo, top=2)
    assert len(resumen) == 2
    assert set(resumen.columns) == {"marca", "productos", "precio_mediano",
                                    "descuento_prom", "resenas_totales"}


def test_historial_reemplaza_misma_fecha(catalogo, articulo):
    ind = analisis.indicadores_articulo(catalogo, articulo)
    hist = analisis.agregar_historial(None, analisis.fila_historial("2026-10-22", ind))
    hist = analisis.agregar_historial(hist, analisis.fila_historial("2026-11-04", ind))
    hist = analisis.agregar_historial(hist, analisis.fila_historial("2026-11-04", ind))
    assert list(hist["fecha"]) == ["2026-10-22", "2026-11-04"]
