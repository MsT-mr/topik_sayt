import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from bot_app.models import Grammar, GrammarExercise


class Command(BaseCommand):
    help = 'Kitob qoidalariga mos bo‘sh joyli grammatika mashqlarini kiritish.'

    @transaction.atomic
    def handle(self, *args, **options):
        data = json.loads((Path(__file__).resolve().parents[2] / 'data/grammar_exercises.json').read_text())
        created = 0
        for row in data:
            grammar = Grammar.objects.filter(source_key=row['grammar_source']).first()
            if not grammar:
                raise CommandError('Avval import_curriculum buyrug‘ini bajaring.')
            fields = {k:v for k,v in row.items() if k not in ('grammar_source','source_key')}
            draft = GrammarExercise(grammar=grammar, **fields)
            draft.full_clean()
            _, new = GrammarExercise.objects.get_or_create(source_key=row['source_key'], defaults={'grammar':grammar, **fields})
            created += new
        self.stdout.write(self.style.SUCCESS(f'{created} ta yangi grammatika mashqi qo‘shildi.'))
