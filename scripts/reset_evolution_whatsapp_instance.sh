#!/usr/bin/env bash
# Delete and recreate the Evolution WhatsApp instance (same name in .env).
# Use after upgrading CONFIG_SESSION_PHONE_VERSION or when the instance is stuck on count=0 / connecting.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi
EVOLUTION_URL="${EVOLUTION_URL:-http://localhost:8080}"
EVOLUTION_API_KEY="${EVOLUTION_API_KEY:?Set EVOLUTION_API_KEY in .env}"
EVOLUTION_INSTANCE_NAME="${EVOLUTION_INSTANCE_NAME:-inika}"
BASE="${EVOLUTION_URL%/}"

echo "Evolution: $BASE | instance: $EVOLUTION_INSTANCE_NAME"
echo "DELETE instance..."
curl -sS -X DELETE "$BASE/instance/delete/$EVOLUTION_INSTANCE_NAME" \
  -H "apikey: $EVOLUTION_API_KEY" \
  -H "Content-Type: application/json" | head -c 400 || true
echo ""
echo "CREATE instance..."
curl -sS -X POST "$BASE/instance/create" \
  -H "apikey: $EVOLUTION_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"instanceName\":\"$EVOLUTION_INSTANCE_NAME\",\"integration\":\"WHATSAPP-BAILEYS\",\"qrcode\":true}" | head -c 600 || true
echo ""
echo "Done. Open the app and tap Connect WhatsApp again."
