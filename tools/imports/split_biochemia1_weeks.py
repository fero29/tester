#!/usr/bin/env python3
"""Rozdelí už extrahované otázky Biochémie 1 podľa plánu ZS 2026/2027.

    python3 tools/imports/split_biochemia1_weeks.py --output /tmp/biochemia-tyzdne
    python3 tools/imports/split_biochemia1_weeks.py --activate

Zaradenie podľa obsahu je uložené v biochemia1_weeks.json. Skript nepriraďuje
otázky podľa kľúčových slov ani ich poradia; iba vykoná a overí toto zaradenie.
Presné duplikáty preberajú rovnakú kategóriu, ale zostávajú samostatnými otázkami.
--activate uloží 12 týždenných testov a test Na zaradenie do testy/ a presunie
pôvodných osem častí do podpriečinka so zálohou, ktorý aplikácia nenačítava.
Texty, možnosti, odpovede a pôvodných 45 otázok na kontrolu sa nemenia.
"""

import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = Path('biochemia1/archiv_povodneho_rozdelenia')
ANSWER_REVIEW = Path('biochemia1/na_kontrolu.json')
REPORT = Path('biochemia1/rozdelenie_podla_tyzdnov.json')


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def encode(data):
    return (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def question_digest(questions):
    return sha256(json.dumps(questions, ensure_ascii=False, sort_keys=True,
                            separators=(',', ':')).encode('utf-8'))


def read_input(tests_dir, manifest):
    files, questions = [], []
    for part in range(1, 9):
        filename = f'Biochémia 1 - {part:02}.json'
        candidates = [tests_dir / filename, tests_dir / ARCHIVE / filename]
        existing = [p for p in candidates if p.is_file()]
        if len(existing) != 1:
            raise ValueError(f'Očakávaný práve jeden originál: {filename}')
        path = existing[0]
        payload = path.read_bytes()
        tests = json.loads(payload)
        if not isinstance(tests, list) or len(tests) != 1:
            raise ValueError(f'Neočakávaný formát: {path}')
        questions.extend(tests[0]['questions'])
        files.append((path, payload))
    questions.sort(key=lambda q: q['source']['sequence'])
    if (len(questions) != manifest['inputQuestions']
            or question_digest(questions) != manifest['inputQuestionsSha256']):
        raise ValueError('Zdrojové otázky sa zmenili; treba znova skontrolovať mapovanie.')
    review_bytes = (tests_dir / ANSWER_REVIEW).read_bytes()
    if (sha256(review_bytes) != manifest['answerReviewSha256']
            or len(json.loads(review_bytes)) != manifest['answerReviewQuestions']):
        raise ValueError('Pôvodný zoznam 45 otázok na kontrolu sa zmenil.')
    return questions, files, review_bytes


def build(questions, manifest):
    canonical, canonical_ids, duplicates = {}, set(), {}
    for question in questions:
        sequence = question['source']['sequence']
        key = question['question'], tuple(question['answers'])
        if key not in canonical:
            canonical[key] = sequence
            canonical_ids.add(sequence)
        else:
            duplicates[sequence] = canonical[key]

    assigned = {}
    for group in manifest['groups']:
        week = group['week']
        if week is not None and (type(week) is not int or not 1 <= week <= 12):
            raise ValueError(f'Neplatný týždeň: {group["key"]}')
        if not group['reason'] or (week is None and not group['candidateWeeks']):
            raise ValueError(f'Chýba odôvodnenie zaradenia: {group["key"]}')
        for sequence in group['sequences']:
            if sequence in assigned or sequence not in canonical_ids:
                raise ValueError(f'Duplicitné alebo neznáme zaradenie: {sequence}')
            assigned[sequence] = group
    if set(assigned) != canonical_ids:
        raise ValueError(f'Chýbajú zaradenia: {sorted(canonical_ids - set(assigned))}')
    for sequence, original in duplicates.items():
        assigned[sequence] = assigned[original]

    buckets = {week: [] for week in [*range(1, 13), None]}
    assignments = []
    for question in questions:
        sequence = question['source']['sequence']
        group = assigned[sequence]
        week = group['week']
        classification = {
            'week': week,
            'relatedWeeks': group['relatedWeeks'],
            'candidateWeeks': group['candidateWeeks'],
            'topicGroup': group['key'],
            'reason': group['reason'],
            'curriculumFile': manifest['curriculumFile'],
            'curriculumPage': week + 1 if week else None,
            'objectiveRefs': group['objectiveRefs'],
        }
        item = copy.deepcopy(question)
        item['curriculum'] = classification
        buckets[week].append(item)
        assignments.append({
            'sequence': sequence,
            'questionNumber': question['source']['questionNumber'],
            'sourcePage': question['source']['page'],
            'question': question['question'],
            'sameTextAsSequence': duplicates.get(sequence),
            **classification,
        })

    files, summaries = {}, []
    metadata = {'year': manifest['year'], 'category': manifest['category']}
    for entry in manifest['weeks']:
        week, title = entry['week'], entry['title']
        files[Path(f'{title}.json')] = [{
            'title': title, 'description': entry['description'], **metadata,
            'sortOrder': week, 'previousTitles': entry['previousTitles'],
            'questions': buckets[week],
        }]
        summaries.append({
            'week': week, 'title': title, 'file': f'{title}.json',
            'description': entry['description'],
            'questions': len(buckets[week]), 'curriculumPage': entry['curriculumPage'],
            'coverageNote': entry['coverageNote'],
        })
    unassigned = manifest['unassignedTest']
    files[Path(f'{unassigned["title"]}.json')] = [{
        **unassigned, **metadata, 'sortOrder': 13,
        'questions': buckets[None],
    }]
    report = {
        'curriculumFile': manifest['curriculumFile'],
        'curriculumSha256': manifest['curriculumSha256'],
        'academicYear': manifest['academicYear'],
        **metadata,
        'totalQuestions': len(questions),
        'weeklyQuestions': sum(len(buckets[n]) for n in range(1, 13)),
        'unassignedQuestions': len(buckets[None]),
        'answerReviewQuestions': manifest['answerReviewQuestions'],
        'answerReviewFile': str(ANSWER_REVIEW),
        'originalTestsArchive': str(ARCHIVE),
        'assignmentPolicy': manifest['assignmentPolicy'],
        'weekPolicy': manifest['weekPolicy'],
        'tests': summaries,
        'unassignedTest': f'{unassigned["title"]}.json',
        'assignments': assignments,
    }
    validate(questions, files)
    files[REPORT] = report
    return files, report


def validate(originals, files):
    expected = {q['source']['sequence']: q for q in originals}
    occurrences = Counter()
    for path, payload in files.items():
        if len(payload) != 1 or payload[0]['title'] != path.stem:
            raise ValueError(f'Neplatný formát testu: {path}')
        if not payload[0]['questions']:
            raise ValueError(f'Prázdny test: {path}')
        for question in payload[0]['questions']:
            sequence = question['source']['sequence']
            unchanged = {k: v for k, v in question.items() if k != 'curriculum'}
            if unchanged != expected[sequence]:
                raise ValueError(f'Zmenený text, odpovede alebo zdroj: {sequence}')
            if (len(question['answers']) != 4 or not question['correct']
                    or any(type(i) is not int or not 0 <= i < 4 for i in question['correct'])):
                raise ValueError(f'Neplatné odpovede: {sequence}')
            occurrences[sequence] += 1
    if occurrences != Counter(expected.keys()):
        raise ValueError('Otázka chýba alebo je zaradená viackrát.')


def write_outputs(output, files):
    encoded = {output / path: encode(data) for path, data in files.items()}
    conflicts = [str(path) for path, payload in encoded.items()
                 if path.exists() and path.read_bytes() != payload]
    if conflicts:
        raise ValueError('Existujúce odlišné súbory sa neprepíšu: ' + ', '.join(conflicts))
    for path, payload in encoded.items():
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as handle:
            handle.write(payload)


def verify_app_loader(folder, files):
    # Použiť skutočné úložisko aplikácie, bez Flask, AI a zápisu do živých dát.
    sys.path.insert(0, str(ROOT))
    from storage import TestStore
    with tempfile.TemporaryDirectory(prefix='tester-import-check-') as data_dir:
        loaded, _ = TestStore(folder, data_dir).catalog()
    expected = {path.name: data[0] for path, data in files.items() if path.parent == Path('.')}
    actual = {test['filename']: test for test in loaded if test['filename'] in expected}
    if set(actual) != set(expected):
        raise ValueError('Aplikácia nenačítala všetky nové testy.')
    for name, test in expected.items():
        if actual[name] != {**test, 'filename': name, 'version': actual[name]['version']}:
            raise ValueError(f'Aplikácia načítala odlišné dáta testu: {name}')
    if len(actual) != 13:
        raise ValueError('Očakávaných 12 týždenných testov a jeden na zaradenie.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tests-dir', type=Path, default=ROOT / 'testy')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--output', type=Path)
    mode.add_argument('--activate', action='store_true')
    args = parser.parse_args()
    manifest = json.loads(Path(__file__).with_name('biochemia1_weeks.json').read_text())
    if sha256((ROOT / 'sources' / manifest['curriculumFile']).read_bytes()) != manifest['curriculumSha256']:
        raise ValueError('Týždenný plán sa zmenil; treba skontrolovať zaradenie.')
    questions, originals, review = read_input(args.tests_dir, manifest)
    files, report = build(questions, manifest)
    output = args.tests_dir if args.activate else args.output

    # Všetky zálohy a pôvodné dáta overiť ešte pred zápisom výstupov.
    to_archive = []
    if args.activate:
        for path, payload in originals:
            if path.parent == args.tests_dir:
                target = args.tests_dir / ARCHIVE / path.name
                if target.exists() or path.read_bytes() != payload:
                    raise ValueError(f'Kolízia zálohy alebo zmenený originál: {path}')
                to_archive.append((path, target))
    write_outputs(output, files)
    verify_app_loader(output, files)
    for source, target in to_archive:
        target.parent.mkdir(parents=True, exist_ok=True)
        source.rename(target)
    if (args.tests_dir / ANSWER_REVIEW).read_bytes() != review:
        raise ValueError('Pôvodných 45 otázok na kontrolu sa zmenilo.')
    for entry in report['tests']:
        print(f'Týždeň {entry["week"]:02}: {entry["questions"]} otázok')
    print(f'Na zaradenie: {report["unassignedQuestions"]} otázok')
    print(f'Spolu {report["totalQuestions"]}; kontrola integrity a načítania aplikáciou úspešná.')
    if args.activate:
        print(f'Pôvodné testy sú v {args.tests_dir / ARCHIVE}')


if __name__ == '__main__':
    main()
