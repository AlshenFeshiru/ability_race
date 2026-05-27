#!/bin/bash
SURGE_PARTICIPANT="championships-race.surge.sh"
SURGE_VIEWER="stream-rate.surge.sh"
DIST_P="$HOME/ability_race/surge_participant"
DIST_V="$HOME/ability_race/surge_viewer"
FOUND_URL=""

mkdir -p "$DIST_P" "$DIST_V"

try_serveo() {
    local sub="ability-race-syamailcoin"
    ssh -o StrictHostKeyChecking=no \
        -o ServerAliveInterval=30 \
        -o ServerAliveCountMax=3 \
        -o ExitOnForwardFailure=yes \
        -R "${sub}:80:localhost:28836" serveo.net -N 2>/dev/null &
    local pid=$!
    sleep 6
    if curl -sf --max-time 4 "https://${sub}.serveo.net/health" | python3 -c "import sys,json;d=json.load(sys.stdin);exit(0 if d.get('ok') else 1)" 2>/dev/null; then
        echo "https://${sub}.serveo.net"
        kill 0 2>/dev/null
        return 0
    fi
    kill $pid 2>/dev/null
    return 1
}

try_bore() {
    local BORE_BIN="$HOME/.local/bin/bore"
    mkdir -p "$HOME/.local/bin"
    if [ ! -f "$BORE_BIN" ]; then
        local VER
        VER=$(curl -sf --max-time 5 https://api.github.com/repos/ekzhang/bore/releases/latest \
            | python3 -c "import sys,json;print(json.load(sys.stdin)['tag_name'])" 2>/dev/null)
        [ -z "$VER" ] && return 1
        curl -sfL "https://github.com/ekzhang/bore/releases/download/${VER}/bore-${VER}-x86_64-unknown-linux-musl.tar.gz" \
            -o /tmp/bore.tar.gz 2>/dev/null || return 1
        tar -xzf /tmp/bore.tar.gz -C "$HOME/.local/bin" bore 2>/dev/null || return 1
        chmod +x "$BORE_BIN"
    fi
    "$BORE_BIN" local 28836 --to bore.pub --secret syamailcoin28836 > /tmp/bore_out.txt 2>&1 &
    local pid=$!
    sleep 6
    local bore_port
    bore_port=$(grep -oP 'listening.*?(\d{4,5})' /tmp/bore_out.txt | grep -oP '\d{4,5}$' | head -1)
    if [ -n "$bore_port" ]; then
        echo "http://bore.pub:${bore_port}"
        return 0
    fi
    kill $pid 2>/dev/null
    return 1
}

try_localtunnel() {
    local NPM_PREFIX="$HOME/.npm-global"
    mkdir -p "$NPM_PREFIX"
    npm config set prefix "$NPM_PREFIX" 2>/dev/null
    export PATH="$NPM_PREFIX/bin:$PATH"
    if ! command -v lt &>/dev/null; then
        npm install -g localtunnel --prefix "$NPM_PREFIX" -q 2>/dev/null || return 1
    fi
    lt --port 28836 --subdomain ability-race-syamailcoin > /tmp/lt_out.txt 2>&1 &
    local pid=$!
    sleep 6
    local lt_url
    lt_url=$(grep -oP 'https://\S+' /tmp/lt_out.txt | head -1)
    if [ -n "$lt_url" ] && curl -sf --max-time 4 "${lt_url}/health" | python3 -c "import sys,json;d=json.load(sys.stdin);exit(0 if d.get('ok') else 1)" 2>/dev/null; then
        echo "$lt_url"
        return 0
    fi
    kill $pid 2>/dev/null
    return 1
}

for fn in try_serveo try_bore try_localtunnel; do
    FOUND_URL=$($fn)
    [ -n "$FOUND_URL" ] && break
done

if [ -z "$FOUND_URL" ]; then
    LOCAL_IP=$(ip route get 1.1.1.1 2>/dev/null | awk '{print $7; exit}')
    FOUND_URL="http://${LOCAL_IP}:28836"
fi

WS_URL="${FOUND_URL/https:\/\//wss://}"
WS_URL="${WS_URL/http:\/\//ws://}"

python3 -c "
import json
url_data = {'url':'${FOUND_URL}','ws':'${WS_URL}','status':'online'}
with open('$DIST_P/backend_url.json','w') as f: json.dump(url_data, f)
with open('$DIST_V/backend_url.json','w') as f: json.dump(url_data, f)
"

cp -r "$HOME/ability_race/static/." "$DIST_P/"
cp "$HOME/ability_race/static/viewer.html" "$DIST_V/index.html"
cp "$DIST_P/backend_url.json" "$DIST_V/backend_url.json"

sed -i "s|const API = window.AR_API\|\|'';|const API = '${FOUND_URL}';|g" "$DIST_P/index.html"
sed -i "s|const wsBase=API.replace.*location.host;|const wsBase='${WS_URL}';|g" "$DIST_P/index.html" 2>/dev/null
sed -i "s|const API = '';|const API = '${FOUND_URL}';|g" "$DIST_V/index.html"

surge "$DIST_P" "$SURGE_PARTICIPANT" --no-interaction
surge "$DIST_V" "$SURGE_VIEWER" --no-interaction

python3 -c "
print('Peserta : https://$SURGE_PARTICIPANT')
print('Viewer  : https://$SURGE_VIEWER')
print('Backend : ${FOUND_URL}')
"
