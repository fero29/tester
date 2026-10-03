from flask import Flask, render_template, request, jsonify, abort, session, redirect, url_for
import json
import os
import base64
import io
import hashlib
import secrets
import math
from functools import wraps
import threading
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter, defaultdict, deque
from storage import TestStore, StoreError, validate_tests
from security import init_security
import anthropic
from dotenv import load_dotenv
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import cv2
import numpy as np
import re

def fix_json_string(json_str):
    """Pokúsi sa opraviť bežné chyby v JSON reťazci generovanom AI"""
    # Odstráň neplatné kontrolné znaky
    json_str = ''.join(char for char in json_str if ord(char) >= 32 or char in '\n\r\t')

    # Oprav trailing commas pred ] alebo }
    json_str = re.sub(r',\s*]', ']', json_str)
    json_str = re.sub(r',\s*}', '}', json_str)

    # Oprav chýbajúce čiarky medzi objektami v poli: }{ -> },{
    json_str = re.sub(r'}\s*{', '},{', json_str)

    # Oprav chýbajúce čiarky medzi hodnotou a kľúčom: "hodnota"\s*"kluc" -> "hodnota","kluc"
    json_str = re.sub(r'"\s*\n\s*"([a-zA-Z_])', r'","\1', json_str)

    # Oprav neuzavreté stringy pred čiarkou/zátvorkou
    # Hľadá pattern kde string začína ale nekončí pred čiarkou

    return json_str

def parse_ai_response(response):
    text = next(block.text for block in response.content if block.type == 'text').strip()
    match = re.search(r'```(?:json)?\s*(.*?)```', text, re.DOTALL)
    if match:
        text = match.group(1)
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        result = json.loads(fix_json_string(text))
    if not isinstance(result, dict):
        raise StoreError('AI nevrátilo platný objekt s otázkami alebo slovíčkami.')
    return result


# Load environment variables
load_dotenv()

app = Flask(__name__)

# Dáta sú oddelené od kódu a image. Testovací Compose používa ich kópiu.
BASE_DIR = Path(__file__).resolve().parent
APP_VERSION = (BASE_DIR / 'VERSION').read_text().strip()
DATA_DIR = Path(os.environ.get('DATA_DIR', BASE_DIR / 'data'))
TESTS_DIR = os.environ.get('TESTS_DIR', str(BASE_DIR / 'testy'))
app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY') or secrets.token_hex(32),
    ADMIN_SECRET=os.environ.get('ADMIN_SECRET', ''),
    SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE', 'false').lower() == 'true',
    MAX_CONTENT_LENGTH=32 * 1024 * 1024,
    MAX_FORM_MEMORY_SIZE=1024 * 1024,
)
if app.config['ADMIN_SECRET'] and not os.environ.get('SECRET_KEY'):
    raise RuntimeError('Pre správu testov nastavte stabilný SECRET_KEY v prostredí.')
app.extensions['test_store'] = TestStore(TESTS_DIR, DATA_DIR)
EVENTS_FILE = DATA_DIR / 'events.jsonl'
if os.environ.get('TRUST_PROXY_HEADERS', 'false').lower() == 'true':
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
rate_limiter = init_security(app)
EVENT_LOCK = threading.Lock()
AI_LOCK = threading.Lock()


def store():
    return app.extensions['test_store']


@app.errorhandler(StoreError)
def store_error(error):
    return jsonify(error=str(error)), error.status


@app.errorhandler(413)
def too_large(error):
    return jsonify(error='Súbor je príliš veľký. Limit je 32 MB.'), 413


def json_object():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise StoreError('Očakáva sa JSON objekt.')
    return data


def anthropic_client():
    if not os.environ.get('ANTHROPIC_API_KEY'):
        raise StoreError('AI import nie je nakonfigurovaný.', 503)
    return anthropic.Anthropic(timeout=90, max_retries=1)


