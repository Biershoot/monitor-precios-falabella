# Flujo de trabajo DevOps del proyecto

Este documento explica paso a paso cómo trabajo el proyecto, desde que empiezo una
funcionalidad hasta que queda publicada.

## 1. Planear

Cada funcionalidad la manejo como una tarea pequeña (por ejemplo "extraer el catálogo",
"agregar pruebas", "publicar en Pages"). Para cada una creo una rama `feature/...`.

## 2. Programar y versionar (Git)

```bash
git checkout develop
git pull
git checkout -b feature/reporte-html
# ... cambios ...
git add monitor_precios/reporte.py tests/test_reporte_cli.py
git commit -m "feat: generar sitio estático con gráficas e indicadores"
git push -u origin feature/reporte-html
```

Los commits son pequeños y con un mensaje que dice qué cambió, con prefijos
`feat`, `fix`, `test`, `ci`, `docs`, `chore` y `datos`.

## 3. Probar (CI)

Con el push, GitHub Actions ejecuta `ci.yml`:

1. `actions/checkout` descarga el código.
2. `actions/setup-python` instala Python 3.11 y 3.12 (matriz) y guarda en caché las librerías.
3. `ruff check .` revisa el estilo y errores comunes (imports sin usar, variables no definidas...).
4. `pytest --cov --cov-fail-under=85` corre las 28 pruebas. Si la cobertura baja de 85 % el job falla.
5. Se genera el sitio con los datos guardados para comprobar que el reporte no se rompió.

Las pruebas **no usan internet**: en `tests/conftest.py` armo páginas HTML con la misma
estructura `__NEXT_DATA__` de Falabella, y con `monkeypatch` reemplazo la función de descarga.
Así las pruebas siempre dan el mismo resultado aunque cambien los precios del día.

## 4. Revisar e integrar (pull request)

Abro un pull request de `feature/...` hacia `develop` usando la plantilla
`.github/pull_request_template.md`. El PR muestra el resultado de la CI; solo lo fusiono
si está en verde. Cuando `develop` tiene una versión estable, abro un PR de `develop` a `main`.

Configuración recomendada de protección de `main` (Settings → Branches):
requerir pull request y requerir que pase el check "Lint y pruebas".

## 5. Desplegar (CD)

Al fusionar en `main` se ejecuta `cd.yml`:

1. Llama otra vez a `ci.yml` (`workflow_call`) para no desplegar nada que no pase las pruebas.
2. Genera el sitio con `python -m monitor_precios reporte --salida sitio`.
3. Lo sube con `actions/upload-pages-artifact` y lo publica con `actions/deploy-pages`.

Para activarlo hay que ir a **Settings → Pages → Build and deployment → Source: GitHub Actions**.

## 6. Operar y monitorear (automatización)

`scraping.yml` se ejecuta con `cron: "0 12 * * 1"` (lunes 7:00 a. m. hora Colombia):

1. Corre el scraper (revisa `robots.txt`, 5 páginas, pausa de 2 s).
2. Si obtiene menos de 100 productos, falla y no guarda nada (por si Falabella bloquea la
   petición o cambia la página). El correo de GitHub avisa que el workflow falló.
3. Si todo sale bien, hace commit de los CSV en `datos/` con el usuario `github-actions[bot]`.
4. Llama a `cd.yml` para publicar el sitio con el historial actualizado. Lo llamo directamente
   porque un push hecho con `GITHUB_TOKEN` no dispara otros workflows.

## Resumen del ciclo

```
rama feature → commits → push → CI (ruff + pytest) → PR → develop → PR → main
     → CD (pruebas + build) → GitHub Pages
cron semanal → scraping → commit de datos → CD → GitHub Pages
```
