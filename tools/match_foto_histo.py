#!/usr/bin/env python3
"""Match extracted foto histo questions against ALL existing histo tests
and append new ones to 'histo zápočet Moodle.json'.

Inputs:
  - tools/out/foto_histo.json
  - testy/histo 2.json
  - testy/histológia 2 zápočet.json
  - testy/histo zápočet Moodle.json   (will be UPDATED in place)

Output:
  - tools/out/REPORT_foto_histo.md
  - testy/histo zápočet Moodle.json (with appended new questions)
"""
import json
import re
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).parent.parent
TESTY_DIR = ROOT / 'testy'
OUT_DIR = ROOT / 'tools' / 'out'

EXISTING_TESTS = [
    'histo 2.json',
    'histológia 2 zápočet.json',
    'histo zápočet Moodle.json',
]
EXTRACTED_FILE = 'foto_histo.json'
TARGET_TEST = 'histo zápočet Moodle.json'
REPORT_PATH = OUT_DIR / 'REPORT_foto_histo.md'

FUZZY_THRESHOLD = 0.88


def normalize(text: str) -> str:
    text = text.lower()
    text = ''.join(c for c in unicodedata.normalize('NFD', text)
                   if unicodedata.category(c) != 'Mn')
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def correct_to_bool_label(correct_indices, answers):
    if not correct_indices or not answers:
        return None
    idx = correct_indices[0]
    if idx < 0 or idx >= len(answers):
        return None
    ans_text = answers[idx].strip().lower()
    if ans_text.startswith('pravda'):
        return 'pravda'
    if ans_text.startswith('nepravda'):
        return 'nepravda'
    return None


def load_existing():
    entries = []
    for fn in EXISTING_TESTS:
        path = TESTY_DIR / fn
        if not path.exists():
            print(f'WARN: {path} missing', file=sys.stderr)
            continue
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, list):
            continue
        for test in data:
            for q in test.get('questions', []):
                correct = correct_to_bool_label(q.get('correct') or [], q.get('answers') or [])
                if correct is None:
                    continue
                qtext = q.get('question', '').strip()
                if not qtext:
                    continue
                entries.append({
                    'norm': normalize(qtext),
                    'orig': qtext,
                    'correct': correct,
                    'source': fn,
                })
    return entries


def load_extracted():
    items = []
    path = OUT_DIR / EXTRACTED_FILE
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    for q in data:
        qtext = (q.get('question') or '').strip()
        correct = (q.get('correct') or '').strip().lower()
        if not qtext or correct not in ('pravda', 'nepravda'):
            continue
        items.append({
            'norm': normalize(qtext),
            'orig': qtext,
            'correct': correct,
            'source_image': q.get('source_image'),
        })
    return items


def find_match(query_norm, existing, fuzzy_threshold=FUZZY_THRESHOLD):
    for e in existing:
        if e['norm'] == query_norm:
            return e, 'exact'
    best_ratio = 0.0
    best = None
    for e in existing:
        if abs(len(e['norm']) - len(query_norm)) > max(40, len(query_norm) * 0.3):
            continue
        r = SequenceMatcher(None, query_norm, e['norm']).ratio()
        if r > best_ratio:
            best_ratio = r
            best = e
    if best and best_ratio >= fuzzy_threshold:
        return best, 'fuzzy'
    return None, 'none'


def dedupe(items, fuzzy_threshold=FUZZY_THRESHOLD):
    unique = []
    conflicts = []
    for it in items:
        match_idx = None
        for i, u in enumerate(unique):
            if u['norm'] == it['norm']:
                match_idx = i
                break
            if abs(len(u['norm']) - len(it['norm'])) <= max(40, len(it['norm']) * 0.3):
                r = SequenceMatcher(None, u['norm'], it['norm']).ratio()
                if r >= fuzzy_threshold:
                    match_idx = i
                    break
        if match_idx is None:
            unique.append({
                'norm': it['norm'],
                'orig': it['orig'],
                'correct': it['correct'],
                'sources': [it['source_image']],
            })
        else:
            u = unique[match_idx]
            u['sources'].append(it['source_image'])
            if u['correct'] != it['correct']:
                conflicts.append((u, it))
    return unique, conflicts


