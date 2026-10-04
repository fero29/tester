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
- **🧪 Biochémia v 2. ročníku** - 12 týždenných testov a test Na zaradenie, spolu 699 otázok
- **✅ Viacero správnych odpovedí** - Podpora otázok s viacerými správnymi odpoveďami
- **📊 Štatistiky a učenie** - Samostatné voľby pre započítanie výsledku a plánovanie opakovania
- **⏱️ Časové limity** - 20/30/60 minút alebo bez limitu
- **🎲 Nastaviteľný test** - Predvoľby Učenie/Tréning/Skúška, nezávislé miešanie otázok a odpovedí
- **📚 Pomoc pri učení** - Postupné nápovedy a vysvetlenia z overeného JSON; samostatný Prehľad učiva
- **🔄 Zlučovanie testov** - Absolvujte viac testov naraz
- **✏️ Editor testov** - Upravujte testy priamo v aplikácii

## Lokálne spustenie

Stačí Docker s Compose v2.24.4 alebo novším a Bash (Linux, macOS alebo WSL2). Z koreňa projektu:

```bash
./tools/manage.sh local up
```

Otvorte **http://test.localhost** na počítači, kde beží Docker. Záložná adresa je http://localhost:8080. Netreba upravovať `/etc/hosts`. Z iného počítača či mobilu adresa `.localhost` odkazuje na dané zariadenie, nie na server.

Príprava skopíruje chýbajúce JSON testy do `.local/testy/` a vytvorí `.env.local`. Existujúce lokálne súbory neprepisuje. Pôvodné `testy/` a `data/` zostávajú oddelené. Testy nie sú v Gite ani v image: na novom PC ich treba preniesť zo zálohy. Bez nich sa spustí prázdna aplikácia.

Absolvovanie testov je verejné. Pre import, editor a štatistiky návštev kliknite hore na tlačidlo **Správa testov** a prihláste sa; heslo je hodnota `ADMIN_SECRET` v `.env.local`. Po prihlásení sa pri testoch zobrazí tlačidlo **✏️ Upraviť** a hore ovládanie importu a odhlásenia. Lokálne je platený AI import a Cloudflare analytika vypnutá. Na testovanie AI možno výslovne nastaviť lokálny kľúč a odstrániť príslušné prázdne prepísanie v lokálnom Compose.

Po zmene kódu zopakujte `./tools/manage.sh local up`. Skript pripraví chýbajúce lokálne dáta, zostaví image a počká na zdravý web. Verzia aplikácie je v súbore `VERSION`.

```bash
./tools/manage.sh local status
./tools/manage.sh local down
```

`down` odstráni kontajnery a ich sieť, zachová testy, konfiguráciu aj zálohy. Na hostiteľovi sa neupravuje DNS, `/etc/hosts` ani systémové služby. Skript automaticky použije UID/GID aktuálneho používateľa; spúšťajte ho ako bežný používateľ s prístupom k Dockeru.

| Režim | Spustenie | Dostupnosť | Dáta / heslo správcu |
| --- | --- | --- | --- |
| Tento PC | `./tools/manage.sh local up` | `http://test.localhost`, iba tento PC | `.local/testy`, `.local/data`, `.env.local` |
| Lokálna sieť | `./tools/manage.sh lan up` | `http://IP-počítača:8081`, aj iné zariadenia | `.local/lan/testy`, `.local/lan/data`, `.env.lan` |
| Verejný web | `./tools/manage.sh public up` | `https://test.frantisekmasiar.sk` cez Cloudflare | `testy`, `data`, `.env` |

Pre každý režim fungujú aj `status` a `down`. LAN má vlastné kópie testov a prihlásenie, AI a tunnel sú vypnuté. Vyžaduje dostupný port v sieti/firewalle; predvolene počúva na všetkých IPv4 rozhraniach. Voliteľne obmedzte adresu a port, napríklad `LAN_BIND_ADDRESS=192.168.1.10 LAN_PORT=8081 ./tools/manage.sh lan up`. Na inom zariadení použite IP servera, nie `test.localhost`. Zmeny testov sa medzi režimami automaticky nesynchronizujú.

**Verejné nasadenie sa robí až na pokyn vlastníka.** Pripravené sú aj príkazy `./tools/manage.sh public up`, `public status` a `public down`. Pri presune na iný PC preneste projekt, testy, dáta a súkromnú `.env`; nastavenie existujúcej domény zostáva v Cloudflare. Prvé nastavenie tunela, zálohy a presun sú v [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). Samotné lokálne spustenie neaktivuje tunnel.

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

Otázkový priebeh a mobilné svetlé/tmavé zobrazenie kontroluje aj `node tests/browser_practice.cjs` proti bežiacemu lokálnemu Docker prostrediu na `test.localhost`. Táto voliteľná vývojová kontrola vyžaduje Node ≥18, modul `ws` a Google Chrome (alebo `CHROME_BIN`). Používa dočasný profil; otázky pridáva iba do pamäte prehliadača, katalóg nemení. Snímky a výsledok uloží do vypísaného adresára v `/tmp`.

## Štruktúra

