#!/usr/bin/env python3
"""Match extracted 'zápočet LS 2' questions against existing histo tests.

Statistics:
  - unique (across photos, deduplicated)
  - same as in any existing test (exact match, same answer)
  - similar in any existing test (fuzzy match ≥0.88, same answer)
  - answer conflict (matches existing but different answer)
  - flagged as questionable OCR (extractor returned uncertain → none here, but we
    spot-check biologically dubious ones below)
"""
import json
import re
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]
TESTY_DIR = ROOT / 'testy'
OUT_DIR = ROOT / 'tools' / 'out'

EXISTING = [
    'histo 2.json',
    'histológia 2 zápočet.json',
    'histo zápočet Moodle.json',
    'histo zápočet foto.json',
    'histológia zubári.json',
]
EXTRACTED_FILE = OUT_DIR / 'zap_ls2.json'

FUZZY_HIGH = 0.95  # near-identical
FUZZY_LOW = 0.85   # similar


def normalize(text):
    text = text.lower()
    text = ''.join(c for c in unicodedata.normalize('NFD', text)
                   if unicodedata.category(c) != 'Mn')
    text = re.sub(r'[^\w\s]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def correct_label(correct, answers):
    if not correct or not answers:
        return None
    idx = correct[0]
    if idx < 0 or idx >= len(answers):
        return None
    t = answers[idx].strip().lower()
    if t.startswith('pravda'):
        return 'pravda'
    if t.startswith('nepravda'):
        return 'nepravda'
    return None


def load_existing():
    entries = []
    for fn in EXISTING:
        p = TESTY_DIR / fn
        if not p.exists():
            continue
        with open(p, encoding='utf-8') as f:
            data = json.load(f)
        for t in data:
            for q in t.get('questions', []):
                c = correct_label(q.get('correct') or [], q.get('answers') or [])
                if c is None:
                    continue
                qt = q.get('question', '').strip()
                if not qt:
                    continue
                entries.append({'norm': normalize(qt), 'orig': qt,
                                'correct': c, 'source': fn})
    return entries


def load_extracted():
    with open(EXTRACTED_FILE, encoding='utf-8') as f:
        data = json.load(f)
    out = []
    for q in data:
        qt = (q.get('question') or '').strip()
        c = (q.get('correct') or '').strip().lower()
        if not qt or c not in ('pravda', 'nepravda'):
            continue
        out.append({'norm': normalize(qt), 'orig': qt, 'correct': c,
                    'q_num': q.get('q'), 'pdf_page': q.get('pdf_page')})
    return out


def dedupe(items):
    unique = []
    for it in items:
        found = None
        for u in unique:
            if u['norm'] == it['norm']:
                found = u; break
            if abs(len(u['norm']) - len(it['norm'])) <= max(40, len(it['norm']) * 0.3):
                if SequenceMatcher(None, u['norm'], it['norm']).ratio() >= FUZZY_HIGH:
                    found = u; break
        if found is None:
            unique.append({'norm': it['norm'], 'orig': it['orig'],
                           'correct': it['correct'],
                           'sources': [(it['q_num'], it['pdf_page'])]})
        else:
            found['sources'].append((it['q_num'], it['pdf_page']))
            if found['correct'] != it['correct']:
                found.setdefault('intra_conflict', []).append((it['correct'], it['q_num'], it['pdf_page']))
    return unique


def best_match(query_norm, existing):
    best = None; best_r = 0.0; exact = None
    for e in existing:
        if e['norm'] == query_norm:
            exact = e; break
        if abs(len(e['norm']) - len(query_norm)) <= max(40, len(query_norm) * 0.3):
            r = SequenceMatcher(None, e['norm'], query_norm).ratio()
            if r > best_r:
                best_r = r; best = e
    if exact:
        return exact, 'exact', 1.0
    if best_r >= FUZZY_HIGH:
        return best, 'near_identical', best_r
    if best_r >= FUZZY_LOW:
        return best, 'similar', best_r
    return None, 'none', best_r


def main():
    if not EXTRACTED_FILE.exists():
        print(f'ERROR: {EXTRACTED_FILE} missing', file=sys.stderr)
        sys.exit(1)
    existing = load_existing()
    raw = load_extracted()
    unique = dedupe(raw)
    print(f'Raw extracted: {len(raw)}')
    print(f'Unique (after dedupe): {len(unique)}')
    print(f'Existing test questions (across {len(EXISTING)} tests): {len(existing)}')
    print()

    cnt = Counter()
    same, similar, conflict, news = [], [], [], []
    for u in unique:
        m, kind, r = best_match(u['norm'], existing)
        cnt[kind] += 1
        if kind == 'exact':
            (same if m['correct'] == u['correct'] else conflict).append((u, m, kind, r))
        elif kind == 'near_identical':
            (same if m['correct'] == u['correct'] else conflict).append((u, m, kind, r))
        elif kind == 'similar':
            (similar if m['correct'] == u['correct'] else conflict).append((u, m, kind, r))
        else:
            news.append(u)

    intra_conflicts = [u for u in unique if 'intra_conflict' in u]

    print('=== ŠTATISTIKA ===')
    print(f'Unikátnych otázok zo zápočet LS 2: {len(unique)}')
    print(f'  Z toho úplne nové (nikde v existujúcich): {len(news)}')
    print(f'  Z toho rovnaké v ktoromsi existujúcom (exact/near, OK odpoveď): {len(same)}')
    print(f'  Z toho podobné (fuzzy 0.85-0.95, OK odpoveď): {len(similar)}')
    print(f'  KONFLIKT v odpovedi s existujúcim: {len(conflict)}')
    print(f'  Intra-PDF konflikt (rôzne odpovede v rôznych snímkach): {len(intra_conflicts)}')

    # Save details
    report_path = OUT_DIR / 'REPORT_zap_ls2.md'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('# Zápočet LS 2 — porovnanie s existujúcimi testami\n\n')
        f.write(f'## Štatistika\n\n')
        f.write(f'- Spolu unikátnych otázok: **{len(unique)}**\n')
        f.write(f'- Nové (nikde inde): **{len(news)}**\n')
        f.write(f'- Rovnaké v existujúcom teste (správna odpoveď): **{len(same)}**\n')
        f.write(f'- Podobné (mierna úprava textu, správna odpoveď): **{len(similar)}**\n')
        f.write(f'- **Konflikt v odpovedi** s existujúcim: **{len(conflict)}**\n')
        f.write(f'- Intra-PDF konflikt: **{len(intra_conflicts)}**\n\n')

        if conflict:
            f.write('## Konflikty v odpovedi\n\n')
            for u, m, kind, r in conflict:
                f.write(f'### {u["orig"]}\n')
                f.write(f'- nový (zápočet LS 2): **{u["correct"]}**\n')
                f.write(f'- existujúci ({m["source"]}, {kind}, ratio={r:.3f}): **{m["correct"]}** _{m["orig"]}_\n\n')

        if intra_conflicts:
            f.write('## Intra-PDF konflikty\n\n')
            for u in intra_conflicts:
                f.write(f'- **{u["orig"]}** → primárne `{u["correct"]}`, ale tiež `{u["intra_conflict"]}`\n')
            f.write('\n')

        if similar:
            f.write(f'## Podobné (over text) — {len(similar)}\n\n')
            for u, m, kind, r in similar:
                f.write(f'- ratio={r:.3f} obe `{u["correct"]}`\n')
                f.write(f'  - nový: _{u["orig"]}_\n')
                f.write(f'  - existujúci ({m["source"]}): _{m["orig"]}_\n')

    print(f'\nReport: {report_path}')


if __name__ == '__main__':
    main()
