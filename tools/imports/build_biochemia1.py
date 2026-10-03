#!/usr/bin/env python3
"""Prevedie lokálne PDF Biochémia 1 otázky do formátu LFUK tester.

Použitie z koreňa projektu:
    python3 tools/imports/build_biochemia1.py
    python3 tools/imports/build_biochemia1.py --output /tmp/biochemia-testy

Vyžaduje pdftohtml, pdftoppm (Poppler), Pillow a NumPy. Nevolá AI ani sieť.
Viditeľný text oddeľuje od skrytej OCR vrstvy ručných poznámok. Farebné bodky
pri odpovediach číta z rastra; krížiky a sporné opravy rieši vizuálna kontrola
uložená v biochemia1_review.json. Ide o prepis zdroja, nie odbornú revíziu.
Existujúce výstupy nikdy neprepisuje; na nový beh použite iný --output.
"""

import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unicodedata
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = Path(__file__).with_name('biochemia1_review.json')


def read_rows(pdf, scratch):
    xml = scratch / 'source.xml'
    subprocess.run(
        ['pdftohtml', '-q', '-xml', '-hidden', '-i', '-zoom', '1', str(pdf), str(xml)],
        check=True, capture_output=True,
    )
    root = ET.parse(xml).getroot()
    fonts = {font.get('id'): font.attrib for font in root.iter('fontspec')}
    rows = []
    pages = root.findall('page')
    for page in pages:
        lines = defaultdict(list)
        for element in page.findall('text'):
            if float(fonts[element.get('font')].get('opacity', '1')) == 0:
                continue
            text = ''.join(element.itertext())
            if text.strip():
                lines[int(element.get('top'))].append((int(element.get('left')), text))
        for top, fragments in sorted(lines.items()):
            fragments.sort()
            rows.append({
                'page': int(page.get('number')), 'top': top,
                'left': fragments[0][0],
                'text': ''.join(text for _, text in fragments).strip(),
            })
    return rows, len(pages)


def parse_questions(rows):
    questions, empty_numbers = [], []
    current = None
    for row in rows:
        text = row['text']
        if re.fullmatch(r'\d+\.', text):
            if current:
                (questions if current['question'] else empty_numbers).append(current)
            current = {
                'number': int(text[:-1]), 'page': row['page'],
                'question': '', 'answers': [], 'positions': [], 'labels': [],
            }
            continue
        if not current or re.fullmatch(r'-+', text) or text == 'A,B,C,':
            continue
        answer = re.match(r'^([a-h])[),]\s*(.*)', text)
        if answer:
            current['answers'].append(answer[2])
            current['labels'].append(answer[1])
            current['positions'].append(row)
        elif current['answers']:
            current['answers'][-1] += ' ' + text
        else:
            current['question'] += ' ' + text
    if current:
        (questions if current['question'] else empty_numbers).append(current)
    for sequence, question in enumerate(questions, 1):
        question['sequence'] = sequence
        question['question'] = question['question'].strip()
        if question['labels'] not in [list('abcd'), list('efgh')]:
            raise ValueError(f'Neúplné možnosti pri otázke {sequence}: {question["labels"]}')
        if not all(question['answers']):
            raise ValueError(f'Prázdna možnosť pri otázke {sequence}')
    return questions, [{'number': q['number'], 'page': q['page']} for q in empty_numbers]


def rasterize(pdf, page, scratch):
    path = scratch / f'{page:02}.png'
    subprocess.run([
        'pdftoppm', '-f', str(page), '-l', str(page), '-r', '216',
        '-x', '1200', '-y', '420', '-W', '1200', '-H', '1620',
        '-png', '-singlefile', str(pdf), str(path.with_suffix('')),
    ], check=True, capture_output=True)
    return page, path


