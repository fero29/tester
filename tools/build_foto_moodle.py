#!/usr/bin/env python3
"""Build 'foto moodle pdf' test from zápočet LS 2 extraction.

Inclusion criteria (per analysis):
  - new (98): include as-is
  - similar with same answer (13): include PDF text + same answer
  - false-positive conflicts (8): include PDF text + PDF answer
                                   (they are biologically distinct from existing)
  - intra-PDF conflicts with clear biology (13): include with bio-determined answer
  - real conflicts (4 Vision errors): EXCLUDE
  - sporné intra (1, ependymocyty): EXCLUDE

Then apply topic filter: only krv / nervové tkanivo / svalové tkanivo /
embryológia (úvod, embryogenéza, notochord, neurálna rúra).
"""
import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).parent.parent
TESTY = ROOT / 'testy'
OUT = ROOT / 'tools' / 'out'

EXISTING = [
    'histo 2.json',
    'histológia 2 zápočet.json',
    'histo zápočet Moodle.json',
    'histo zápočet foto.json',
    'histológia zubári.json',
]

FUZZY_HIGH = 0.95
FUZZY_LOW = 0.85

# 4 Vision real-error questions to EXCLUDE entirely
EXCLUDE_REAL_CONFLICTS = [
    'kapacitacia spermii prebieha v nadsemenniku',
    'zlte telesko corpus luteum je docasny endokrinny organ v stene maternice',
    'primitivne crevo vznika z ektodermalnej',
    # hladká svalovina jednotka vlákno: tu Vision raz pravda raz nepravda;
    # existujúci test má nepravda; pridáme to s nepravdou ako intra-conflict resolution
]

# Intra-PDF conflicts: manual biology-determined answers
INTRA_RESOLUTIONS = {
    'sarkolema je funkcna jednotka kostroveho svaloveho': 'nepravda',
    'velkost bazofilneho granulocytu je mensia ako velkost erytrocytu': 'nepravda',
    'interteritorialny matrix hyalinovej chrupky je homogenny obsahuje vela vody a fibrily z kolagenu ii': 'pravda',
    'kapacitacia spermii prebieha v nadsemenniku': 'EXCLUDE',
    'zakladnou morfologickou jednotkou hladkej svaloviny je svalove vlakno': 'nepravda',
    'eozinofilny granulocyt ma v cytoplazme vyrazne tehlovocervene': 'pravda',
    'zlte telesko corpus luteum je docasny endokrinny organ v stene maternice': 'nepravda',
    'lymfocyty obsahuju specificke granuly': 'nepravda',
    'vsetky tri zarodkove vrstvy su povodom z hypoblastu': 'nepravda',
    'bazofilne granulocyty produkuju histamin a heparin ktore su skladovane v nespecifickych': 'nepravda',
    'dutinky medzi trabekulami spongioznej kosti su vystlane periostom': 'nepravda',
    'agranulocyty su charakterizovane acidofilnou cytoplazmou': 'nepravda',
    'medzibunkova hmota elastickej chrupky obsahuje fibrily z kolagenu ii a pocetne elasticke': 'pravda',
    # ependymocyty mikroklky+riasinky — sporné, vylúčiť
    'na apikalnom povrchu ependymocytov sa mozu nachadzat mikroklky a riasinky': 'EXCLUDE',
}

# Topic filter
WHITELIST = [
    # Krv
    r'\berytrocyt', r'\bleukocyt', r'\btrombocyt',
    r'\bneutrofil', r'\beozinofil', r'\bbazofil(?!ne)',
    r'\bmonocyt', r'\blymfocyt', r'\bgranulocyt', r'\bretikulocyt',
    r'\bkrvink', r'\bkrvi\b', r'\bkrvn[aey]',
    r'\bmikrofag', r'hematokrit', r'hemoglobin',
    r'azurofiln', r'periferne[jy] krvi', r'\bplazmocyt',
    r'pappenheim',
    # Nervové tkanivo
    r'\bneuron', r'neurogli', r'\bgli[aoue]\b', r'\bgliov',
    r'astrocyt', r'oligodendrocyt', r'\bmikrogli', r'ependym',
    r'satelitov[ae] bunk', r'schwann',
    r'pyramidov', r'multipolarn', r'pseudounipolarn',
    r'nisslov', r'neurofibril', r'neurit\b', r'\baxon', r'\bdendrit',
    r'perikaryon', r'\bmielin', r'\bmyelin',
    r'nervov\w* tkaniv', r'nervov\w* vlakn',
    r'\bsivej hmot', r'sed[ae] hmot', r'biel\w* hmot',
    r'kor\w+ mozg', r'kor\w+ mozock',
    r'\bmozg\b', r'\bmozock\b', r'\bmozgu\b', r'\bmiech',
    r'\bgangli', r'\bcns\b', r'\bpns\b',
    r'\bholmes', r'bielschowsk', r'\bgolgi\b', r'luxulov',
    r'tigroid', r'hemato.encefal',
    # Svalové tkanivo
    r'\bmyocyt', r'kardiomyocyt',
    r'\bsval\w*',
    r'priecn\w* pruh', r'\bmyokard',
    r'sarkoplazm', r'sarkomer', r'sarkolem',
    r'myofilamen', r'myofibril', r'\baktin', r'\bmyozin',
    r'\btriad', r'\bdiad', r'\bz.lini',
    r't.tubul', r'a.pruzok', r'i.pruzok',
    r'endomyz', r'perimyz', r'epimy[zs]',
    r'denzn\w* teliesk', r'purkynov\w* vlakn',
    # Embryológia
    r'notochord', r'chorda dor',
    r'neuraln\w* rur', r'neuraln\w* trub',
    r'gastrula', r'blastula', r'blastomer', r'morul', r'blastocyst',
    r'\bektoderm', r'\bmezoderm', r'\bendoderm', r'epiblast', r'hypoblast',
    r'oplodn', r'fertilizac', r'\bakrozom', r'zona pelluc',
    r'\bzygot', r'\bspermi[aei]', r'\boocyt', r'ovula',
    r'embryon', r'embryoblast', r'trofoblast',
    r'implantac', r'deciduin', r'kapacitac',
    r'primitivn\w* prouz', r'primitivn\w* cre',
    r'zarodkov\w* vrstv', r'zarodkov\w* stit',
]