```text
app.py                     Flask endpointy, obrázky a analytika
storage.py                 JSON validácia, cache, zámky a zálohy
security.py                prihlásenie správcu, CSRF a limity
static/                    app.js (katalóg/editor/slovíčka), practice.js (otázkový test), CSS
templates/                 aplikácia, prihlásenie, dashboard
VERSION                    jediný zdroj verzie
testy/                     pôvodné JSON testy a ich archívy; mimo Gitu
data/                      eventy a zálohy; mimo Gitu
.local/                    samostatné lokálne dáta; mimo Gitu
tests/                     regresné testy API a úložiska
tools/prepare_local.py     príprava lokálneho prostredia
tools/manage.sh            správa nasadenia na PC, v LAN a verejne
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

1. Vyberte test alebo zlúčte viac otázkových testov.
2. Použite predvoľbu **Učenie**, **Tréning** alebo **Skúška**, prípadne nastavte všetky voľby samostatne. Nastavenia si prehliadač pamätá.
3. Nastavte výber otázok, miešanie otázok/odpovedí, čas, nápovedy, okamih vyhodnotenia, vysvetlenia a opakovanie.
4. Osobitne zvoľte **Započítať výsledok do štatistík** a **Použiť odpovede na plánovanie učenia**. Potom kliknite **Spustiť**.
5. Po vyhodnotení už odpoveď nemožno meniť. „Žiadna z možností“ je výslovná odpoveď; „Neviem / preskočiť“ a odkryté riešenie sa počítajú ako neúspešný pokus.

Predvoľba Učenie zapína pomoc, automatické vysvetlenia a opakovanie, vypína štatistiky a čas. Tréning má spätnú väzbu po otázke, Skúška až na konci a limit 20 minút. Všetky nastavenia zostávajú upraviteľné. Vysvetlenie sa nikdy nezobrazí pred vyhodnotením, okrem výslovného odkrytia riešenia pri povolenej pomoci.

**Štatistiky** uchovávajú posledných 200 výsledkov v `localStorage` tohto prehliadača a originu. Nový výsledok obsahuje aj nastavenia, počet otázok s použitou pomocou a samostatne správne odpovede. Priemer zahŕňa všetky započítané pokusy; počet pokusov s pomocou je pri teste označený. Opakovanie nikdy neprepíše prvý výsledok ani nepridá ďalšie absolvovanie.

**Plán učenia** je oddelený (`learningProgress`). Aktualizuje sa po prvom odovzdaní, aj keď sú štatistiky vypnuté. Chyby a asistované odpovede sú hneď dostupné vo výbere **Otázky na zopakovanie**. Samostatné úspechy plánujú ďalší pokus o 1, 3, 7, 14 alebo 30 dní; interval sa predlžuje až pri úspechu s odstupom aspoň 20 hodín. Opakovanie v rámci toho istého testu tento interval nezvyšuje. Ide o jednoduché pravidlá plánovania, nie hodnotenie pripravenosti na skúšku. Predčasne opustený neodovzdaný test sa neuloží. Dáta sa medzi zariadeniami automaticky nesynchronizujú. Vymazanie štatistík nemaže plán učenia.

**Nápovedy a vysvetlenia** sa čítajú z voliteľného poľa `learning`. Aplikácia ich nevytvára za behu; existujúce otázky bez nich fungujú a ukazujú dostupnosť obsahu. Zobrazuje sa iba `status: "reviewed"`; `draft` slúži na kontrolu. Pôvodné vysvetlenia v zátvorkách pravda/nepravda zostávajú podporované.

```json
{
  "id": "ukazka-001",
  "question": "Ktoré číslo je párne?",
  "answers": ["2", "3"],
  "correct": [0],
  "learning": {
    "status": "draft",
    "hints": ["Pripomeňte si deliteľnosť dvoma.", "Pri delení nesmie zostať zvyšok."],
    "explanation": {
      "summary": "Párne číslo je deliteľné dvoma bez zvyšku.",
      "byAnswer": ["2 je deliteľné dvoma.", "Pri delení 3 dvoma zostane zvyšok 1."],
      "memoryTip": "Pár znamená dvojicu.",
      "sources": []
    }
  }
}
```

`hints` má ľubovoľný počet postupných úrovní. `byAnswer`, ak je prítomné, musí mať rovnaký počet položiek a poradie ako `answers`; pri miešaní sa presúvajú spolu. `sources` je zoznam objektov `title` a `url` (HTTP/HTTPS). Neznáme metadáta sa zachovávajú. Editor pri zmene otázky, možností alebo správneho kľúča vráti pomôcku do `draft`; jej novú odbornú kontrolu a doplnenie treba vykonať v JSON. ID je voliteľné; pokrok používa ID spolu s obsahovou revíziou, pri starých otázkach samotný pôvodný obsah. Miešanie a zlúčenie testov kľúč nemení, oprava obsahu vytvorí nový záznam. Pôvodné testy sa kvôli tomu automaticky neupravujú.

### Ďalšie funkcie

- **Spustenie viacerých testov:** Zaškrtnite checkboxy pri testoch a kliknite "Spustiť vybrané testy"
- **Štatistiky:** Pri každom teste sa zobrazujú štatistiky (absolvované, posledný výsledok, priemer)
- **Prehľad učiva:** Zobrazí celý otázkový test so správnymi odpoveďami bez ukladania výsledku alebo pokroku
