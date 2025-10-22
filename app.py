from flask import Flask, render_template, request, jsonify
import json
import os
import glob
import base64
import io
from openai import OpenAI
from dotenv import load_dotenv
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import cv2
import numpy as np

# Load environment variables
load_dotenv()

app = Flask(__name__)

# OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Ukladanie testov v pamäti
tests = []

# Cesta k priečinku s testami
TESTS_DIR = os.path.join(os.path.dirname(__file__), 'testy')

# Vytvoriť priečinok ak neexistuje
if not os.path.exists(TESTS_DIR):
    os.makedirs(TESTS_DIR)
    print(f"Vytvorený priečinok: {TESTS_DIR}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/tests', methods=['GET'])
def get_tests():
    """Vráti zoznam všetkých testov - automaticky načíta z priečinka testy/"""
    try:
        # Vymazať existujúce testy
        tests.clear()

        # Načítať všetky JSON súbory z priečinka
        json_files = glob.glob(os.path.join(TESTS_DIR, '*.json'))

        if json_files:
            for filepath in json_files:
                try:
                    filename = os.path.basename(filepath)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                        # Validácia formátu
                        if isinstance(data, list):
                            # Pridať filename k každému testu v array
                            for test in data:
                                test['filename'] = filename
                            tests.extend(data)
                        else:
                            # Pridať filename k testu
                            data['filename'] = filename
                            tests.append(data)
                except Exception as e:
                    print(f"Chyba pri načítaní {filename}: {str(e)}")

        return jsonify(tests)
    except Exception as e:
        print(f"Chyba pri načítaní testov: {str(e)}")
        return jsonify([])

@app.route('/api/import', methods=['POST'])
def import_tests():
    """Importuje testy zo súboru a uloží ich do priečinka testy/"""
    try:
        file = request.files.get('file')
        if not file:
            return jsonify({'error': 'Žiadny súbor'}), 400

        data = json.load(file)

        # Validácia formátu a uloženie do súborov
        saved_count = 0
        if isinstance(data, list):
            # Array testov
            for test in data:
                if 'title' in test:
                    filename = f"{test['title']}.json"
                    filepath = os.path.join(TESTS_DIR, filename)

                    # Uložiť test ako array (konzistentný formát)
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump([test], f, ensure_ascii=False, indent=2)
                    saved_count += 1
                    print(f"Uložený test: {test['title']}")
        else:
            # Jeden test
            if 'title' in data:
                filename = f"{data['title']}.json"
                filepath = os.path.join(TESTS_DIR, filename)

                # Uložiť test ako array (konzistentný formát)
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump([data], f, ensure_ascii=False, indent=2)
                saved_count += 1
                print(f"Uložený test: {data['title']}")

        return jsonify({'success': True, 'count': saved_count})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/clear', methods=['POST'])
def clear_tests():
    """Vymaže všetky testy"""
    tests.clear()
    return jsonify({'success': True})

@app.route('/api/load-from-folder', methods=['POST'])
def load_from_folder():
    """Načíta všetky testy z určeného priečinka"""
    try:
        # Získať cestu z requestu
        data = request.get_json()
        folder_path = data.get('folder', 'testy') if data else 'testy'

        # Ak je relatívna cesta, pridať k base dir
        if not os.path.isabs(folder_path):
            folder_path = os.path.join(os.path.dirname(__file__), folder_path)

        # Vymazať existujúce testy
        tests.clear()

        # Načítať všetky JSON súbory z priečinka
        if not os.path.exists(folder_path):
            return jsonify({'success': False, 'error': f'Priečinok "{folder_path}" neexistuje'}), 400

        json_files = glob.glob(os.path.join(folder_path, '*.json'))

        if not json_files:
            return jsonify({'success': True, 'count': 0, 'message': f'Žiadne JSON súbory v priečinku {folder_path}'})

        loaded_count = 0
        for filepath in json_files:
            try:
                filename = os.path.basename(filepath)
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                    # Validácia formátu
                    if isinstance(data, list):
                        # Pridať filename k každému testu v array
                        for test in data:
                            test['filename'] = filename
                        tests.extend(data)
                        loaded_count += len(data)
                    else:
                        # Pridať filename k testu
                        data['filename'] = filename
                        tests.append(data)
                        loaded_count += 1
            except Exception as e:
                print(f"Chyba pri načítaní {filepath}: {e}")

        return jsonify({
            'success': True,
            'count': loaded_count,
            'files': len(json_files),
            'message': f'Načítaných {loaded_count} testov z {len(json_files)} súborov'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/list-files', methods=['POST'])
def list_files():
    """Vráti zoznam JSON súborov v určenom priečinku"""
    try:
        # Získať cestu z requestu
        data = request.get_json()
        folder_path = data.get('folder', 'testy') if data else 'testy'

        # Ak je relatívna cesta, pridať k base dir
        if not os.path.isabs(folder_path):
            folder_path = os.path.join(os.path.dirname(__file__), folder_path)

        if not os.path.exists(folder_path):
            return jsonify({'files': [], 'error': f'Priečinok "{folder_path}" neexistuje'})

        json_files = glob.glob(os.path.join(folder_path, '*.json'))
        files = [os.path.basename(f) for f in json_files]

        return jsonify({'files': files, 'path': folder_path})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

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
def ai_import():
    """AI import otázok z obrázku pomocou OpenAI Vision API"""
    try:
        # Získať obrázok z requestu
        if 'image' not in request.files:
            return jsonify({'error': 'Žiadny obrázok'}), 400

        image_file = request.files['image']

        # Získať nastavenie pokročilého predspracovania
        advanced_preprocessing = request.form.get('advancedPreprocessing', 'false') == 'true'

        # Získať manuálnu rotáciu
        rotation = int(request.form.get('rotation', 0))

        # Uložiť pôvodný obrázok pre vytvorenie výrezov
        image_file.seek(0)
        original_image_bytes = image_file.read()
        image_file.seek(0)

        # Predspracovať obrázok pre AI
        image_file.seek(0)
        processed_image = preprocess_image(image_file, advanced=advanced_preprocessing, rotation=rotation)
        image_data = base64.b64encode(processed_image.read()).decode('utf-8')

        # Uložiť aj predspracovaný obrázok ako PIL Image pre výrezy
        image_file.seek(0)
        processed_pil = Image.open(preprocess_image(image_file, advanced=advanced_preprocessing, rotation=rotation))

        # Prompt pre OpenAI
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

        # Zavolať OpenAI Vision API
        # Použiť detail: "high" pre lepšiu detekciu pozícií
        try:
            response = client.chat.completions.create(
                model="gpt-4o",  # Najnovší model s najlepšou vision schopnosťou
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_data}",
                                    "detail": "high"  # Vysoké rozlíšenie pre presnejšiu detekciu
                                }
                            }
                        ]
                    }
                ],
                max_tokens=4096,
                temperature=0.1
            )
        except Exception as e:
            print(f"OpenAI API Error: {str(e)}")
            return jsonify({
                'error': f'Chyba pri volaní OpenAI API: {str(e)}'
            }), 400

        # Extrahovať JSON odpoveď
        ai_response = response.choices[0].message.content.strip()
        print(f"AI Response length: {len(ai_response)} chars")
        print(f"AI Response preview: {ai_response[:200]}")

        # Pokúsiť sa parsovať JSON (ak AI pridalo markdown bloky, odstránime ich)
        if '```json' in ai_response:
            # Nájsť JSON medzi ```json a ```
            start = ai_response.find('```json') + 7
            end = ai_response.find('```', start)
            ai_response = ai_response[start:end].strip()
        elif '```' in ai_response:
            # Nájsť JSON medzi ``` a ```
            parts = ai_response.split('```')
            if len(parts) >= 2:
                ai_response = parts[1].strip()
                if ai_response.startswith('json'):
                    ai_response = ai_response[4:].strip()

        # Odstrániť možné úvodné/záverečné znaky
        ai_response = ai_response.strip()

        # Parsovať JSON
        try:
            result = json.loads(ai_response)
        except json.JSONDecodeError as e:
            # Logovať pre debugging
            print(f"JSON Parse Error: {e}")
            print(f"AI Response: {ai_response[:500]}")  # Prvých 500 znakov
            return jsonify({
                'error': f'Chyba pri parsovaní AI odpovede: {str(e)}',
                'raw_response': ai_response[:200]  # Prvých 200 znakov pre užívateľa
            }), 400

        # Vytvoriť výrezy pre každú otázku
        num_questions = len(result.get('questions', []))

        if num_questions > 0:
            img_width, img_height = processed_pil.size
            questions = result.get('questions', [])

            # Skontrolovať či AI poskytlo pozície
            has_positions = all('positionPercent' in q for q in questions)

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

