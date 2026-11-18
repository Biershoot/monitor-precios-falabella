# Despliegue de la aplicación web en Render

Esta guía explica cómo quedó desplegada la aplicación y qué hay que configurar
para repetir el despliegue desde cero.

## 1. Por qué Render

Comparé tres opciones gratuitas para una aplicación en Python:

| Servicio | Ventajas | Desventajas |
|----------|----------|-------------|
| **Render** | Plan gratis para servicios web, soporta Docker, health checks, Blueprint (`render.yaml`) y Deploy Hooks para dispararlo desde GitHub Actions. | El servicio gratis se apaga a los 15 min sin tráfico y tarda en volver a arrancar. |
| GitHub Pages | Ya lo usaba en la EA2, cero configuración. | Solo sirve archivos estáticos: no puede ejecutar Flask ni la API. |
| Hugging Face Spaces | Gratis y con Docker. | Está pensado para demos de modelos de IA, no para aplicaciones web generales. |

Elegí Render porque permite tener la configuración del servidor dentro del repositorio
(infraestructura como código) y controlar el despliegue desde el pipeline.

## 2. Cómo está armado

```
GitHub (main) ──► GitHub Actions (cd.yml)
                     │ 1. corre la CI completa
                     │ 2. POST al Deploy Hook con ?ref=<commit>
                     ▼
                  Render
                     │ 3. clona ese commit y construye el Dockerfile
                     │ 4. arranca gunicorn en el puerto PORT=10000
                     │ 5. espera a que /api/salud responda 200 (health check)
                     │ 6. cambia el tráfico a la nueva versión (sin caída)
                     ▼
       https://monitor-precios-falabella.onrender.com
                     ▲
GitHub Actions ──────┘ 7. consulta /api/salud hasta ver el commit nuevo
                       8. pruebas de humo: /, /catalogo, /api/indicadores
```

### Archivos involucrados

- **`Dockerfile`**: imagen `python:3.12-slim`, instala `requirements.txt`, copia el paquete y la
  carpeta `datos/`, crea un usuario sin privilegios (`app`) y arranca **gunicorn** con
  `monitor_precios.web:create_app()`. Tiene un `HEALTHCHECK` que consulta `/api/salud`.
- **`.dockerignore`**: deja por fuera pruebas, notebooks, `.git`, `.venv` y documentación para que la imagen sea más liviana.
- **`render.yaml`**: Blueprint con el servicio web.

```yaml
services:
  - type: web
    name: monitor-precios-falabella
    runtime: docker
    plan: free
    region: oregon
    branch: main
    dockerfilePath: ./Dockerfile
    healthCheckPath: /api/salud
    autoDeployTrigger: "off"
    envVars:
      - key: APP_ENV
        value: production
      - key: DATOS_DIR
        value: /app/datos
      ...
```

`autoDeployTrigger: "off"` es importante: Render no despliega por su cuenta con cada commit,
el despliegue lo dispara el pipeline únicamente cuando las pruebas pasan.

### Variables de entorno en Render

| Variable | Valor | De dónde sale |
|----------|-------|---------------|
| `APP_ENV` | `production` | `render.yaml` |
| `DATOS_DIR` | `/app/datos` | `render.yaml` |
| `LIMITE_MAXIMO` | `500` | `render.yaml` |
| `POR_PAGINA` | `50` | `render.yaml` |
| `WEB_CONCURRENCY` | `2` | `render.yaml` (procesos de gunicorn) |
| `PORT` | `10000` | Render (por defecto) |
| `RENDER_GIT_COMMIT` | commit desplegado | Render (automática); la app la muestra en `/api/salud` |

### Secretos y variables en GitHub

En **Settings → Secrets and variables → Actions** del repositorio:

| Tipo | Nombre | Valor |
|------|--------|-------|
| Secret | `RENDER_DEPLOY_HOOK_URL` | URL del Deploy Hook (Render → servicio → Settings → Deploy Hook). Es secreta porque cualquiera que la tenga puede disparar despliegues. |
| Variable | `RENDER_URL` | `https://monitor-precios-falabella.onrender.com` |

Desde la terminal también se pueden crear con GitHub CLI:

```bash
gh secret set RENDER_DEPLOY_HOOK_URL
gh variable set RENDER_URL --body "https://monitor-precios-falabella.onrender.com"
```

## 3. Pasos para desplegar desde cero

1. Crear la cuenta en https://render.com con **Sign in with GitHub** y darle acceso al repositorio `monitor-precios-falabella`.
2. **New → Blueprint**, seleccionar el repositorio y la rama `main`. Render muestra el servicio que va a crear según `render.yaml`; confirmar con **Deploy Blueprint**.
3. Esperar el primer despliegue (unos 3 a 5 minutos). En **Logs** debe aparecer `Listening at: http://0.0.0.0:10000` y en **Events** `Deploy live`.
4. Copiar la URL del Deploy Hook (**Settings → Deploy Hook**) y crear el secret y la variable en GitHub.
5. Correr el workflow **CD - despliegue** a mano (Actions → CD - despliegue → Run workflow) para comprobar que todo el ciclo funciona.

## 4. Verificar el despliegue

```bash
curl https://monitor-precios-falabella.onrender.com/api/salud
```

Respuesta esperada (resumida):

```json
{
  "estado": "ok",
  "version": "2.0.0",
  "commit": "<sha del último merge a main>",
  "entorno": "production",
  "datos": "ok",
  "ultima_extraccion": "2026-11-18",
  "productos": 245
}
```

Si `commit` coincide con el último commit de `main`, la versión desplegada es la correcta.
El job **Desplegar en Render** del workflow hace exactamente esta comprobación de forma automática.

## 5. Problemas conocidos

- **Arranque en frío**: el plan gratis apaga el servicio tras 15 minutos sin tráfico. Por eso la
  espera del pipeline usa `--max-time 60` en cada intento y hasta 45 intentos.
- **Sistema de archivos efímero**: los datos no se guardan en el servidor sino dentro de la imagen.
  Cuando el scraping semanal hace commit de datos nuevos, el CD vuelve a construir y desplegar la imagen.
- **Rollback**: si una versión sale mal, en Render → **Events** se puede volver a un despliegue anterior
  con **Rollback**, o hacer `git revert` del merge en `main` para que el pipeline despliegue la versión anterior.
