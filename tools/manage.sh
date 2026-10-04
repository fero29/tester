#!/usr/bin/env bash
# Spustenie a odstránenie nasadenia bez úprav DNS alebo služieb hostiteľa.
set -euo pipefail

usage() {
    cat <<'EOF'
Použitie: tools/manage.sh {local|lan|public} {up|down|status}

  local up      Pripraví lokálne kópie a spustí http://test.localhost.
  lan up        Pripraví oddelené LAN dáta a sprístupní web na porte 8081.
  public up     Spustí verejný web cez už nakonfigurovaný Cloudflare Tunnel.
  ... down      Odstráni kontajnery a ich sieť; zachová dáta aj konfiguráciu.
  ... status    Zobrazí stav kontajnerov.

Vyžaduje Bash, Docker a Compose v2.24.4+. Verejné spustenie vyžaduje
prenesenú .env a testy/. Prvý Cloudflare setup: docs/DEPLOYMENT.md.
EOF
}

if [[ "${1:-}" == '--help' || "${1:-}" == '-h' ]]; then
    usage
    exit 0
fi
if [[ $# != 2 || ! "$1" =~ ^(local|lan|public)$ || ! "$2" =~ ^(up|down|status)$ ]]; then
    usage >&2
    exit 2
fi

mode="$1"
action="$2"
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$project_root"

# .env sa nikdy nespúšťa ako shell skript. UID/GID zodpovedajú používateľovi
# nového PC; explicitné APP_UID/APP_GID v prostredí majú prednosť.
export APP_UID="${APP_UID:-$(id -u)}"
export APP_GID="${APP_GID:-$(id -g)}"
unset COMPOSE_PROFILES

if [[ "$action" == 'up' && "$APP_UID" == '0' ]]; then
    echo 'Spustite ako bežný používateľ s prístupom k Dockeru, alebo nastavte nenulové APP_UID a príslušné APP_GID.' >&2
    exit 1
fi

env_file=/dev/null
project=tester-local
files=(-f docker-compose.yml -f docker-compose.local.yml)
if [[ "$mode" == 'lan' ]]; then
    project=tester-lan
    files+=(-f docker-compose.lan.yml)
fi
if [[ "$mode" == 'public' ]]; then
    project=tester
    files=(-f docker-compose.yml)
    if [[ -f .env ]]; then env_file=.env; fi
    if [[ "$action" == 'up' ]]; then
        if [[ ! -f .env || ! -d testy ]]; then
            echo 'Chýba .env alebo testy/. Preneste konfiguráciu a testy zo zálohy; prvé nasadenie opisuje docs/DEPLOYMENT.md.' >&2
            exit 1
        fi
        mkdir -p data
    fi
fi

# Výnimka pre izolované overenie alebo ďalšiu výslovne oddelenú inštanciu.
project="${TESTER_PROJECT_NAME:-$project}"
compose=(docker compose --project-directory "$project_root" --env-file "$env_file"
    -p "$project" "${files[@]}")
if [[ "$mode" == 'public' ]]; then compose+=(--profile public); fi
docker compose version >/dev/null

case "$action" in
    up)
        if [[ "$mode" != 'public' ]]; then
            "${compose[@]}" run --rm prepare
        fi
        "${compose[@]}" up -d --build --wait
        if [[ "$mode" == 'local' ]]; then
            echo 'Lokálne: http://test.localhost (záloha: http://localhost:8080).'
        elif [[ "$mode" == 'lan' ]]; then
            echo "LAN: http://<IP-tohto-počítača>:${LAN_PORT:-8081}. Prístup z iného zariadenia vyžaduje povolený port v sieti/firewalle."
        else
            echo 'Kontajnery spustené. Overte verejnú adresu nastavenú v Cloudflare; zdravý web ešte nepotvrdzuje funkčný tunnel.'
        fi
        ;;
    down)
        "${compose[@]}" down
        echo 'Kontajnery a ich sieť odstránené. Testy, zálohy a konfigurácia zostali zachované.'
        ;;
    status) "${compose[@]}" ps ;;
esac
