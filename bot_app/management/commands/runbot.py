import asyncio
from django.core.management.base import BaseCommand
import bot


class Command(BaseCommand):
    help = "TOPIK Telegram Botini ishga tushirish"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🚀 Telegram bot ishga tushirilmoqda..."))
        try:
            asyncio.run(bot.main())
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("\nBot to'xtatildi."))
