FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod

RUN addgroup --system tmd && adduser --system --ingroup tmd --home /app tmd

WORKDIR /app
COPY requirements ./requirements
RUN pip install --no-cache-dir -r requirements/base.txt

COPY . .
RUN chmod +x entrypoint.sh

USER tmd
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready/', timeout=3)"

ENTRYPOINT ["./entrypoint.sh"]
