# LFUK tester — spoločné pokyny pre AI

Malá slovenská aplikácia na samoštúdium: otázkové testy a latinské slovíčka, výber ročníka a predmetu, editor a voliteľný AI import z fotiek. Tento súbor je spoločný zdroj projektových pravidiel; `CLAUDE.md` ho importuje. Pravidlá udržiavaj tu, bez kópií pre každý nástroj.

## Dohoda s vlastníkom

- **KISS:** vyber najjednoduchšie riešenie, ktoré zvládne aktuálnu potrebu. Zachovaj Flask, obyčajný JS/CSS a JSON súbory, kým nie je konkrétny dôvod na zmenu. Nepridávaj framework, databázu, službu, build systém ani univerzálne abstrakcie len pre hypotetický rast.
- Používateľ opisuje požadovaný výsledok; technické rozhodnutia, opravu a primerané lokálne overenie rieši AI. Bežné implementačné voľby nevracaj používateľovi na rozhodnutie. Pri chýbajúcom podstatnom zadaní sa opýtaj stručne.
- **Docker + Docker Compose sú podmienka.** Bežné spustenie nesmie vyžadovať Python/Node na hostiteľovi.
- **Commit a push sú v tomto projekte povolené priebežne podľa uváženia AI**, bez ďalšieho pýtania. Pred commitom skontroluj pripravovaný obsah a pred pushom všetky odosielané commity, aby neobsahovali tajomstvá ani ignorované súkromné dáta. Používaj bežný push; neprepisuj vzdialenú históriu. Toto povolenie nemení pravidlo verejného nasadenia nižšie.
- **Kedy a kde sa nasadí verejne, určuje používateľ.** Požiadavka na opravu, refaktoring či lokálny test sama neaktivuje produkciu. Produkčná doména je `test.frantisekmasiar.sk`; budúci hosting môže byť iný PC. Neviaž projekt na konkrétnu IP alebo `/home/fmasiar`.
- Komunikuj po slovensky, stručne a vecne. UI a chybové správy sú slovensky. Rozlišuj hotovú zmenu, návrh a neoverený predpoklad.

## Dáta majú prednosť pred upratovaním

- `testy/`, jeho podadresáre, `archive/tests-aws/`, `archive/tests-clean/`, `data/` a `sources/` obsahujú hotové testy, podklady alebo históriu. Pri práci na kóde ich neupravuj ani nemaž.
- `work/` je dohodnuté miesto na nové podklady pred spracovaním a rozpracované výsledky. Pri úlohe s podkladmi ho skontroluj aj napriek ignorovaniu Gitom (napr. `rg --files --hidden --no-ignore work`). Obsah chráň ako používateľskú prácu, nemaž ho ako cache a neaktivuj automaticky. Po dokončení presuň iba súbory dotknuté zadaním na ich trvalé miesto podľa `docs/STRUCTURE.md`.
- Podobné otázky v rôznych testoch nemusia byť omyl. Neodstraňuj ani neopravuj odborný obsah na základe technického review.
- Ak zadanie zahŕňa zmenu dát, najprv zachovaj pôvodné bajty v zálohe a over zmenu na kópii. Import nesmie potichu prepísať existujúci súbor. Hromadné presuny over mapovaním ciest a SHA-256 pred/po.
- `testy/`, `data/`, `sources/` a obsah `work/` okrem jeho README nie sú súčasťou image ani bežného Git checkoutu; zálohuj ich samostatne. Kód a historické kópie v `archive/` chráni Git iba po commite; kópia na vzdialenom repozitári existuje až po pushi. Lokálne `.local/backups/` sú návratové zálohy na tom istom disku, nie náhrada zálohy mimo PC. Chýbajúce súbory na novom stroji neznamenajú, že ich máš vytvoriť z historickej zálohy cez aktuálne dáta.
- Tajomstvá z `.env` a `.env.local` nepatria do Gitu, image, dokumentácie, URL ani výpisov. Heslo správcu sa zadáva cez `/admin/login`; neuvádzaj jeho hodnotu v odpovedi.

## Prostredia a príkazy

