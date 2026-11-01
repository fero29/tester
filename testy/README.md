# Priečinok pre testy

Do tohto priečinka vložte vlastné JSON súbory s testami.

## Ako pridať testy

1. Vytvorte JSON súbor (napr. `moje_testy.json`) v tomto priečinku
2. V aplikácii kliknite na "📁 Import testov"
3. Kliknite na "📂 Automaticky načítať"
4. Všetky JSON súbory z tohto priečinka sa načítajú

## Formát súboru

```json
[
  {
    "title": "Názov testu",
    "description": "Popis testu",
    "questions": [
      {
        "question": "Otázka?",
        "answers": ["Odpoveď 1", "Odpoveď 2", "Odpoveď 3"],
        "correct": 0
      }
    ]
  }
]
```

Pre viac informácií o formáte pozrite `example_test.json` v hlavnom priečinku projektu.
