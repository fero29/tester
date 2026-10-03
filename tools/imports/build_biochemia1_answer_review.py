#!/usr/bin/env python3
"""Build a review-only JSON and HTML report; never write to active test files."""

import hashlib
import html
import json
from collections import Counter
from pathlib import Path
from urllib.parse import quote, urlparse


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = Path(__file__).with_name('biochemia1_answer_review.json')
OUTPUT = ROOT / 'testy/biochemia1'
LABELS = {
    'key_proposed': 'Návrh kľúča',
    'no_correct_option': 'Žiadna správna možnosť',
    'wording_required': 'Treba spresniť znenie',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def letters(indices):
    return ', '.join('ABCD'[i] for i in indices) or 'žiadne'


def build_data():
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    source = ROOT / manifest['inputFile']
    raw = source.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == manifest['inputSha256'],
            'Odložené otázky sa zmenili; revíziu treba znova skontrolovať.')
    original = json.loads(raw)
    by_id = {q['source']['sequence']: q for q in original}
    require(len(original) == len(by_id) == 45, 'Očakáva sa 45 rôznych poradí.')
    require(all(q['correct'] is None for q in original), 'Pôvodný kľúč musí zostať otvorený.')
    for ref in manifest['sources'].values():
        require(urlparse(ref['url']).scheme == 'https', 'Zdroj musí používať HTTPS.')

    items, covered = [], []
    for decision in manifest['decisions']:
        ids = decision['sequences']
        require(bool(ids) and all(i in by_id for i in ids), 'Neznáme poradie otázky.')
        occurrences = [by_id[i] for i in ids]
        first = occurrences[0]
        require(all(q['question'] == first['question'] and q['answers'] == first['answers']
                    for q in occurrences), 'Zlúčiť možno len rovnaké znenia.')
        require(len(first['answers']) == 4, 'Očakávajú sa štyri možnosti.')
        status, key = decision['status'], decision['proposedCorrect']
        require(status in LABELS, 'Neznámy stav revízie.')
        if status == 'wording_required':
            require(key is None, 'Otvorený návrh nesmie obsahovať definitívny kľúč.')
        else:
            require(isinstance(key, list) and key == sorted(set(key))
                    and all(type(i) is int and 0 <= i < 4 for i in key), 'Neplatný kľúč.')
            require(bool(key) == (status == 'key_proposed'), 'Stav nezodpovedá kľúču.')
        require(decision['sourceRefs'] and all(
            ref in manifest['sources'] for ref in decision['sourceRefs']), 'Chýba zdroj.')
        items.append({**decision, 'approvalStatus': 'pending',
                      'question': first['question'], 'answers': first['answers'],
                      'originalOccurrences': occurrences})
        covered.extend(ids)
    require(Counter(covered) == Counter(by_id.keys()), 'Revízia nepokrýva presne všetkých 45 záznamov.')
    distinct = {(q['question'], tuple(q['answers'])) for q in original}
    require(len(items) == len(distinct), 'Každé odlišné znenie má mať jednu revíziu.')
    return {
        **{k: v for k, v in manifest.items() if k != 'decisions'},
        'summary': {
            'occurrences': len(original), 'distinctQuestions': len(items),
            'byStatus': {status: {
                'distinctQuestions': sum(i['status'] == status for i in items),
                'occurrences': sum(len(i['sequences']) for i in items if i['status'] == status),
            } for status in LABELS},
        },
        'items': items,
    }


