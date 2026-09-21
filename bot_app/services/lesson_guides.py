"""Optional supplemental study material. Original curriculum remains unchanged."""
import json
from pathlib import Path

GUIDE_DIR = Path(__file__).resolve().parents[1] / 'data' / 'lesson_guides'


def validate_guide(data, source_keys):
    def text(value, limit=3500):
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise ValueError('Invalid guide text')
    if not isinstance(data, dict):
        raise ValueError('Invalid guide')
    text(data.get('overview'))
    goals = data.get('goals')
    if not isinstance(goals, list) or not 3 <= len(goals) <= 5:
        raise ValueError('Invalid goals')
    for goal in goals:
        text(goal)
    rules = data.get('rules')
    if not isinstance(rules, list) or {r.get('source_key') for r in rules if isinstance(r, dict)} != set(source_keys) or len(rules) != len(source_keys):
        raise ValueError('Missing rules')
    for rule in rules:
        for key in ('meaning', 'formation', 'usage', 'mistake'):
            text(rule.get(key))
        examples = rule.get('examples')
        if not isinstance(examples, list) or len(examples) != 3:
            raise ValueError('Need three examples')
        for example in examples:
            if not isinstance(example, dict):
                raise ValueError('Invalid example')
            text(example.get('ko')); text(example.get('uz'))
        exercise = rule.get('exercise')
        if not isinstance(exercise, dict):
            raise ValueError('Invalid exercise')
        for key in ('question', 'answer', 'explanation'):
            text(exercise.get(key))
    dialog = data.get('dialogue')
    if not isinstance(dialog, list) or not 4 <= len(dialog) <= 8:
        raise ValueError('Invalid dialogue')
    for line in dialog:
        if not isinstance(line, dict):
            raise ValueError('Invalid dialogue line')
        for key in ('speaker', 'ko', 'uz'):
            text(line.get(key))
    return data


def load_guide(lesson):
    path = GUIDE_DIR / f'{lesson.book_level}-{lesson.number}.json'
    try:
        data = json.loads(path.read_text())
        keys = list(lesson.grammar.values_list('source_key', flat=True))
        validate_guide(data, keys)
        return data
    except (OSError, ValueError, TypeError, KeyError):
        return None
