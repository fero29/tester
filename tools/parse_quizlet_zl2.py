#!/usr/bin/env python3
"""Parse Quizlet print PDF 'Histologia ZL 2. zápočet' to JSON.

Format per question:
  N.    text first line                                       s|n
        continuation line
        continuation line

Output: list of {q: int, text: str, correct: 'pravda'|'nepravda'}
"""
import json
import re
import subprocess
import sys
from pathlib import Path

PDF = Path('quizlet.com_695005625_print.pdf')
OUT = Path('tools/out/zl2.json')

HEADER_RE = re.compile(r'(Histologia ZL 2\. zápočet|Study online at|^\s*\d+\s*/\s*\d+\s*$)')

def main():
    raw = subprocess.run(['pdftotext', '-layout', str(PDF), '-'],
                         check=True, capture_output=True, text=True).stdout
    # Drop headers/footers
    lines = [ln.rstrip() for ln in raw.split('\n')
             if ln.strip() and not HEADER_RE.search(ln)]

    # Split into question groups. A question line starts with "<num>."
    q_start = re.compile(r'^(\d+)\.\s*(.*?)\s*([sn])\s*$')
    q_continuation_marker = re.compile(r'^\s*\d+\.')

    questions = {}
    current_q = None  # (num, text_parts, correct)

    for ln in lines:
        m = q_start.match(ln)
        if m:
            # Flush previous
            if current_q is not None:
                num, parts, correct = current_q
                text = ' '.join(parts).strip()
                # Fix hyphen-splits like "sval- ové" → "svalové"
                text = re.sub(r'(\w)-\s+(\w)', r'\1\2', text)
                text = re.sub(r'\s+', ' ', text).strip()
                questions[num] = {'q': num, 'text': text,
                                  'correct': 'pravda' if correct == 's' else 'nepravda'}
            num = int(m.group(1))
            first_text = m.group(2).strip()
            correct = m.group(3)
            current_q = (num, [first_text] if first_text else [], correct)
        else:
            # Continuation: must be indented and NOT a new question number
            if q_continuation_marker.match(ln):
                continue  # safety: not a continuation
            if current_q is not None:
                current_q[1].append(ln.strip())

    # Flush last
    if current_q is not None:
        num, parts, correct = current_q
        text = ' '.join(parts).strip()
        text = re.sub(r'(\w)-\s+(\w)', r'\1\2', text)
        text = re.sub(r'\s+', ' ', text).strip()
        questions[num] = {'q': num, 'text': text,
                          'correct': 'pravda' if correct == 's' else 'nepravda'}

    ordered = [questions[k] for k in sorted(questions)]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, 'x', encoding='utf-8') as f:
        json.dump(ordered, f, ensure_ascii=False, indent=2)
    print(f'Parsed {len(ordered)} questions → {OUT}')

    # Sanity check
    missing = [i for i in range(1, max(questions)+1) if i not in questions]
    if missing:
        print(f'WARN: missing numbers: {missing[:20]}', file=sys.stderr)
    empty = [q['q'] for q in ordered if not q['text']]
    if empty:
        print(f'WARN: empty text: {empty}', file=sys.stderr)


if __name__ == '__main__':
    main()