def ai_request(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not os.environ.get('ANTHROPIC_API_KEY'):
            return jsonify(error='AI import nie je nakonfigurovaný.'), 503
        if not AI_LOCK.acquire(blocking=False):
            return jsonify(error='Prebieha iný AI import. Skúste to po jeho dokončení.'), 429
        try:
            return view(*args, **kwargs)
        finally:
            AI_LOCK.release()
    return wrapped


def client_ip():
    return request.remote_addr or 'unknown'


@app.route('/')
def index():
    return render_template('index.html', app_version=APP_VERSION, cf_analytics_token=os.environ.get('CF_ANALYTICS_TOKEN', ''))


@app.route('/api/track', methods=['POST'])
def track():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or data.get('event') not in ('page_view', 'test_start', 'test_finish'):
        return jsonify(ok=False), 400
    for field, limit in (('test', 200), ('mode', 50)):
        if not isinstance(data.get(field, ''), str) or len(data.get(field, '')) > limit:
            return jsonify(ok=False), 400
    for field in ('score', 'total', 'percent', 'duration_sec'):
        value = data.get(field)
        if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
            return jsonify(ok=False), 400
    if data.get('percent') is not None and data['percent'] > 100:
        return jsonify(ok=False), 400
    rec = {key: data.get(key) for key in ('event', 'test', 'score', 'total', 'percent', 'mode', 'duration_sec')}
    rec.update(ts=datetime.now(timezone.utc).isoformat(), ip=client_ip(),
               ua=(request.headers.get('User-Agent') or '')[:300],
               ref=(request.headers.get('Referer') or '')[:300])
    try:
        with EVENT_LOCK:
            # Otočenie logu zachová staršie eventy a obmedzí veľkosť aktívneho súboru.
            if EVENTS_FILE.exists() and EVENTS_FILE.stat().st_size > 10 * 1024 * 1024:
                EVENTS_FILE.rename(EVENTS_FILE.with_name('events-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f') + '.jsonl'))
            with EVENTS_FILE.open('a', encoding='utf-8') as handle:
                handle.write(json.dumps(rec, ensure_ascii=False, allow_nan=False) + '\n')
    except OSError:
        app.logger.exception('Nepodarilo sa uložiť analytický event')
        return jsonify(ok=False), 503
    return jsonify(ok=True)


def _parse_ua(ua):
    """Very lightweight UA parser → (device, browser, os)."""
    ua_l = ua.lower()
    if 'iphone' in ua_l or 'ipod' in ua_l: device = 'iPhone'
    elif 'ipad' in ua_l: device = 'iPad'
    elif 'android' in ua_l: device = 'Android'
    elif 'mobile' in ua_l: device = 'Mobile'
    elif 'tablet' in ua_l: device = 'Tablet'
    else: device = 'Desktop'
    if 'edg/' in ua_l: browser = 'Edge'
    elif 'opr/' in ua_l or 'opera' in ua_l: browser = 'Opera'
    elif 'chrome' in ua_l and 'safari' in ua_l: browser = 'Chrome'
    elif 'firefox' in ua_l: browser = 'Firefox'
    elif 'safari' in ua_l: browser = 'Safari'
    else: browser = 'Other'
    if 'iphone os' in ua_l or 'cpu os' in ua_l: os_name = 'iOS'
    elif 'mac os' in ua_l: os_name = 'macOS'
    elif 'android' in ua_l: os_name = 'Android'
    elif 'windows' in ua_l: os_name = 'Windows'
    elif 'linux' in ua_l: os_name = 'Linux'
    else: os_name = 'Other'
    return device, browser, os_name