def colored_components(path):
    with Image.open(path) as image:
        pixels_rgb = np.asarray(image.convert('RGB'), dtype=np.int16)
    red, green, blue = (pixels_rgb[:, :, i] for i in range(3))
    masks = {
        'red': (red - green > 20) & (red - blue > 15),
        'blue': (blue - red > 30) & (green - red > 20),
    }
    components = []
    for color, mask in masks.items():
        ys, xs = np.where(mask)
        remaining = set(zip(xs.tolist(), ys.tolist()))
        while remaining:
            point = remaining.pop()
            pending, connected = [point], [point]
            while pending:
                x, y = pending.pop()
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        neighbor = x + dx, y + dy
                        if neighbor in remaining:
                            remaining.remove(neighbor)
                            pending.append(neighbor)
                            connected.append(neighbor)
            if len(connected) < 3:
                continue
            xs, ys = zip(*connected)
            components.append({
                'color': color, 'pixels': len(connected),
                'box': [min(xs) / 3 + 400, min(ys) / 3 + 140,
                        (max(xs) + 1) / 3 + 400, (max(ys) + 1) / 3 + 140],
            })
    return components


def detect_answers(questions, components):
    for question in questions:
        question['correct'] = []
        for index, row in enumerate(question['positions']):
            x, y = row['left'], row['top']
            for component in components[row['page']]:
                left, top, right, bottom = component['box']
                cx, cy = (left + right) / 2, (top + bottom) / 2
                if (x - 9 <= cx < x + 1 and y + 2 <= cy <= y + 10
                        and right - left <= 6 and bottom - top <= 6
                        and component['pixels'] >= 4):
                    question['correct'].append(index)
                    break


