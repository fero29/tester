#!/usr/bin/env bash
# Nasadenie jednej verzie (Git tag vX.Y.Z) z tohto repozitára: najprv lokálny
# test, potom server. Repozitár je zdroj pravdy pre kód aj testy; server iba
# spúšťa nasadenú verziu. Postup a dôvody: docs/DEPLOYMENT.md.
set -euo pipefail

usage() {
    cat <<'EOF'
Použitie: tools/deploy.sh {local|server} vX.Y.Z
          tools/deploy.sh fetch-data

  local vX.Y.Z   Regresné kontroly, nasadenie tagu na http://test.localhost
                 a overenie verzie a obsahu testov.
  server vX.Y.Z  Kontrola zmien na serveri, záloha, inštalácia tagu,
                 rebuild a overenie verejnej adresy. Vyžaduje úspešný
                 "local" pre ten istý commit.
  fetch-data     Stiahne kópiu serverového data/ do .local/server-data/.

Tag musí ukazovať na aktuálny HEAD, byť pushnutý a zhodovať sa s VERSION;
pracovný strom musí byť čistý. Ciele sa dajú zmeniť premennými
TESTER_SERVER, TESTER_REMOTE_DIR, TESTER_PUBLIC_URL a TESTER_LOCAL_URL.
EOF
}

die() { echo "CHYBA: $*" >&2; exit 1; }

