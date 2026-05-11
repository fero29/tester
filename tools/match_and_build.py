#!/usr/bin/env python3
"""Match extracted Moodle PDF questions against existing Quizlet histo tests.

Inputs:
  - tools/out/zap1.json, zap2.json, zap3.json  (from extract_moodle_pdf.py)
  - testy/histo 2.json
  - testy/histológia 2 zápočet.json

Outputs:
  - tools/out/REPORT.md            — summary + conflicts + new questions
  - testy/histo zápočet Moodle.json — new test JSON for the NEW questions
"""
import json
import os
import re
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).parent.parent
TESTY_DIR = ROOT / 'testy'
OUT_DIR = ROOT / 'tools' / 'out'

EXISTING_TESTS = ['histo 2.json', 'histológia 2 zápočet.json']
EXTRACTED = ['zap1.json', 'zap2.json', 'zap3.json']
NEW_TEST_FILENAME = 'histo zápočet Moodle.json'
NEW_TEST_TITLE = 'histo zápočet Moodle'
NEW_TEST_DESC = 'Otázky z 3 Moodle/Forms screenshot PDF-iek — len tie, ktoré nie sú v existujúcich histo testoch'
REPORT_PATH = OUT_DIR / 'REPORT.md'

FUZZY_THRESHOLD = 0.88


def normalize(text: str) -> str:
    """Lowercase, strip diacritics, collapse whitespace, drop punctuation."""
    text = text.lower()
    # NFD then drop combining marks
    text = ''.join(c for c in unicodedata.normalize('NFD', text)
                   if unicodedata.category(c) != 'Mn')
    # remove punctuation
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def correct_string_to_bool_label(correct_indices, answers):
    """For an existing test question, return 'pravda'|'nepravda'|None.

    Existing tests use 4 or 2 options. 'correct' is a list of indices.
    """
    if not correct_indices or not answers:
        return None
    # one-correct only (true/false questions always single correct)
    idx = correct_indices[0]
    if idx < 0 or idx >= len(answers):
        return None
    ans_text = answers[idx].strip().lower()
    if ans_text.startswith('pravda'):
        return 'pravda'
    if ans_text.startswith('nepravda'):
        return 'nepravda'
    return None  # not a pravda/nepravda question


def load_existing():
    """Load existing histo tests as flat list of (question_norm, question_orig, correct, source)."""
    entries = []
    for fn in EXISTING_TESTS:
        path = TESTY_DIR / fn
        if not path.exists():
            continue
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, list):
            continue
        for test in data:
            for q in test.get('questions', []):
                correct = correct_string_to_bool_label(
                    q.get('correct') or [], q.get('answers') or []
                )
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
    """Load extracted questions from 3 PDF result files."""
    items = []
    for fn in EXTRACTED:
        path = OUT_DIR / fn
        if not path.exists():
            print(f'WARN: {path} missing', file=sys.stderr)
            continue
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
                'source_pdf': fn,
                'page': q.get('page'),
            })
    return items


def find_match(query_norm, existing, fuzzy_threshold=FUZZY_THRESHOLD):
    """Return (match_entry, kind) where kind ∈ {'exact', 'fuzzy', 'none'}."""
    # exact match first
    for e in existing:
        if e['norm'] == query_norm:
            return e, 'exact'
    # fuzzy
    best_ratio = 0.0
    best = None
    for e in existing:
        # Quick reject: huge length difference
        if abs(len(e['norm']) - len(query_norm)) > max(40, len(query_norm) * 0.3):
            continue
        r = SequenceMatcher(None, query_norm, e['norm']).ratio()
        if r > best_ratio:
            best_ratio = r
            best = e
    if best and best_ratio >= fuzzy_threshold:
        return best, 'fuzzy'
    return None, 'none'


def dedupe_extracted(items, fuzzy_threshold=FUZZY_THRESHOLD):
    """Collapse duplicate questions across the 3 PDFs.

    Returns (unique_items, intra_conflicts) where intra_conflicts lists cases
    where the same question appears with different correct answers in PDFs.
    """
    unique = []  # list of dicts: {norm, orig, correct, sources: [(pdf, page), ...]}
    conflicts = []  # tuples of (variant_A, variant_B)
    for it in items:
        match_idx = None
        match_kind = None
        for i, u in enumerate(unique):
            if u['norm'] == it['norm']:
                match_idx = i
                match_kind = 'exact'
                break
            if abs(len(u['norm']) - len(it['norm'])) <= max(40, len(it['norm']) * 0.3):
                r = SequenceMatcher(None, u['norm'], it['norm']).ratio()
                if r >= fuzzy_threshold:
                    match_idx = i
                    match_kind = 'fuzzy'
                    break
        if match_idx is None:
            unique.append({
                'norm': it['norm'],
                'orig': it['orig'],
                'correct': it['correct'],
                'sources': [(it['source_pdf'], it['page'])],
                'match_kind': None,
            })
        else:
            u = unique[match_idx]
            u['sources'].append((it['source_pdf'], it['page']))
            if u['correct'] != it['correct']:
                conflicts.append((u, it))
    return unique, conflicts


