"""Punto de entrada: python -m monitor_precios <comando>

Comandos:
  scrapear   descarga el catálogo y la ficha del artículo y actualiza datos/
  reporte    genera el sitio estático en sitio/ a partir de los datos guardados
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from monitor_precios import analisis, extraccion, limpieza, reporte

DATOS = Path("datos")


def comando_scrapear(args):
    url_prueba = extraccion.URL_BUSQUEDA.format(busqueda="audifonos", pagina=1)
    if not extraccion.puede_rastrear(url_prueba):
        print("El robots.txt no permite rastrear la búsqueda. Me detengo.")
        return 1

    productos, fuente = extraccion.scrapear_con_respaldo(args.busqueda, args.paginas, args.pausa)
    print(f"Fuente de los datos: {fuente}")
    catalogo = limpieza.limpiar_catalogo(productos)
    if len(catalogo) < args.minimo:
        # Si Falabella bloquea la petición o cambia la página, prefiero fallar
        # antes que guardar datos incompletos y dañar el historial.
        print(f"Solo se obtuvieron {len(catalogo)} productos (mínimo {args.minimo}).")
        return 1

    articulo = extraccion.parsear_articulo(extraccion.descargar(extraccion.URL_ARTICULO))
    hoy = args.fecha or date.today().isoformat()

    (DATOS / "catalogos").mkdir(parents=True, exist_ok=True)
    catalogo.to_csv(DATOS / "catalogos" / f"catalogo_{hoy}.csv", index=False, encoding="utf-8-sig")
    catalogo.to_csv(DATOS / "catalogo_ultimo.csv", index=False, encoding="utf-8-sig")
    (DATOS / "articulo_ultimo.json").write_text(
        json.dumps(articulo, ensure_ascii=False, indent=2), encoding="utf-8")

    indicadores = analisis.indicadores_articulo(catalogo, articulo)
    ruta_hist = DATOS / "historial.csv"
    historial = pd.read_csv(ruta_hist) if ruta_hist.exists() else None
    fila = analisis.fila_historial(hoy, indicadores, fuente)
    historial = analisis.agregar_historial(historial, fila)
    historial.to_csv(ruta_hist, index=False)

    print(f"{len(catalogo)} productos guardados. Indicadores: {indicadores}")
    return 0


def comando_reporte(args):
    catalogo = pd.read_csv(DATOS / "catalogo_ultimo.csv")
    articulo = json.loads((DATOS / "articulo_ultimo.json").read_text(encoding="utf-8"))
    historial = pd.read_csv(DATOS / "historial.csv")
    indicadores = analisis.indicadores_articulo(catalogo, articulo)
    resumen = analisis.resumen_marcas(catalogo)
    ruta = reporte.generar_sitio(catalogo, articulo, historial, indicadores, resumen, args.salida)
    print(f"Sitio generado en {ruta}")
    return 0


def crear_parser():
    parser = argparse.ArgumentParser(prog="monitor_precios",
                                     description="Monitor de precios de audífonos en Falabella")
    sub = parser.add_subparsers(dest="comando", required=True)

    p_scr = sub.add_parser("scrapear", help="Extrae los datos y actualiza el historial")
    p_scr.add_argument("--busqueda", default="audifonos inalambricos")
    p_scr.add_argument("--paginas", type=int, default=5)
    p_scr.add_argument("--pausa", type=float, default=1.5)
    p_scr.add_argument("--minimo", type=int, default=100,
                       help="Número mínimo de productos para aceptar la extracción")
    p_scr.add_argument("--fecha", help="Fecha a registrar (por defecto, hoy)")
    p_scr.set_defaults(func=comando_scrapear)

    p_rep = sub.add_parser("reporte", help="Genera el sitio estático")
    p_rep.add_argument("--salida", default="sitio")
    p_rep.set_defaults(func=comando_reporte)
    return parser


def main(argv=None):
    args = crear_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