@app.route('/api/save-test', methods=['POST'])
def save_test():
    """Uloží test do JSON súboru v priečinku testy/"""
    try:
        data = request.get_json()

        test_name = data.get('testName')
        test_data = data.get('testData')
        mode = data.get('mode', 'new')  # 'new' alebo 'append'

        if not test_name or not test_data:
            return jsonify({'error': 'Chýbajúce údaje'}), 400

        # Vytvorenie cesty k súboru
        filename = f"{test_name}.json"
        filepath = os.path.join(TESTS_DIR, filename)

        if mode == 'append' and os.path.exists(filepath):
            # Pridať k existujúcemu testu
            with open(filepath, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)

            # Ak je existujúci súbor array, pridať otázky do prvého testu
            if isinstance(existing_data, list) and len(existing_data) > 0:
                existing_data[0]['questions'].extend(test_data['questions'])
                print(f"Pridané {len(test_data['questions'])} otázok do testu: {existing_data[0].get('title')}")
            else:
                # Ak je objekt, pridať otázky priamo
                if 'questions' in existing_data:
                    existing_data['questions'].extend(test_data['questions'])
                    print(f"Pridané {len(test_data['questions'])} otázok do testu: {existing_data.get('title')}")
                else:
                    # Chybný formát - vytvoriť ako nový
                    print("Chybný formát existujúceho testu, vytvorím nový")
                    existing_data = [test_data]

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2)
        else:
            # Vytvoriť nový test (ako array s jedným testom)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump([test_data], f, ensure_ascii=False, indent=2)

        return jsonify({
            'success': True,
            'filename': filename,
            'filepath': filepath
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/load-test/<filename>', methods=['GET'])
def load_test(filename):
    """Načíta test súbor pre editáciu"""
    try:
        filepath = os.path.join(TESTS_DIR, filename)

        if not os.path.exists(filepath):
            return jsonify({'error': 'Súbor neexistuje'}), 404

        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return jsonify({
            'success': True,
            'filename': filename,
            'data': data
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/update-test/<filename>', methods=['POST'])
def update_test(filename):
    """Aktualizuje existujúci test súbor"""
    try:
        filepath = os.path.join(TESTS_DIR, filename)

        if not os.path.exists(filepath):
            return jsonify({'error': 'Súbor neexistuje'}), 404

        data = request.get_json()
        test_data = data.get('data')

        if not test_data:
            return jsonify({'error': 'Chýbajúce údaje'}), 400

        # Získať nový názov testu (z prvého testu v array alebo priamo z objektu)
        if isinstance(test_data, list) and len(test_data) > 0:
            new_test_title = test_data[0].get('title', '')
        else:
            new_test_title = test_data.get('title', '')

        # Vytvoriť nový názov súboru na základe názvu testu
        new_filename = f"{new_test_title}.json"
        new_filepath = os.path.join(TESTS_DIR, new_filename)

        # Uložiť aktualizovaný test
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(test_data, f, ensure_ascii=False, indent=2)

        # Ak sa zmenil názov súboru, premenovať
        if filename != new_filename and new_test_title:
            if os.path.exists(new_filepath) and new_filepath != filepath:
                # Súbor s novým názvom už existuje
                return jsonify({'error': f'Test s názvom "{new_test_title}" už existuje'}), 400

            os.rename(filepath, new_filepath)
            print(f"Test premenovaný: {filename} → {new_filename}")
            return jsonify({
                'success': True,
                'filename': new_filename,
                'renamed': True
            })

        return jsonify({
            'success': True,
            'filename': filename
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/delete-test/<filename>', methods=['DELETE'])
def delete_test(filename):
    """Zmaže test súbor"""
    try:
        filepath = os.path.join(TESTS_DIR, filename)

        if not os.path.exists(filepath):
            return jsonify({'error': 'Súbor neexistuje'}), 404

        os.remove(filepath)

        return jsonify({
            'success': True,
            'message': f'Test {filename} bol zmazaný'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
