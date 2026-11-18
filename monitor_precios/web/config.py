"""Configuración de la aplicación a partir de variables de entorno.

En local no hace falta definir nada. En Render las variables se configuran en render.yaml
(o en el panel Environment del servicio) y el propio Render agrega RENDER_GIT_COMMIT.
"""

import os


def _entero(nombre, defecto):
    valor = os.environ.get(nombre)
    return int(valor) if valor not in (None, "") else defecto


def desde_entorno():
    """Devuelve un diccionario con la configuración leída del entorno."""
    return {
        # carpeta donde están catalogo_ultimo.csv, articulo_ultimo.json e historial.csv
        "DATOS_DIR": os.environ.get("DATOS_DIR", "datos"),
        # development | production (solo cambia el nivel de detalle de los errores)
        "APP_ENV": os.environ.get("APP_ENV", "development"),
        # commit desplegado: Render lo pone solo; en Docker local se puede pasar APP_COMMIT
        "COMMIT": os.environ.get("RENDER_GIT_COMMIT") or os.environ.get("APP_COMMIT", "local"),
        # máximo de productos que devuelve /api/catalogo en una sola respuesta
        "LIMITE_MAXIMO": _entero("LIMITE_MAXIMO", 500),
        "POR_PAGINA": _entero("POR_PAGINA", 50),
    }
