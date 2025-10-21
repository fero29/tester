#!/bin/bash

# Skript pre prvotné získanie Let's Encrypt certifikátu

if [ ! -d "certbot/conf" ]; then
  echo "### Vytváram priečinky pre certbot..."
  mkdir -p certbot/conf certbot/www
fi

domains=(photostory.sk)
rsa_key_size=4096
data_path="./certbot"
email="fero.masiar@gmail.com"
staging=0 # Nastav na 1 pre testovanie

if [ -d "$data_path/conf/live/photostory.sk" ]; then
  read -p "Existujúce dáta nájdené pre photostory.sk. Pokračovať a prepísať? (y/N) " decision
  if [ "$decision" != "Y" ] && [ "$decision" != "y" ]; then
    exit
  fi
fi

if [ ! -e "$data_path/conf/options-ssl-nginx.conf" ] || [ ! -e "$data_path/conf/ssl-dhparams.pem" ]; then
  echo "### Sťahujem odporúčané TLS parametre..."
  mkdir -p "$data_path/conf"
  curl -s https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf > "$data_path/conf/options-ssl-nginx.conf"
  curl -s https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem > "$data_path/conf/ssl-dhparams.pem"
  echo
fi

echo "### Vytváram dočasný certifikát pre $domains..."
path="/etc/letsencrypt/live/photostory.sk"
mkdir -p "$data_path/conf/live/photostory.sk"
docker compose run --rm --entrypoint "\
  openssl req -x509 -nodes -newkey rsa:$rsa_key_size -days 1\
    -keyout '$path/privkey.pem' \
    -out '$path/fullchain.pem' \
    -subj '/CN=localhost'" certbot
echo

echo "### Spúšťam nginx..."
docker compose up --force-recreate -d nginx
echo

echo "### Mažem dočasný certifikát pre $domains..."
docker compose run --rm --entrypoint "\
  rm -Rf /etc/letsencrypt/live/photostory.sk && \
  rm -Rf /etc/letsencrypt/archive/photostory.sk && \
  rm -Rf /etc/letsencrypt/renewal/photostory.sk.conf" certbot
echo

echo "### Požadujem Let's Encrypt certifikát pre $domains..."
# Pripoj doménové argumenty
domain_args=""
for domain in "${domains[@]}"; do
  domain_args="$domain_args -d $domain"
done

# Vyber staging alebo produkčný režim
case "$staging" in
  1) staging_arg="--staging" ;;
  *) staging_arg="" ;;
esac

docker compose run --rm --entrypoint "\
  certbot certonly --webroot -w /var/www/certbot \
    $staging_arg \
    $domain_args \
    --email $email \
    --rsa-key-size $rsa_key_size \
    --agree-tos \
    --force-renewal" certbot
echo

echo "### Certifikát úspešne získaný!"
echo

# Vždy pokračuj s prepnutím na SSL (certbot úspešne prebehol)
echo "### Prepínam nginx na SSL verziu..."

# Zálohuj aktuálny nginx.conf
cp nginx.conf nginx-http-only.conf.bak

# Nahraď s SSL verziou
cp nginx-with-ssl.conf nginx.conf

echo "### Reštartujem Docker Compose s SSL..."
docker compose down
docker compose up -d

echo
echo "==================================================================="
echo "SSL certifikát je nainštalovaný!"
echo "Aplikácia je dostupná na: https://photostory.sk"
echo "Certifikát platný do: 2026-01-19"
echo "==================================================================="
