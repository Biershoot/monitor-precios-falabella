"""Limpieza del catálogo extraído."""

import pandas as pd

COLUMNAS = ["pagina", "posicion", "id_producto", "nombre", "marca", "vendedor",
            "precio_oferta", "precio_normal", "precio_cmr", "calificacion",
            "num_resenas", "patrocinado", "url"]


def limpiar_catalogo(productos):
    """Recibe la lista de productos (o un DataFrame) y la deja lista para analizar.

    - quita productos repetidos (el mismo id puede salir en dos páginas)
    - quita productos sin precio
    - corrige el precio normal cuando viene vacío o menor que la oferta
    - calcula el porcentaje de descuento
    """
    df = pd.DataFrame(productos).copy()
    for col in COLUMNAS:
        if col not in df.columns:
            df[col] = None
    df = df[COLUMNAS]

    df["id_producto"] = df["id_producto"].astype(str)
    df = df.drop_duplicates(subset="id_producto", keep="first")

    df["precio_oferta"] = pd.to_numeric(df["precio_oferta"], errors="coerce")
    df["precio_normal"] = pd.to_numeric(df["precio_normal"], errors="coerce")
    df = df.dropna(subset=["precio_oferta"])
    df = df[df["precio_oferta"] > 0]

    sin_normal = df["precio_normal"].isna() | (df["precio_normal"] < df["precio_oferta"])
    df.loc[sin_normal, "precio_normal"] = df.loc[sin_normal, "precio_oferta"]

    df["marca"] = df["marca"].fillna("").astype(str).str.strip().str.upper()
    df.loc[df["marca"] == "", "marca"] = "SIN MARCA"

    df["calificacion"] = pd.to_numeric(df["calificacion"], errors="coerce").fillna(0.0)
    df["num_resenas"] = pd.to_numeric(df["num_resenas"], errors="coerce").fillna(0).astype(int)
    df["patrocinado"] = df["patrocinado"].fillna(False).astype(bool)

    df["descuento_pct"] = ((1 - df["precio_oferta"] / df["precio_normal"]) * 100).round(1)
    df["precio_oferta"] = df["precio_oferta"].astype(int)
    df["precio_normal"] = df["precio_normal"].astype(int)
    return df.reset_index(drop=True)
