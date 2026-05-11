# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Spustenie

Vývoj (lokálne, HTTP na :5000):
```bash
docker compose -f docker-compose.dev.yml up -d
docker compose -f docker-compose.dev.yml logs -f
docker compose -f docker-compose.dev.yml down
```

Bez Dockera (vyžaduje `ANTHROPIC_API_KEY` v `.env`):
```bash
pip install -r requirements.txt
python app.py
```

Produkcia (Flask + nginx + certbot, doména `photostory.sk`): `docker compose up -d`. Pre prvé získanie TLS certifikátu spusti `./init-letsencrypt.sh` na servri — skript automaticky prepne nginx na SSL verziu.

Repo nemá test suite. `test_ai.py` v koreni nie je unit test — je to one-off skript na manuálne overenie Claude Vision odpovede na pevne nahardcoded ceste k obrázku.

## Architektúra

**Backend (`app.py`, ~917 riadkov, single-file Flask):** všetky endpointy v jednom module. Storage je adresár `testy/` s JSON súbormi — žiadna databáza. Globálna `tests = []` sa **mazre a celá znova načíta z disku pri každom volaní `/api/tests`**. Nepiš logiku ktorá sa spolieha na to, že `tests` ostane zachovaná medzi requestmi; je to len pomocný buffer pre práve servovaný request.

**Frontend (`static/app.js`, ~3570 riadkov, vanilla JS, jeden súbor):** žiadny build step, žiadny framework. Súbor je rozdelený section komentármi `// =====` — orientuj sa podľa nich:
- IndexedDB CACHE (cache testov v prehliadači)
- TÉMA (svetlá/tmavá)
- OCHRANA PRED NECHCENOU NAVIGÁCIOU
- AI IMPORT FUNKCIE
- TEST EDIT FUNKCIE
- VOCABULARY (SLOVÍČKA) FUNKCIE
- VOCABULARY TEST FUNKCIE

Stav je v module-level `let` premenných (`tests`, `currentTest`, `currentQuestionIndex`, `userAnswers`, `testMode`, atď.). Štatistiky a téma sa perzistujú v `localStorage`, telá testov v IndexedDB (`AITesterCache` DB, `cache` store).

**Cache invalidation flow:** `GET /api/tests/meta` vráti pre každý súbor hash z `mtime + size`. Frontend porovná s cached meta a stiahne plné `GET /api/tests` len keď sa hash zmení. Keď upravuješ endpoint ktorý mení súbory v `testy/`, mtime sa zmení sám — žiadnu manuálnu invalidáciu netreba.

**Šablóna:** jediný `templates/index.html` (~997 riadkov) so všetkými views (zoznam, test, AI import, editor, výsledky) prepínanými cez `display: none`. Funguje to ako SPA bez routera.

## Dva typy testov

Toto je najdôležitejší architektonický rozdiel — väčšina endpointov a JS funkcií musí oba typy zvládať:

1. **Klasický test** — pole `questions[]`, každá otázka má `answers[]` (presne 4) a `correct` ktoré je **buď int (jedna správna) alebo array intov (viac správnych)**. Frontend aj backend musia handlovať oba tvary `correct`.
2. **Vocabulary test** — `testType: "vocabulary"` + pole `vocabulary[]` so záznamami `{ latin, type: "noun"|"adjective", genitive, gender, slovak }`. Pre adjektíva sú `genitive` a `gender` prázdne stringy.

`/api/save-test` v `mode=append` musí podľa prítomnosti kľúča `vocabulary` (vs. `questions`) rozhodnúť do akého poľa appendovať — nezamieňaj.

## Ukladanie testov

- Súbory v `testy/` sú vždy uložené ako **JSON array s jedným testom** aj keď ide o jediný test (konzistencia s `/api/import`).
- Filename je `{test.title}.json`. `/api/update-test` premenuje súbor pri zmene titulku — ak nový názov koliduje, vracia 400.
- `testy/` je v `.gitignore`. README-SETUP.md tvrdí opak; v tejto vetve platí gitignore. Pri deploy musí používateľ testy nakopírovať manuálne.
- Pri importe via UI sa testy z uploadnutého JSONu rozbijú na samostatné súbory (po jednom za `title`).

## Claude Vision integrácia

Backend používa **Anthropic SDK** (`anthropic` package) s modelom **`claude-sonnet-4-6`**. API kľúč ide cez env var `ANTHROPIC_API_KEY` (klient ho číta automaticky cez `anthropic.Anthropic()`).

Dva endpointy, oba volajú Sonnet 4.6 s `temperature=0.1` a `max_tokens=8192`:

- `/api/ai-import` — extrakcia otázok. Prompt nariaďuje AI vrátiť `positionPercent` (vertikálna pozícia začiatku otázky 0–100). Backend z týchto pozícií vyrobí per-question crop výrezy (každá otázka v UI má pri sebe svoj výrez fotky pre vizuálnu kontrolu). Ak AI pozície nedodá, fallback je rovnomerné rozdelenie.
- `/api/ai-import-vocab` — extrakcia latinských slovíčok.

Vision message format pre Claude (líši sa od OpenAI):
```python
{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_data}}
```
`image_data` je čistý base64 string **bez** `data:image/jpeg;base64,` prefixu. Response sa extrahuje cez `next(b.text for b in response.content if b.type == "text")`.

Oba endpointy:
1. Predspracujú obrázok cez `preprocess_image()` — buď základný PIL (sharpen, kontrast, jas) alebo `advanced=True` OpenCV pipeline (deskew via Hough lines → CLAHE → fastNlMeans denoise → bilateral → adaptive threshold → morphology → sharpen kernel). Advanced režim je určený pre čiernobiele scany s nízkym kontrastom.
2. Zoberú AI odpoveď, vystrihnú prípadné ` ```json ` markdown bloky, a ak `json.loads` zlyhá, prejdú cez `fix_json_string()` (trailing commas, chýbajúce čiarky medzi objektmi, kontrolné znaky).

Ak menis prompt, drž sa existujúceho JSON kontraktu — frontend očakáva presne tieto polia. Ak chceš odstrániť potrebu `fix_json_string()` a manuálneho stripovania markdown, zváž použiť Claude `output_config={"format": {"type": "json_schema", "schema": {...}}}` ktorý JSON garantuje natívne.

## Verzovanie

Verzia je hardcoded na troch miestach a musí sa updatnúť spolu:
- `static/app.js` riadok 1: `console.log('LFUK tester vX.Y.Z ...')`
- `templates/index.html`: `<span class="version-badge">vX.Y.Z</span>` a `<h2>` v `versionPage`
- `README.md` nadpis

## Konvencie

UI texty, komentáre v kóde, console logy a chybové hlášky sú slovensky — drž to tak.