def fetch_cf_analytics():
    """Fetch Cloudflare Web Analytics via GraphQL. Returns None if not configured."""
    token = os.environ.get('CF_API_TOKEN')
    account_tag = os.environ.get('CF_ACCOUNT_TAG')
    site_tag = os.environ.get('CF_SITE_TAG')
    if not (token and account_tag and site_tag):
        return None
    import urllib.request
    from datetime import timedelta
    since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime('%Y-%m-%d')
    query = """
    query($accountTag: String!, $siteTag: String!, $since: Date!) {
      viewer {
        accounts(filter: {accountTag: $accountTag}) {
          totals: rumPageloadEventsAdaptiveGroups(filter: {siteTag: $siteTag, date_geq: $since}, limit: 1) {
            count
            sum { visits }
          }
          countries: rumPageloadEventsAdaptiveGroups(filter: {siteTag: $siteTag, date_geq: $since}, limit: 10, orderBy: [count_DESC]) {
            count
            dimensions { countryName }
          }
          devices: rumPageloadEventsAdaptiveGroups(filter: {siteTag: $siteTag, date_geq: $since}, limit: 10, orderBy: [count_DESC]) {
            count
            dimensions { deviceType }
          }
        }
      }
    }
    """
    payload = json.dumps({'query': query, 'variables': {
        'accountTag': account_tag, 'siteTag': site_tag, 'since': since
    }}).encode('utf-8')
    req = urllib.request.Request(
        'https://api.cloudflare.com/client/v4/graphql',
        data=payload, method='POST',
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f'CF API error: {e}')
        return None
    try:
        acct = data['data']['viewer']['accounts'][0]
        totals = acct.get('totals', [])
        pageviews = sum(t.get('count', 0) for t in totals)
        visits = sum((t.get('sum') or {}).get('visits', 0) for t in totals)
        visitors = visits  # CF RUM AdaptiveGroups nemá samostatný unique visitors field
        # Aggregate countries
        country_groups = Counter()
        for g in acct.get('countries', []):
            c = (g.get('dimensions') or {}).get('countryName') or 'Unknown'
            country_groups[c] += g.get('count', 0)
        device_groups = Counter()
        for g in acct.get('devices', []):
            d = (g.get('dimensions') or {}).get('deviceType') or 'Unknown'
            device_groups[d] += g.get('count', 0)
        return {
            'pageviews': pageviews, 'visits': visits, 'visitors': visitors,
            'countries': country_groups.most_common(8),
            'devices': device_groups.most_common(6),
        }
    except (KeyError, IndexError, TypeError) as e:
        print(f'CF API parse error: {e}, data={data}')
        return None


