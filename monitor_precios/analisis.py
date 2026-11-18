"""Indicadores para saber qué tan competitivo es el artículo frente al catálogo."""

import pandas as pd


def indicadores_articulo(catalogo, articulo):
    """Compara el artículo contra el catálogo y devuelve un diccionario de indicadores."""
    if catalogo.empty:
        raise ValueError("El catálogo está vacío, no hay con qué comparar")
    precio = articulo["precio_oferta"]
    normal = articulo.get("precio_normal") or precio
    descuento = round((1 - precio / normal) * 100, 1) if normal else 0.0
    mas_baratos = (catalogo["precio_oferta"] < precio).mean() * 100
    return {
        "productos_catalogo": int(len(catalogo)),
        "precio_articulo": int(precio),
        "precio_mediano_catalogo": float(catalogo["precio_oferta"].median()),
        "pct_mas_baratos_que_articulo": round(float(mas_baratos), 1),
        "descuento_articulo": descuento,
        "descuento_promedio_catalogo": round(float(catalogo["descuento_pct"].mean()), 1),
        "pct_patrocinados": round(float(catalogo["patrocinado"].mean() * 100), 1),
    }


def resumen_marcas(catalogo, top=10):
    """Tabla con las marcas que más productos tienen en la búsqueda."""
    resumen = (catalogo.groupby("marca")
               .agg(productos=("id_producto", "count"),
                    precio_mediano=("precio_oferta", "median"),
                    descuento_prom=("descuento_pct", "mean"),
                    resenas_totales=("num_resenas", "sum"))
               .sort_values(["productos", "resenas_totales"], ascending=False)
               .head(top))
    resumen["descuento_prom"] = resumen["descuento_prom"].round(1)
    return resumen.reset_index()


def fila_historial(fecha, indicadores, fuente="busqueda"):
    """Arma la fila que se agrega a datos/historial.csv en cada ejecución.

    fuente indica si los datos salieron de la búsqueda o de la categoría (respaldo).
    """
    return {
        "fecha": str(fecha),
        "productos": indicadores["productos_catalogo"],
        "precio_mediano": indicadores["precio_mediano_catalogo"],
        "descuento_promedio": indicadores["descuento_promedio_catalogo"],
        "precio_articulo": indicadores["precio_articulo"],
        "pct_mas_baratos": indicadores["pct_mas_baratos_que_articulo"],
        "fuente": fuente,
    }


def agregar_historial(historial, fila):
    """Agrega la fila al historial; si ya había una de la misma fecha la reemplaza."""
    nueva = pd.DataFrame([fila])
    if historial is None or historial.empty:
        return nueva
    historial = historial[historial["fecha"].astype(str) != str(fila["fecha"])]
    return (pd.concat([historial, nueva], ignore_index=True)
            .sort_values("fecha").reset_index(drop=True))


def cambio_precio(historial):
    """Compara el precio del artículo en las dos últimas extracciones.

    Devuelve un diccionario con el cambio, o None si el precio sigue igual
    (o si todavía no hay dos fechas para comparar).
    """
    if historial is None or len(historial) < 2:
        return None
    anterior, actual = historial.iloc[-2], historial.iloc[-1]
    if int(anterior["precio_articulo"]) == int(actual["precio_articulo"]):
        return None
    variacion = (actual["precio_articulo"] / anterior["precio_articulo"] - 1) * 100
    return {
        "fecha_anterior": str(anterior["fecha"]),
        "precio_anterior": int(anterior["precio_articulo"]),
        "fecha": str(actual["fecha"]),
        "precio": int(actual["precio_articulo"]),
        "variacion_pct": round(float(variacion), 1),
    }