| Účel | Compose projekt a súbory | Dáta / konfigurácia |
| --- | --- | --- |
| Lokálne opravy | `tester-local`, hlavný + `docker-compose.local.yml` | `.local/testy`, `.local/data`, `.env.local` |
| Verejné nasadenie | `tester`, hlavný Compose, výslovný profil `public` | `testy`, `data`, `.env` |
| Regresné kontroly | `tester-checks`, `docker-compose.test.yml` | dočasné dáta v kontajneri |

Lokálna adresa je **http://test.localhost** na počítači s Dockerom, záložná **http://localhost:8080**. Staršiu `test.local` už nepoužívame; nemeníme `/etc/hosts`. `.localhost` z iného zariadenia neukazuje na server.

Z koreňa projektu, Docker Compose v2.24.4+:

```bash
# Prvé spustenie; doplní iba chýbajúce lokálne kópie a konfiguráciu.
docker compose -p tester-local -f docker-compose.yml -f docker-compose.local.yml run --rm prepare
# Spustenie alebo overenie zmeneného kódu.
docker compose -p tester-local -f docker-compose.yml -f docker-compose.local.yml up -d --build --wait
# Stav a posledné logy bez výpisu tajomstiev.
docker compose -p tester-local -f docker-compose.yml -f docker-compose.local.yml ps
docker compose -p tester-local -f docker-compose.yml -f docker-compose.local.yml logs --tail 100 web
# Automatické regresné kontroly.
docker compose -p tester-checks -f docker-compose.test.yml run --build --rm tests
```

Kód je zabudovaný v image: editácia súboru sama nezmení bežiaci kontajner. `prepare` zámerne neobnovuje už existujúce lokálne kópie. Pri zmene pôvodných testov over, ktorú verziu dát lokálne skúšaš. Lokálny AI kľúč a analytika sú vypnuté; testy AI používajú simulovanú odpoveď.

## Kde hľadať zmenu

| Súbor / adresár | Zodpovednosť |
| --- | --- |
| `app.py` | HTTP endpointy, spracovanie fotiek, AI a analytika |
| `storage.py` | validácia, cache súborov, verzie, zámky, atómový zápis a zálohy |
| `security.py` | prihlásenie, relácia, CSRF, limity požiadaviek |
| `static/app.js` | zoznam, filtre, priebeh testov/slovíčok, editor, výsledky, cache prehliadača |
| `static/style.css`, `templates/` | témy, rozloženie a obrazovky; v `templates/index.html` aj návod `helpPage` a história verzií `versionPage`; bez frontend build kroku |
| `tests/` | regresné kontroly; nie používateľské testy z `testy/` |
| `tools/prepare_local.py`, `tools/imports/` | príprava prostredia a oddelené ručné extrakcie; nie sú súčasťou runtime |
| `VERSION` | jediný zdroj verzie aplikácie pre backend, šablónu aj JS |

## Kontrakty, ktoré nesmie oprava porušiť

- Otázkový test má `questions[]`, odpovede `answers[]` a `correct` ako index alebo pole indexov od nuly. Existujú otázky s 2 aj 4 odpoveďami; `correct: []` znamená žiadnu správnu. Zachovaj neznáme metadáta.
- Slovíčkový test má `testType: "vocabulary"` a `vocabulary[]`. Typy sú `noun`, `adjective`, `phrase`; posledné dva nevyžadujú rod/genitív. Append nesmie zmiešať slovíčka s otázkami.
- Chýbajúci `year` znamená 1. ročník, podporované sú 1 a 2. Nový predmet sa zobrazí z `category` v príslušnom ročníku. Existujúce testy kvôli filtru neprepisuj. Zachovaj `previousTitles` pre osobné výsledky a `sortOrder` pre poradie.
- Úložisko číta objekt aj pole testov, zapisuje pole. Import kolízie odmieta (409). Update/append/delete vyžadujú aktuálnu SHA-256 `version` (428 chýbajúca, 409 konflikt). Pred zmenou vzniká presná záloha, zápis je atómový pod súborovým zámkom. Editor ukladá výslovne tlačidlom.
- `/api/tests/meta` kontroluje zmeny, `/api/tests` podporuje ETag a vracia verzie súborov spolu s obsahom. Obsah a verzie v IndexedDB musia pochádzať z tej istej odpovede, inak sa môže zafixovať zastaraná cache.
- Osobné výsledky sú v localStorage pre konkrétny prehliadač a origin. Serverové štatistiky návštev sú samostatné eventy v `data/`. Jeden pokus má jeden výsledok; opakovanie chybných odpovedí ho nesmie počítať znova. Vypršanie času ukončí test aj slovíčka.
- Zápisy vyžadujú správcu a CSRF; `/api/track` je validovaná verejná výnimka s limitom. Text testov escapuj aj v HTML atribútoch. Správne odpovede sú verejné pre samoštúdium.
- Runtime používa Gunicorn 1 worker / 4 vlákna. Limit AI a zámok event logu sú procesové; počet workerov nemeň bez zodpovedajúcej synchronizácie. Kontajner beží bez roota a s read-only koreňom, zapisuje iba do dát a `/tmp`.
- AI import je voliteľný, momentálne Claude Sonnet 4.6, jedna súbežná požiadavka. Extrakčné skripty nespúšťaj hromadne: niektoré volajú platené API alebo aktivujú testy. Najprv prečítaj konkrétny skript a jeho cesty.

