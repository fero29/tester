# Nasadenie, zálohy a presun

O verejnom nasadení a hostiteľskom počítači rozhoduje vlastník. Opravy sa najprv overujú na `http://test.localhost`; lokálny postup je v [README.md](../README.md). Nižšie uvedené produkčné príkazy sa používajú až pri schválenom nasadení.

## Prostredia

| Prostredie | Compose | Dáta | Konfigurácia |
| --- | --- | --- | --- |
| Lokálne | hlavný + `docker-compose.local.yml`, projekt `tester-local` | `.local/testy`, `.local/data` | `.env.local` |
| Produkcia | `docker-compose.yml`, projekt `tester` | `testy`, `data` | `.env` |
| Regresné testy | `docker-compose.test.yml` | dočasné adresáre v kontajneri | testovacie hodnoty |

Compose v2.24.4+ je potrebný kvôli `!override`. Runtime je Python 3.12 + Gunicorn (1 worker, 4 vlákna), bez Flask debug servera. Jeden worker udržiava jednotný limit AI požiadaviek a analytických zápisov; nezvyšovať ho bez úpravy synchronizácie. Kód je v image, zmena vyžaduje rebuild. Image neobsahuje `.env`, testy, zdrojové fotografie ani analytiku.

Kontajner beží pod UID/GID 1000, s koreňovým systémom iba na čítanie a bez Linux capabilities. Zapisuje len do dátových mountov a dočasného `/tmp`. Ak má používateľ hostiteľa iné UID/GID, nastavte `APP_UID` a `APP_GID` podľa `id -u` a `id -g`. Prenesené dátové adresáre musia tomuto používateľovi umožniť zápis; nepoužívajte `chmod 777`.

## Verejný prístup

```text
prehliadač → HTTPS Cloudflare → cloudflared → http://web:5000 → Gunicorn/Flask
```

Hlavný Compose nezverejňuje porty hostiteľa. Služba `cloudflared` je iba v profile `public`. Cloudflare poskytuje HTTPS; hostiteľ nepotrebuje prichádzajúce porty z internetu. [Dokumentácia tunela](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/).

1. Preneste aktuálne adresáre `testy/` a `data/` vrátane podadresárov. Nestačí Git clone. Na prvom nasadení vytvorte prázdny `data/`, ak ešte neexistuje.
2. Pripravte `.env` podľa `.env.example`. Zachovajte už používané tajomstvá; existujúcu konfiguráciu neprepisujte vzorom. Súbor obmedzte právami `chmod 600 .env`.
3. Nastavte rôzne náhodné `SECRET_KEY` (podpis relácie) a `ADMIN_SECRET` (heslo správcu). Generátor bez lokálneho Pythonu: `docker run --rm python:3.12-slim python -c "import secrets; print(secrets.token_urlsafe(48))"`. Spustite dvakrát a hodnoty uchovajte súkromne.
4. Nastavte `COOKIE_SECURE=true`, `TRUST_PROXY_HEADERS=true` a token tunnela. AI a analytika sú voliteľné.
5. V konfigurácii spravovaného Cloudflare tunnela nastavte verejnú doménu `test.frantisekmasiar.sk` na službu `http://web:5000`.
6. Vytvorte zálohu a až pri schválenom nasadení spustite:

```bash
docker compose -p tester --profile public up -d --build --wait
docker compose -p tester --profile public ps
docker compose -p tester logs --tail 100 web cloudflared
```

Následne overte domovskú stránku, oba ročníky, testovanie a prihlásenie na `https://test.frantisekmasiar.sk`. Lokálny Compose má tunnel token prázdny a produkčné mounty nahrádza samostatnými kópiami.

Aktualizácia používa rovnaký príkaz `up -d --build --wait` po lokálnych kontrolách a zálohe. Python balíky majú pevné verzie; aktualizujte ich zámerne spolu s auditom a testami. Základný Python image priebežne aktualizujte cez build `--pull` a znova overte lokálne. TLS cookies a dôvera v proxy hlavičky patria iba za dôveryhodný HTTPS proxy, nie na priamo publikovaný HTTP port.

## Záloha

Pred nasadením alebo presunom krátko zastavte web, aby bola kópia dát konzistentná. Vyberte nový názov archívu; `set -C` zabráni prepísaniu existujúceho súboru. Tieto príkazy používajú hostiteľský `tar`, ktorý je na bežnom Linuxe:

```bash
docker compose -p tester stop web
(set -C; tar -czf - testy data > tester-backup-YYYYMMDD-HHMM.tar.gz)
docker compose -p tester start web
tar -tzf tester-backup-YYYYMMDD-HHMM.tar.gz
```