BLACKLIST = [
    r'\bven[ay]\b', r'\bvene\b', r'\btepn[ay]', r'\btepiny', r'\barteri',
    r'\baort[ae]', r'pericyt', r'vasa vasorum',
    r'tunica intim', r'tunica medi', r'tunica advet?iti',
    r'elastick\w* membran', r'\bkapilar',
    r'osteoblast', r'osteoprogenitor', r'\bosteoid', r'osteoklast',
    r'osteocyt', r'osteon', r'\bperiost', r'\bendost',
    r'haversov', r'volkmann', r'lakun',
    r'\bfibroblast', r'plazmatick\w* bunky vaziv',
    r'perichondri', r'\bchondrocyt', r'\bchondroblast',
    r'\bchrupk', r'enchondr', r'hyalinov\w* chrupk',
    r'vazivov\w* chrupk', r'elastick\w* chrupk',
    r'endokard', r'\bmezotel', r'\bepikard', r'subepikard',
    r'\bzirnicov\w* bunk', r'\bzlnicov\w* bunk', r'\bzirn\w* bunk',
    r'kostn\w* tkaniv', r'kostn\w* trabec', r'spongiozn\w* kost',
]


def norm(s):
    s = s.lower()
    s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    return re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', ' ', s)).strip()


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
        p = TESTY / fn
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
                if qt:
                    entries.append({'norm': norm(qt), 'correct': c, 'source': fn})
    return entries


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
                           'sources': [(it.get('q_num'), it.get('pdf_page'))],
                           'answers_seen': Counter([it['correct']])})
        else:
            found['sources'].append((it.get('q_num'), it.get('pdf_page')))
            found['answers_seen'][it['correct']] += 1
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


def topic_match(text):
    n = norm(text)
    for bp in BLACKLIST:
        if re.search(bp, n):
            return False
    for wp in WHITELIST:
        if re.search(wp, n):
            return True
    return False


def main():
    with open(OUT / 'zap_ls2.json', encoding='utf-8') as f:
        raw = json.load(f)
    items = []
    for r in raw:
        q = (r.get('question') or '').strip()
        c = (r.get('correct') or '').strip().lower()
        if not q or c not in ('pravda', 'nepravda'):
            continue
        items.append({'norm': norm(q), 'orig': q, 'correct': c,
                      'q_num': r.get('q'), 'pdf_page': r.get('pdf_page')})

    unique = dedupe(items)
    existing = load_existing()
    print(f'Unique: {len(unique)} | Existing: {len(existing)}')

    selected = []
    stats = Counter()

    for u in unique:
        n = u['norm']
        # Resolve answer
        # 1) Check explicit EXCLUDE
        excluded_explicit = False
        for kw in EXCLUDE_REAL_CONFLICTS:
            if kw in n:
                excluded_explicit = True; break
        # 2) Check intra resolution
        resolved_correct = None
        for kw, ans in INTRA_RESOLUTIONS.items():
            if kw in n:
                if ans == 'EXCLUDE':
                    excluded_explicit = True
                else:
                    resolved_correct = ans
                break

        if excluded_explicit:
            stats['excluded_real_conflict'] += 1
            continue

        correct = resolved_correct or u['correct']

        # 3) Match against existing
        m, kind, ratio = best_match(n, existing)
        if kind == 'exact' or kind == 'near_identical':
            if m['correct'] == correct:
                stats['duplicate_of_existing'] += 1
                continue
            else:
                # Real conflict — if not in EXCLUDE list and not in INTRA — keep PDF
                # but flag (likely Vision error, but per analysis 8 were FP)
                # We trust the topic filter; just include PDF text+answer
                stats['conflict_kept_as_fp'] += 1
        elif kind == 'similar':
            stats['similar_to_existing'] += 1
        else:
            stats['new'] += 1

        # 4) Apply topic filter
        if not topic_match(u['orig']):
            stats['topic_filtered_out'] += 1
            continue

        selected.append({'question': u['orig'], 'correct': correct})

    print('\nClassification stats:')
    for k, v in stats.most_common():
        print(f'  {k}: {v}')
    print(f'\nFinal selected: {len(selected)}')

    # Build test
    questions = []
    for s in selected:
        ans = ['pravda', 'nepravda']
        idx = ans.index(s['correct'])
        questions.append({'question': s['question'], 'answers': ans, 'correct': [idx]})

    test = [{
        'title': 'foto moodle pdf',
        'description': f'Otázky zo zápočetného PDF (zápočet LS 2, 395 strán screenshotov). Filtrované: len krv, nervové tkanivo, svalové tkanivo a embryológia úvod (notochord, neurálna rúra). Nezahrnuté otázky, ktoré sú už v iných existujúcich histo testoch. Vylúčené Vision chyby a sporné OCR. Spolu {len(questions)} otázok.',
        'category': 'Histológia',
        'questions': questions,
    }]
    path = TESTY / 'foto moodle pdf.json'
    with open(path, 'x', encoding='utf-8') as f:
        json.dump(test, f, ensure_ascii=False, indent=2)
    print(f'\nSaved: {path} ({len(questions)} questions)')


if __name__ == '__main__':
    main()
