#!/usr/bin/env python3
import base64
import json
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Načítať obrázok
with open('/home/fmasiar/20251020_223506.jpg', 'rb') as f:
    image_data = base64.b64encode(f.read()).decode('utf-8')

print('Posielam request do OpenAI...')

prompt = """Analyzuj tento obrázok a extrahuj z neho všetky otázky s možnými odpoveďami.

Vráť odpoveď v tomto PRESNOM JSON formáte:
{
  "suggestedTitle": "Navrhnutý názov testu (krátky, opisný)",
  "suggestedDescription": "Krátky popis testu",
  "questions": [
    {
      "question": "Text otázky",
      "answers": ["odpoveď 1", "odpoveď 2", "odpoveď 3", "odpoveď 4"],
      "correct": 0
    }
  ]
}

DÔLEŽITÉ:
- "correct" je index správnej odpovede (0-based, takže 0 = prvá odpoveď, 1 = druhá atď.)
- Ak je správna odpoveď označená (napr. podčiarknutá, zvýraznená), použi jej index
- Ak nie je označená, použi 0 a užívateľ to opraví manuálne
- Answers musia byť presne 4 (ak sú menej, doplň prázdne reťazce)
- Vráť IBA čistý JSON, žiadny iný text

Analyzuj obrázok a vráť JSON:"""

response = client.chat.completions.create(
    model='gpt-4o',
    messages=[
        {
            'role': 'user',
            'content': [
                {'type': 'text', 'text': prompt},
                {
                    'type': 'image_url',
                    'image_url': {
                        'url': f'data:image/jpeg;base64,{image_data}'
                    }
                }
            ]
        }
    ],
    max_tokens=4096,
    temperature=0.1
)

ai_response = response.choices[0].message.content.strip()
print('AI odpoveď (prvých 500 znakov):')
print(ai_response[:500])
print('...\n')

# Pokus o parsovanie
if '```json' in ai_response:
    start = ai_response.find('```json') + 7
    end = ai_response.find('```', start)
    ai_response = ai_response[start:end].strip()
elif '```' in ai_response:
    parts = ai_response.split('```')
    if len(parts) >= 2:
        ai_response = parts[1].strip()
        if ai_response.startswith('json'):
            ai_response = ai_response[4:].strip()

try:
    result = json.loads(ai_response.strip())
    print(f'Úspešne parsované! Počet otázok: {len(result["questions"])}')
    print(f'Názov: {result["suggestedTitle"]}')
    print(f'Popis: {result["suggestedDescription"]}')
    print('\nPrvá otázka:')
    print(f'  {result["questions"][0]["question"]}')
    for i, ans in enumerate(result["questions"][0]["answers"]):
        correct = " ✓" if i == result["questions"][0]["correct"] else ""
        print(f'    {i+1}. {ans}{correct}')
except json.JSONDecodeError as e:
    print(f'CHYBA pri parsovaní: {e}')
    print(f'Parsovaný text (prvých 200 znakov): {ai_response[:200]}')