@app.route('/admin/stats')
def admin_stats():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    # Dashboard pracuje s poslednými 50 000 eventmi; archívy zostávajú na disku.
    events = []
    if EVENTS_FILE.exists():
        with EVENTS_FILE.open(encoding='utf-8') as handle:
            for line in deque(handle, maxlen=50000):
                try:
                    event = json.loads(line)
                    if (isinstance(event, dict) and isinstance(event.get('ts'), str)
                            and event.get('event') in ('page_view', 'test_start', 'test_finish')
                            and all(isinstance(event.get(key) or '', str) for key in ('test', 'ua', 'ip', 'ref'))):
                        events.append(event)
                except (ValueError, TypeError):
                    continue
    # Aggregations
    daily = Counter()
    by_event = Counter()
    by_test = Counter()
    finishes_by_test = defaultdict(list)  # test → [percent...]
    device_cnt = Counter()
    browser_cnt = Counter()
    os_cnt = Counter()
    unique_ips = set()
    hourly = Counter()
    referrers = Counter()
    sessions = defaultdict(list)  # ip → [timestamps]

    for e in events:
        ts = e.get('ts', '')
        if not ts: continue
        try:
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        except (ValueError, TypeError):
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        daily[dt.date().isoformat()] += 1
        hourly[dt.hour] += 1
        ev = e.get('event', '')
        by_event[ev] += 1
        test = e.get('test')
        if test:
            by_test[test] += 1
        if ev == 'test_finish' and test and type(e.get('percent')) in (int, float) and math.isfinite(e['percent']):
            finishes_by_test[test].append(e['percent'])
        d, b, o = _parse_ua(e.get('ua') or '')
        device_cnt[d] += 1
        browser_cnt[b] += 1
        os_cnt[o] += 1
        ip = e.get('ip', '')
        if ip:
            unique_ips.add(ip)
            sessions[ip].append(dt)
        ref = e.get('ref', '')
        if ref:
            # zjednoduš na hostname
            m = re.search(r'https?://([^/]+)', ref)
            if m:
                referrers[m.group(1)] += 1

    # avg score per test
    avg_score = {t: round(sum(v) / len(v), 1) for t, v in finishes_by_test.items() if v}
    score_count = {t: len(v) for t, v in finishes_by_test.items()}

    # sessions (gap > 30 min)
    total_sessions = 0
    for ip, times in sessions.items():
        times.sort()
        prev = None
        for t in times:
            if prev is None or (t - prev).total_seconds() > 30 * 60:
                total_sessions += 1
            prev = t

    stats = {
        'total_events': len(events),
        'unique_ips': len(unique_ips),
        'total_sessions': total_sessions,
        'daily': dict(sorted(daily.items())),
        'hourly': dict(sorted(hourly.items())),
        'by_event': dict(by_event.most_common()),
        'by_test': dict(by_test.most_common(20)),
        'avg_score': avg_score,
        'score_count': score_count,
        'device': dict(device_cnt.most_common()),
        'browser': dict(browser_cnt.most_common()),
        'os': dict(os_cnt.most_common()),
        'referrers': dict(referrers.most_common(10)),
    }
    cf_data = fetch_cf_analytics()
    return render_template('admin_stats.html', stats=stats,
                           cf_data=cf_data)

@app.get('/health')
def health():
    return jsonify(status='ok')


@app.get('/api/tests/meta')
def get_tests_meta():
    _, meta = store().catalog(include_tests=False)
    return jsonify(meta)


@app.get('/api/tests')
def get_tests():
    tests, meta = store().catalog()
    response = jsonify(tests)
    response.set_etag(hashlib.sha256(json.dumps(meta, sort_keys=True).encode()).hexdigest())
    response.headers['Cache-Control'] = 'no-cache'
    return response.make_conditional(request)


@app.post('/api/import')
def import_tests():
    file = request.files.get('file')
    if file is None:
        raise StoreError('Žiadny súbor.')
    try:
        data = json.load(file)
    except (ValueError, UnicodeError):
        raise StoreError('Súbor neobsahuje platný JSON.') from None
    return jsonify(success=True, count=store().import_tests(data))


def check_folder():
    if json_object().get('folder', 'testy') != 'testy':
        raise StoreError('Prístup je povolený iba k adresáru testov.')


@app.post('/api/load-from-folder')
def load_from_folder():
    check_folder()
    tests, meta = store().catalog()
    return jsonify(success=True, count=len(tests), files=len(meta), message=f'Načítaných {len(tests)} testov.')


@app.post('/api/list-files')
def list_files():
    check_folder()
    _, meta = store().catalog(include_tests=False)
    return jsonify(files=[m['filename'] for m in meta])