def render_report(data):
    esc = html.escape
    cards, rows = [], []
    for item in data['items']:
        ids = ', '.join(map(str, item['sequences']))
        anchor, status = f"q-{item['sequences'][0]}", item['status']
        rows.append(f'<tr data-status="{status}"><td><a href="#{anchor}">{ids}</a></td>'
                    f'<td>{esc(item["question"])}</td><td>{esc(item["verdict"])}</td></tr>')
        options = []
        for i, answer in enumerate(item['answers']):
            selected = item['proposedCorrect'] is not None and i in item['proposedCorrect']
            options.append(f'<li class="{"selected" if selected else ""}">'
                           f'<strong>{"ABCD"[i]}.</strong> {esc(answer)}'
                           f'{" <span class=marker>navrhnutá</span>" if selected else ""}</li>')
        originals = []
        for occurrence in item['originalOccurrences']:
            src = occurrence['source']
            pdf_url = '../../' + quote(src['file']) + f'#page={src["page"]}'
            page = str(src['page'])
            if src['endPage'] != src['page']:
                page += f'–{src["endPage"]}'
            originals.append(
                f'<li>Poradie {src["sequence"]}; vytlačené číslo {src["questionNumber"]}; '
                f'<a href="{esc(pdf_url)}">PDF, strana {page}</a>. '
                f'Zachytené označenia: {letters(occurrence["detectedCorrect"])}. '
                f'Dôvod odloženia: {esc(" ".join(occurrence["reviewReasons"]))}</li>')
        refs = ' · '.join(
            f'<a href="{esc(data["sources"][ref]["url"])}">{esc(data["sources"][ref]["title"])}</a>'
            for ref in item['sourceRefs'])
        observation = (f'<p><strong>Poznámka z PDF:</strong> {esc(item["sourceObservation"])}</p>'
                       if item.get('sourceObservation') else '')
        cards.append(f'''<article id="{anchor}" data-status="{status}">
<div class="card-top"><span class="badge {status}">{LABELS[status]}</span><a href="#{anchor}">Poradie {ids}</a></div>
<h2>{esc(item['question'])}</h2>
<ol class="answers">{''.join(options)}</ol>
<div class="verdict"><strong>Návrh:</strong> {esc(item['verdict'])}<br>
<span><strong>Istota:</strong> {esc(item['confidence'])}</span></div>
<p><strong>Zdôvodnenie:</strong> {esc(item['reason'])}</p>
<p><strong>Odporúčaná úprava:</strong> {esc(item['action'])}</p>
{observation}<p class="sources"><strong>Podklady:</strong> {refs}</p>
<details><summary>Pôvodné označenia a výskyty ({len(item['sequences'])})</summary>
<p>Zachytené značky nie sú overeným kľúčom.</p><ul>{''.join(originals)}</ul></details>
</article>''')
    counts = ''.join(
        f'<div><strong>{data["summary"]["byStatus"][s]["occurrences"]}</strong>{label}'
        f'<small>{data["summary"]["byStatus"][s]["distinctQuestions"]} odlišných znení</small></div>'
        for s, label in LABELS.items())
    filters = ''.join(f'<option value="{s}">{label}</option>' for s, label in LABELS.items())
    return '''<!doctype html>
<html lang="sk"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Biochémia 1 — revízia 45 otázok</title>
<style>
:root{color-scheme:light;--ink:#182638;--muted:#465870;--line:#d9e1ea;--accent:#215a94}
*{box-sizing:border-box}body{margin:0;background:#f2f5f9;color:var(--ink);font:16px/1.6 system-ui,sans-serif}
main{max-width:1050px;margin:auto;padding:40px 24px 70px}h1{font-size:2rem;line-height:1.2;margin:12px 0}
h2{font-size:1.2rem;line-height:1.4;margin:16px 0}a{color:var(--accent);text-underline-offset:3px}
p{margin:12px 0}.eyebrow,.muted{color:var(--muted)}.eyebrow{font-size:.85rem;text-transform:uppercase;letter-spacing:.06em}
.notice{border-left:4px solid var(--accent);padding:12px 18px;background:#e7effa;border-radius:4px}
.counts{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:24px 0}.counts div{background:white;padding:18px;border:1px solid var(--line);border-radius:10px}
.counts strong{display:block;font-size:2rem;line-height:1.1;margin-bottom:10px}.counts small{display:block;color:var(--muted)}
.controls{display:flex;gap:12px;flex-wrap:wrap;margin:24px 0 8px}label{display:flex;flex-direction:column;gap:5px;flex:1;min-width:200px}
input,select,button{font:inherit;padding:9px 12px;border:1px solid #a4b4c5;border-radius:6px;background:#fff;color:var(--ink)}
button{cursor:pointer;align-self:end}input:focus,select:focus,button:focus,a:focus{outline:3px solid #80b7e9;outline-offset:2px}
article{background:white;border:1px solid var(--line);border-radius:12px;padding:24px;margin:20px 0;scroll-margin-top:20px}
.card-top{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;font-size:.9rem}
.badge{padding:4px 10px;border-radius:5px;background:#e9edf4}.key_proposed{background:#e3f2e8;color:#1d603b}
.no_correct_option{background:#f1eafb;color:#603882}.wording_required{background:#fff0d3;color:#76501a}
.answers{list-style:none;padding:0}.answers li{padding:9px 12px;margin:6px 0;border:1px solid var(--line);border-radius:6px}
.answers .selected{background:#eff8f1;border-color:#82b491}.marker{font-size:.8rem;color:#1d603b;white-space:nowrap}
.verdict{border-top:1px solid var(--line);padding-top:14px}.verdict span{color:var(--muted);font-size:.93rem}
.sources,details{font-size:.9rem}details{border-top:1px solid var(--line);padding-top:12px;margin-top:16px}summary{cursor:pointer;font-weight:600}
.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;font-size:.9rem}th,td{text-align:left;vertical-align:top;padding:10px;border-bottom:1px solid var(--line)}
th{background:#e7edf5}td:first-child{min-width:90px}[hidden]{display:none!important}
@media(max-width:650px){main{padding:24px 14px}.counts{grid-template-columns:1fr}.counts div{padding:12px 16px}.counts strong{display:inline;margin-right:12px;font-size:1.6rem}article{padding:18px}h1{font-size:1.6rem}}
@media print{body{background:white;font-size:11pt}main{max-width:none;padding:0}.controls,#visible-count,.table-wrap{display:none}article{break-inside:avoid;border-color:#bbb}a{color:inherit}.counts{grid-template-columns:repeat(3,1fr)}}
</style></head><body><main>
<header><div class="eyebrow">2. ročník · Biochémia · ''' + esc(data['reviewDate']) + '''</div>
<h1>Revízia 45 odložených otázok</h1>
<p>39 odlišných znení; šesť dvojíc presných duplikátov sa posudzuje spoločne.</p>
<p class="notice"><strong>Návrh na kontrolu.</strong> Každá odpoveď čaká na posúdenie. Aktívne testy ani pôvodný súbor odložených otázok sa touto revíziou nemenia.</p>
<div class="counts">''' + counts + '''</div>
<p>Pri každej otázke je pôvodný text, návrh odpovedí, miera istoty, zdôvodnenie a zdroje. Zelené možnosti sú návrhy pre pôvodné znenie. Pri nejasnom zadaní zostáva kľúč otvorený; prípadný kľúč po oprave je uvedený iba slovne.</p>
<details><summary>Predpoklady a spôsob hodnotenia</summary><p>''' + esc(data['policy']) + '''</p>
<p>Počty v kartách hore označujú výskyty otázok. Identifikátor „poradie“ zodpovedá extrakcii; vytlačené číslo je uvedené pri odkaze na PDF. Pri poradí 28 ide o vytlačenú otázku 26.</p>
<p>„Žiadna správna možnosť“ je vecný návrh v uvedenom modeli, nie chýbajúca odpoveď. Pri bilanciách ATP sa nepovažujú približné učebnicové hodnoty za presnú stechiometriu každej bunky.</p>
<p>Podklad pre energetickú konvenciu: <a href="''' + esc(data['sources']['po']['url']) + '''">''' + esc(data['sources']['po']['title']) + '''</a>.</p></details>
<p><a href="revizia_odpovedi.json" download>Stiahnuť celý prehľad v JSON</a></p></header>
<div class="controls"><label>Hľadať otázku alebo poradie<input id="search" type="search" placeholder="napr. 441, FMN, glukóza"></label>
<label>Výsledok posúdenia<select id="status"><option value="all">Všetky otázky</option>''' + filters + '''</select></label>
<button id="reset" type="button">Zobraziť všetko</button></div>
<p id="visible-count" class="muted" role="status" aria-live="polite">Zobrazených 39 znení (45 výskytov).</p>
<details class="table-wrap"><summary>Rýchly prehľad všetkých návrhov</summary><table><thead><tr><th>Poradie</th><th>Otázka</th><th>Návrh</th></tr></thead><tbody>''' + ''.join(rows) + '''</tbody></table></details>
<section id="questions" aria-label="Posúdené otázky">''' + ''.join(cards) + '''</section>
<p class="muted">Posúdenie sa týka len tejto odloženej sady. Zdroje podporujú odborné vysvetlenie; nenahrádzajú oficiálny kľúč predmetu.</p>
</main><script>
const cards = [...document.querySelectorAll('article')];
const search = document.querySelector('#search');
const status = document.querySelector('#status');
const normalize = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
function filter() {
  const query = normalize(search.value.trim());
  let visible = 0;
  let occurrences = 0;
  for (const card of cards) {
    card.hidden = !((status.value === 'all' || card.dataset.status === status.value)
      && normalize(card.textContent).includes(query));
    if (!card.hidden) {
      visible += 1;
      occurrences += card.querySelectorAll('details li').length;
    }
  }
  document.querySelector('#visible-count').textContent = `Zobrazených ${visible} znení (${occurrences} výskytov).`;
}
search.addEventListener('input', filter);
status.addEventListener('change', filter);
function reset() { search.value = ''; status.value = 'all'; filter(); }
document.querySelector('#reset').addEventListener('click', reset);
function revealHash() {
  const target = document.getElementById(location.hash.slice(1));
  if (target && target.hidden) { reset(); target.scrollIntoView(); }
}
window.addEventListener('hashchange', revealHash);
</script></body></html>
'''


def main():
    data = build_data()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / 'revizia_odpovedi.json').write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (OUTPUT / 'revizia_odpovedi.html').write_text(render_report(data), encoding='utf-8')
    print(json.dumps(data['summary'], ensure_ascii=False, indent=2))
    print(f'Prehľad: {OUTPUT / "revizia_odpovedi.html"}')


if __name__ == '__main__':
    main()
