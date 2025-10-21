# Testovacia aplikácia

Jednoduchá webová aplikácia na vytváranie a absolvovanie testov.

## Funkcie

- Import testov zo JSON súboru
- Absolvovanie testov s možnosťou vrátiť sa k predchádzajúcim otázkam
- Zobrazenie výsledkov
- Žiadna databáza, všetko v pamäti (reštartom sa vymaže)
- Bez používateľov a prihlásenia

## Spustenie v Dockeri

```bash
docker-compose up --build
```

Aplikácia bude dostupná na: http://localhost:5000

## Formát JSON súboru

### Otázka s jednou správnou odpoveďou:
```json
{
  "question": "Text otázky?",
  "answers": [
    "Odpoveď 1",
    "Odpoveď 2",
    "Odpoveď 3",
    "Odpoveď 4"
  ],
  "correct": 0
}
```

### Otázka s viacerými správnymi odpoveďami:
```json
{
  "question": "Text otázky s viacerými odpoveďami?",
  "answers": [
    "Odpoveď 1",
    "Odpoveď 2",
    "Odpoveď 3",
    "Odpoveď 4"
  ],
  "correct": [0, 2]
}
```

### Celý test:
```json
[
  {
    "title": "Názov testu",
    "description": "Popis testu",
    "questions": [...]
  }
]
```

**Pravidlá:**
- `correct` môže byť jedno číslo (jedna správna odpoveď) alebo pole čísel (viac správnych odpovedí)
- Index začína od 0 (0 = prvá odpoveď, 1 = druhá, atď.)
- Pri viacerých správnych odpovediach musia byť vybrané všetky správne odpovede
- Môžete nahrať jeden test alebo pole testov
- Pozrite si `example_test.json` pre príklad

## Použitie

### Načítanie testov

**Spôsob 1: Automatické načítanie z priečinka (odporúčané)**
1. Vložte JSON súbory s testami do priečinka `testy/`
2. V aplikácii kliknite na "📁 Import testov"
3. Kliknite na "📂 Automaticky načítať"

**Spôsob 2: Manuálne nahratie súboru**
1. Kliknite na "📁 Import testov"
2. Vyberte JSON súbor z vášho počítača
3. Kliknite na "📤 Nahrať súbor"

### Absolvovanie testu

1. Vyberte test zo zoznamu (zobrazí sa dialóg s nastaveniami)
2. Nastavte parametre (čas, rozsah otázok, mixáž)
3. Kliknite na "Spustiť test" alebo "Režim učenia"
4. Absolvujte test a pozrite si výsledky

### Ďalšie funkcie

- **Spustenie viacerých testov:** Zaškrtnite checkboxy pri testoch a kliknite "Spustiť vybrané testy"
- **Štatistiky:** Pri každom teste sa zobrazujú štatistiky (absolvované, posledný výsledok, priemer)
- **Režim učenia:** Zobrazí celý test so správnymi odpoveďami

## Ukončenie

```bash
docker-compose down
```
