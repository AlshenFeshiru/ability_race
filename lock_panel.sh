#!/bin/bash
sed -i 's/ADMIN_LOCKED=false/ADMIN_LOCKED=true/' ~/ability_race/.env
source ~/ability_race/.env
docker stop ability_race
docker rm ability_race
docker run -d \
    --name ability_race \
    --restart unless-stopped \
    --network host \
    -v ar_data:/data \
    --tmpfs /tmp:size=256m \
    -e SERVER_PORT=28836 \
    -e DATABASE_URL=sqlite:////data/ability_race.db \
    -e GROQ_API_KEY="$GROQ_API_KEY" \
    -e SECRET_KEY="$SECRET_KEY" \
    -e ADMIN_TOKEN="$ADMIN_TOKEN" \
    -e KECCAK_CTRL="$KECCAK_CTRL" \
    -e ORGANIZER_TOKEN="$ORGANIZER_TOKEN" \
    -e ADMIN_LOCKED=true \
    ability_race:local
