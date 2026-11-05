"""Genera el sitio estático (HTML + gráficas) que se publica en GitHub Pages."""

import html
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # sin ventana, para que funcione en el servidor de GitHub Actions
import matplotlib.pyplot as plt  # noqa: E402

AZUL = "#1f5fa8"
NARANJA = "#e07b00"


def pesos(valor):
    """Formatea un número como pesos colombianos: 59900 -> $59.900."""
    return "$" + f"{int(round(valor)):,}".replace(",", ".")


def grafica_precios(catalogo, articulo, ruta):
    fig, ax = plt.subplots(figsize=(8, 4.2))
    limite = catalogo["precio_oferta"].quantile(0.95)
    datos = catalogo.loc[catalogo["precio_oferta"] <= limite, "precio_oferta"] / 1000
    ax.hist(datos, bins=30, color=AZUL, alpha=0.85)
    ax.axvline(articulo["precio_oferta"] / 1000, color=NARANJA, linewidth=2.5,
               label=f"Redmi Buds 6 Play ({pesos(articulo['precio_oferta'])})")
    ax.axvline(catalogo["precio_oferta"].median() / 1000, color="gray", linestyle="--",
               label=f"Mediana del catálogo ({pesos(catalogo['precio_oferta'].median())})")
    ax.set_xlabel("Precio de oferta (miles de pesos)")
    ax.set_ylabel("Número de productos")
    ax.set_title("Distribución de precios de audífonos inalámbricos")
    ax.legend()
    fig.tight_layout()
    fig.savefig(ruta, dpi=110)
    plt.close(fig)


def grafica_marcas(resumen, ruta):
    fig, ax = plt.subplots(figsize=(8, 4.2))
    datos = resumen.sort_values("productos")
    ax.barh(datos["marca"], datos["productos"], color=AZUL)
    ax.set_xlabel("Productos en la búsqueda")
    ax.set_title("Marcas con más productos")
    fig.tight_layout()
    fig.savefig(ruta, dpi=110)
    plt.close(fig)


def grafica_historial(historial, ruta):
    fig, ax = plt.subplots(figsize=(8, 4.2))
    fechas = historial["fecha"].astype(str)
    ax.plot(fechas, historial["precio_mediano"] / 1000, marker="o", color=AZUL,
            label="Mediana del catálogo")
    ax.plot(fechas, historial["precio_articulo"] / 1000, marker="o", color=NARANJA,
            label="Redmi Buds 6 Play")
    ax.set_ylabel("Precio (miles de pesos)")
    ax.set_title("Evolución de precios por fecha de extracción")
    ax.set_ylim(bottom=0)
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(ruta, dpi=110)
    plt.close(fig)


def _tabla(df, formatos=None):
    formatos = formatos or {}
    cab = "".join(f"<th>{html.escape(str(c))}</th>" for c in df.columns)
    filas = []
    for _, fila in df.iterrows():
        celdas = []
        for c in df.columns:
            valor = formatos[c](fila[c]) if c in formatos else fila[c]
            celdas.append(f"<td>{html.escape(str(valor))}</td>")
        filas.append("<tr>" + "".join(celdas) + "</tr>")
    return f"<table><thead><tr>{cab}</tr></thead><tbody>{''.join(filas)}</tbody></table>"


PLANTILLA = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Monitor de precios Falabella</title>
<style>
  body {{ font-family: Segoe UI, Arial, sans-serif; margin: 0; background: #f4f6f9; color: #222; }}
  header {{ background: {azul}; color: white; padding: 24px 16px; }}
  header h1 {{ margin: 0 0 6px; font-size: 1.6rem; }}
  main {{ max-width: 960px; margin: auto; padding: 16px; }}
  .kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; }}
  .kpi {{ background: white; border-radius: 8px; padding: 14px; box-shadow: 0 1px 3px #0002; }}
  .kpi b {{ display: block; font-size: 1.5rem; color: {azul}; }}
  section {{ background: white; border-radius: 8px; padding: 16px; margin-top: 16px;
             box-shadow: 0 1px 3px #0002; overflow-x: auto; }}
  img {{ max-width: 100%; }}
  table {{ border-collapse: collapse; width: 100%; font-size: .9rem; }}
  th, td {{ border-bottom: 1px solid #ddd; padding: 6px 8px; text-align: left; }}
  th {{ background: #eef2f7; }}
  footer {{ text-align: center; font-size: .8rem; color: #666; padding: 24px; }}
</style>
</head>
<body>
<header>
  <h1>Monitor de precios: Xiaomi Redmi Buds 6 Play vs. catálogo de Falabella</h1>
  <div>Última extracción: {fecha} &middot; Actualizado automáticamente con GitHub Actions</div>
</header>
<main>
  <div class="kpis">
    <div class="kpi">Precio del artículo<b>{precio}</b></div>
    <div class="kpi">Mediana del catálogo<b>{mediana}</b></div>
    <div class="kpi">Productos más baratos que el artículo<b>{mas_baratos}%</b></div>
    <div class="kpi">Descuento del artículo<b>{descuento}%</b></div>
    <div class="kpi">Productos analizados<b>{productos}</b></div>
    <div class="kpi">Resultados patrocinados<b>{patrocinados}%</b></div>
  </div>
  <section><h2>Precio del artículo frente al catálogo</h2>
    <img src="precios.png" alt="Histograma de precios"></section>
  <section><h2>Evolución en el tiempo</h2>
    <img src="historial.png" alt="Evolución de precios">{tabla_historial}</section>
  <section><h2>Marcas con más productos</h2>
    <img src="marcas.png" alt="Marcas">{tabla_marcas}</section>
  <section><h2>Datos</h2>
    <p>Descarga el catálogo completo en <a href="catalogo.csv">catalogo.csv</a>
       y el historial en <a href="historial.csv">historial.csv</a>.</p></section>
</main>
<footer>Proyecto académico &middot; Alejandro Arango Calderón &middot; IU Digital de Antioquia
&middot; Generado el {generado}</footer>
</body>
</html>
"""


def generar_sitio(catalogo, articulo, historial, indicadores, resumen, salida):
    """Crea la carpeta del sitio con index.html, las gráficas y los CSV."""
    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)

    grafica_precios(catalogo, articulo, salida / "precios.png")
    grafica_marcas(resumen, salida / "marcas.png")
    grafica_historial(historial, salida / "historial.png")
    catalogo.to_csv(salida / "catalogo.csv", index=False, encoding="utf-8-sig")
    historial.to_csv(salida / "historial.csv", index=False, encoding="utf-8-sig")

    tabla_historial = _tabla(historial, {"precio_mediano": pesos, "precio_articulo": pesos})
    tabla_marcas = _tabla(resumen, {"precio_mediano": pesos})
    pagina = PLANTILLA.format(
        azul=AZUL,
        fecha=html.escape(str(historial["fecha"].iloc[-1])),
        precio=pesos(indicadores["precio_articulo"]),
        mediana=pesos(indicadores["precio_mediano_catalogo"]),
        mas_baratos=indicadores["pct_mas_baratos_que_articulo"],
        descuento=indicadores["descuento_articulo"],
        productos=indicadores["productos_catalogo"],
        patrocinados=indicadores["pct_patrocinados"],
        tabla_historial=tabla_historial,
        tabla_marcas=tabla_marcas,
        generado=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
    (salida / "index.html").write_text(pagina, encoding="utf-8")
    return salida / "index.html"