def prepare_outputs(questions, review, pdf, empty_numbers, page_count):
    reasons = defaultdict(list)
    for sequence, correction in review['visualChecks'].items():
        question = questions[int(sequence) - 1]
        if 'correct' in correction:
            question['correct'] = correction['correct']
        if 'defer' in correction:
            reasons[int(sequence)].append(correction['defer'])
    for sequence, stem in review['cleanQuestionText'].items():
        questions[int(sequence) - 1]['question'] = stem

    duplicates = defaultdict(list)
    for question in questions:
        sequence = question['sequence']
        if not question['correct']:
            reasons[sequence].append('V PDF nie je jednoznačne označená správna odpoveď.')
        if any('...' in text or '…' in text
               for text in [question['question'], *question['answers']]):
            reasons[sequence].append('Zdroj obsahuje nedokončený text možnosti (výpustku).')
        duplicates[(question['question'], tuple(question['answers']))].append(question)

    duplicate_groups = []
    for group in duplicates.values():
        if len(group) < 2:
            continue
        sequences = [question['sequence'] for question in group]
        conflict = len({tuple(question['correct']) for question in group}) > 1
        duplicate_groups.append({'sequences': sequences, 'conflictingAnswers': conflict})
        if conflict:
            for sequence in sequences:
                reasons[sequence].append(
                    f'Rovnaký text má rozdielne označenia odpovedí; poradia {sequences}.')

    files, deferred, summary_parts = {}, [], []
    for start in range(0, len(questions), 100):
        block = questions[start:start + 100]
        accepted = []
        for question in block:
            sequence = question['sequence']
            source = {
                'file': pdf.name, 'sequence': sequence,
                'questionNumber': question['number'], 'page': question['page'],
                'endPage': question['positions'][-1]['page'],
                'answerLabels': question['labels'],
            }
            item = {
                'question': question['question'], 'answers': question['answers'],
                'correct': question['correct'], 'source': source,
            }
            if reasons[sequence]:
                item['detectedCorrect'] = item.pop('correct')
                item['correct'] = None
                item['reviewReasons'] = reasons[sequence]
                deferred.append(item)
            else:
                if not item['correct'] or not all(type(i) is int and 0 <= i < 4
                                                 for i in item['correct']):
                    raise ValueError(f'Neplatný kľúč odpovedí pri otázke {sequence}')
                accepted.append(item)
        part = start // 100 + 1
        title = f'Biochémia 1 - {part:02}'
        last = start + len(block)
        filename = f'{title}.json'
        omitted = len(block) - len(accepted)
        files[filename] = [{
            'title': title,
            'description': (
                f'Otázky z PDF Biochémia 1 otázky, časť {part:02}. '
                f'Poradie v zdroji {start + 1}–{last}, '
                f'strany {block[0]["page"]}–{block[-1]["positions"][-1]["page"]}. '
                f'Odpovede podľa označenia v PDF. Otázky odložené na kontrolu: {omitted}.'
            ),
            'questions': accepted,
        }]
        summary_parts.append({'file': filename, 'questions': len(accepted), 'deferred': omitted})

    summary = {
        'sourceFile': pdf.name, 'sourceSha256': review['sourceSha256'],
        'sourcePages': page_count, 'totalQuestions': len(questions),
        'importedQuestions': sum(part['questions'] for part in summary_parts),
        'deferredQuestions': len(deferred), 'tests': summary_parts,
        'answerPolicy': 'Prepis vyznačených odpovedí v PDF, bez odbornej revízie.',
        'reviewPolicy': 'Nejasné, neoznačené, neúplné a protichodné otázky sú mimo testov. '
                        'correct=null v kontrolnom súbore znamená neoverený kľúč; '
                        'detectedCorrect zachováva pracovnú detekciu, nie schválené odpovede.',
        'numberingPolicy': 'source.sequence je poradie 1–729; source.questionNumber '
                           'je pôvodné, miestami duplicitné alebo preskočené číslo v PDF.',
        'duplicatePolicy': 'Opakované otázky sú zachované v pôvodnom poradí.',
        'emptyNumberingArtifacts': empty_numbers,
        'duplicateGroups': duplicate_groups,
    }
    if summary['importedQuestions'] + len(deferred) != len(questions):
        raise ValueError('Nesedí počet spracovaných otázok.')
    files['biochemia1/na_kontrolu.json'] = deferred
    files['biochemia1/prehlad.json'] = summary
    return files, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'testy')
    args = parser.parse_args()
    if args.pdf:
        pdf = args.pdf.resolve()
    else:
        candidates = [p for p in (ROOT / 'sources').glob('*.pdf')
                      if unicodedata.normalize('NFC', p.name) == 'Biochémia 1 otázky.pdf']
        if len(candidates) != 1:
            parser.error('Zdrojové PDF sa nepodarilo jednoznačne nájsť; použite --pdf.')
        pdf = candidates[0]
    review = json.loads(MANIFEST.read_text(encoding='utf-8'))
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    if digest != review['sourceSha256']:
        parser.error('PDF sa zmenilo. Vizuálnu kontrolu treba zopakovať pre nový zdroj.')

    with tempfile.TemporaryDirectory(prefix='biochemia1-') as directory:
        scratch = Path(directory)
        rows, page_count = read_rows(pdf, scratch)
        questions, empty_numbers = parse_questions(rows)
        if len(questions) != review['expectedQuestions'] or page_count != review['expectedPages']:
            raise ValueError('Počet strán alebo otázok nesúhlasí s kontrolovaným zdrojom.')
        print(f'Načítané: {len(questions)} otázok, {page_count} strán.', flush=True)
        with ThreadPoolExecutor(max_workers=4) as pool:
            rendered = dict(pool.map(lambda p: rasterize(pdf, p, scratch), range(1, page_count + 1)))
        components = {page: colored_components(path) for page, path in rendered.items()}
        detect_answers(questions, components)
        files, summary = prepare_outputs(questions, review, pdf, empty_numbers, page_count)

    # Pred prvým zápisom overiť všetky kolízie; živé testy sa neprepisujú.
    existing = [str(args.output / name) for name in files if (args.output / name).exists()]
    if existing:
        parser.error('Výstupy už existujú; použite nový --output: ' + ', '.join(existing))
    for filename, data in files.items():
        path = args.output / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x', encoding='utf-8') as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
    for part in summary['tests']:
        print(f'{part["file"]}: {part["questions"]} otázok, {part["deferred"]} na kontrolu')
    print(f'Spolu: {summary["importedQuestions"]} v testoch, '
          f'{summary["deferredQuestions"]} na kontrolu.')


if __name__ == '__main__':
    main()
