#!/bin/sh
set -eu
export DJANGO_SETTINGS_MODULE=config.production
# /data must be a persistent volume, not the disposable container filesystem.
if [ ! -d /data ]; then
    echo 'Persistent /data volume is required.' >&2
    exit 1
fi
python manage.py check --deploy --fail-level WARNING
python manage.py migrate --noinput
python manage.py import_curriculum
python manage.py import_exercises
python manage.py collectstatic --noinput
# One process keeps cache-based AI limits consistent; threads handle API waits.
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers 1 --threads 4 --timeout 120 --access-logfile - --error-logfile -