def deskew_image(img_array):
    """Perspektívna korekcia - opravuje fotky fotené z uhla

    Args:
        img_array: Numpy array obrázka

    Returns:
        Numpy array s opravenou perspektívou
    """
    try:
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

        # Detekcia hrán pomocou Canny
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)

        # Nájsť línie pomocou Hough Transform
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=100, minLineLength=100, maxLineGap=10)

        if lines is None or len(lines) < 4:
            # Ak sa nenašli dostatočné línie, vráť originál
            return img_array

        # Vypočítať uhol sklonu (skew)
        angles = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
            # Normalizovať uhol do rozsahu -90 až 90
            if angle < -45:
                angle += 90
            elif angle > 45:
                angle -= 90
            angles.append(angle)

        if not angles:
            return img_array

        # Použiť mediánový uhol (robustnejšie ako priemer)
        median_angle = np.median(angles)

        # Ak je uhol príliš malý, neaplikuj korekciu
        if abs(median_angle) < 0.5:
            return img_array

        # Rotovať obrázok o detekovaný uhol
        (h, w) = img_array.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
        rotated = cv2.warpAffine(img_array, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

        return rotated
    except Exception as e:
        print(f"Chyba pri deskew: {e}")
        return img_array

def preprocess_image(image_file, advanced=False, rotation=0):
    """Predspracuje obrázok pre lepšie rozpoznávanie AI

    Args:
        image_file: Súbor s obrázkom
        advanced: Ak True, použije pokročilé predspracovanie s OpenCV
        rotation: Manuálna rotácia v stupňoch (0, 90, 180, 270)
    """
    # Načítať obrázok
    img = Image.open(image_file)
    if img.width * img.height > 20_000_000:
        raise StoreError('Obrázok je príliš veľký (maximum 20 megapixelov).')
    if rotation not in (0, 90, 180, 270):
        raise StoreError('Neplatné otočenie obrázka.')

    # Opraviť EXIF orientáciu (fotky z mobilu)
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass  # Ak EXIF nie je dostupný, pokračuj bez opravy

    # Aplikovať manuálnu rotáciu
    if rotation and rotation != 0:
        img = img.rotate(-rotation, expand=True)  # PIL používa opačný smer rotácie

    # Konverzia na RGB
    if img.mode != 'RGB':
        img = img.convert('RGB')

    # Zväčšenie rozlíšenia ak je príliš malé
    max_size = 2048
    if max(img.size) < max_size:
        ratio = max_size / max(img.size)
        new_size = tuple(int(dim * ratio) for dim in img.size)
        img = img.resize(new_size, Image.LANCZOS)

    # Ak je príliš veľké, zmenši
    max_size_limit = 3000
    if max(img.size) > max_size_limit:
        ratio = max_size_limit / max(img.size)
        new_size = tuple(int(dim * ratio) for dim in img.size)
        img = img.resize(new_size, Image.LANCZOS)

    if advanced:
        # Pokročilé predspracovanie s OpenCV
        # Konverzia do numpy array
        img_array = np.array(img)

        # Perspektívna korekcia - opraviť fotky z uhla
        img_array = deskew_image(img_array)

        # Konverzia do grayscale pre lepšie spracovanie
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

        # Aplikovať CLAHE (Contrast Limited Adaptive Histogram Equalization)
        # - Vylepší lokálny kontrast
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(gray)

        # Silnejší denoising - odstráni viac šumu
        # h=15 pre silnejší efekt (default 10)
        # templateWindowSize=7, searchWindowSize=21 pre lepšie výsledky
        denoised = cv2.fastNlMeansDenoising(enhanced, None, h=15, templateWindowSize=7, searchWindowSize=21)

        # Bilateral filter pre ďalšie vyhladzenie pri zachovaní hrán
        denoised = cv2.bilateralFilter(denoised, 9, 75, 75)

        # Adaptívny threshold - konverzia na čiernobiele s lepším kontrastom
        # Pomôže pri rozpoznávaní krúžkov a podčiarknutí
        binary = cv2.adaptiveThreshold(
            denoised, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11, 2
        )

        # Morfologické operácie - odstráni drobné artefakty
        kernel = np.ones((2,2), np.uint8)
        cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

        # Sharpen filter pre lepšiu čitateľnosť
        kernel_sharpen = np.array([[-1,-1,-1],
                                   [-1, 9,-1],
                                   [-1,-1,-1]])
        sharpened = cv2.filter2D(cleaned, -1, kernel_sharpen)

        # Konverzia späť do PIL Image
        img = Image.fromarray(sharpened)
        # Konverzia grayscale späť na RGB pre API
        img = img.convert('RGB')
    else:
        # Základné predspracovanie
        # Zvýšenie ostrosti
        img = img.filter(ImageFilter.SHARPEN)

        # Zvýšenie kontrastu
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.3)

        # Zvýšenie jasu
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(1.1)

    # Uložiť do bytového bufferu
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=95, optimize=True)
    buffer.seek(0)

    return buffer

