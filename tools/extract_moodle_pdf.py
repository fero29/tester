#!/usr/bin/env python3
"""Extract pravda/nepravda questions + correct answers from Moodle/Forms screenshot PDFs.

Per page:
  1. Rasterize via pdftoppm (PNG, 150 DPI)
  2. Send to Claude Sonnet 4.6 Vision
  3. Parse strict-JSON response: list of {question, correct}
  4. Append to per-PDF output file

Usage:
    extract_moodle_pdf.py <pdf_path> <out_json_path> [--dpi 150] [--start N] [--end N]
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
from dotenv import load_dotenv  # type: ignore  # optional

# Load API key from .env in project root
try:
    load_dotenv(Path(__file__).parent.parent / '.env')
except Exception:
    pass


MODEL = 'claude-sonnet-4-6'

PROMPT = """Toto je screenshot z online testu (Moodle / MS Forms / Google Forms) v slovenčine.
Test má otázky typu PRAVDA/NEPRAVDA (alebo SPRÁVNE/NESPRÁVNE).

Pre KAŽDÚ otázku viditeľnú na obrázku extrahuj:
1. **question**: presný text otázky (slovensky, vrátane diakritiky)
2. **correct**: správna odpoveď — vždy len `"pravda"` alebo `"nepravda"`

Existujú DVA formáty zobrazenia. Použi pravidlá podľa toho, ktorý je na obrázku:

**Formát A (Moodle / MS Forms — explicitné označenie správnej odpovede):**
- Vedľa správnej odpovede je zelená ✓ (priamo pri texte "správne"/"Pravda"/atď.)
- Alebo pod otázkou text "Správna odpoveď je 'Pravda'" / "Správna odpoveď je 'Nepravda'"
- V tomto formáte ignoruj vyplnený krúžok (●) — to je len výber používateľa, nie správna odpoveď.

**Formát B (Google Forms — len status "Correct"/"Incorrect"):**
- Nad otázkou je zelený badge "✓ Correct  1/1 Points" alebo červený "✗ Incorrect  0/1 Points"
- Vyplnený krúžok (●) označuje voľbu používateľa.
- Pravidlo: ak je status **Correct** → správna odpoveď = voľba používateľa (●). Ak je **Incorrect** → správna odpoveď = OPAČNÁ možnosť (tá s prázdnym krúžkom).

Vždy normalizuj odpoveď: "správne"/"Pravda"/"SPRÁVNE" → `"pravda"`, "nesprávne"/"Nepravda" → `"nepravda"`.

Ak otázku nedokážeš spoľahlivo prečítať (orezaná, neostrá, žiadny indikátor správnej odpovede), vynechaj ju.
Ak na obrázku NIE JE žiadna otázka (titulná strana, navigácia), vráť prázdny array `[]`.

Vráť **iba** JSON array, nič viac:
```json
[
  {"question": "...", "correct": "pravda"},
  {"question": "...", "correct": "nepravda"}
]
```"""


def rasterize_page(pdf_path: str, page_num: int, dpi: int, out_dir: str) -> str:
    """Run pdftoppm to extract a single page as PNG. Returns path to PNG."""
    out_prefix = os.path.join(out_dir, f'page_{page_num:04d}')
    subprocess.run(
        ['pdftoppm', '-png', '-r', str(dpi), '-f', str(page_num), '-l', str(page_num),
         pdf_path, out_prefix],
        check=True,
        capture_output=True,
    )
    # pdftoppm adds suffix like -1.png for single page, or -001.png if multi-digit
    candidates = sorted(Path(out_dir).glob(f'page_{page_num:04d}-*.png'))
    if not candidates:
        raise RuntimeError(f'pdftoppm produced no output for page {page_num}')
    return str(candidates[0])


def parse_json_response(text: str):
    """Extract JSON array from Claude response, handling markdown fences."""
    # Strip markdown fences if present
    m = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    payload = m.group(1) if m else text
    payload = payload.strip()
    # Fallback: find first '[' and last ']'
    if not payload.startswith('['):
        lo = payload.find('[')
        hi = payload.rfind(']')
        if lo >= 0 and hi > lo:
            payload = payload[lo:hi + 1]
    return json.loads(payload)


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
                    'type': 'base64', 'media_type': 'image/png', 'data': img_b64,
                }},
                {'type': 'text', 'text': PROMPT},
            ],
        }],
    )
    text = next(b.text for b in msg.content if b.type == 'text')

    try:
        data = parse_json_response(text)
    except Exception as e:
        print(f'  [page {page_num}] JSON parse error: {e}', file=sys.stderr)
        print(f'  Response: {text[:300]!r}', file=sys.stderr)
        return []

    if not isinstance(data, list):
        print(f'  [page {page_num}] Not a list, got {type(data).__name__}', file=sys.stderr)
        return []

    results = []
    for item in data:
        if not isinstance(item, dict):
            continue
        q = (item.get('question') or '').strip()
        a = (item.get('correct') or '').strip().lower()
        if not q or a not in ('pravda', 'nepravda'):
            continue
        results.append({'question': q, 'correct': a, 'page': page_num})

    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pdf')
    ap.add_argument('out_json')
    ap.add_argument('--dpi', type=int, default=150)
    ap.add_argument('--start', type=int, default=1)
    ap.add_argument('--end', type=int, default=None)
    args = ap.parse_args()

    # Determine total pages via pdfinfo
    info = subprocess.run(['pdfinfo', args.pdf], capture_output=True, text=True, check=True)
    total = int(re.search(r'Pages:\s*(\d+)', info.stdout).group(1))
    end = args.end or total
    print(f'PDF: {args.pdf}, pages {args.start}-{end} of {total}, DPI={args.dpi}')

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print('ERROR: ANTHROPIC_API_KEY not set', file=sys.stderr)
        sys.exit(1)
    client = anthropic.Anthropic(api_key=api_key)

    all_results = []
    if os.path.exists(args.out_json):
        with open(args.out_json) as f:
            all_results = json.load(f)
        already = {r['page'] for r in all_results}
        print(f'Resuming: already have {len(all_results)} questions from pages {sorted(already)[:10]}...')
    else:
        already = set()

    with tempfile.TemporaryDirectory(prefix='moodle_pages_') as tmp:
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
                print(f'  [page {page}] FAILED: {e}', file=sys.stderr)
                continue
            all_results.extend(items)
            dt = time.time() - t0
            print(f'  page {page}/{end}: +{len(items)} questions ({dt:.1f}s)', flush=True)
            # Persist after each page so we don't lose progress
            with open(args.out_json, 'w', encoding='utf-8') as f:
                json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(f'Done. Total: {len(all_results)} questions → {args.out_json}')


if __name__ == '__main__':
    main()
