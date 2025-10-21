# Návod na nasadenie na AWS

## 1. AWS EC2 Security Group
Otvor tieto porty:
- **Port 80** (HTTP) - Source: 0.0.0.0/0
- **Port 22** (SSH) - Source: 0.0.0.0/0 alebo tvoja IP

## 2. Websupport DNS nastavenie
V DNS zóne pre `frantisekmasiar.sk`:
- **A záznam**: `test` → **verejná IP tvojho AWS EC2**
- Príklad: `test` → `54.123.45.67`
- Výsledok: `test.frantisekmasiar.sk` bude smerovať na tvoj server

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

# Vytvor priečinok pre testy
mkdir -p testy

# Uprav docker-compose.yml - riadok 10
# Zmeň: /home/fmasiar/tester/testy:/app/testy
# Na:    /root/testy:/app/testy (alebo kde máš priečinok testy)

# Spusti aplikáciu
docker compose up -d

# Skontroluj že beží
docker compose ps
docker compose logs -f
```

### Pridanie testov
```bash
# Skopíruj .json súbory do priečinka testy/
cd /root/testy
# Nahraj súbory cez scp alebo vytvor priamo
```

## 4. Prístup
Otvor v prehliadači: `http://test.frantisekmasiar.sk`

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
