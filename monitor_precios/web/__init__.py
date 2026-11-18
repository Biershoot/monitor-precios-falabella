"""Aplicación web del monitor de precios (Evidencia 3).

Tiene dos partes:
  - páginas HTML: el tablero (/) y el catálogo con filtros (/catalogo)
  - una API REST en JSON bajo /api/ para consultar los mismos datos desde otros programas

Se crea con el patrón "application factory" (create_app) para poder pasarle una
configuración distinta en las pruebas.

En producción se ejecuta con gunicorn:
    gunicorn "monitor_precios.web:create_app()"
"""

import logging
import math
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request

from monitor_precios import __version__, analisis
from monitor_precios.reporte import pesos
from monitor_precios.web import config, datos


class ParametroInvalido(ValueError):
    """Error en un parámetro de la URL; se responde con 400."""


def _numero(nombre, minimo=0):
    """Lee un parámetro numérico de la URL; None si no viene."""
    valor = request.args.get(nombre, "").strip()
    if valor == "":
        return None
    try:
        numero = int(float(valor))
    except ValueError as error:
        raise ParametroInvalido(f"El parámetro '{nombre}' debe ser un número") from error
    if numero < minimo:
        raise ParametroInvalido(f"El parámetro '{nombre}' debe ser mayor o igual a {minimo}")
    return numero


def _filtros():
    """Filtros comunes del catálogo (los usan la página y la API)."""
    return {
        "marca": request.args.get("marca", "").strip() or None,
        "texto": request.args.get("q", "").strip() or None,
        "precio_min": _numero("precio_min"),
        "precio_max": _numero("precio_max"),
        "orden": request.args.get("orden", "precio_asc"),
    }


def create_app(configuracion=None):
    app = Flask(__name__)
    app.config.update(config.desde_entorno())
    if configuracion:
        app.config.update(configuracion)
    app.json.ensure_ascii = False      # para que las tildes salgan bien en el JSON
    app.json.sort_keys = False
    app.jinja_env.filters["pesos"] = pesos

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    app.logger.info("Monitor de precios v%s (%s) - datos en %s", __version__,
                    app.config["APP_ENV"], app.config["DATOS_DIR"])

    def cargar():
        return datos.cargar(app.config["DATOS_DIR"])

    @app.context_processor
    def variables_globales():
        return {"version": __version__, "commit": app.config["COMMIT"][:7],
                "entorno": app.config["APP_ENV"]}

    # ------------------------------------------------------------------ páginas HTML
    @app.get("/")
    def tablero():
        d = cargar()
        historial = d.historial
        return render_template(
            "tablero.html",
            ind=d.indicadores,
            articulo=d.articulo,
            fecha=str(historial["fecha"].iloc[-1]),
            fuente=str(historial["fuente"].iloc[-1]),
            historial=datos.a_registros(historial),
            histograma=datos.histograma(d.catalogo),
            marcas=datos.a_registros(d.marcas),
        )

    @app.get("/catalogo")
    def catalogo():
        d = cargar()
        filtros = _filtros()
        resultado = datos.filtrar_catalogo(d.catalogo, **filtros)
        por_pagina = app.config["POR_PAGINA"]
        paginas = max(1, math.ceil(len(resultado) / por_pagina))
        pagina = min(_numero("pagina", minimo=1) or 1, paginas)
        inicio = (pagina - 1) * por_pagina
        return render_template(
            "catalogo.html",
            productos=datos.a_registros(resultado.iloc[inicio:inicio + por_pagina]),
            total=len(resultado),
            pagina=pagina,
            paginas=paginas,
            filtros=filtros,
            marcas=sorted(d.catalogo["marca"].dropna().unique()),
            ordenes=datos.ORDENES,
            articulo=d.articulo,
        )

    # ------------------------------------------------------------------ API REST
    @app.get("/api/salud")
    def salud():
        """Lo usa Render (healthCheckPath) y la prueba de humo del pipeline."""
        try:
            d = cargar()
            estado = {"datos": "ok", "ultima_extraccion": str(d.historial["fecha"].iloc[-1]),
                      "productos": int(len(d.catalogo))}
            codigo = 200
        except (FileNotFoundError, ValueError) as error:
            estado, codigo = {"datos": "error", "detalle": str(error)}, 503
        respuesta = {
            "estado": "ok" if codigo == 200 else "degradado",
            "version": __version__,
            "commit": app.config["COMMIT"],
            "entorno": app.config["APP_ENV"],
            "hora_servidor": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            **estado,
        }
        return jsonify(respuesta), codigo

    @app.get("/api/indicadores")
    def api_indicadores():
        d = cargar()
        return jsonify({"fecha": str(d.historial["fecha"].iloc[-1]), **d.indicadores})

    @app.get("/api/articulo")
    def api_articulo():
        return jsonify(cargar().articulo)

    @app.get("/api/historial")
    def api_historial():
        return jsonify(datos.a_registros(cargar().historial))

    @app.get("/api/marcas")
    def api_marcas():
        top = _numero("top", minimo=1) or 10
        return jsonify(datos.a_registros(analisis.resumen_marcas(cargar().catalogo, top)))

    @app.get("/api/catalogo")
    def api_catalogo():
        d = cargar()
        filtros = _filtros()
        limite = min(_numero("limite", minimo=1) or 50, app.config["LIMITE_MAXIMO"])
        desde = _numero("desde") or 0
        resultado = datos.filtrar_catalogo(d.catalogo, **filtros)
        return jsonify({
            "total": int(len(resultado)),
            "desde": desde,
            "limite": limite,
            "filtros": filtros,
            "productos": datos.a_registros(resultado.iloc[desde:desde + limite]),
        })

    # ------------------------------------------------------------------ errores
    def _es_api():
        return request.path.startswith("/api/")

    @app.errorhandler(ValueError)       # incluye ParametroInvalido y un orden no válido
    def error_parametro(error):
        if _es_api():
            return jsonify({"error": str(error)}), 400
        return render_template("error.html", codigo=400, mensaje=str(error)), 400

    @app.errorhandler(404)
    def no_encontrado(_error):
        if _es_api():
            return jsonify({"error": f"No existe la ruta {request.path}"}), 404
        return render_template("error.html", codigo=404,
                               mensaje="La página que buscas no existe."), 404

    @app.errorhandler(FileNotFoundError)
    def sin_datos(error):
        app.logger.error("No se pudieron leer los datos: %s", error)
        if _es_api():
            return jsonify({"error": "Los datos no están disponibles"}), 503
        return render_template("error.html", codigo=503,
                               mensaje="Los datos no están disponibles en este momento."), 503

    return app
