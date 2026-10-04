# LFUK tester

Inteligentná webová aplikácia na vytváranie a absolvovanie testov s podporou AI importu otázok z fotiek.

## Práca s AI

Otvorte tento projekt v Claude Code alebo Codexe a zadajte požadovanú zmenu. Kontext, KISS princíp, ochrana hotových testov, lokálne overovanie a hranica verejného nasadenia sú v [AGENTS.md](AGENTS.md). Technické detaily má riešiť AI; o termíne a mieste verejného nasadenia rozhoduje vlastník.

[CLAUDE.md](CLAUDE.md) používa skutočný import `@AGENTS.md`, aby sa udržiavala iba jedna sada pokynov. Používame štandardný názov veľkými písmenami, bez druhej kópie `claude.md`. Načítanie zodpovedá [dokumentácii Claude Code](https://code.claude.com/docs/en/memory#share-one-file-with-other-coding-tools) a [pokynom pre Codex](https://learn.chatgpt.com/docs/agent-configuration/agents-md). Pri inom AI nástroji bez podpory týchto súborov treba na AGENTS výslovne odkázať.

Pred každým commitom má AI skontrolovať a podľa zmeny aktualizovať príslušnú dokumentáciu, návod priamo na stránke, históriu zmien, verziu a súvisiace ukážky či konfiguráciu. Podrobný postup je v [AGENTS.md](AGENTS.md#pracovný-postup-a-odovzdanie); aktualizácie patria do rovnakého commitu ako zmena. Heslá a dočasné výpisy sa do dokumentácie neukladajú. [Mapa projektu](docs/STRUCTURE.md) opisuje aktuálne usporiadanie a kam ukladať nové súbory.

Nové podklady pred spracovaním a rozpracované veci vkladajte do [work/](work/README.md). Stačí tam nahrať súbory a zadať AI, čo s nimi spraviť. Pracovný obsah je mimo Gitu a Docker image; pri zálohe ho treba pribaliť.

## 🎯 Hlavné funkcie

- **🤖 AI Import z fotky** - Odfotíte otázky a AI ich automaticky rozpozná (Claude Sonnet 4.6 vision)
- **📸 Spracovanie viacerých fotiek** - Nahrajte až 5 fotiek naraz, automaticky sa spoja
- **🔄 Rotácia fotiek** - Jednoduché otočenie fotiek pred spracovaním
- **🔬 Pokročilé predspracovanie** - OpenCV algoritmy pre lepšie rozpoznávanie
- **📁 Import/Export testov** - JSON formát pre jednoduchú výmenu testov
- **🎓 Ročníky a predmety** - Najprv výber ročníka, potom predmetu; každý ročník má vlastné predmety
- **🧪 Biochémia v 2. ročníku** - 12 týždenných testov a test Na zaradenie, spolu 684 otázok
- **✅ Viacero správnych odpovedí** - Podpora otázok s viacerými správnymi odpoveďami
- **📊 Štatistiky a sledovanie pokroku** - Automatické sledovanie výsledkov
- **⏱️ Časové limity** - 20/30/60 minút alebo bez limitu
- **🎲 Mixovanie otázok** - Náhodné poradie pre lepšiu prípravu
- **📚 Režim učenia** - Prezeranie všetkých otázok so správnymi odpoveďami
- **🔄 Zlučovanie testov** - Absolvujte viac testov naraz
- **✏️ Editor testov** - Upravujte testy priamo v aplikácii

## Lokálne spustenie

Stačí Docker s Compose v2.24.4 alebo novším. Z koreňa projektu:

```bash
docker compose -p tester-local -f docker-compose.yml -f docker-compose.local.yml run --rm prepare
docker compose -p tester-local -f docker-compose.yml -f docker-compose.local.yml up -d --build --wait
```

Otvorte **http://test.localhost** na počítači, kde beží Docker. Záložná adresa je http://localhost:8080. Netreba upravovať `/etc/hosts`. Z iného počítača či mobilu adresa `.localhost` odkazuje na dané zariadenie, nie na server.

Príprava skopíruje chýbajúce JSON testy do `.local/testy/` a vytvorí `.env.local`. Existujúce lokálne súbory neprepisuje. Pôvodné `testy/` a `data/` zostávajú oddelené. Testy nie sú v Gite ani v image: na novom PC ich treba preniesť zo zálohy. Bez nich sa spustí prázdna aplikácia.

Absolvovanie testov je verejné. Pre import, editor a štatistiky návštev kliknite na **Správa testov**; heslo je hodnota `ADMIN_SECRET` v `.env.local`. Lokálne je platený AI import a Cloudflare analytika vypnutá. Na testovanie AI možno výslovne nastaviť lokálny kľúč a odstrániť príslušné prázdne prepísanie v lokálnom Compose.

Po zmene kódu zopakujte druhý príkaz. Verzia aplikácie je v súbore `VERSION`.

```bash
docker compose -p tester-local -f docker-compose.yml -f docker-compose.local.yml logs --tail 100 web
docker compose -p tester-local -f docker-compose.yml -f docker-compose.local.yml down
```

**Verejné nasadenie sa robí až na pokyn vlastníka.** Postup pre `test.frantisekmasiar.sk`, zálohy a presun na iný PC sú v [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). Samotné lokálne spustenie neaktivuje tunnel.

## Ochrana dát a overenie

- Import nikdy neprepisuje existujúci názov. Editor ukladá až tlačidlom **Uložiť zmeny**.
- Pred úpravou, pridaním otázok alebo odstránením vznikne presná záloha pôvodného súboru v `data/backups/` (lokálne `.local/data/backups/`).
- Ukladanie je atómové, chránené zámkom a kontrolou verzie. Staré otvorené okno nesmie prepísať novšiu zmenu.
- Zálohy sa automaticky nemažú. Je potrebná aj kópia mimo hostiteľského disku.

Automatické regresné testy používajú dočasné dáta v samostatnom kontajneri:

```bash
docker compose -p tester-checks -f docker-compose.test.yml run --build --rm tests
docker compose -p tester-checks -f docker-compose.test.yml run --rm tests pip-audit --cache-dir /tmp/pip-audit-cache
```

## Štruktúra

```text
app.py                     Flask endpointy, obrázky a analytika
storage.py                 JSON validácia, cache, zámky a zálohy
security.py                prihlásenie správcu, CSRF a limity
static/                    vanilla JS + CSS bez build stepu
templates/                 aplikácia, prihlásenie, dashboard
VERSION                    jediný zdroj verzie
testy/                     pôvodné JSON testy a ich archívy; mimo Gitu
data/                      eventy a zálohy; mimo Gitu
.local/                    samostatné lokálne dáta; mimo Gitu
tests/                     regresné testy API a úložiska
tools/prepare_local.py     príprava lokálneho prostredia
tools/imports/             ručné extrakcie a ich JSON konfigurácie
tools/out/, tools/pages/   pracovné výstupy; mimo Gitu
docs/                      prevádzka, zálohy a mapa projektu
examples/                  ukážkové JSON testy
work/                      nové podklady a rozpracované úlohy; obsah mimo Gitu
sources/                   zdrojové PDF/fotografie; mimo Gitu
archive/                   historické testy sledované Gitom
```

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
    "year": 2,
    "category": "Fyziológia",
    "questions": [...]
  }
]
```

**Pravidlá:**
- `year` určuje ročník (`1` alebo `2`). Ak chýba, test patrí do 1. ročníka — existujúce súbory netreba meniť. Platí aj pre slovíčkové testy.
- `category` je názov predmetu. Nový názov sa automaticky zobrazí ako predmet iba v príslušnom ročníku. Ak chýba, predmet sa odvodí z názvu testu/súboru.
- Pre nový predmet v 2. ročníku importujte test s `"year": 2` a napr. `"category": "Fyziológia"`. Ročník ostáva dostupný aj bez testov; počty a filter „Všetky“ sa vzťahujú na vybraný ročník.
- `correct` môže byť jedno číslo (jedna správna odpoveď) alebo pole čísel (viac správnych odpovedí)
- Index začína od 0 (0 = prvá odpoveď, 1 = druhá, atď.)
- Pri viacerých správnych odpovediach musia byť vybrané všetky správne odpovede
- Môžete nahrať jeden test alebo pole testov
- Pozrite si [examples/test.json](examples/test.json) pre príklad

## Použitie

### 🤖 AI Import otázok z fotky (Odporúčané)

1. Prihláste sa ako správca a kliknite na "🤖 AI Import"
2. Nahrajte fotku/fotky s otázkami (podporuje až 5 fotiek naraz)
3. Použijte tlačidlo ↷ pre otočenie fotky (stlačte 3x pre 270°)
4. Zapnite "Pokročilé predspracovanie" pre čiernobiele otázky
5. Kliknite "✨ Spracovať s AI"
6. Skontrolujte a upravte rozpoznané otázky
7. Uložte test

Fotky sa spracujú postupne a otázky sa spoja do jedného návrhu testu. Pred uložením skontrolujte ich obsah a správne odpovede.

### 📁 Import testov zo súborov

**Spôsob 1: Automatické načítanie z priečinka (odporúčané)**
1. Vložte nové JSON súbory do `.local/testy/` pri lokálnom skúšaní alebo do `testy/` pri nasadení. Existujúce súbory neprepisujte.
2. Prihláste sa ako správca a kliknite na "Import JSON"
3. Kliknite na "📂 Automaticky načítať"

**Spôsob 2: Manuálne nahratie súboru**
1. Prihláste sa ako správca a kliknite na "Import JSON"
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