## Pracovný postup a odovzdanie

1. Pozri `git status` a príslušný diff, potom relevantný kód. Zachovaj rozpracované cudzie zmeny. Aktuálnu verziu a stav kontajnerov zisťuj zo súborov/príkazov; starý chat nie je dôkaz aktuálneho nasadenia.
2. Urob najmenšiu zrozumiteľnú opravu vrátane príčiny problému. Nový súbor alebo závislosť má mať konkrétnu úlohu.
3. Over rizikové správanie primeranými regresnými kontrolami; pri zmene UI aj dotknutý priebeh v prehliadači na `test.localhost`, mobil a svetlú/tmavú tému. Testuj na dočasných dátach alebo lokálnych kópiách. Pri čistej dokumentácii stačí kontrola odkazov a diffu.
4. Zmenu závislostí over aj auditom podľa README. Ak kontrolu nemožno vykonať, presne povedz čo a prečo; neoznač ju za úspešnú.
5. **Pred každým commitom skontroluj a podľa zmien aktualizuj príslušné Markdown súbory:** `README.md` pre používanie a spustenie, `docs/STRUCTURE.md` pre to, čo je kde a na čo slúži, `docs/DEPLOYMENT.md` pre prevádzku, konfiguráciu, zálohy a presun, tento súbor pre trvalé dohody a kontext AI, prípadne návody pri dotknutých nástrojoch. Dokumentácia musí opisovať stav odovzdávaný v commite vrátane zmenených ciest, príkazov, formátov a obmedzení. `CLAUDE.md` naďalej importuje tieto pravidlá; nevytváraj ich kópie ani nezapisuj celý rozhovor či dočasné výpisy.
6. **Pred commitom over aj návod a verziu priamo na stránke.** Pri zmene používateľského správania aktualizuj relevantné časti návodu `helpPage` a históriu zmien `versionPage` v `templates/index.html` a zvýš `VERSION`, ktorý zostáva jediným zdrojom čísla verzie. Podľa zmeny zosúlaď aj ukážky, konfiguračné vzory a regresné kontroly. Samotná dokumentácia či technické testy verziu nezvyšujú; nedotknuté návody netreba meniť kozmeticky.
7. Kód, súvisiacu dokumentáciu, návod a prípadnú verziu odovzdaj spolu; ich aktualizáciu neodkladaj na ďalšiu úlohu ani na pripomenutie používateľa. Pred commitom over odkazy, diff a neprítomnosť tajomstiev. Odovzdaj čo sa zmenilo, výsledok overenia a pri zmene aplikácie lokálnu adresu. Verejné nasadenie vykonaj iba v rozsahu pokynu používateľa.

Ďalšie čítanie podľa úlohy: [README.md](README.md) — použitie a JSON formát; [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) — nasadenie, zálohy a presun PC; [docs/STRUCTURE.md](docs/STRUCTURE.md) — aktuálne usporiadanie a pravidlá umiestňovania súborov.
