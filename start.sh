#!/bin/bash
cd ~/ability_race
[ -z "$GROQ_API_KEY" ] && exit 1

export SECRET_KEY="${SECRET_KEY:-syamailcoin_PoE_SAI288_ar_2026_keccak}"
export ADMIN_TOKEN="${ADMIN_TOKEN:-arysq_admin_ar_2026_poe}"
export KECCAK_CTRL="${KECCAK_CTRL:-keccak_ctrl_syamail_28836_2026}"
export ORGANIZER_TOKEN="${ORGANIZER_TOKEN:-}"

docker build -t ability_race:local . 2>&1 | tail -5

docker stop ability_race 2>/dev/null
docker rm ability_race 2>/dev/null

docker run -d \
    --name ability_race \
    --restart unless-stopped \
    --network host \
    -v /home/bakugan/ability_race/data:/data \
    --tmpfs /tmp:mode=1777,size=256m \
    -e SERVER_PORT=28836 \
    -e DATABASE_URL=sqlite:////data/ability_race.db \
    -e GROQ_API_KEY="$GROQ_API_KEY" \
    -e SECRET_KEY="$SECRET_KEY" \
    -e ADMIN_TOKEN="$ADMIN_TOKEN" \
    -e KECCAK_CTRL="$KECCAK_CTRL" \
    -e ORGANIZER_TOKEN="$ORGANIZER_TOKEN" \
    ability_race:local

sleep 8
curl -sf http://localhost:28836/health || exit 1

bash ~/ability_race/tunnel.sh
