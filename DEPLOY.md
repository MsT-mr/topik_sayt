# Railway’da doimiy ishlatish

1. Railway hisobida loyiha va bo‘sh service yarating. Dockerfile orqali deploy qiling (`railway up` yoki private GitHub repo).
2. Service uchun `/data` manziliga **Volume** ulang. Bitta replica ishlating.
3. Public domain yarating. Quyidagi Variables qiymatlarini kiriting:
   - `DJANGO_SETTINGS_MODULE=config.production`
   - `DJANGO_SECRET_KEY`: tasodifiy, kamida 50 belgili maxfiy qiymat.
   - `DJANGO_ALLOWED_HOSTS`: berilgan domen, `https://` va `/` siz. Bir nechta domen vergul bilan ajratiladi.
   - `GEMINI_API_KEY`: ishlayotgan kalitni maxfiy hosting variable sifatida kiriting.
   - `GEMINI_MODEL=gemini-3.8-flash`
   - `GEMINI_FALLBACK_MODEL=gemini-3.5-flash-lite`
   - `DATABASE_PATH=/data/db.sqlite3`
4. Deploy: start script migratsiya, dars va mashq importi, static yig‘ishdan keyin Gunicorn’ni boshlaydi. Telegram bot bu service’da ishga tushirilmaydi.
5. Yangi bazada hosting shell orqali `python manage.py createsuperuser` bajaring. O‘quvchi manzili `/`, ustoz paneli `/admin/`.

## Mavjud ma’lumotlarni ko‘chirish

Mahalliy `db.sqlite3` deploy paketiga kiritilmaydi: unda o‘quvchilar va hisoblar bor.
Ko‘chirishdan oldin SQLite backup API bilan izchil nusxa oling, bazani yozayotgan
serverni to‘xtatib, backup’ni volume’dagi `/data/db.sqlite3` ga xavfsiz ko‘chiring.
Avval manzildagi bazadan ham backup oling; mavjud bazani bilmasdan almashtirmang.
Keyin service’ni qayta ishga tushiring. Eski ustoz hisobi va o‘quvchi ID’lari saqlanadi.

## Tekshiruv va saqlash

- HTTPS bosh sahifa, admin kirishi, static CSS/JS, o‘quvchi kirishi va AI javobini tekshiring.
- Service qayta ishga tushgandan so‘ng natijalar va o‘quvchilar saqlanishini tekshiring.
- Railway Volume backups’ni yoqing. Kompyuterdagi loyiha nusxasi onlayn natijalarni zaxiralamaydi.
- `.env`, Gemini kaliti, bazalar va backup’lar repo yoki image’ga kiritilmaydi.
- AI va hosting alohida xarajat qilishi mumkin; hosting usage limitini sozlang.
