# Návod na nasadenie na AWS

## 1. AWS EC2 Security Group
Otvor tieto porty:
- **Port 80** (HTTP) - Source: 0.0.0.0/0
- **Port 443** (HTTPS) - Source: 0.0.0.0/0
- **Port 22** (SSH) - Source: 0.0.0.0/0 alebo tvoja IP

## 2. Websupport DNS nastavenie
V DNS zóne pre `photostory.sk`:
- **A záznam**: `@` → **verejná IP tvojho AWS EC2**
- **A záznam**: `www` → **verejná IP tvojho AWS EC2**
- Príklad: `@` → `18.209.48.83`
- Výsledok: `photostory.sk` a `www.photostory.sk` budú smerovať na tvoj server

## 3. Na AWS serveri

### Pripojenie
```bash
ssh ubuntu@tvoja-aws-ip
```

### Inštalácia (ak ešte nie je)
```bash
# Docker
sudo apt update
sudo apt install docker.io docker-compose -y
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER
# Odhlás sa a prihlás znova pre docker bez sudo
```

### Nasadenie aplikácie
```bash
# Stiahni repo
cd /root  # alebo /home/ubuntu
git clone https://github.com/tvoj-username/tvoj-repo.git test-app
cd test-app

# Testy sú už v repo v priečinku testy/
# Nič ďalšie nie je potrebné

# Najprv spusti len web service (bez SSL)
docker compose up -d web

# Skontroluj že beží
docker compose ps
curl localhost:5000
```

### Nastavenie SSL certifikátu
```bash
# Uprav init-letsencrypt.sh - zmeň email na riadku 12
nano init-letsencrypt.sh
# Zmeň: email="your-email@example.com"
# Na:    email="tvoj-email@example.com"

# Spusti skript pre získanie certifikátu
./init-letsencrypt.sh

# Spusti všetky services vrátane nginx
docker compose up -d

# Skontroluj že beží
docker compose ps
docker compose logs -f nginx
```

## 4. Prístup
- **HTTP**: `http://photostory.sk` (presmeruje na HTTPS)
- **HTTPS**: `https://photostory.sk` ✅

## Užitočné príkazy
```bash
# Reštart aplikácie
docker compose restart

# Zastavenie
docker compose down

# Aktualizácia kódu
git pull
docker compose up -d --build

# Logy
docker compose logs -f web
```
