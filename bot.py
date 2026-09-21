import os
import sys
import asyncio
import logging
import django

# 1. Loyihaning ildiz katalogini sys.path ga qo'shamiz
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

# 2. Django sozlamalarini yuklaymiz
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

# 3. Importlar
from asgiref.sync import sync_to_async
from bot_app.models import Student, Vocabulary, Exam, ExamResult

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo
)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8524317255:AAGoN4b_x-L9Kc8q6Xa1bcmV06Xc_XK3o0c")
MINI_APP_URL = os.getenv("MINI_APP_URL", "")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


def get_main_menu(mini_app_url: str = "") -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="📚 Bugungi dars"), KeyboardButton(text="📝 Test yechish")],
        [KeyboardButton(text="📊 Mening natijalarim"), KeyboardButton(text="👤 Profil")]
    ]
    if mini_app_url:
        buttons.insert(0, [KeyboardButton(text="🌟 TOPIK Mini App", web_app=WebAppInfo(url=mini_app_url))])

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


@sync_to_async
def get_or_create_student(telegram_id: int, full_name: str):
    """Telegram foydalanuvchisini bazadan topadi yoki yangi yaratadi"""
    student = Student.objects.filter(telegram_id=telegram_id).first()
    if student:
        if full_name and student.name != full_name:
            student.name = full_name
            student.save(update_fields=["name"])
        student.update_streak()
        return student, False

    return None, False



@sync_to_async
def get_daily_words(limit: int = 5):
    """Bugungi dars uchun lug'atdan so'zlarni oladi"""
    return list(Vocabulary.objects.all()[:limit])


@sync_to_async
def get_active_exams():
    """Faol imtihonlar ro'yxatini oladi"""
    return list(Exam.objects.filter(is_active=True).order_by("level", "id")[:5])


@sync_to_async
def get_student_data(telegram_id: int):
    """Talaba va uning so'nggi imtihon natijalarini oladi"""
    student = Student.objects.filter(telegram_id=telegram_id).first()
    if not student:
        return None, []
    student.update_streak()
    results = list(student.exam_results.select_related("exam").order_by("-completed_at")[:3])
    return student, results


@dp.message(CommandStart())
async def start_handler(message: types.Message):
    user = message.from_user
    full_name = user.full_name or user.first_name or "O'quvchi"

    student, created = await get_or_create_student(
        telegram_id=user.id,
        full_name=full_name
    )

    if student is None or not student.is_active:
        await message.answer("Saytga kirish uchun ustozingizdan Student ID oling. Telegramni bog‘lash uchun ustozga Telegram ID raqamingizni bering: " + str(user.id))
        return

    if created:
        text = (
            f"Salom, **{user.first_name}**! 👋\n\n"
            f"Siz **TOPIK Smart Learning** tizimiga muvaffaqiyatli ro'yxatdan o'tdingiz! 🚀\n\n"
            f"🆔 Sizning Student ID: `{student.student_id}`\n"
            f"_(Ushbu ID orqali Mini App-ga kirishingiz mumkin)_"
        )
    else:
        text = (
            f"Qaytganingiz bilan, **{student.name}**! 😊\n\n"
            f"🆔 Sizning Student ID: `{student.student_id}`"
        )

    inline_kb = None
    if MINI_APP_URL:
        inline_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🚀 Mini App-ni ochish", web_app=WebAppInfo(url=MINI_APP_URL))]
            ]
        )

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=inline_kb or get_main_menu(MINI_APP_URL)
    )


@dp.message(F.text == "📚 Bugungi dars")
async def today_lesson_handler(message: types.Message):
    words = await get_daily_words(5)
    if not words:
        await message.answer("📖 Hozircha darslar yuklanmagan. Tez orada yangi darslar qo'shiladi!")
        return

    text = "📚 **Bugungi 5 ta muhim so'z:**\n\n"
    for i, w in enumerate(words, 1):
        text += f"{i}. 🇰🇷 **{w.korean}** — {w.translation}\n"

    text += "\n💡 _Batafsil mashqlar va Flashcardlar uchun Mini App-ga kiring!_"
    await message.answer(text, parse_mode="Markdown")


@dp.message(F.text == "📝 Test yechish")
async def test_handler(message: types.Message):
    exams = await get_active_exams()
    if not exams:
        await message.answer("📝 Hozircha faol testlar mavjud emas.")
        return

    text = "📝 **Mavjud TOPIK Imtihonlari:**\n\n"
    for e in exams:
        text += f"🎯 **{e.title}**\n"
        text += f"• Daraja: TOPIK {e.level}\n"
        text += f"• Vaqt: {e.duration_minutes} daqiqa\n"
        text += f"• O'tish bali: {e.pass_score}%\n\n"

    inline_kb = None
    if MINI_APP_URL:
        inline_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🎯 Testni boshlash (Mini App)", web_app=WebAppInfo(url=MINI_APP_URL))]
            ]
        )

    text += "💡 _Interaktiv test yechish va AI Tutor xatolar tahlili uchun Mini App-dan foydalaning!_"
    await message.answer(text, parse_mode="Markdown", reply_markup=inline_kb)


@dp.message(F.text == "📊 Mening natijalarim")
async def stats_handler(message: types.Message):
    student, results = await get_student_data(message.from_user.id)
    if not student:
        await message.answer("Iltimos, avval /start buyrug'ini yuboring.")
        return

    text = (
        f"📊 **{student.name}** ning o'qish statistikasi:\n\n"
        f"🔥 **Kunlik streak:** {student.streak} kun\n"
        f"📚 **Yodlangan so'zlar:** {student.words_learned} ta\n"
        f"🎯 **Yechilgan testlar:** {student.tests_completed} ta\n"
    )

    if results:
        text += "\n🏆 **So'nggi imtihon natijalari:**\n"
        for r in results:
            status = "✅ O'tdi" if r.passed else "❌ O'tmadi"
            text += f"• {r.exam.title}: **{r.score_percentage}%** ({status})\n"

    await message.answer(text, parse_mode="Markdown")


@dp.message(F.text == "👤 Profil")
async def profile_handler(message: types.Message):
    student, _ = await get_student_data(message.from_user.id)
    if not student:
        await message.answer("Iltimos, avval /start buyrug'ini yuboring.")
        return

    text = (
        f"👤 **O'quvchi Profili:**\n\n"
        f"• **F.I.SH:** {student.name}\n"
        f"• **Student ID:** `{student.student_id}`\n"
        f"• **Telegram ID:** `{student.telegram_id}`\n"
        f"• **Ro'yxatdan o'tgan vaqti:** {student.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
        f"🔑 _Mini App yoki saytga kirish uchun ushbu Student ID dan foydalaning!_"
    )
    await message.answer(text, parse_mode="Markdown")


async def main():
    logger.info("🚀 Bot Djangoga muvaffaqiyatli ulandi va ishga tushdi!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot to'xtatildi.")
