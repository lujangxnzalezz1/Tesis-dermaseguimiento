#!/bin/sh
# Genera (una sola vez) una autoridad de certificación local y, cada vez que cambia la red, un
# certificado para la IP actual de la Mac. El iPhone confía en la autoridad, así que al cambiar de
# red solo se regenera el certificado del servidor: no hay que volver a instalar nada en el teléfono.
set -e
cd "$(dirname "$0")"
mkdir -p certs
IP=$(ipconfig getifaddr en0 || ipconfig getifaddr en1)
[ -z "$IP" ] && { echo "No se encontró la IP de la red."; exit 1; }

if [ ! -f certs/ca.key ]; then
  openssl genrsa -out certs/ca.key 2048 2>/dev/null
  openssl req -x509 -new -key certs/ca.key -sha256 -days 825 -out certs/DermaSeguimiento-CA.pem \
    -subj "/CN=DermaSeguimiento Desarrollo Local CA/O=Tesis UNIDA" \
    -addext "basicConstraints=critical,CA:TRUE" -addext "keyUsage=critical,keyCertSign,cRLSign"
  echo "Autoridad creada: https_local/certs/DermaSeguimiento-CA.pem (esta es la que se instala en el iPhone)"
fi

openssl genrsa -out certs/servidor.key 2048 2>/dev/null
openssl req -new -key certs/servidor.key -out certs/servidor.csr -subj "/CN=$IP" 2>/dev/null
printf "subjectAltName=IP:%s,IP:127.0.0.1,DNS:localhost\nextendedKeyUsage=serverAuth\nkeyUsage=critical,digitalSignature,keyEncipherment\nbasicConstraints=CA:FALSE\n" "$IP" > certs/ext.cnf
openssl x509 -req -in certs/servidor.csr -CA certs/DermaSeguimiento-CA.pem -CAkey certs/ca.key -CAcreateserial \
  -out certs/servidor.crt -days 365 -sha256 -extfile certs/ext.cnf 2>/dev/null
echo "$IP" > certs/ip_actual
echo "Certificado del servidor listo para $IP"
