FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=config.settings

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Migratsiya qilish, Admin yaratish va serverni berilgan portda ishga tushirish:
CMD python manage.py collectstatic --noinput && \
    python manage.py migrate --noinput && \
    python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.filter(username='admin').exists() or User.objects.create_superuser('admin', 'admin@example.com', 'Admin12345!')" && \
    gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