@app.route('/api/ai-import', methods=['POST'])
@ai_request
def ai_import():
    """AI import otázok z obrázku pomocou Claude Vision API"""
    try:
        # Získať obrázok z requestu
        if 'image' not in request.files:
            return jsonify({'error': 'Žiadny obrázok'}), 400

        image_file = request.files['image']

        # Získať nastavenie pokročilého predspracovania
        advanced_preprocessing = request.form.get('advancedPreprocessing', 'false') == 'true'

        # Získať manuálnu rotáciu
        rotation = int(request.form.get('rotation', 0))

        # Predspracovať obrázok pre AI
        image_file.seek(0)
        processed_image = preprocess_image(image_file, advanced=advanced_preprocessing, rotation=rotation)
        image_data = base64.b64encode(processed_image.read()).decode('utf-8')

        # Uložiť aj predspracovaný obrázok ako PIL Image pre výrezy
        image_file.seek(0)
        processed_image.seek(0)
        processed_pil = Image.open(processed_image)

        # Prompt pre Claude
        prompt = """Analyzuj tento obrázok a extrahuj z neho všetky otázky s možnými odpoveďami.

🔴 KRITICKY DÔLEŽITÉ - Viacero správnych odpovedí:
Pri KAŽDEJ otázke musíš skontrolovať VŠETKY odpovede a označiť VŠETKY, ktoré majú vizuálne označenie!

POSTUP:
1. Pre každú otázku prejdi POSTUPNE všetky odpovede (a, b, c, d)
2. Pre KAŽDÚ odpoveď skontroluj, či má NIEKTORÉ z týchto vizuálnych označení:
   ✓ Zakrúžkovaná odpoveď (kruh okolo písmena alebo textu)
   ✓ Zaškrtnutá odpoveď (checkmark, fajka)
   ✓ Podčiarknutý text
   ✓ Tučný text (bold, hrubšie písmo)
   ✓ Zvýraznený text (highlight, farebné pozadie, žltá, zelená)
   ✓ Hviezdička (*) pri odpovedi
   ✓ Text v rámčeku
   ✓ Slová "správna", "correct", "ano" pri odpovedi
3. VŠETKY odpovede s vizuálnym označením pridaj do poľa "correct"

⚠️ ČASTÁ CHYBA: Neuvádzaj len jednu správnu odpoveď ak vidíš viac zakrúžkovaných!

📍 POZÍCIA OTÁZKY:
Pre každú otázku urči jej približnú vertikálnu pozíciu na obrázku v percentách (0-100):
- 0% = úplne navrchu
- 50% = v strede
- 100% = úplne dole
Urči pozíciu ZAČIATKU otázky (nie stredu). Buď čo najpresnejší!

Vráť odpoveď v tomto PRESNOM JSON formáte:
{
  "suggestedTitle": "Navrhnutý názov testu",
  "suggestedDescription": "Krátky popis",
  "questions": [
    {
      "question": "Text otázky",
      "answers": ["odpoveď 1", "odpoveď 2", "odpoveď 3", "odpoveď 4"],
      "correct": [0, 2],
      "positionPercent": 15
    }
  ]
}

FORMÁT:
- "correct" je ARRAY indexov (0=prvá, 1=druhá, 2=tretia, 3=štvrtá)
- "positionPercent" je číslo 0-100 (vertikálna pozícia začiatku otázky)
- Answers musia byť presne 4 (ak je menej, doplň "")
- Vráť IBA čistý JSON

Analyzuj obrázok a vráť JSON:"""

        # Zavolať Claude Vision API (Sonnet 4.6)
        try:
            response = anthropic_client().messages.create(
                model="claude-sonnet-4-6",
                max_tokens=8192,
                temperature=0.1,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": image_data
                                }
                            },
                            {"type": "text", "text": prompt}
                        ]
                    }
                ]
            )
        except anthropic.APIError as e:
            print(f"Claude API Error: {str(e)}")
            return jsonify({
                'error': f'Chyba pri volaní Claude API: {str(e)}'
            }), 400

        result = parse_ai_response(response)
        validate_tests({'title': 'AI import', 'questions': result.get('questions')})

        # Vytvoriť výrezy pre každú otázku
        num_questions = len(result.get('questions', []))

        if num_questions > 0:
            img_width, img_height = processed_pil.size
            questions = result.get('questions', [])

            # Skontrolovať či AI poskytlo pozície
            has_positions = all(type(q.get('positionPercent')) in (int, float) and 0 <= q['positionPercent'] <= 100 for q in questions)
            has_positions = has_positions and all(a['positionPercent'] <= b['positionPercent'] for a, b in zip(questions, questions[1:]))

            for idx, question in enumerate(questions):
                if has_positions:
                    # Použiť AI-detekované pozície
                    current_pos = question.get('positionPercent', 0)

                    # Začiatok výrezu (s kontextom navrchu)
                    top_percent = max(0, current_pos - 5)  # 5% kontext navrchu

                    # Koniec výrezu - buď do nasledujúcej otázky, alebo do konca
                    if idx < num_questions - 1:
                        next_pos = questions[idx + 1].get('positionPercent', 100)
                        bottom_percent = min(100, (current_pos + next_pos) / 2 + 5)  # stred + 5% kontext
                    else:
                        bottom_percent = 100  # Posledná otázka - do konca

                    # Konvertovať percentá na pixely
                    top = int((top_percent / 100) * img_height)
                    bottom = int((bottom_percent / 100) * img_height)
                else:
                    # Fallback: rovnomerné delenie ak AI neposkytlo pozície
                    crop_height = img_height / num_questions
                    top = int(idx * crop_height)
                    bottom = int((idx + 1) * crop_height)

                    # Pridať malý overlap pre kontext (5%)
                    overlap = int(0.05 * crop_height)
                    top = max(0, top - overlap)
                    bottom = min(img_height, bottom + overlap)

                # Vytvoriť výrez
                crop_box = (0, top, img_width, bottom)
                cropped = processed_pil.crop(crop_box)

                # Konvertovať na base64
                buffer = io.BytesIO()
                cropped.save(buffer, format='JPEG', quality=85)
                buffer.seek(0)
                crop_base64 = base64.b64encode(buffer.read()).decode('utf-8')

                # Pridať výrez k otázke
                question['cropImage'] = f'data:image/jpeg;base64,{crop_base64}'

        # Pridať celý predspracovaný obrázok k výsledku
        buffer = io.BytesIO()
        processed_pil.save(buffer, format='JPEG', quality=90)
        buffer.seek(0)
        processed_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        result['processedImage'] = f'data:image/jpeg;base64,{processed_base64}'

        return jsonify({
            'success': True,
            'data': result
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/ai-import-vocab', methods=['POST'])
@ai_request
def ai_import_vocab():
    """AI import latinských slovíčok z obrázku pomocou Claude Vision API"""
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'Žiadny obrázok'}), 400

        image_file = request.files['image']

        # Získať nastavenie pokročilého predspracovania
        advanced_preprocessing = request.form.get('advancedPreprocessing', 'false') == 'true'

        # Predspracovať obrázok
        image_file.seek(0)
        processed_image = preprocess_image(image_file, advanced=advanced_preprocessing, rotation=int(request.form.get('rotation', 0)))
        image_data = base64.b64encode(processed_image.read()).decode('utf-8')

        # Prompt pre Claude - slovíčka
        prompt = """Analyzuj tento obrázok a extrahuj z neho latinské slovíčka.

Očakávaný formát v obrázku:
- Latinské slovo v základnom tvare (nominatív)
- Genitívna koncovka (napr. -ae, -i, -is, -us, -ei) ALEBO "-a, -um" pre prídavné mená
- Rod (m. = maskulínum, f. = feminínum, n. = neutrum) - len pre podstatné mená
- Slovenský preklad

Príklady formátov v texte:
PODSTATNÉ MENÁ (noun):
- "aqua, -ae, f. - voda"
- "liber, libri, m. - kniha"
- "mare, -is, n. - more"

PRÍDAVNÉ MENÁ (adjective) - poznáš ich podľa "-a, -um":
- "bonus, -a, -um - dobrý"
- "magnus, -a, -um - veľký"
- "albus, -a, -um - biely"

Pre KAŽDÉ slovíčko extrahuj:
1. latin: latinské slovo v základnom tvare (len slovo, bez koncovky)
2. type: "noun" pre podstatné mená, "adjective" pre prídavné mená (ak má koncovku -a, -um)
3. genitive: genitívna koncovka - LEN pre podstatné mená (pre prídavné mená nechaj prázdny string "")
4. gender: rod "m"/"f"/"n" - LEN pre podstatné mená (pre prídavné mená nechaj prázdny string "")
5. slovak: slovenský preklad

Vráť odpoveď v tomto PRESNOM JSON formáte:
{
  "vocabulary": [
    {
      "latin": "aqua",
      "type": "noun",
      "genitive": "-ae",
      "gender": "f",
      "slovak": "voda"
    },
    {
      "latin": "bonus",
      "type": "adjective",
      "genitive": "",
      "gender": "",
      "slovak": "dobrý"
    }
  ]
}

⚠️ DÔLEŽITÉ:
- Extrahuj VŠETKY slovíčka z obrázku
- Ak vidíš "-a, -um" alebo "a, um", je to PRÍDAVNÉ MENO (type: "adjective")
- Pre prídavné mená VŽDY nechaj genitive a gender ako prázdny string ""
- Ak nie je jasný rod pri podstatnom mene, odhadni podľa koncovky (napr. -a = f, -us = m, -um = n)
- Ak nie je jasný genitív, nechaj prázdny string
- Vráť LEN platný JSON, žiadny markdown ani iný text"""

        # Volanie Claude API (Sonnet 4.6)
        try:
            response = anthropic_client().messages.create(
                model="claude-sonnet-4-6",
                max_tokens=8192,
                temperature=0.1,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": image_data
                                }
                            },
                            {"type": "text", "text": prompt}
                        ]
                    }
                ]
            )
        except anthropic.APIError as e:
            print(f"Claude API Error (vocab): {str(e)}")
            return jsonify({
                'error': f'Chyba pri volaní Claude API: {str(e)}'
            }), 400

        result = parse_ai_response(response)
        validate_tests({'title': 'AI import', 'testType': 'vocabulary', 'vocabulary': result.get('vocabulary')})

        return jsonify({
            'success': True,
            'data': result
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.post('/api/save-test')
def save_test():
    data = json_object()
    if not isinstance(data.get('testName'), str):
        raise StoreError('Chýba názov súboru.')
    return jsonify(store().save(data['testName'], data.get('testData'), data.get('mode', 'new'), data.get('version')))


@app.get('/api/load-test/<filename>')
def load_test(filename):
    if not session.get('admin'):
        abort(401)
    return jsonify(store().load(filename))


@app.post('/api/update-test/<filename>')
def update_test(filename):
    data = json_object()
    return jsonify(store().update(filename, data.get('data'), data.get('version')))


@app.delete('/api/delete-test/<filename>')
def delete_test(filename):
    return jsonify(store().delete(filename, json_object().get('version')))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
