# Usporiadanie projektu

Toto je aktuálny stav po reorganizácii. Spustenie a použitie sú v [README](../README.md), ochrana dát a pracovný postup v [AGENTS](../AGENTS.md), zálohy a nasadenie v [DEPLOYMENT](DEPLOYMENT.md).

## Strom

Koreň obsahuje malú aplikáciu a jej spustenie. Podklady, historické kópie a ručné importy sú oddelené podľa účelu. Interné adresáre nástrojov a cache sú v prehľade vynechané.

```text
tester/
├── README.md                  vstup pre človeka, spustenie a používanie
├── AGENTS.md                  spoločné pravidlá a kontext pre AI
├── CLAUDE.md                  import AGENTS.md
├── Dockerfile
├── docker-compose.yml
├── docker-compose.local.yml
├── docker-compose.test.yml
├── requirements.txt
├── requirements-dev.txt
├── VERSION
├── .dockerignore
├── .gitignore
├── .env.example
├── .env                       súkromná produkčná konfigurácia, mimo Gitu
├── .env.local                 súkromná lokálna konfigurácia, mimo Gitu
├── app.py                     endpointy a AI
├── storage.py                 JSON úložisko
├── security.py                prihlásenie a ochrana požiadaviek
├── static/                    JS a CSS
├── templates/                 HTML
├── tests/                     technické regresné kontroly
├── testy/                     hotové používateľské testy; zachovať aj podadresáre
├── data/                      eventy a automatické zálohy
├── .local/                    oddelené lokálne testovanie
├── docs/
│   ├── DEPLOYMENT.md           prevádzka, zálohy, presun PC
│   └── STRUCTURE.md            mapa projektu a pravidlá umiestňovania
├── examples/
│   └── test.json               ukážkový test
├── tools/
│   ├── prepare_local.py        bežná príprava lokálneho prostredia
│   ├── imports/               ručné extrakčné skripty aj ich JSON konfigurácie
│   ├── out/                   pracovné výsledky, mimo Gitu
│   └── pages/                 dočasné obrázky strán, mimo Gitu
├── sources/                   vstupné materiály, mimo Gitu; zálohovať samostatne
│   ├── *.pdf
│   └── foto histo/
└── archive/                   historické kópie zachované aj v Gite
    ├── tests-aws/
    └── tests-clean/
```

## Kam patria nové súbory

| Obsah | Umiestnenie | Git |
| --- | --- | --- |
| Kód aplikácie | tri Python moduly, `static/`, `templates/` | áno |
| Technické kontroly | `tests/` | áno |
| Používateľské testy | `testy/`, pri lokálnom skúšaní `.local/testy/` | nie |
| Eventy a automatické zálohy zápisov | `data/`, lokálne `.local/data/` | nie |
| PDF a fotografie | `sources/` | nie; samostatne zálohovať |
| Historické testy z pôvodných záloh | `archive/` | áno; nie sú aktívny katalóg |
| Ručné extrakcie a ich pravidlá | `tools/imports/` | áno |
| Vygenerované medzivýsledky | `tools/out/`, `tools/pages/` | nie |
| Návody | `docs/`, úvodné informácie v README | áno |
| Ukážkové vstupy | `examples/` | áno |
| Návratové zálohy pracovného projektu | `.local/backups/` | nie; môžu obsahovať tajomstvá |

`testy/` je učivo, `tests/` kontroluje program. Aplikácia načítava priamo `testy/*.json`; hotové testy nepresúvať do ročníkových podadresárov. Ročník a predmet určujú JSON metadáta. Podadresáre pod `testy/` obsahujú zachované podklady, reporty a staršie verzie, nie ďalšie aktívne testy.

## Ručné nástroje

`tools/prepare_local.py` je súčasť bežného lokálneho spustenia cez Compose a zostáva na pôvodnej ceste. Ostatné skripty a tri konfiguračné JSON súbory sú v `tools/imports/`. Nie sú súčasťou produkčného image; testovací Docker stage ich zahŕňa pre regresné kontroly.

Skripty odvodzujú koreň od svojho umiestnenia, nie od aktuálneho pracovného adresára. JSON konfigurácie ležia vedľa príslušných skriptov. PDF sa hľadajú v `sources/`; názov `curriculumFile` v biochémii ostáva pôvodným názvom dokumentu, takže sa nemenia metadáta už vytvorených otázok. Obrázkové extrakcie dostávajú vstupný adresár ako argument, napríklad `sources/foto histo/`.

Pred spustením prečítať docstring konkrétneho skriptu. PDF nástroje vyžadujú Poppler, farebná extrakcia aj Pillow/NumPy, AI nástroje Anthropic SDK a kľúč. Niektoré skripty píšu nové testy alebo vykonávajú platené volania. Pri overovaní používať nový dočasný výstup. `test_ai.py` je ručný platený helper s povinnou cestou k JPEG obrázku; jeho import a `--help` API nevolajú.

## Záznam presunov

| Pôvodná cesta | Aktuálna cesta |
| --- | --- |
| `DEPLOYMENT.md` | `docs/DEPLOYMENT.md` |
| `example_test.json` | `examples/test.json` |
| PDF v koreni a `foto histo/` | `sources/` s pôvodnými názvami |
| `testy_backup_aws/` | `archive/tests-aws/` |
| `testy_backup_clean/` | `archive/tests-clean/` |
| `tools/*.py` okrem `prepare_local.py` | `tools/imports/` |
| `tools/biochemia1_*.json` | `tools/imports/` |

Pri migrácii sa nemení obsah hotových testov, PDF, fotografií ani historických kópií. Návratová záloha obsahuje pôvodný pracovný strom aj `.git`; `moves.json` vedľa nej mapuje staré/nové cesty a SHA-256. Ďalšie úpravy dokumentácie a kódu ciest zachytáva Git. Obnovu archívu robiť do nového prázdneho adresára, nie cez novšie živé dáta.

## KISS

Tri Python moduly a Compose zostávajú v koreni; nevzniká ďalší balík, framework, databáza ani obal na spúšťanie. Pravidlá pre AI majú jeden zdroj v AGENTS a krátky CLAUDE import. Nové priečinky vytvárať podľa konkrétnej potreby, nie pre hypotetický rast. Upratovanie stromu nie je dôvod mazať učivo či zálohy.
