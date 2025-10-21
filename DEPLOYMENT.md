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

### Nastavenie SSL certifikátu (HTTPS) - ODPORÚČANÉ

Pre zabezpečenú HTTPS komunikáciu spusti jednoducho:

```bash
# Spusti skript pre získanie SSL certifikátu
chmod +x init-letsencrypt.sh
./init-letsencrypt.sh
```

**Skript automaticky:**
1. Vytvorí dočasný certifikát pre nginx
2. Získa Let's Encrypt certifikát pre photostory.sk
3. Prepne nginx.conf na SSL verziu
4. Reštartuje všetky services s HTTPS

Po úspešnom dokončení:
- **HTTP**: `http://photostory.sk` → presmeruje na HTTPS
- **HTTPS**: `https://photostory.sk` 🔒

**Poznámka:** Email pre Let's Encrypt upozornenia je už nastavený na `fero.masiar@gmail.com`

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
