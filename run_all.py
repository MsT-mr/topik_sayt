#!/usr/bin/env python
"""
TOPIK All-in-One Runner
Django Web Server va Telegram Botni parallel ravishda xatosiz ishga tushiradi.
To'xtatish uchun Ctrl+C bosing.
"""
import sys
import time
import signal
import subprocess
from threading import Thread

processes = []


def stream_logs(pipe, prefix, color_code):
    try:
        for line in iter(pipe.readline, ''):
            if not line:
                break
            # Rangli prefiks bilan chop etish
            sys.stdout.write(f"\033[{color_code}m[{prefix}]\033[0m {line}")
            sys.stdout.flush()
    except Exception:
        pass


def shutdown(signum=None, frame=None):
    print("\n🛑 Barcha xizmatlar to'xtatilmoqda...")
    for p in processes:
        if p.poll() is None:
            p.terminate()
    time.sleep(1)
    for p in processes:
        if p.poll() is None:
            p.kill()
    print("✅ Tizim muvaffaqiyatli to'xtatildi.")
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print("=" * 60)
    print("🚀 TOPIK Study Platform: Django Server va Telegram Bot")
    print("=" * 60)

    # 1. Django Runserver
    django_cmd = [sys.executable, "manage.py", "runserver", "0.0.0.0:8000"]
    django_proc = subprocess.Popen(
        django_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    processes.append(django_proc)

    t_django = Thread(target=stream_logs, args=(django_proc.stdout, "DJANGO", "32"), daemon=True)
    t_django.start()

    # 2. Telegram Bot
    bot_cmd = [sys.executable, "bot.py"]
    bot_proc = subprocess.Popen(
        bot_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    processes.append(bot_proc)

    t_bot = Thread(target=stream_logs, args=(bot_proc.stdout, "BOT", "36"), daemon=True)
    t_bot.start()

    print("🌐 Django server: http://localhost:8000")
    print("🤖 Telegram Bot: Ishga tushirildi")
    print("💡 To'xtatish uchun: Ctrl+C bosing\n")

    try:
        while True:
            time.sleep(1)
            # Agar birortasi o'zidan o'zi to'xtab qolsa
            if django_proc.poll() is not None:
                print("❌ Django server to'xtab qoldi!")
                shutdown()
            if bot_proc.poll() is not None:
                print("❌ Telegram bot to'xtab qoldi!")
                shutdown()
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
