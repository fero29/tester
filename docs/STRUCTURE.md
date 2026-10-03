# Návrh jednoduchšieho stromu

**Stav: návrh, presuny ešte nie sú vykonané.** Aktuálne umiestnenie aplikácie opisuje [README](../README.md). Tento dokument nie je príkaz na automatickú migráciu pri ďalšej úlohe.

## Odporúčanie

Najväčší neporiadok v koreni tvoria vstupné PDF, fotografie a dve historické zálohy. Oddeliť ich podľa účelu prinesie viac než presúvať tri Python moduly do ďalšieho balíka. Aplikácia zostane malá: Flask, vanilla JS/CSS, JSON a Docker Compose.

Navrhovaný strom (vynechané interné adresáre nástrojov a cache):

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
│   └── STRUCTURE.md            tento návrh; po realizácii opis výsledného stavu
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

`testy/` a `tests/` majú rozdielny účel: prvé sú učivo, druhé kontrolujú program. Názvy ani dátové mounty teraz netreba meniť. Filtre ročníkov/predmetov sa riadia JSON metadátami; podadresáre podľa ročníkov by vyžadovali zmenu načítavania, ktoré dnes číta `testy/*.json`.

## Konkrétne presuny a súvisiace zmeny

| Dnes | Návrh | Čo upraviť spolu s presunom |
| --- | --- | --- |
| `DEPLOYMENT.md` | `docs/DEPLOYMENT.md` | odkazy v README/AGENTS a relatívny odkaz späť na README |
| `example_test.json` | `examples/test.json` | odkaz a ukážkové cesty v README |
| PDF priamo v koreni | `sources/` s pôvodnými názvami | cesty v importných skriptoch a ich konfiguráciách; zachovať aj Unicode názvy |
| `foto histo/` | `sources/foto histo/` | vstupné cesty extrakcie fotografií |
| `testy_backup_aws/` | `archive/tests-aws/` | odkazy v dokumentácii; zachovať obsah a sledovanie v Gite |
| `testy_backup_clean/` | `archive/tests-clean/` | rovnaký postup ako pri AWS archíve |
| `tools/*.py` okrem `prepare_local.py` | `tools/imports/` | výpočet koreňa projektu, cesty k `.env`, vstupom a výstupom, príklady spustenia |
| `tools/biochemia1_*.json` | vedľa skriptov v `tools/imports/` | odkazy na podklady a pevná cesta v `build_biochemia1_answer_review.py` |

Importné skripty dnes často počítajú koreň cez `Path(__file__).parent.parent`; po pridaní úrovne by ukazovali nesprávne. `build_biochemia1.py` navyše hľadá PDF priamo v koreni, `parse_quizlet_zl2.py` používa relatívnu cestu a JSON manifesty obsahujú cesty aj kontrolné súčty vstupov. Presun má zahŕňať tieto konkrétne opravy, bez vytvorenia všeobecného frameworku na konfiguráciu ciest.

Pri presune pridať `sources/` do `.gitignore`. `.dockerignore` je zoznam povolených súborov a materiály do image nepustí; po úprave skontrolovať, že to stále platí. Celý `archive/` neignorovať, pretože historické testy už sú sledované Gitom. Podadresáre vo vnútri `testy/` sa v tomto návrhu nepresúvajú.

## Poradie realizácie

1. **Dokumentácia a ukážka:** presunúť iba DEPLOYMENT a example JSON, opraviť odkazy. Bez zmeny runtime.
2. **Podklady a historické zálohy:** urobiť zálohu, inventár ciest a SHA-256; presunúť bez prepisu kolidujúcich názvov a overiť obsah. Upraviť cesty ich konzumentov v tom istom kroku. Git diff samotný nestačí, pretože podklady sú z veľkej časti ignorované.
3. **Ručné nástroje:** presunúť skripty spolu s JSON konfiguráciami, opraviť koreň a výstupné cesty. `tools/prepare_local.py`, `tools/out/` a `tools/pages/` ponechať na mieste, aby sa nemenilo bežné spustenie ani uložené medzivýsledky.
4. **Overenie:** kontrolné súčty všetkých presunutých podkladov a archívov musia sedieť; `testy/` a `data/` zostať nezmenené. Spustiť technické regresné kontroly a lokálny Compose. Importy overovať na dočasných výstupoch, bez hromadného spustenia plateného API. Skontrolovať aj prípravu čistého lokálneho prostredia a odkazy.
5. Aktualizovať mapu v AGENTS/README a tento dokument na skutočný výsledný stav. Verejné nasadenie je samostatná používateľom riadená vec.

## Čo zatiaľ nepridávať

- `src/`, `services/`, `repositories/` alebo viac balíkov len kvôli vzhľadu stromu. Tri Python moduly sú pri tomto rozsahu prehľadné.
- Ďalší Docker obal, Makefile alebo paralelný návod na spustenie. Existujúci Compose zvládne aplikáciu, prípravu aj kontroly.
- Samostatné pravidlá pre každý AI nástroj, kópie architektonickej dokumentácie alebo automatické nasadzovacie hooky. Základ je AGENTS + malý CLAUDE import.
- Mazanie záloh, PDF a podobných otázok označených za „nepotrebné“. Usporiadanie a obsah učiva sú dve samostatné zmeny.

Toto usporiadanie je odporúčanie pre súčasnú veľkosť projektu. Aplikáciu rozdeliť ďalej až vtedy, keď konkrétna úprava ukáže praktický problém.
