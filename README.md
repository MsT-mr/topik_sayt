# TOPIK o‘quv platformasi

Ustoz paneli: `/admin/`. O‘quvchi sayti: `/`.
Ikkalasi ham `config/settings.py` dagi bitta `db.sqlite3` bazasidan foydalanadi.

## Ishga tushirish

```bash
python3 manage.py migrate
python3 manage.py import_curriculum
python3 manage.py runserver 0.0.0.0:8000
```

Admin hisob kerak bo‘lsa: `python3 manage.py createsuperuser`.

Ustoz “O‘quvchilar → Qo‘shish” orqali ism va kitob bosqichini tanlaydi.
ID avtomatik yaratiladi; profilidagi “Nusxalash” bilan o‘quvchiga beriladi.
Har bir 1A, 1B, 2A, 2B bosqichi uchun bitta guruh bor. Bosqich o‘zgarsa,
guruh ham avtomatik o‘zgaradi, ID saqlanadi.

O‘quvchi ID bilan kirib o‘z bosqichidagi darslarni ko‘radi. So‘zdagi
“Yodladim” va grammatikadagi “O‘qib chiqdim” holatlari serverda saqlanadi;
ustoz ularni profil yoki o‘rganish natijalari bo‘limlaridan ko‘ra oladi.
“Yodladim” — o‘quvchining o‘z belgilashi, avtomatik bilim sinovi emas.

## PDF manbalari

- 1A: 8 dars, 439 lug‘at yozuvi, 32 grammatika bandi.
- 1B: 8 dars (9–16), 378 lug‘at yozuvi, 32 grammatika bandi.
- 2A: 9 dars, 484 lug‘at yozuvi, 36 grammatika bandi.
- 2B: 9 dars (10–18), 401 lug‘at yozuvi, 35 grammatika bandi.

Manba matnlari `bot_app/data/curriculum.json` da saqlangan.
Import qayta bajarilganda dublikat yaratilmaydi va ustoz tahrirlari saqlanadi.
Faqat manba bilan ataylab almashtirish uchun `--update-existing` ishlatiladi.
Avvalgi darsga bog‘lanmagan lug‘at yozuvlari o‘chirilmagan; ular admin panelda
mavjud, lekin o‘quvchining kitob darslariga qo‘shilmagan.

PDF’dan qayta ajratish: `python3 scripts/extract_curriculum.py` (PyMuPDF/`fitz` kerak).

Manbadagi holatlar:
- 1B, 16-darsdagi 26-so‘z ikki marta bosilgan; bir marta import qilingan.
- 1A grammatikaning 23-bandida o‘zbekcha izoh yo‘q; sayt bu haqda aytadi.
- 2A grammatikada 16-raqam yo‘q; qo‘shimcha qoida to‘qib chiqarilmagan.
- PDF’larda mavzu nomlari o‘rnida dars raqamlari bor; shu tartib saqlangan.
- Matnlarning manbadagi imlo va tarjimalari saqlangan, ustoz tahrirlashi mumkin.

## Tekshirish

```bash
python3 manage.py test bot_app
python3 manage.py check
```

Gemini ulanishi quyida sozlanadi. Telegram orqali ommaviy xabar yuborish hali ulanmagan.
Sayt ichidagi xabarlar ishlaydi. Bot o‘quvchi yaratmaydi; ID ustoz orqali beriladi.

## Ikki xil mashq va ko‘rinish sozlamalari

- **Grammatika:** kitobdagi qoidalarga mos bo‘sh joyli gaplar. 34 darsga 34 ta boshlang‘ich
  mashq yozilgan. `python3 manage.py import_exercises` ularni takrorlamasdan kiritadi.
  Ustoz “Grammatika mashqlari” orqali savol, variant va izohlarni o‘zgartira oladi.
  Savollar tegishli qoidaning darsidan aniq 1A/1B/2A/2B darajasini oladi.
- **Lug‘at:** dars bo‘yicha flashkartalar. Bosilganda karta silkinadi va tarjimasi ochiladi.
  “Yodladim” va “Yana takrorlayman” oldingi so‘z progressi bilan bitta bazada saqlanadi.
