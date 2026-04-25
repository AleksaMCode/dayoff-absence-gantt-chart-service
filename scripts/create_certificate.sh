#!/bin/bash

echo "Generating self-signed certificate and private key..."
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes

echo "Certificate generated."
echo "SHA1 fingerprint (raw OpenSSL output):"
openssl x509 -in cert.pem -noout -fingerprint -sha1

normalized_fingerprint="$(openssl x509 -in cert.pem -noout -fingerprint -sha1 | cut -d'=' -f2 | tr -d ':' | tr '[:lower:]' '[:upper:]')"
echo "SHA1 fingerprint (normalized for .env):"
echo "${normalized_fingerprint}"
echo "Use this value for SHAREPOINT_CERT_FINGERPRINT."
