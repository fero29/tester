# Nasadenie, zálohy a presun

O verejnom nasadení a hostiteľskom počítači rozhoduje vlastník. Opravy sa najprv overujú na `http://test.localhost`; lokálny postup je v [README.md](../README.md). Verejné nasadenie sa robí iba postupom [Nasadenie verzie](#nasadenie-verzie-notebook--localhost--server) a až pri schválenom nasadení.

## Prostredia

| Prostredie | Compose | Dáta | Konfigurácia |
| --- | --- | --- | --- |
| Lokálne | hlavný + `docker-compose.local.yml`, projekt `tester-local` | `.local/testy`, `.local/data` | `.env.local` |
| LAN | hlavný + lokálny + `docker-compose.lan.yml`, projekt `tester-lan` | `.local/lan/testy`, `.local/lan/data` | `.env.lan` |
| Produkcia | `docker-compose.yml`, projekt `tester` | `testy`, `data` | `.env` |
| Regresné testy | `docker-compose.test.yml` | dočasné adresáre v kontajneri | testovacie hodnoty |

Compose v2.24.4+ je potrebný kvôli `!override`. Runtime je Python 3.12 + Gunicorn (1 worker, 4 vlákna), bez Flask debug servera. Jeden worker udržiava jednotný limit AI požiadaviek a analytických zápisov; nezvyšovať ho bez úpravy synchronizácie. Kód je v image, zmena vyžaduje rebuild. Image neobsahuje `.env`, testy, zdrojové fotografie ani analytiku.

Kontajner má koreňový systém iba na čítanie a nemá Linux capabilities. Zapisuje len do dátových mountov a dočasného `/tmp`. Pri priamom použití Compose je predvolené UID/GID 1000; `tools/manage.sh` automaticky použije UID/GID aktuálneho používateľa, prípadne explicitné premenné `APP_UID` a `APP_GID` z prostredia shellu. Spúšťajte ho ako bežný používateľ s prístupom k Dockeru. Prenesené dátové adresáre musia tomuto používateľovi umožniť zápis; nepoužívajte `chmod 777`.

## Nasadenie verzie: notebook → localhost → server

Zdrojom pravdy pre kód aj testy je tento Git repozitár. Na serveri sa nič needituje ručne; editor na verejnom webe slúži iba na výnimočné opravy, ktoré sa potom prenesú do repozitára. Server vždy beží jeden Git tag `vX.Y.Z`. Kód a testy sa nasadzujú spolu, `data/` a `.env` zostávajú iba na serveri.

1. Zmena, aktualizácia dokumentácie a pri zmene pre používateľa aj `VERSION` a `versionPage`. Nový obsah testov je zmena pre používateľa, preto tiež zvyšuje verziu.
2. Commit, tag rovnaký ako `VERSION` a push:

   ```bash
   git tag v1.8.2 && git push origin main v1.8.2
   ```

3. Lokálny test presne tohto tagu:

   ```bash
   ./tools/deploy.sh local v1.8.2
   ```

   Spustí regresné kontroly, nahradí `.local/testy` testami z tagu (predchádzajúca kópia ide do `.local/backups/`), spustí `tester-local` a overí, že `http://localhost:8080` hlási verziu tagu a poskytuje presne jeho testové súbory (SHA-256 cez `/api/tests/meta`). Potom treba skontrolovať priebeh v prehliadači na `http://test.localhost` vrátane mobilu a oboch tém.
4. Server:

   ```bash
   ./tools/deploy.sh server v1.8.2
   ```

   - Pokračuje iba po úspešnom `local` pre ten istý commit, s čistým pracovným stromom a pushnutým tagom.
   - Porovná server s `RELEASE.sha256` posledného nasadenia. Ručne zmenený súbor alebo nový test zo serverového editora/importu nasadenie zastaví; kópie sa stiahnu do `.local/server-changes/<čas>/`. Najprv ich preneste do repozitára (nový release) alebo vedome zamietnite.
   - Krátko zastaví web a uloží celý projektový adresár servera vrátane `data/` a `.env` do `~/tester-backups/<čas>-before-vX.Y.Z.tar.gz`, potom web znova spustí.
   - Rozbalí release z `git archive` (s `RELEASE` a `RELEASE.sha256`), overí hashe a spustí `tools/manage.sh public up`. Súbory, ktoré nová verzia neobsahuje, iba vypíše; nemaže ich.
   - Overí, že `https://test.frantisekmasiar.sk` hlási verziu tagu a poskytuje presne testy z releasu. Záznam uloží do `.local/deployments/<čas>-vX.Y.Z/` a release archív na server do `~/tester-releases/`.
5. Kópiu serverových štatistík a záloh zápisov stiahne na požiadanie `./tools/deploy.sh fetch-data` do `.local/server-data/<čas>/`.

Návrat na predchádzajúcu verziu: `./tools/deploy.sh local vPREDOŠLÁ` a `./tools/deploy.sh server vPREDOŠLÁ` po `git checkout vPREDOŠLÁ`. Dáta zo zálohy sa obnovujú iba výslovným rozhodnutím vlastníka.

Cieľ sa dá zmeniť premennými `TESTER_SERVER` (predvolene `ferom@fero-server.local`), `TESTER_REMOTE_DIR` (`/home/ferom/tester`), `TESTER_PUBLIC_URL` a `TESTER_LOCAL_URL`. Skript potrebuje na notebooku Bash, Git, Docker, `ssh`/`scp` s prístupom kľúčom a `curl`; na serveri Bash, `tar`, `sha256sum` a Docker Compose.

Prvé nasadenie na server bez `RELEASE.sha256` (nový stroj alebo inštalácia spred tohto postupu): over obsah servera proti repozitáru a potom vytvor referenčný manifest z aktuálneho stavu servera pre súbory, ktoré obsahuje release. Až potom spusti `deploy.sh server`. Skript bez referencie odmietne pokračovať.

## Prenosné spustenie a odstránenie

Vyžaduje Docker/Compose a Bash na hostiteľovi (Linux, macOS alebo WSL2). Z koreňa projektu:

```bash
./tools/manage.sh local up
./tools/manage.sh local status
./tools/manage.sh local down
```

`local up` najprv pripraví chýbajúce lokálne súbory v kontajneri a potom zostaví a spustí web. Existujúce testy ani `.env.local` neprepisuje. Vyžaduje voľné lokálne porty 80 a 8080. Skript funguje aj pri zavolaní z iného adresára a pre cesty s medzerami. Výslovný `TESTER_PROJECT_NAME` umožňuje oddelenú skúšobnú inštanciu; tá potrebuje aj vlastné dáta a voľné porty v Compose konfigurácii.

LAN má samostatné dáta a prihlásenie. Pri zadaní sprístupniť web v lokálnej sieti:

```bash
./tools/manage.sh lan up
./tools/manage.sh lan status
./tools/manage.sh lan down
```

Otvorte `http://IP-počítača:8081` z druhého zariadenia v sieti. LAN predvolene počúva na všetkých IPv4 rozhraniach, bez tunela; dostupnosť riadi sieť a firewall počítača. Neotvárajte presmerovanie portu na routeri na internet. Voliteľné `LAN_BIND_ADDRESS` a `LAN_PORT` z prostredia umožňujú konkrétnu lokálnu IP a port. Lokálny PC režim počúva iba na loopbacku 80/8080, takže tieto dva režimy môžu bežať súčasne. `test.localhost` na druhom zariadení označuje toto druhé zariadenie, nie server. Názov namiesto LAN IP by vyžadoval samostatné nastavenie DNS v sieti.

LAN príprava vytvorí `.env.lan` a skopíruje chýbajúce testy do `.local/lan/testy/`. Existujúce kópie ani prihlasovanie neprepisuje. AI a analytika sú vypnuté rovnako ako lokálne, cookies sa používajú cez HTTP. PC, LAN a verejné nasadenie si automaticky nesynchronizujú zmeny; pri presune LAN inštancie preneste aj `.local/lan/` a `.env.lan`.

Verejný variant po nastavení tunela a prenose dát, iba pri schválenom nasadení:

```bash
./tools/manage.sh public up
./tools/manage.sh public status
./tools/manage.sh public down
```

`public up` vyžaduje `.env` a `testy/`, chýbajúci `data/` vytvorí. Pri migrácii preneste celý pôvodný `data/`, aby zostali aj štatistiky a zálohy. Spustenie kontajnerov nepotvrdzuje funkčnosť verejnej domény; po nasadení treba overiť aj tunnel a HTTPS adresu. Pri opakovanom spustení sa použije existujúca konfigurácia. Docker sa na novom PC inštaluje samostatne; tento skript nemení jeho systémovú inštaláciu.

`down` odstráni kontajnery zvoleného Compose projektu a jeho sieť. Zachová `.env`, `.env.local`, `.env.lan`, všetky dátové adresáre, zálohy aj image; nepoužíva `--volumes`, `--rmi` ani globálne čistenie Dockeru. Nemení iné projekty. Na PC po nás netreba odstraňovať záznamy z `/etc/hosts`, vlastné DNS, nginx, certbot ani systémovú službu. Pripravené kontajnery používajú `restart: unless-stopped`; po reštarte dostupného Docker démona sa obnovia, pokiaľ boli spustené.

Samotný kontajner neurčuje DNS v prehliadači alebo verejnej doméne. `test.localhost` je lokálny názov pre počítač s prehliadačom ([RFC 6761](https://www.rfc-editor.org/rfc/rfc6761.html#section-6.3)). Verejné smerovanie je jednorazovo uložené v Cloudflare; [spravovaný tunnel](https://developers.cloudflare.com/tunnel/features/locally-managed-tunnels/) si konfiguráciu načíta zo služby. Na iný PC stačí preniesť kód, testy, dáta a `.env` s platným tokenom toho istého tunela. IP nového PC sa do aplikácie ani DNS nezapisuje. Najprv zastavte staré nasadenie, aby Cloudflare neposielal požiadavky na dve nezávislé kópie dát.

Tajomstvá sú samostatný súkromný súbor prenesený so zálohou a pri štarte sa odovzdajú kontajneru. Nepatria do Docker image ani Gitu. Odstránenie lokálnych kontajnerov nezruší doménu alebo tunnel v účte Cloudflare; tie sa rušia samostatne až pri trvalom ukončení služby.

## Verejný prístup

```text
prehliadač → HTTPS Cloudflare → cloudflared → http://web:5000 → Gunicorn/Flask
```

Hlavný Compose nezverejňuje porty hostiteľa. Služba `cloudflared` je iba v profile `public`. Cloudflare poskytuje HTTPS; hostiteľ nepotrebuje prichádzajúce porty z internetu. [Dokumentácia tunela](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/).

1. Kód a testy prenáša `tools/deploy.sh` z Git tagu. Pri presune na nový stroj preneste aj celý `data/` vrátane podadresárov; na prvom nasadení vytvorte prázdny `data/`, ak ešte neexistuje.
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

Osobné výsledky (`testResults`), nastavenia otázkových testov (`practiceSettings`) a plán opakovania (`learningProgress`) sú v `localStorage` konkrétneho prehliadača a originu. Nie sú súčasťou serverovej zálohy a pri zmene domény alebo zariadenia sa automaticky neprenesú. Pomôcky `learning` sú naopak súčasťou JSON otázok a zálohujú sa spolu s testami.

Pred nasadením alebo presunom krátko zastavte web, aby bola kópia dát konzistentná. Vyberte nový názov archívu; `set -C` zabráni prepísaniu existujúceho súboru. Tieto príkazy používajú hostiteľský `tar`, ktorý je na bežnom Linuxe:

```bash
docker compose -p tester stop web
(set -C; tar -czf - testy data > tester-backup-YYYYMMDD-HHMM.tar.gz)
docker compose -p tester start web
tar -tzf tester-backup-YYYYMMDD-HHMM.tar.gz
```

Tento archív obsahuje prevádzkové dáta. Pre úplnú zálohu pracovného projektu pribaľte aj `work/`, `sources/`, `tools/out/`, `tools/pages/` a prípadné lokálne dáta; uchovajte tiež kód a históriu Gitu. Archív a `.env` uložte bezpečne aj mimo hostiteľského disku. Git ich neobsahuje. Pred aktualizáciou si ponechajte aj predchádzajúcu verziu zdrojového kódu alebo image. Záloha aplikácie neobsahuje osobné výsledky uložené v prehliadači.

Automatické zálohy každého zápisu sú v `data/backups/<čas>-<akcia>-<id>/<pôvodný názov>.json`. Sú to pôvodné bajty vrátane všetkých metadát. Neprerezávajú sa automaticky. Aktívny analytický log sa otáča pri 10 MB, staré súbory zostávajú; dashboard zobrazuje posledných najviac 50 000 udalostí z aktívneho súboru. Sledujte voľné miesto a zálohy odnášajte mimo disku.

## Obnova a presun na iný PC

1. Zálohu rozbaľte najprv do **nového prázdneho adresára**, nie cez existujúce dáta. Overte počet testov a obsah.
2. Na nový PC preneste kód, overené `testy/`, celé `data/` a súkromnú `.env`. Pri presune pracovného prostredia preneste aj `work/`, `sources/` a potrebné pracovné výstupy nástrojov. Pripravte Docker/Compose a práva UID/GID.
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

Git sleduje kód, dokumentáciu vrátane `work/README.md`, konfigurácie bez tajomstiev, `examples/`, `tools/imports/` a historické kópie v `archive/`. Aktuálne `testy/`, `data/`, `sources/`, obsah `work/` okrem README, `.env*` okrem vzoru, `.local/` a pracovné výstupy nástrojov sú ignorované.

- Zmena uložená v súbore ešte nie je v histórii; treba commit.
- Lokálny commit stále žije na hostiteľskom disku. Push vytvorí kópiu kódu na vzdialenom repozitári, nepošle ignorované dáta.
- Pred presunmi vznikajú súkromné návratové zálohy v `.local/backups/` vrátane kontrolných súčtov. Obsahujú aj tajomstvá: necommitovať ani verejne nezdieľať.
- Úplná ochrana vyžaduje osobitnú zálohu dát mimo PC. Samotné `git push` nestačí.

Stav kódu overíte cez `git status --short`, `git log -3 --oneline` a `git log --oneline '@{upstream}..HEAD'`. Lokálne údaje o vzdialenej vetve môžu byť staré; aktuálny commit na serveri zistíte read-only príkazom `git ls-remote --heads origin main`. Obsah celej `.env` ani `docker compose config` s rozbalenými tajomstvami nevypisujte do záznamu práce.