def build_report(unique, intra_conflicts, classification):
    lines = []
    lines.append('# Foto histo — porovnanie s existujúcimi testami\n')

    n_total = len(unique)
    n_ok = sum(1 for u, m, _k in classification if m and m['correct'] == u['correct'])
    n_conflict = sum(1 for u, m, _k in classification if m and m['correct'] != u['correct'])
    n_new = sum(1 for _u, m, _k in classification if m is None)
    n_exact = sum(1 for _u, m, k in classification if m and k == 'exact')
    n_fuzzy = sum(1 for _u, m, k in classification if m and k == 'fuzzy')

    lines.append('## Súhrn\n')
    lines.append(f'- **Spolu unikátnych otázok zo 14 fotiek**: {n_total}')
    lines.append(f'- **Zhoda s existujúcimi (správne)**: {n_ok}')
    lines.append(f'  - z toho **exact match**: {n_exact - n_conflict}')
    lines.append(f'  - z toho **fuzzy match (≥{FUZZY_THRESHOLD})**: {n_fuzzy} (over manuálne)')
    lines.append(f'- **Konflikt v odpovedi**: {n_conflict}')
    lines.append(f'- **Nové otázky (idú do `{TARGET_TEST}`)**: {n_new}')
    lines.append('')

    if intra_conflicts:
        lines.append('## Konflikty MEDZI fotkami (rovnaká otázka, rôzna odpoveď)\n')
        for a, b in intra_conflicts:
            lines.append(f'- **{a["orig"]}**')
            lines.append(f'  - zdroje A `{a["sources"]}` → `{a["correct"]}`')
            lines.append(f'  - zdroj B `{b["source_image"]}` → `{b["correct"]}`')
        lines.append('')

    conflicts = [(u, m, k) for u, m, k in classification if m and m['correct'] != u['correct']]
    if conflicts:
        lines.append('## Konflikty s existujúcimi testami\n')
        for u, m, k in conflicts:
            lines.append(f'### {u["orig"]}')
            lines.append(f'- match: **{k}** (zdroj v Quizlet/Moodle: `{m["source"]}`)')
            lines.append(f'- existujúci ({m["source"]}): **{m["correct"]}**')
            lines.append(f'- foto: **{u["correct"]}** — výskyty: {u["sources"]}')
            if k == 'fuzzy':
                lines.append(f'- text v existujúcom (pre kontrolu): _{m["orig"]}_')
            lines.append('')

    fuzzy_oks = [(u, m, k) for u, m, k in classification
                 if m and m['correct'] == u['correct'] and k == 'fuzzy']
    if fuzzy_oks:
        lines.append('## Fuzzy zhody (odpoveď OK, ale text mierne odlišný — over)\n')
        for u, m, k in fuzzy_oks:
            lines.append(f'- **Foto**: _{u["orig"]}_')
            lines.append(f'  - **Existujúci** ({m["source"]}): _{m["orig"]}_')
            lines.append(f'  - obe: `{u["correct"]}`')
            lines.append('')

    news = [u for u, m, _ in classification if m is None]
    if news:
        lines.append(f'## Nové otázky ({len(news)}) — pridávané do `{TARGET_TEST}`\n')
        for u in news:
            lines.append(f'- [{u["correct"]}] {u["orig"]}')
        lines.append('')

    return '\n'.join(lines)


def append_to_target(news):
    """Append new pravda/nepravda questions to the existing target test."""
    path = TESTY_DIR / TARGET_TEST
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    if not isinstance(data, list) or not data:
        raise RuntimeError(f'Unexpected structure in {path}')
    test = data[0]
    questions = test.setdefault('questions', [])
    for u in news:
        ans = ['pravda', 'nepravda']
        idx = ans.index(u['correct'])
        questions.append({
            'question': u['orig'],
            'answers': ans,
            'correct': [idx],
        })
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return len(questions)


def main():
    existing = load_existing()
    extracted = load_extracted()
    print(f'Existing histo pravda/nepravda questions: {len(existing)}')
    print(f'Extracted from 14 photos: {len(extracted)}')

    unique, intra_conflicts = dedupe(extracted)
    print(f'After dedupe across photos: {len(unique)} unique')
    print(f'Intra-photo conflicts: {len(intra_conflicts)}')

    classification = []
    for u in unique:
        match, kind = find_match(u['norm'], existing)
        classification.append((u, match, kind))

    report = build_report(unique, intra_conflicts, classification)
    REPORT_PATH.write_text(report, encoding='utf-8')
    print(f'Report: {REPORT_PATH}')

    news = [u for u, m, _ in classification if m is None]
    if news:
        total_after = append_to_target(news)
        print(f'Appended {len(news)} new questions to {TARGET_TEST} (now {total_after} total)')
    else:
        print('No new questions to append.')


if __name__ == '__main__':
    main()
