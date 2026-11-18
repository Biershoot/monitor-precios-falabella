# Imagen de la aplicación web del monitor de precios.
# La usa Render para desplegar (runtime: docker) y la CI para probar que el contenedor arranca.
FROM python:3.15-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MPLCONFIGDIR=/tmp/matplotlib

WORKDIR /app

# Primero solo las dependencias, para que Docker reutilice esta capa
# mientras requirements.txt no cambie.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY monitor_precios/ monitor_precios/
COPY datos/ datos/

# No correr la aplicación como root
RUN useradd --create-home --uid 1000 app
USER app

# APP_COMMIT se pasa en la CI; en Render se usa RENDER_GIT_COMMIT
ARG APP_COMMIT=local
ENV APP_COMMIT=${APP_COMMIT} \
    APP_ENV=production \
    DATOS_DIR=/app/datos \
    PORT=10000

EXPOSE 10000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ['PORT'] + '/api/salud', timeout=4)"

# gunicorn es el servidor WSGI de producción (el servidor de Flask es solo para desarrollo).
# Se usa sh -c para que tome el PORT que asigna Render y exec para que reciba las señales.
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT} --workers ${WEB_CONCURRENCY:-2} --threads 2 --timeout 60 --access-logfile - 'monitor_precios.web:create_app()'"]
