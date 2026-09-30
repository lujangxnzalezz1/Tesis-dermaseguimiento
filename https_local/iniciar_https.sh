#!/bin/sh
# Levanta la versión HTTPS para abrir la app desde el iPhone (la versión http de la Mac sigue igual).
#   App:     https://IP:8443     (puente hacia Expo en 8081)
#   Backend: https://IP:8444     (segunda instancia de la API con TLS; comparte la misma base)
# Requiere que ya estén corriendo la API (8000) y Expo web (8081).
cd "$(dirname "$0")"
IP=$(ipconfig getifaddr en0 || ipconfig getifaddr en1)
if [ ! -f certs/servidor.crt ] || [ "$(cat certs/ip_actual 2>/dev/null)" != "$IP" ]; then
  ./generar_certificados.sh
fi
pkill -f "proxy_tls.py" 2>/dev/null
pkill -f "uvicorn main:app --host 0.0.0.0 --port 8444" 2>/dev/null
sleep 1
nohup ../backend/venv/bin/python proxy_tls.py 8443 8081 > /tmp/derma_proxy.log 2>&1 &
( cd ../backend && nohup ./venv/bin/uvicorn main:app --host 0.0.0.0 --port 8444 \
    --ssl-keyfile ../https_local/certs/servidor.key --ssl-certfile ../https_local/certs/servidor.crt > /tmp/derma_api_https.log 2>&1 & )
sleep 6
echo "Listo. En el iPhone abrí:  https://$IP:8443"
