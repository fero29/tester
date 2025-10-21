# Test App - Návod na spustenie

## Lokálne testovanie (HTTP)

Pre lokálne testovanie na `http://localhost:5000`:

```bash
# Spusti development verziu
docker compose -f docker-compose.dev.yml up -d

# Skontroluj logy
docker compose -f docker-compose.dev.yml logs -f

# Otvor v prehliadači
http://localhost:5000

# Zastavenie
docker compose -f docker-compose.dev.yml down
```

## Produkčné nasadenie na AWS (HTTPS)

Pre nasadenie s nginx a SSL certifikátom:

### 1. Príprava

**AWS Security Group:**
- Port 80, 443, 22

**DNS (WebSupport):**
- A záznam `@` → AWS IP
- A záznam `www` → AWS IP

### 2. Nasadenie

```bash
# Na AWS serveri
git clone https://github.com/tvoj-repo.git test-app
cd test-app

# Najprv spusti len Flask bez SSL
docker compose up -d web
curl localhost:5000  # Over že funguje

# Uprav email v init-letsencrypt.sh
nano init-letsencrypt.sh
# Zmeň: email="your-email@example.com"

# Získaj SSL certifikát
./init-letsencrypt.sh

# Spusti všetko vrátane nginx
docker compose up -d

# Skontroluj
docker compose ps
docker compose logs -f
```

### 3. Prístup

- `http://photostory.sk` → presmeruje na `https://photostory.sk`
- `https://photostory.sk` ✅

## Štruktúra

```
test-app/
├── app.py                      # Flask backend
├── static/                     # CSS, JS
├── templates/                  # HTML
├── testy/                      # JSON testy (commitnuté do gitu)
├── docker-compose.yml          # Produkcia (nginx + SSL)
├── docker-compose.dev.yml      # Lokálne (len Flask)
├── nginx.conf                  # Nginx konfigurácia
├── init-letsencrypt.sh         # Skript pre SSL certifikát
└── DEPLOYMENT.md               # Detailný deployment návod
```

## Certbot auto-renewal

Certbot kontajner automaticky obnovuje certifikáty každých 12 hodín. Nič manuálne nie je potrebné.
