"""Lectura de los datos que deja el scraping en la carpeta datos/.

La aplicación no hace scraping: solo lee los CSV y el JSON que guarda el workflow
programado. Así la página responde rápido y no depende de que Falabella esté arriba.
"""

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from monitor_precios import analisis

ARCHIVOS = ("catalogo_ultimo.csv", "articulo_ultimo.json", "historial.csv")


@dataclass
class Datos:
    catalogo: pd.DataFrame
    articulo: dict
    historial: pd.DataFrame
    indicadores: dict
    marcas: pd.DataFrame


_cache = {}


def _firma(carpeta):
    """Fecha de modificación de los tres archivos; si cambia alguno, se vuelven a leer."""
    return tuple((carpeta / nombre).stat().st_mtime_ns for nombre in ARCHIVOS)


def cargar(carpeta):
    """Lee los datos de la carpeta y los guarda en memoria hasta que cambien en disco."""
    carpeta = Path(carpeta)
    faltantes = [n for n in ARCHIVOS if not (carpeta / n).exists()]
    if faltantes:
        raise FileNotFoundError(f"Faltan archivos de datos en {carpeta}: {', '.join(faltantes)}")

    firma = _firma(carpeta)
    clave = str(carpeta.resolve())
    if clave in _cache and _cache[clave][0] == firma:
        return _cache[clave][1]

    catalogo = pd.read_csv(carpeta / "catalogo_ultimo.csv")
    catalogo["id_producto"] = catalogo["id_producto"].astype(str)
    articulo = json.loads((carpeta / "articulo_ultimo.json").read_text(encoding="utf-8"))
    historial = pd.read_csv(carpeta / "historial.csv")
    # la fila de la EA1 no tiene fuente porque esa columna se agregó después
    if "fuente" not in historial.columns:
        historial["fuente"] = "busqueda"
    historial["fuente"] = historial["fuente"].fillna("busqueda")

    datos = Datos(
        catalogo=catalogo,
        articulo=articulo,
        historial=historial,
        indicadores=analisis.indicadores_articulo(catalogo, articulo),
        marcas=analisis.resumen_marcas(catalogo),
    )
    _cache[clave] = (firma, datos)
    return datos


def histograma(catalogo, cubetas=20, percentil=0.95):
    """Agrupa los precios en rangos para la gráfica de barras del tablero.

    Dejo por fuera el 5 % más caro para que unos pocos modelos premium no aplasten la gráfica
    (lo mismo que hacía la gráfica de matplotlib de la Evidencia 2).
    """
    precios = catalogo["precio_oferta"]
    precios = precios[precios <= precios.quantile(percentil)]
    if precios.empty:
        return {"rangos": [], "conteos": []}
    cortes = pd.cut(precios, bins=cubetas)
    conteo = cortes.value_counts(sort=False)
    rangos = [f"{int(i.left / 1000)}k-{int(i.right / 1000)}k" for i in conteo.index]
    return {"rangos": rangos, "conteos": [int(c) for c in conteo.values]}


ORDENES = {
    "precio_asc": ("precio_oferta", True),
    "precio_desc": ("precio_oferta", False),
    "descuento": ("descuento_pct", False),
    "resenas": ("num_resenas", False),
}


def filtrar_catalogo(catalogo, marca=None, texto=None, precio_min=None, precio_max=None,
                     orden="precio_asc"):
    """Filtra y ordena el catálogo con los parámetros que llegan por la URL."""
    df = catalogo
    if marca:
        df = df[df["marca"].str.upper() == marca.strip().upper()]
    if texto:
        df = df[df["nombre"].str.contains(texto.strip(), case=False, na=False, regex=False)]
    if precio_min is not None:
        df = df[df["precio_oferta"] >= precio_min]
    if precio_max is not None:
        df = df[df["precio_oferta"] <= precio_max]
    if orden not in ORDENES:
        raise ValueError(f"Orden no válido: {orden}. Use uno de {', '.join(ORDENES)}")
    columna, ascendente = ORDENES[orden]
    return df.sort_values(columna, ascending=ascendente, kind="stable")


def a_registros(df):
    """DataFrame -> lista de diccionarios lista para JSON (sin NaN)."""
    return json.loads(df.to_json(orient="records", force_ascii=False))
