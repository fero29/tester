from flask import Flask, render_template, request, jsonify
import json
import os
import glob
import base64
import io
from openai import OpenAI
from dotenv import load_dotenv
from PIL import Image, ImageEnhance, ImageFilter

# Load environment variables
load_dotenv()

app = Flask(__name__)

# OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Ukladanie testov v pamäti
tests = []

# Cesta k priečinku s testami
TESTS_DIR = os.path.join(os.path.dirname(__file__), 'testy')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/tests', methods=['GET'])
def get_tests():
    """Vráti zoznam všetkých testov"""
    return jsonify(tests)

@app.route('/api/import', methods=['POST'])
def import_tests():
    """Importuje testy zo súboru"""
    try:
        file = request.files.get('file')
        if not file:
            return jsonify({'error': 'Žiadny súbor'}), 400

        data = json.load(file)

        # Validácia formátu
        if isinstance(data, list):
            tests.extend(data)
        else:
            tests.append(data)

        return jsonify({'success': True, 'count': len(tests)})
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

def preprocess_image(image_file):
    """Predspracuje obrázok pre lepšie rozpoznávanie AI"""
    # Načítať obrázok
    img = Image.open(image_file)

    # Konverzia na RGB (ak je RGBA alebo iný formát)
    if img.mode != 'RGB':
        img = img.convert('RGB')

    # Zväčšenie rozlíšenia ak je príliš malé (zachová pomer strán)
    max_size = 2048
    if max(img.size) < max_size:
        ratio = max_size / max(img.size)
        new_size = tuple(int(dim * ratio) for dim in img.size)
        img = img.resize(new_size, Image.LANCZOS)

    # Ak je príliš veľké, zmenši (ušetríme API náklady)
    max_size_limit = 3000
    if max(img.size) > max_size_limit:
        ratio = max_size_limit / max(img.size)
        new_size = tuple(int(dim * ratio) for dim in img.size)
        img = img.resize(new_size, Image.LANCZOS)

    # Zvýšenie ostrosti - pomôže rozpoznať kruhy a podčiarknutia
    img = img.filter(ImageFilter.SHARPEN)

    # Zvýšenie kontrastu - lepšie sa odlíšia označenia
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.3)

    # Zvýšenie jasu ak je obrázok tmavý
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

        # Predspracovať obrázok
        processed_image = preprocess_image(image_file)
        image_data = base64.b64encode(processed_image.read()).decode('utf-8')

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
4. Ak napríklad sú zakrúžkované odpovede A a C, výsledok musí byť: "correct": [0, 2]
5. Ak sú zakrúžkované odpovede B, C a D, výsledok musí byť: "correct": [1, 2, 3]
6. Ak nie je zakrúžkovaná ŽIADNA odpoveď, použi [0] (prvú)

⚠️ ČASTÁ CHYBA: Neuvádzaj len jednu správnu odpoveď ak vidíš viac zakrúžkovaných!

PRÍKLAD:
Ak otázka má odpovede A, B, C, D a vidíš že sú zakrúžkované A aj C:
✓ SPRÁVNE: "correct": [0, 2]
✗ NESPRÁVNE: "correct": [0]

Vráť odpoveď v tomto PRESNOM JSON formáte:
{
  "suggestedTitle": "Navrhnutý názov testu",
  "suggestedDescription": "Krátky popis",
  "questions": [
    {
      "question": "Text otázky",
      "answers": ["odpoveď 1", "odpoveď 2", "odpoveď 3", "odpoveď 4"],
      "correct": [0, 2]
    }
  ]
}

FORMÁT:
- "correct" je ARRAY indexov (0=prvá, 1=druhá, 2=tretia, 3=štvrtá)
- Answers musia byť presne 4 (ak je menej, doplň "")
- Vráť IBA čistý JSON

Analyzuj obrázok a vráť JSON:"""

        # Zavolať OpenAI Vision API
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=4096,
            temperature=0.1
        )

        # Extrahovať JSON odpoveď
        ai_response = response.choices[0].message.content.strip()

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

            # Ak je existujúci súbor array
            if isinstance(existing_data, list):
                # Nájsť test s rovnakým názvom
                found = False
                for test in existing_data:
                    if test.get('title') == test_data.get('title'):
                        test['questions'].extend(test_data['questions'])
                        found = True
                        break
                if not found:
                    existing_data.append(test_data)
            else:
                # Ak je objekt, pridať otázky
                if existing_data.get('title') == test_data.get('title'):
                    existing_data['questions'].extend(test_data['questions'])
                else:
                    # Vytvoriť array
                    existing_data = [existing_data, test_data]

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

        # Uložiť aktualizovaný test
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(test_data, f, ensure_ascii=False, indent=2)

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
