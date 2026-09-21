"""Extract the supplied Seoul textbook tables; preserve source text and provenance."""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
import fitz

ROOT = Path(__file__).resolve().parents[1]

def clean(value):
    return re.sub(r'\s+', ' ', value or '').strip()


def extract():
    vocabulary, grammar, warnings = [], [], []
    book, lesson = None, None
    doc = fitz.open(ROOT / '서울대 1A-2B.pdf')
    seen = {}
    for page_no in range(1, len(doc)):
        page = doc[page_no]
        tables = page.find_tables().tables
        if len(tables) != 1:
            raise ValueError(f'Expected one table on page {page_no + 1}')
        table = tables[0]
        rows = table.extract()
        if table.col_count == 13:  # Page 9 has merged cells; its two halves remain separate.
            rows = [[clean(v) for v in row[:7] if clean(v)] + [clean(v) for v in row[7:] if clean(v)] for row in rows]
            assert all(len(row) == 6 for row in rows)
        assert all(len(row) == 6 for row in rows)
        for offset in (0, 3):
            for row in rows:
                cells = [clean(v) for v in row[offset:offset+3]]
                text = ' '.join(cells)
                book_match = re.search(r'서울대.*?([12][AB])', text)
                if book_match:
                    book = book_match[1]
                    continue
                lesson_match = re.fullmatch(r'(?:№\s*)?(\d+)\s*과', text.strip())
                if lesson_match:
                    lesson = int(lesson_match[1])
                    continue
                if not any(cells):
                    continue
                if not cells[0].isdigit() or not cells[1] or not cells[2] or not book or not lesson:
                    raise ValueError(f'Unparsed vocabulary page {page_no+1}: {cells}')
                number = int(cells[0])
                key = f'vocab:{book}:{lesson}:{number}'
                entry = dict(book=book, lesson=lesson, order=number, korean=cells[1], translation=cells[2], source_key=key, source_page=page_no+1)
                if key in seen:
                    if (entry['korean'], entry['translation']) != (seen[key]['korean'], seen[key]['translation']):
                        raise ValueError(f'Conflicting duplicate {key}: {entry}')
                    warnings.append(f'Identical source row repeated: {key}, page {page_no+1}; imported once.')
                    continue
                seen[key] = entry
                vocabulary.append(entry)
    for book, filename in [('1A','서울대 1A 문법.pdf'),('1B','서울대 1B 문법.pdf'),('2A','서울대 2A 문법.pdf'),('2B','서울대 2B.pdf')]:
        page = fitz.open(ROOT / filename)[0]
        rows = page.find_tables().tables[0].extract()
        lesson = None
        for indices in ((0,1,2,5),(8,9,10,13)):
            offset = indices[0]
            for row in rows[2:]:
                part = row[:8] if offset == 0 else row[8:]
                heading = re.search(r'제\s*(\d+)\s*과', ' '.join(clean(v) for v in part))
                if heading:
                    lesson = int(heading[1])
                    continue
                cells = [clean(row[i]) for i in indices]
                if not any(cells):
                    continue
                if not cells[0].isdigit() or not lesson:
                    raise ValueError(f'Unparsed grammar {book}: {cells}')
                number = int(cells[0])
                if not cells[2]:
                    warnings.append(f'Grammar {book} #{number}: Uzbek explanation empty in source.')
                grammar.append(dict(book=book, lesson=lesson, order=number, title=cells[1], explanation=cells[2], examples=cells[3], source_key=f'grammar:{book}:{number}', source_page=1, source_file=filename))
    groups = defaultdict(list)
    for entry in vocabulary:
        groups[(entry['book'], entry['lesson'])].append(entry['order'])
    for key, numbers in groups.items():
        missing = sorted(set(range(1, max(numbers)+1)) - set(numbers))
        if missing:
            warnings.append(f'Vocabulary {key}: missing source numbers {missing}.')
    warnings.append('Grammar 2A: source numbering skips 16; no rule invented.')
    data = dict(vocabulary=vocabulary, grammar=grammar, warnings=warnings)
    target = ROOT / 'bot_app/data/curriculum.json'
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
    print('Vocabulary:', Counter(e['book'] for e in vocabulary))
    print('Grammar:', Counter(e['book'] for e in grammar))
    print('Lessons:', len(groups))
    print('Warnings:', *warnings, sep='\n')

if __name__ == '__main__':
    extract()