- Grammatika javoblari serverda baholanadi. Test savollari nusxasi saqlanadi;
  ustoz keyinchalik savolni tahrirlasa, eski natija o‘zgarmaydi. Takror yuborish
  bitta natijani ikki marta hisoblamaydi.
- Yorug‘/qorong‘i ko‘rinish va animatsiya sozlamalari brauzerda saqlanadi.
  Qurilmadagi “harakatlarni kamaytirish” sozlamasi ham hisobga olinadi.

## Gemini ulash

1. `.env` faylida `GEMINI_API_KEY=` dan keyin kalitni kiriting.
2. `GEMINI_MODEL` va `GEMINI_FALLBACK_MODEL` hisobingizda mavjud modellarga mos bo‘lsin.
3. Serverni qayta ishga tushiring. Natija oynasida “AI bilan tahlil qilish” yoki
   bosh sahifada “AI tavsiyasini olish”ni bosing.

[Rasmiy Gemini REST API](https://ai.google.dev/api/generate-content) orqali ishlaydi.
[Model nomlari](https://ai.google.dev/gemini-api/docs/models) muhit sozlamalaridan boshqariladi.
Kalit serverdan brauzerga yoki promptga uzatilmaydi. Ism, Student ID va Telegram ID
AI’ga yuborilmaydi; tahlil uchun kitob bosqichi va kerakli mashq natijalari yuboriladi. AI chatda o‘quvchi yozgan savol, oxirgi suhbat va tanlangan dars matni ham yuboriladi.

Asosiy model ishlamasa, zaxira Gemini modeli sinab ko‘riladi. Zaxira uchun boshqa loyiha
kaliti `GEMINI_FALLBACK_API_KEY` bilan berilishi mumkin. Ikkala model ham Gemini xizmatida:
provayder umumiy uzilishi yoki umumiy kvota muammosi ikkala so‘rovga ham ta’sir qilishi mumkin.
Har model so‘rovida 30 soniyalik timeout bor. Ikkalasi ham javob bermasa, AI xatosi ko‘rsatiladi;
mashq va natijalar ishlashda davom etadi. Test AI tahlili bazada saqlanadi; qayta o‘qish
qo‘shimcha API so‘rovi yubormaydi. Umumiy tavsiya 5 daqiqa keshlanadi, yangi AI so‘rovlari
orasida 45 soniya tanaffus bor. Ushbu ishlab chiqish serverida cheklov Django local-memory
cache orqali ishlaydi; ko‘p jarayonli serverda umumiy cache sozlash kerak.


## AI dars, suhbat va o‘quvchi testlari

- O‘quvchi bosh sahifasida dars tanlab tushuntirish oladi, koreys tili haqida savol beradi yoki 5 ta yangi AI test yaratadi.
- AI faqat o‘quvchining kitob bosqichidagi darslardan foydalanadi. Suhbatning oxirgi 6 juft savol-javobi server keshida 1 soat saqlanadi.
- Test JSON tuzilishi, qoida nomi, variantlar va javob indeksi tekshiriladi. Bu tekshiruv tilga oid mazmunning mutlaq to‘g‘riligini kafolatlamaydi.
- Javob kalitlari serverda qoladi, mavjud mashq tizimi testni baholaydi va natijani saqlaydi. Natija oynasidagi AI tahlili ham ishlatiladi.
- Ustoz menyusidagi **AI dars** mavzu bo‘yicha konspekt yaratadi. Konspekt avtomatik nashr qilinmaydi; ustoz tekshirib dars yoki grammatika shakliga kiritadi.
- Chat so‘rovlari orasida 8 soniya, yangi AI testlar orasida 45 soniya, ustoz konspektlari orasida 30 soniya cheklov bor.
- Ishlash uchun `.env` ichida haqiqiy `GEMINI_API_KEY` va hisobda mavjud model nomlari kerak. Kalitsiz tushunarli xabar ko‘rsatiladi; oddiy dars va mashqlar ishlayveradi.
