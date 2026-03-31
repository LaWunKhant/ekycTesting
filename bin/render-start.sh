#!/usr/bin/env bash
set -euo pipefail

python manage.py migrate --noinput

exec gunicorn myproject.wsgi:application \
  --bind "0.0.0.0:${PORT:-10000}" \
  --workers "${WEB_CONCURRENCY:-1}" \
  --timeout "${GUNICORN_TIMEOUT:-120}" \
  --access-logfile - \
  --error-logfile -
