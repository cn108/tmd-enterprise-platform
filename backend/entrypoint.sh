#!/usr/bin/env sh
set -eu

echo "Applying database migrations"
python manage.py migrate --noinput

echo "Running deployment checks"
python manage.py check --deploy

exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:8000" \
  --workers "${GUNICORN_WORKERS:-3}" \
  --timeout "${GUNICORN_TIMEOUT:-60}" \
  --access-logfile - \
  --error-logfile -
