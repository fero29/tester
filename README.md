# AI Tester v1.3.14

Inteligentná webová aplikácia na vytváranie a absolvovanie testov s podporou AI importu otázok z fotiek.

## 🎯 Hlavné funkcie

- **🤖 AI Import z fotky** - Odfotíte otázky a AI ich automaticky rozpozná (OpenAI GPT-4 Vision)
- **📸 Spracovanie viacerých fotiek** - Nahrajte až 5 fotiek naraz, automaticky sa spoja
- **🔄 Rotácia fotiek** - Jednoduché otočenie fotiek pred spracovaním
- **🔬 Pokročilé predspracovanie** - OpenCV algoritmy pre lepšie rozpoznávanie
- **📁 Import/Export testov** - JSON formát pre jednoduchú výmenu testov
- **✅ Viacero správnych odpovedí** - Podpora otázok s viacerými správnymi odpoveďami
- **📊 Štatistiky a sledovanie pokroku** - Automatické sledovanie výsledkov
- **⏱️ Časové limity** - 20/30/60 minút alebo bez limitu
- **🎲 Mixovanie otázok** - Náhodné poradie pre lepšiu prípravu
- **📚 Režim učenia** - Prezeranie všetkých otázok so správnymi odpoveďami
- **🔄 Zlučovanie testov** - Absolvujte viac testov naraz
- **✏️ Editor testov** - Upravujte testy priamo v aplikácii

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

### 🤖 AI Import otázok z fotky (Odporúčané)

1. Kliknite na "🤖 AI Import" v hlavnom menu
2. Nahrajte fotku/fotky s otázkami (podporuje až 5 fotiek naraz)
3. Použijte tlačidlo ↷ pre otočenie fotky (stlačte 3x pre 270°)
4. Zapnite "Pokročilé predspracovanie" pre čiernobiele otázky
5. Kliknite "✨ Spracovať s AI"
6. Skontrolujte a upravte rozpoznané otázky
7. Uložte test

**Tip:** Viacero fotiek sa automaticky spoja do jednej a spracujú naraz. Fotky sa prispôsobia OpenAI API limitom (max 2048px).

### 📁 Import testov zo súborov

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
