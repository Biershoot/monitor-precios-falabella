import json

import pandas as pd

from monitor_precios import __main__ as cli
from monitor_precios import analisis, extraccion, limpieza, reporte


def test_pesos():
    assert reporte.pesos(59900) == "$59.900"
    assert reporte.pesos(1299900.4) == "$1.299.900"


def test_generar_sitio(tmp_path, html_busqueda, articulo):
    catalogo = limpieza.limpiar_catalogo(extraccion.parsear_busqueda(html_busqueda))
    ind = analisis.indicadores_articulo(catalogo, articulo)
    hist = analisis.agregar_historial(None, analisis.fila_historial("2026-11-04", ind))
    resumen = analisis.resumen_marcas(catalogo)

    index = reporte.generar_sitio(catalogo, articulo, hist, ind, resumen, tmp_path / "sitio")

    contenido = index.read_text(encoding="utf-8")
    assert "Redmi Buds 6 Play" in contenido
    assert "$59.900" in contenido
    for archivo in ["precios.png", "marcas.png", "historial.png", "catalogo.csv",
                    "historial.csv"]:
        assert (tmp_path / "sitio" / archivo).exists()


def test_cli_scrapear_y_reporte(tmp_path, monkeypatch, html_busqueda, html_busqueda_vacia,
                                html_articulo):
    """Prueba el flujo completo del comando sin conectarse a internet."""
    monkeypatch.chdir(tmp_path)
    paginas = iter([html_busqueda, html_busqueda_vacia])
    monkeypatch.setattr(extraccion, "puede_rastrear", lambda url: True)
    monkeypatch.setattr(extraccion, "descargar",
                        lambda url: html_articulo if "product" in url else next(paginas))

    codigo = cli.main(["scrapear", "--pausa", "0", "--minimo", "3", "--fecha", "2026-11-04"])
    assert codigo == 0
    assert (tmp_path / "datos" / "catalogos" / "catalogo_2026-11-04.csv").exists()
    hist = pd.read_csv(tmp_path / "datos" / "historial.csv")
    assert hist.loc[0, "precio_articulo"] == 59900
    art = json.loads((tmp_path / "datos" / "articulo_ultimo.json").read_text(encoding="utf-8"))
    assert art["marca"] == "XIAOMI"

    assert cli.main(["reporte", "--salida", "sitio"]) == 0
    assert (tmp_path / "sitio" / "index.html").exists()


def test_cli_scrapear_falla_con_pocos_productos(tmp_path, monkeypatch, html_busqueda_vacia):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(extraccion, "puede_rastrear", lambda url: True)
    monkeypatch.setattr(extraccion, "descargar", lambda url: html_busqueda_vacia)
    assert cli.main(["scrapear", "--pausa", "0"]) == 1
    assert not (tmp_path / "datos" / "historial.csv").exists()


def test_cli_respeta_robots(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(extraccion, "puede_rastrear", lambda url: False)
    assert cli.main(["scrapear"]) == 1
