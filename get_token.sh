#!/usr/bin/env bash
#
# Obtiene un Firebase ID token via email/contraseña.
# Imprime SOLO el token en stdout (los mensajes van a stderr),
# para poder capturarlo:  TOKEN=$(./get_token.sh correo@ej.com)
#
# Uso:
#   ./get_token.sh <email> [password]
#   FIREBASE_API_KEY=... ./get_token.sh <email>      # override de la API key
#
# Si no se pasa la contraseña, se pide de forma oculta.

set -euo pipefail

API_KEY="${FIREBASE_API_KEY:-AIzaSyBno2GSk4ZAb88KzcFAe9cpRJbK7lt9zdM}"

EMAIL="${1:-}"
PASSWORD="${2:-}"

if [ -z "$EMAIL" ]; then
  read -rp "Email: " EMAIL
fi
if [ -z "$PASSWORD" ]; then
  read -rsp "Password: " PASSWORD
  echo >&2
fi

RESP=$(curl -s -X POST \
  "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=$API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\",\"returnSecureToken\":true}")

# Parsea con jq si está disponible, si no con python
parse() {  # $1 = campo
  if command -v jq >/dev/null 2>&1; then
    echo "$RESP" | jq -r ".$1 // empty"
  else
    echo "$RESP" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('$1',''))"
  fi
}

TOKEN=$(parse idToken)

if [ -z "$TOKEN" ]; then
  ERR=$(parse 'error.message' 2>/dev/null || true)
  echo "Error obteniendo token: ${ERR:-respuesta inesperada}" >&2
  echo "$RESP" >&2
  exit 1
fi

# uid a stderr (informativo); token a stdout (capturable)
echo "uid=$(parse localId)" >&2
echo "$TOKEN"
