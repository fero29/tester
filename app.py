from flask import Flask, render_template, request, jsonify
import json
import os
import glob

app = Flask(__name__)

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
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                    # Validácia formátu
                    if isinstance(data, list):
                        tests.extend(data)
                        loaded_count += len(data)
                    else:
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
