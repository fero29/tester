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
cd ~
git clone https://github.com/tvoj-username/tvoj-repo.git tester
cd tester

# Testy sú už v repo v priečinku testy/
# Nič ďalšie nie je potrebné

# Spusti všetky services (web + nginx)
docker compose up -d

# Skontroluj že beží
docker compose ps
curl localhost:80

# Skontroluj logy
docker compose logs -f nginx
```

## 4. Prístup
- **HTTP**: `http://photostory.sk` ✅

### Voliteľne: Nastavenie SSL certifikátu (HTTPS)

**POZOR:** Momentálne je nginx.conf nastavený len pre HTTP. Pre HTTPS urob:

```bash
# 1. Nahraď nginx.conf s SSL verziou
mv nginx.conf nginx-http-only.conf
mv nginx-with-ssl.conf nginx.conf

# 2. Uprav init-letsencrypt.sh - zmeň email
nano init-letsencrypt.sh
# Zmeň: email="your-email@example.com"

# 3. Spusti skript pre získanie certifikátu
./init-letsencrypt.sh

# 4. Reštartuj všetko
docker compose down
docker compose up -d

# 5. Skontroluj
docker compose logs -f nginx
```

Po úspešnom nastavení SSL:
- **HTTP**: `http://photostory.sk` → presmeruje na HTTPS
- **HTTPS**: `https://photostory.sk` 🔒

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
