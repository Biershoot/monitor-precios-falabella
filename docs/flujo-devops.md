# Flujo de trabajo DevOps del proyecto

Este documento explica paso a paso cómo trabajo el proyecto, desde que empiezo una
funcionalidad hasta que queda publicada en producción. Lo actualicé en la Evidencia 3
para incluir la aplicación web, Docker y el despliegue en Render.

## 1. Planear

Cada funcionalidad la manejo como una tarea pequeña con su propia rama. En la EA3 fueron:

| Rama | Tarea |
|------|-------|
| `fix/paginacion-busquedas` | Corregir el scraper porque Falabella dejó de respetar el parámetro `page`. |
| `feature/app-web` | Aplicación Flask con tablero, catálogo y API REST. |
| `feature/docker-render` | Dockerfile y `render.yaml`. |
| `feature/cd-render` | Workflows: prueba del contenedor, despliegue en Render y ghcr.io, releases y Dependabot. |
| `feature/alertas-precio` | Comando `alerta` y creación automática de issues. |
| `docs/ea3` | README, esta guía y la guía de despliegue. |

## 2. Programar y versionar (Git)

```bash
git checkout develop
git pull
git checkout -b feature/app-web
# ... cambios ...
ruff check . && pytest            # antes de subir, lo mismo que corre la CI
git add monitor_precios/web tests/test_web.py
git commit -m "feat: aplicación Flask con tablero, catálogo con filtros y API REST"
git push -u origin feature/app-web
```

Prefijos de commit: `feat`, `fix`, `test`, `ci`, `docs`, `chore` y `datos`.

## 3. Probar (CI – `ci.yml`)

Con cada push y cada pull request se ejecutan dos jobs:

**Job `pruebas`** (matriz con Python 3.11, 3.12 y 3.13):

1. `actions/checkout@v5` descarga el código.
2. `actions/setup-python@v6` instala la versión de Python y guarda en caché las librerías (`cache: pip`).
3. `pip install -r requirements-dev.txt`.
4. `ruff check .` revisa estilo y errores comunes.
5. `pytest --cov --cov-fail-under=90` corre las 68 pruebas; si la cobertura baja de 90 % el job falla.
6. `python -m monitor_precios reporte` comprueba que el sitio estático se sigue generando.
7. En Python 3.12 se guarda `coverage.xml` como artefacto.

**Job `contenedor`** (solo si `pruebas` pasó):

1. `docker build --build-arg APP_COMMIT=$GITHUB_SHA` construye la misma imagen que usa Render.
2. `docker run -d -p 10000:10000` la levanta.
3. Prueba de humo con `curl` y `jq`: `/api/salud` debe responder `estado: ok` y el mismo commit
   que se construyó, `/` debe contener el nombre del artículo, `/api/catalogo?limite=5` debe
   traer 5 productos y una ruta inexistente debe dar 404.
4. Si algo falla, se imprimen los logs del contenedor.

Las pruebas de Python **no usan internet**: en `tests/conftest.py` armo HTML con la misma
estructura `__NEXT_DATA__` de Falabella, y las pruebas de la aplicación usan el cliente de
pruebas de Flask (`app.test_client()`) con datos en una carpeta temporal.

## 4. Revisar e integrar (pull request)

Abro un pull request de la rama hacia `develop` con la plantilla
`.github/pull_request_template.md`. Solo lo fusiono si la CI está en verde. Cuando `develop`
tiene una versión estable, abro un PR de `develop` a `main` (PR de versión).

## 5. Desplegar (CD – `cd.yml`)

Al fusionar en `main`:

1. `pruebas`: llama a `ci.yml` con `workflow_call`, para no desplegar nada que no pase exactamente las mismas pruebas.
2. Si pasa, se ejecutan tres despliegues en paralelo:
   - **GitHub Pages** (`construir-sitio` + `pages`): genera el reporte estático y lo publica.
   - **Imagen** (`imagen`): construye la imagen y la sube a `ghcr.io/biershoot/monitor-precios-falabella` con las etiquetas `<sha>` y `latest`, usando el `GITHUB_TOKEN` (permiso `packages: write`).
   - **Render** (`render`), en el entorno `produccion` de GitHub:
     1. Verifica que existan el secret `RENDER_DEPLOY_HOOK_URL` y la variable `RENDER_URL`.
     2. Hace `POST` al Deploy Hook con `&ref=<commit>` para que Render construya ese commit exacto.
     3. Consulta `/api/salud` cada 20 segundos (hasta 15 minutos) hasta que el campo `commit` sea el nuevo.
     4. Corre pruebas de humo contra producción y escribe un resumen en la página de la ejecución.

## 6. Operar y monitorear (`scraping.yml`)

Cada lunes a las 12:00 UTC (7:00 a. m. en Colombia):

1. Corre el scraper (revisa `robots.txt`, 5 términos de búsqueda, una página por término, pausa de 2 s).
2. Si obtiene menos de 100 productos falla y no guarda nada; GitHub envía un correo avisando.
3. Hace commit de los CSV en `datos/` con el usuario `github-actions[bot]`.
4. `python -m monitor_precios alerta` compara el precio del artículo con la semana anterior.
   Si cambió, `gh issue create` abre un issue con el detalle (permiso `issues: write`).
5. Llama a `cd.yml` con `secrets: inherit` para redesplegar Pages y Render con los datos nuevos.
   Lo llamo directamente porque un push hecho con `GITHUB_TOKEN` no dispara otros workflows.

## 7. Versionar entregas (`release.yml`) y mantener dependencias (Dependabot)

- Al subir una etiqueta, por ejemplo `git tag v2.0.0 && git push origin v2.0.0`, se corre la CI,
  se comprueba que la etiqueta coincida con `monitor_precios.__version__` y se crea el Release
  con notas generadas a partir de los PR.
- Dependabot revisa cada semana pip, las GitHub Actions y la imagen base de Docker, y abre
  PR hacia `develop` que pasan por la misma CI.

## Resumen del ciclo

```
rama feature/fix → commits → push → CI (ruff + pytest x3 + Docker) → PR → develop → PR → main
     → CD: CI otra vez → Pages + ghcr.io + Render → espera del commit → pruebas de humo
cron semanal → scraping → commit de datos → alerta (issue) → CD
etiqueta vX.Y.Z → CI → Release
```
