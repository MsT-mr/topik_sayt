#!/usr/bin/env bash
# TOPIK Study: Django & Bot parallel runner

trap 'kill 0' SIGINT SIGTERM EXIT

echo "=========================================================="
echo "🚀 TOPIK Study: Django server va Telegram Bot ishga tushmoqda..."
echo "=========================================================="

python manage.py runserver 0.0.0.0:8000 &
python bot.py &

wait
