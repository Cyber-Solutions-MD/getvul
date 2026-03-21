#!/bin/sh
# Generate a self-signed cert if none exists so nginx can start with HTTPS enabled
if [ ! -f /etc/nginx/certs/server.crt ]; then
    echo "No TLS certificate found, generating self-signed for localhost..."
    mkdir -p /etc/nginx/certs
    openssl req -x509 -newkey rsa:2048 \
        -keyout /etc/nginx/certs/server.key \
        -out /etc/nginx/certs/server.crt \
        -days 365 -nodes \
        -subj "/CN=localhost/O=GetVul" \
        -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" 2>/dev/null
    echo "Self-signed certificate generated."
fi

exec nginx -g "daemon off;"
