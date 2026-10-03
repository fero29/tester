#!/usr/bin/env python3
"""Extract pravda/nepravda questions from 'zápočet LS 2 1.pdf' (395 pages).

Two formats appear:
  - Moodle (yellow box: "Správna odpoveď je 'Pravda'/'Nepravda'")
  - Forms (status "Správne 1/1 Body" / "Nesprávne 0/1 Body" → flip rule)

Ignore everything written by hand (fixka): green crosses/checks, corrections.
If question text is not completely readable, SKIP it (don't guess).
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv  # type: ignore

try:
    load_dotenv(Path(__file__).parent.parent / '.env')
except Exception:
    pass


MODEL = 'claude-sonnet-4-6'

PROMPT = """Toto je screenshot z online testu (Moodle / MS Forms / Google Forms) v slovenčine.
Otázky sú typu PRAVDA/NEPRAVDA.

DÔLEŽITÉ PRAVIDLÁ:
1. **Ignoruj všetko dopísané rukou alebo fixkou** — zelené ✓, červené X, krížiky, podčiarknutia, dopísané opravy/poznámky študenta nad alebo pri otázkach. Tie NIE SÚ súčasťou otázky ani správnej odpovede.
2. **Správna odpoveď** sa určuje výlučne z OFICIÁLNEHO indikátora aplikácie:
   - **Formát Moodle**: pod otázkou je žltý/krémový rámček s textom *"Správna odpoveď je 'Pravda'"* alebo *"Správna odpoveď je 'Nepravda'"*. Toto je jediný zdroj pravdy.
   - **Formát Forms (Google/MS)**: nad otázkou je status *"✓ Správne 1/1 Body"* alebo *"X Nesprávne 0/1 Body"*. Vyplnený krúžok je voľba používateľa.
     - Ak status = Správne → správna odpoveď = voľba používateľa
     - Ak status = Nesprávne → správna odpoveď = OPAK voľby používateľa
3. **Ak text otázky nie je úplne a jednoznačne čitateľný** (fixka prekrýva, orezané, neostré), VYNECHAJ ju. Nevymýšľaj a nehádaj.
4. Číslo otázky (napr. "Otázka 18", "28.") **zachyť**, ak je viditeľné.

Pre KAŽDÚ čitateľnú otázku vráť:
  - `q`: číslo otázky (integer) — alebo `null` ak číslo nie je vidieť
  - `question`: presný text otázky (slovensky, s diakritikou)
  - `correct`: `"pravda"` alebo `"nepravda"`

Ak na stránke NIE JE žiadna otázka s indikátorom správnej odpovede (úvodná strana, navigácia, prázdne), vráť `[]`.

