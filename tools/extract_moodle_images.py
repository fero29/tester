#!/usr/bin/env python3
"""Extract pravda/nepravda questions from a folder of screenshot images.

Sister script of extract_moodle_pdf.py — same prompt and parsing, but iterates
over JPEG/PNG files in a directory instead of rasterizing PDF pages.

Usage:
    extract_moodle_images.py <images_dir> <out_json_path>
"""
import argparse
import base64
import json
import os
import re
import sys
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv  # type: ignore

try:
    load_dotenv(Path(__file__).parent.parent / '.env')
except Exception:
    pass


MODEL = 'claude-sonnet-4-6'

PROMPT = """Toto je fotka monitora alebo screenshot z online testu (Moodle / MS Forms / Google Forms) v slovenčine.
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

Ak je text otázky orezaný alebo nečitateľný, vynechaj ju.
Ak na obrázku NIE JE žiadna otázka s indikátorom správnej odpovede, vráť prázdny array `[]`.

Vráť **iba** JSON array, nič viac:
```json
[
  {"question": "...", "correct": "pravda"},
  {"question": "...", "correct": "nepravda"}
]
```"""


def parse_json_response(text: str):
    m = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    payload = m.group(1) if m else text
    payload = payload.strip()
    if not payload.startswith('['):
        lo = payload.find('[')
        hi = payload.rfind(']')
        if lo >= 0 and hi > lo:
            payload = payload[lo:hi + 1]
    return json.loads(payload)


def extract_image(client, img_path: Path) -> list[dict]:
    ext = img_path.suffix.lower().lstrip('.')
    media_type = 'image/jpeg' if ext in ('jpg', 'jpeg') else f'image/{ext}'
    with open(img_path, 'rb') as f:
        img_b64 = base64.standard_b64encode(f.read()).decode('ascii')

    msg = client.messages.create(
        model=MODEL,
        max_tokens=16384,
        temperature=0.0,
        messages=[{
            'role': 'user',
            'content': [
                {'type': 'image', 'source': {
                    'type': 'base64', 'media_type': media_type, 'data': img_b64,
                }},
                {'type': 'text', 'text': PROMPT},
            ],
        }],
    )
    text = next(b.text for b in msg.content if b.type == 'text')

    try:
        data = parse_json_response(text)
    except Exception as e:
        print(f'  [{img_path.name}] JSON parse error: {e}', file=sys.stderr)
        print(f'  Response: {text[:300]!r}', file=sys.stderr)
        return []

    if not isinstance(data, list):
        print(f'  [{img_path.name}] Not a list, got {type(data).__name__}', file=sys.stderr)
        return []

    results = []
    for item in data:
        if not isinstance(item, dict):
            continue
        q = (item.get('question') or '').strip()
        a = (item.get('correct') or '').strip().lower()
        if not q or a not in ('pravda', 'nepravda'):
            continue
        results.append({'question': q, 'correct': a, 'source_image': img_path.name})

    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('images_dir')
    ap.add_argument('out_json')
    args = ap.parse_args()

    images_dir = Path(args.images_dir)
    images = sorted([p for p in images_dir.iterdir()
                     if p.suffix.lower() in ('.jpg', '.jpeg', '.png')])
    print(f'Found {len(images)} images in {images_dir}')

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
        already = {r['source_image'] for r in all_results}
        print(f'Resuming: already processed {len(already)} images')

    for img in images:
        if img.name in already:
            continue
        t0 = time.time()
        try:
            items = extract_image(client, img)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f'  [{img.name}] FAILED: {e}', file=sys.stderr)
            continue
        all_results.extend(items)
        dt = time.time() - t0
        print(f'  {img.name}: +{len(items)} questions ({dt:.1f}s)', flush=True)
        with open(args.out_json, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(f'Done. Total: {len(all_results)} questions → {args.out_json}')


if __name__ == '__main__':
    main()
