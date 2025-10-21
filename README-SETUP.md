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
cd ~
git clone https://github.com/tvoj-repo.git tester
cd tester

# Spusti aplikáciu (HTTP)
docker compose up -d

# Over že funguje
curl localhost:80
# Otvor v prehliadači: http://photostory.sk

# Pre HTTPS - spusti SSL certifikát skript
chmod +x init-letsencrypt.sh
./init-letsencrypt.sh
# Skript automaticky získa certifikát a prepne na HTTPS
```

### 3. Prístup

**Po docker compose up -d:**
- `http://photostory.sk` ✅

**Po spustení init-letsencrypt.sh:**
- `http://photostory.sk` → presmeruje na HTTPS
- `https://photostory.sk` 🔒

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