**JSON formát**: text otázky vlož ako reťazec medzi `"..."`. Ak text obsahuje slovenské úvodzovky („..." alebo "...") alebo apostrofy, **escapuj ich** ako `\\"`. Príklad: text *Ako „locus fecundationis" sa označuje...* musíš v JSON napísať ako `"Ako \\"locus fecundationis\\" sa označuje..."`.

Vráť **iba** JSON array, nič viac:
```json
[
  {"q": 18, "question": "...", "correct": "pravda"},
  {"q": 19, "question": "...", "correct": "nepravda"}
]
```"""


def rasterize_page(pdf_path: str, page_num: int, dpi: int, out_dir: str) -> str:
    out_prefix = os.path.join(out_dir, f'page_{page_num:04d}')
    subprocess.run(
        ['pdftoppm', '-png', '-r', str(dpi), '-f', str(page_num), '-l', str(page_num),
         pdf_path, out_prefix],
        check=True, capture_output=True,
    )
    candidates = sorted(Path(out_dir).glob(f'page_{page_num:04d}-*.png'))
    if not candidates:
        raise RuntimeError(f'no output for page {page_num}')
    return str(candidates[0])


def fix_unescaped_quotes(payload: str) -> str:
    """Best-effort fix: replace ASCII " inside Slovak-quote pairs „...".
    e.g. „locus fecundationis" → 'locus fecundationis'
    Also replace bare „...""...""..." that appear inside JSON string values.
    """
    # Replace „X" pairs with 'X' to avoid JSON-breaking inner quotes
    payload = re.sub(r'„([^"]*?)"', r"'\1'", payload)
    # Replace fancy curly double quotes with straight apostrophes inside strings
    payload = payload.replace('“', "'").replace('”', "'")
    return payload

def parse_json_response(text: str):
    m = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    payload = m.group(1) if m else text
    payload = payload.strip()
    if not payload.startswith('['):
        lo = payload.find('['); hi = payload.rfind(']')
        if lo >= 0 and hi > lo:
            payload = payload[lo:hi + 1]
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return json.loads(fix_unescaped_quotes(payload))


def extract_page(client, png_path: str, page_num: int) -> list[dict]:
    with open(png_path, 'rb') as f:
        img_b64 = base64.standard_b64encode(f.read()).decode('ascii')
    msg = client.messages.create(
        model=MODEL,
        max_tokens=16384,
        temperature=0.0,
        messages=[{
            'role': 'user',
            'content': [
                {'type': 'image', 'source': {
                    'type': 'base64', 'media_type': 'image/png', 'data': img_b64}},
                {'type': 'text', 'text': PROMPT},
            ],
        }],
    )
    text = next(b.text for b in msg.content if b.type == 'text')
    try:
        data = parse_json_response(text)
    except Exception as e:
        print(f'  [p{page_num}] JSON parse error: {e}', file=sys.stderr)
        print(f'  Response: {text[:300]!r}', file=sys.stderr)
        return []
    if not isinstance(data, list):
        return []
    out = []
    for item in data:
        if not isinstance(item, dict):
            continue
        q = (item.get('question') or '').strip()
        c = (item.get('correct') or '').strip().lower()
        qnum = item.get('q')
        if not q or c not in ('pravda', 'nepravda'):
            continue
        out.append({'q': qnum, 'question': q, 'correct': c, 'pdf_page': page_num})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pdf')
    ap.add_argument('out_json')
    ap.add_argument('--dpi', type=int, default=150)
    ap.add_argument('--start', type=int, default=1)
    ap.add_argument('--end', type=int, default=None)
    args = ap.parse_args()

    info = subprocess.run(['pdfinfo', args.pdf], capture_output=True, text=True, check=True)
    total = int(re.search(r'Pages:\s*(\d+)', info.stdout).group(1))
    end = args.end or total
    print(f'PDF: {args.pdf} | pages {args.start}-{end} of {total} | DPI={args.dpi}')

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print('ERROR: ANTHROPIC_API_KEY not set', file=sys.stderr)
        sys.exit(1)
    client = anthropic.Anthropic(api_key=api_key)

    all_results = []
    already = set()
    if os.path.exists(args.out_json):
        with open(args.out_json) as f:
            all_results = json.load(f)
        already = {r['pdf_page'] for r in all_results}
        print(f'Resuming: {len(all_results)} items, {len(already)} pages done')

    with tempfile.TemporaryDirectory(prefix='zaplls2_') as tmp:
        for page in range(args.start, end + 1):
            if page in already:
                continue
            t0 = time.time()
            try:
                png = rasterize_page(args.pdf, page, args.dpi, tmp)
                items = extract_page(client, png, page)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f'  [p{page}] FAILED: {e}', file=sys.stderr)
                continue
            all_results.extend(items)
            dt = time.time() - t0
            print(f'  p{page}/{end}: +{len(items)} ({dt:.1f}s)', flush=True)
            with open(args.out_json, 'w', encoding='utf-8') as f:
                json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(f'Done. Total: {len(all_results)} questions → {args.out_json}')


if __name__ == '__main__':
    main()