Tento archív obsahuje prevádzkové dáta. Pre úplnú zálohu pracovného projektu pribaľte aj `sources/`, `tools/out/`, `tools/pages/` a prípadné lokálne dáta; uchovajte tiež kód a históriu Gitu. Archív a `.env` uložte bezpečne aj mimo hostiteľského disku. Git ich neobsahuje. Pred aktualizáciou si ponechajte aj predchádzajúcu verziu zdrojového kódu alebo image. Záloha aplikácie neobsahuje osobné výsledky uložené v prehliadači.

Automatické zálohy každého zápisu sú v `data/backups/<čas>-<akcia>-<id>/<pôvodný názov>.json`. Sú to pôvodné bajty vrátane všetkých metadát. Neprerezávajú sa automaticky. Aktívny analytický log sa otáča pri 10 MB, staré súbory zostávajú; dashboard zobrazuje posledných najviac 50 000 udalostí z aktívneho súboru. Sledujte voľné miesto a zálohy odnášajte mimo disku.

## Obnova a presun na iný PC

1. Zálohu rozbaľte najprv do **nového prázdneho adresára**, nie cez existujúce dáta. Overte počet testov a obsah.
2. Na nový PC preneste kód, overené `testy/`, celé `data/` a súkromnú `.env`. Pri presune pracovného prostredia preneste aj `sources/` a potrebné pracovné výstupy nástrojov. Pripravte Docker/Compose a práva UID/GID.
3. Najprv spustite lokálny postup z README; ten vytvorí oddelené kópie. Overte testy a prihlásenie.
4. Pri schválenom prechode zastavte pôvodný web/tunnel, preneste poslednú konzistentnú zálohu a spustite produkčný profil na novom stroji. Dve nezávislé zapisovateľné inštancie nesmú obsluhovať tú istú doménu.
5. Pôvodný počítač a zálohu ponechajte pre návrat. Pri návrate použite aj zodpovedajúce dáta, nie iba starý image.

Obnova jednotlivého odstráneného testu: skopírujte vybranú revíziu z `data/backups` do voľného názvu v `testy/` pomocou `cp -n`; existujúcu verziu najprv samostatne archivujte. Rovnaký titul v dvoch súboroch môže duplikovať zobrazenie a spájať osobné štatistiky, preto výsledok skontrolujte v lokálnej kópii.

## Prevádzkové poznámky

- `http://test.localhost` funguje na stroji s Dockerom v podporovanom prehliadači. Pre prístup z iného zariadenia treba samostatne dohodnúť LAN adresu/doménu a prístupové pravidlá.
- Heslo správcu sa zadáva cez `/admin/login`, nikdy ako parameter URL. Relácia vyprší po 8 hodinách nečinnosti. Zmena `SECRET_KEY` odhlási všetkých správcov.
- Hotové testy aj správne odpovede sú verejne čitateľné pre samoštúdium. Aplikácia nie je systém na utajené školské skúšky.
- Podklady v `sources/` a historické testy v `archive/tests-aws/` a `archive/tests-clean/` sú podklady a historické zálohy, nie nepotrebný kód. Zachovať ich.
- Starší AWS/nginx/certbot setup je dostupný v Git histórii. Aktuálne nasadenie ho nepoužíva.

## Čo chráni Git

Git sleduje kód, dokumentáciu, konfigurácie bez tajomstiev, `examples/`, `tools/imports/` a historické kópie v `archive/`. Aktuálne `testy/`, `data/`, `sources/`, `.env*` okrem vzoru, `.local/` a pracovné výstupy nástrojov sú ignorované.

- Zmena uložená v súbore ešte nie je v histórii; treba commit.
- Lokálny commit stále žije na hostiteľskom disku. Push vytvorí kópiu kódu na vzdialenom repozitári, nepošle ignorované dáta.
- Pred presunmi vznikajú súkromné návratové zálohy v `.local/backups/` vrátane kontrolných súčtov. Obsahujú aj tajomstvá: necommitovať ani verejne nezdieľať.
- Úplná ochrana vyžaduje osobitnú zálohu dát mimo PC. Samotné `git push` nestačí.

Stav kódu overíte cez `git status --short`, `git log -3 --oneline` a `git log --oneline '@{upstream}..HEAD'`. Lokálne údaje o vzdialenej vetve môžu byť staré; aktuálny commit na serveri zistíte read-only príkazom `git ls-remote --heads origin main`. Obsah celej `.env` ani `docker compose config` s rozbalenými tajomstvami nevypisujte do záznamu práce.
