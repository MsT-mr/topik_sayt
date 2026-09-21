import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from bot_app.models import Lesson, Vocabulary, Grammar


class Command(BaseCommand):
    help = 'PDF manbalaridan tayyorlangan 1A–2B lug‘at va grammatikani darslar bo‘yicha yuklaydi.'

    def add_arguments(self, parser):
        parser.add_argument('--update-existing', action='store_true', help='Import qilingan matnlardagi ustoz tahrirlarini ham manba bilan almashtirish.')

    @transaction.atomic
    def handle(self, *args, **options):
        path = Path(__file__).resolve().parents[2] / 'data/curriculum.json'
        data = json.loads(path.read_text())
        if len(data['vocabulary']) != 1702 or len(data['grammar']) != 135:
            raise CommandError('Kutilgan manba sonlari mos emas. Import to‘xtatildi.')
        created = {'vocabulary': 0, 'grammar': 0}
        lessons = {}
        for kind, model, fields in [('vocabulary', Vocabulary, ('korean','translation','order','source_page')), ('grammar', Grammar, ('title','explanation','examples','order','source_page'))]:
            for entry in data[kind]:
                key = (entry['book'], entry['lesson'])
                if key not in lessons:
                    lessons[key], _ = Lesson.objects.get_or_create(book_level=key[0], number=key[1], defaults={'title': f'{key[1]}-dars'})
                defaults = {field: entry[field] for field in fields}
                defaults['lesson'] = lessons[key]
                if kind == 'vocabulary':
                    defaults['level'] = int(entry['book'][0])
                method = model.objects.update_or_create if options['update_existing'] else model.objects.get_or_create
                obj, new = method(source_key=entry['source_key'], defaults=defaults)
                created[kind] += new
        self.stdout.write(self.style.SUCCESS(f"{len(lessons)} dars. Yangi: {created['vocabulary']} so‘z, {created['grammar']} qoida."))
        for warning in data['warnings']:
            self.stdout.write(self.style.WARNING(warning))
