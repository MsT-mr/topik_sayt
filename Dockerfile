FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=config.settings

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Static fayllarni yig'ish va bazani migratsiya qilib, gunicorn ni ishga tushirish
CMD python manage.py collectstatic --noinput && \
    python manage.py migrate --noinput && \
    gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
