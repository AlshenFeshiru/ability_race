#!/bin/bash
SURGE_DOMAIN="ceaseless-partner.surge.sh"
DIST="$HOME/ability_race/surge_dist"

NGROK_URL=$(curl -s --max-time 3 http://localhost:4040/api/tunnels 2>/dev/null | python3 -c "
import sys,json
try:
    for t in json.load(sys.stdin).get('tunnels',[]):
        if t.get('proto')=='https': print(t['public_url']); break
except: pass
" 2>/dev/null)

if [ -z "$NGROK_URL" ]; then
    echo "ngrok belum berjalan. Jalankan: ngrok http 28836"
    exit 1
fi

rm -rf "$DIST" && mkdir -p "$DIST"
cp -r "$HOME/ability_race/static/." "$DIST/"
sed -i "s|const API = window.AR_API\|\|'';|const API = '${NGROK_URL}';|g" "$DIST/index.html"
WS_BASE="${NGROK_URL/https:\/\//wss://}"
sed -i "s|const base=API?API.replace.*:proto+'://'+location.host;|const base='${WS_BASE}';|g" "$DIST/index.html"
cd "$DIST" && surge . "$SURGE_DOMAIN" --no-interaction
echo "https://$SURGE_DOMAIN"
