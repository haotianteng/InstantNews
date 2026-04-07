#!/bin/bash
# Generate certificates for AWS Client VPN using openssl
#
# Usage: ./scripts/generate-vpn-certs.sh
# Output: certs/vpn/ with CA, server, and client certs
# Next:   Upload to ACM, set ARNs in cdk.json, uncomment VPN in stack.py

set -e

CERT_DIR="certs/vpn"
mkdir -p "$CERT_DIR"

if [ -f "$CERT_DIR/ca.crt" ]; then
    echo "Certs already exist in $CERT_DIR — delete them first to regenerate."
    exit 0
fi

echo "=== Generating CA ==="
openssl req -new -x509 -days 3650 -nodes \
    -keyout "$CERT_DIR/ca.key" \
    -out "$CERT_DIR/ca.crt" \
    -subj "/CN=InstantNews VPN CA"

echo "=== Generating Server Certificate ==="
openssl req -new -nodes \
    -keyout "$CERT_DIR/server.key" \
    -out "$CERT_DIR/server.csr" \
    -subj "/CN=vpn.instnews.net"

openssl x509 -req -days 3650 \
    -in "$CERT_DIR/server.csr" \
    -CA "$CERT_DIR/ca.crt" \
    -CAkey "$CERT_DIR/ca.key" \
    -CAcreateserial \
    -out "$CERT_DIR/server.crt"

echo "=== Generating Client Certificate ==="
openssl req -new -nodes \
    -keyout "$CERT_DIR/client.key" \
    -out "$CERT_DIR/client.csr" \
    -subj "/CN=admin-client"

openssl x509 -req -days 3650 \
    -in "$CERT_DIR/client.csr" \
    -CA "$CERT_DIR/ca.crt" \
    -CAkey "$CERT_DIR/ca.key" \
    -CAcreateserial \
    -out "$CERT_DIR/client.crt"

# Cleanup CSRs
rm -f "$CERT_DIR"/*.csr "$CERT_DIR"/*.srl

echo ""
echo "=== Certificates generated in $CERT_DIR ==="
echo "  CA:     $CERT_DIR/ca.crt"
echo "  Server: $CERT_DIR/server.crt + server.key"
echo "  Client: $CERT_DIR/client.crt + client.key"
echo ""
echo "=== Step 1: Upload to ACM ==="
echo ""
echo "# Server cert:"
echo "aws acm import-certificate \\"
echo "  --certificate fileb://$CERT_DIR/server.crt \\"
echo "  --private-key fileb://$CERT_DIR/server.key \\"
echo "  --certificate-chain fileb://$CERT_DIR/ca.crt \\"
echo "  --region us-east-1"
echo ""
echo "# Client cert:"
echo "aws acm import-certificate \\"
echo "  --certificate fileb://$CERT_DIR/client.crt \\"
echo "  --private-key fileb://$CERT_DIR/client.key \\"
echo "  --certificate-chain fileb://$CERT_DIR/ca.crt \\"
echo "  --region us-east-1"
echo ""
echo "=== Step 2: Add ARNs to infra/cdk.json ==="
echo '  "context": {'
echo '    "vpn_server_cert_arn": "arn:aws:acm:...(from server upload)...",'
echo '    "vpn_client_cert_arn": "arn:aws:acm:...(from client upload)..."'
echo '  }'
echo ""
echo "=== Step 3: Uncomment VPN section in infra/stack.py, then: cdk deploy ==="