if [[ "${1:-}" == '--help' || "${1:-}" == '-h' ]]; then usage; exit 0; fi
command="${1:-}"
tag="${2:-}"
if [[ "$command" == 'fetch-data' && $# == 1 ]]; then
    :
elif [[ "$command" =~ ^(local|server)$ && $# == 2 && "$tag" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    :
else
    usage >&2
    exit 2
fi

server="${TESTER_SERVER:-ferom@fero-server.local}"
remote_dir="${TESTER_REMOTE_DIR:-/home/ferom/tester}"
public_url="${TESTER_PUBLIC_URL:-https://test.frantisekmasiar.sk}"
local_url="${TESTER_LOCAL_URL:-http://localhost:8080}"
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$project_root"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
records=.local/deployments

remote() { ssh -o BatchMode=yes -o ConnectTimeout=15 "$server" "$@"; }

check_release() {
    local version
    version="$(tr -d '[:space:]' < VERSION)"
    [[ "v$version" == "$tag" ]] || die "VERSION je $version, tag je $tag."
    [[ -z "$(git status --porcelain)" ]] || die 'Pracovný strom nie je čistý; nasadzuje sa iba commitnutý stav.'
    git rev-parse -q --verify "refs/tags/$tag" >/dev/null || die "Tag $tag neexistuje."
    [[ "$(git rev-parse HEAD)" == "$(git rev-parse "$tag^{commit}")" ]] \
        || die "Tag $tag neukazuje na HEAD; prepnite sa na tag alebo vytvorte nový."
    local pushed
    pushed="$(git ls-remote origin "refs/tags/$tag" | cut -f1)"
    [[ "$pushed" == "$(git rev-parse "$tag")" ]] || die "Tag $tag nie je pushnutý na origin."
    commit="$(git rev-parse HEAD)"
}

# Presný obsah tagu s manifestom. RELEASE.sha256 pokrýva všetky súbory okrem
# seba; na serveri slúži aj ako referencia pre kontrolu ručných zmien.
build_release() {
    staging="$(mktemp -d)"
    trap 'rm -rf -- "$staging"' EXIT
    git archive --format=tar "$tag" | tar -x -C "$staging"
    printf 'version=%s\ncommit=%s\nbuilt=%s\n' "${tag#v}" "$commit" "$stamp" > "$staging/RELEASE"
    (cd "$staging" && find . -type f ! -name RELEASE.sha256 -printf '%P\0' | sort -z \
        | xargs -0 sha256sum > RELEASE.sha256)
}

expected_tests() { (cd "$staging/testy" && sha256sum -- *.json | cut -d' ' -f1 | sort); }
served_tests() { curl -fsS "$1/api/tests/meta" | grep -o '"hash":"[0-9a-f]\{64\}"' | cut -d'"' -f4 | sort; }
served_version() { curl -fsS "$1/?deploy=$stamp" | grep -o 'data-version="[^"]*"' | head -1 | cut -d'"' -f2; }

verify() {
    local url="$1" version
    version="$(served_version "$url" || true)"
    if [[ "$version" != "${tag#v}" ]]; then
        echo "$url hlási verziu '$version', očakávaná ${tag#v}." >&2
        return 1
    fi
    if ! diff <(expected_tests) <(served_tests "$url") >/dev/null; then
        echo "$url neposkytuje presne testy z $tag." >&2
        return 1
    fi
    echo "OK: $url beží $tag a poskytuje $(expected_tests | wc -l) testových súborov z releasu."
}

deploy_local() {
    check_release
    build_release
    docker compose -p tester-checks -f docker-compose.test.yml run --build --rm tests
    # Lokálna kópia sa nahradí testami z tagu; predchádzajúca ostane v zálohe.
    if [[ -d .local/testy ]]; then
        mkdir -p .local/backups
        mv .local/testy ".local/backups/$stamp-local-testy"
        echo "Predchádzajúce .local/testy: .local/backups/$stamp-local-testy"
    fi
    cp -a "$staging/testy" .local/testy
    ./tools/manage.sh local up
    verify "$local_url" || die 'Lokálne overenie zlyhalo.'
    mkdir -p "$records"
    echo "$commit" > "$records/local-$tag.ok"
    echo "Skontrolujte priebeh v prehliadači na http://test.localhost (mobil, svetlá a tmavá téma)."
}

deploy_server() {
    check_release
    [[ "$(cat "$records/local-$tag.ok" 2>/dev/null)" == "$commit" ]] \
        || die "Chýba úspešný lokálny test: tools/deploy.sh local $tag"
    build_release
    local record="$records/$stamp-$tag"
    mkdir -p "$record"
    cp "$staging/RELEASE" "$staging/RELEASE.sha256" "$record/"

    # 1. Server sa od posledného nasadenia nesmie líšiť (ručné úpravy, editor).
    local drift
    drift="$(remote bash -s -- "$remote_dir" <<'EOF'
set -euo pipefail
export LC_ALL=C  # sort and comm must use the same byte order for names with diacritics
cd -- "$1"
[[ -f RELEASE.sha256 ]] || { echo 'MISSING RELEASE.sha256'; exit 0; }
sha256sum -c --quiet RELEASE.sha256 2>/dev/null | sed -n 's/: FAILED.*$//p' || true
# Nové testy na serveri (import/editor) mimo nasadenej verzie.
comm -13 <(cut -c67- RELEASE.sha256 | grep '^testy/' | sort) \
         <(find testy -type f ! -name '*.pdf' | sort)
EOF
)"
    if [[ "$drift" == 'MISSING RELEASE.sha256' ]]; then
        die "Na serveri chýba RELEASE.sha256 (referencia posledného nasadenia); pozri docs/DEPLOYMENT.md, prvé nasadenie."
    fi
    if [[ -n "$drift" ]]; then
        local changes=".local/server-changes/$stamp"
        mkdir -p "$changes"
        printf '%s\n' "$drift" > "$changes/FILES"
        # Názvy môžu obsahovať medzery; posielajú sa ako zoznam oddelený NUL.
        tr '\n' '\0' < "$changes/FILES" | remote "cd -- '$remote_dir' && xargs -0 tar -czf - --" \
            | tar -xzf - -C "$changes"
        die "Na serveri sa od posledného nasadenia zmenili súbory (zoznam a kópie: $changes). Najprv ich preneste do repozitára alebo zamietnite."
    fi

    # 2.–4. Záloha, inštalácia a rebuild. Súbory odstránené z releasu sa iba vypíšu.
    tar -czf "$record/release.tar.gz" -C "$staging" .
    remote "mkdir -p ~/tester-releases ~/tester-backups"
    scp -q -o BatchMode=yes "$record/release.tar.gz" "$server:tester-releases/$stamp-$tag.tar.gz"
    remote bash -s -- "$remote_dir" "$stamp" "$tag" <<'EOF' | tee "$record/server.log"
set -euo pipefail
export LC_ALL=C  # sort and comm must use the same byte order for names with diacritics
dir="$1"; stamp="$2"; tag="$3"
archive="$HOME/tester-releases/$stamp-$tag.tar.gz"
backup="$HOME/tester-backups/$stamp-before-$tag.tar.gz"
cd -- "$dir"
# Krátke zastavenie webu kvôli konzistentnej kópii dát; web sa spustí aj pri chybe zálohy.
docker compose -p tester stop web
status=0; (set -C; tar -czf "$backup" -C "$dir" .) || status=$?
docker compose -p tester start web
[[ "$status" == 0 ]] || { echo "Záloha zlyhala ($status), nič sa nezmenilo." >&2; exit "$status"; }
echo "backup=$backup"
old="$(mktemp)"; cp RELEASE.sha256 "$old"
tar -xzf "$archive" -C "$dir"
sha256sum -c --quiet RELEASE.sha256
comm -23 <(cut -c67- "$old" | sort) <(cut -c67- RELEASE.sha256 | sort) | sed 's/^/removed-in-release (left in place): /'
rm -f -- "$old"
./tools/manage.sh public up
docker compose -p tester --profile public ps --format '{{.Name}} {{.Status}}'
EOF

    # 5. Overenie verejnej adresy (tunel a Cloudflare).
    local attempt
    for attempt in 1 2 3 4 5 6; do
        if verify "$public_url" 2>/dev/null; then break; fi
        if [[ "$attempt" == 6 ]]; then
            verify "$public_url" || die "Verejné overenie zlyhalo; záznam a záloha: $record"
        fi
        sleep 10
    done
    echo "Záznam nasadenia: $record"
}

fetch_data() {
    local target=".local/server-data/$stamp"
    mkdir -p "$target"
    remote "cd -- '$remote_dir' && tar -czf - data" | tar -xzf - -C "$target"
    echo "Kópia serverového data/: $target"
}

case "$command" in
    local) deploy_local ;;
    server) deploy_server ;;
    fetch-data) fetch_data ;;
esac