def build_report(unique, intra_conflicts, classification):
    """classification: list of (unique_item, match_entry_or_None, match_kind)."""
    lines = []
    lines.append('# Histo Moodle PDF — porovnanie s existujúcimi testami\n')

    n_total = len(unique)
    n_ok = sum(1 for u, m, _k in classification if m and m['correct'] == u['correct'])
    n_conflict = sum(1 for u, m, _k in classification if m and m['correct'] != u['correct'])
    n_new = sum(1 for _u, m, _k in classification if m is None)
    n_exact = sum(1 for _u, m, k in classification if m and k == 'exact')
    n_fuzzy = sum(1 for _u, m, k in classification if m and k == 'fuzzy')

    lines.append('## Súhrn\n')
    lines.append(f'- **Spolu unikátnych otázok zo 3 PDF**: {n_total}')
    lines.append(f'- **Zhoda s existujúcimi (správne)**: {n_ok}')
    lines.append(f'  - z toho **exact match**: {n_exact - n_conflict}')
    lines.append(f'  - z toho **fuzzy match (≥{FUZZY_THRESHOLD})**: {n_fuzzy} (over manuálne)')
    lines.append(f'- **Konflikt v odpovedi**: {n_conflict}')
    lines.append(f'- **Nové otázky (idú do nového testu)**: {n_new}')
    lines.append('')

    if intra_conflicts:
        lines.append(f'## Konflikty MEDZI PDF (rovnaká otázka, rôzna odpoveď v rôznych PDF)\n')
        for a, b in intra_conflicts:
            lines.append(f'- **{a["orig"]}**')
            lines.append(f'  - v PDF: `{a["sources"]}` → `{a["correct"]}`')
            lines.append(f'  - v PDF: `{b["source_pdf"]}` strana {b["page"]} → `{b["correct"]}`')
        lines.append('')

    conflicts = [(u, m, k) for u, m, k in classification if m and m['correct'] != u['correct']]
    if conflicts:
        lines.append('## Konflikty s existujúcimi testami\n')
        lines.append('Otázka existuje aj v Moodle PDF aj v Quizlet teste, ale odpoveď sa líši.\n')
        for u, m, k in conflicts:
            lines.append(f'### {u["orig"]}')
            lines.append(f'- match: **{k}** (zdroj v Quizlet: `{m["source"]}`)')
            lines.append(f'- v Quizlet ({m["source"]}): **{m["correct"]}**')
            lines.append(f'- v Moodle PDF: **{u["correct"]}** — výskyty: {u["sources"]}')
            if k == 'fuzzy':
                lines.append(f'- text v Quizlet (pre kontrolu): _{m["orig"]}_')
            lines.append('')

    fuzzy_oks = [(u, m, k) for u, m, k in classification
                 if m and m['correct'] == u['correct'] and k == 'fuzzy']
    if fuzzy_oks:
        lines.append('## Fuzzy zhody (odpoveď OK, ale text mierne odlišný — over)\n')
        for u, m, k in fuzzy_oks:
            lines.append(f'- **Moodle**: _{u["orig"]}_')
            lines.append(f'  - **Quizlet** ({m["source"]}): _{m["orig"]}_')
            lines.append(f'  - obe: `{u["correct"]}`')
            lines.append('')

    news = [u for u, m, _ in classification if m is None]
    if news:
        lines.append(f'## Nové otázky ({len(news)}) — pôjdu do `{NEW_TEST_FILENAME}`\n')
        for u in news:
            lines.append(f'- [{u["correct"]}] {u["orig"]}')
        lines.append('')

    return '\n'.join(lines)


def build_new_test(news):
    """Build the new test JSON with 2-option pravda/nepravda format."""
    questions = []
    for u in news:
        ans = ['pravda', 'nepravda']
        idx = ans.index(u['correct'])
        questions.append({
            'question': u['orig'],
            'answers': ans,
            'correct': [idx],
        })
    return [{
        'title': NEW_TEST_TITLE,
        'description': NEW_TEST_DESC,
        'category': 'Histológia',
        'questions': questions,
    }]


def main():
    existing = load_existing()
    extracted = load_extracted()
    print(f'Existing histo questions (pravda/nepravda type): {len(existing)}')
    print(f'Extracted from 3 PDFs: {len(extracted)}')

    unique, intra_conflicts = dedupe_extracted(extracted)
    print(f'After dedupe across PDFs: {len(unique)} unique')
    print(f'Intra-PDF conflicts (same Q, different A across PDFs): {len(intra_conflicts)}')

    classification = []
    for u in unique:
        match, kind = find_match(u['norm'], existing)
        classification.append((u, match, kind))

    report = build_report(unique, intra_conflicts, classification)
    REPORT_PATH.write_text(report, encoding='utf-8')
    print(f'Report: {REPORT_PATH}')

    news = [u for u, m, _ in classification if m is None]
    new_test = build_new_test(news)
    new_test_path = TESTY_DIR / NEW_TEST_FILENAME
    with open(new_test_path, 'w', encoding='utf-8') as f:
        json.dump(new_test, f, ensure_ascii=False, indent=2)
    print(f'New test: {new_test_path} ({len(news)} questions)')


if __name__ == '__main__':
    main()
