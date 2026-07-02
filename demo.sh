#!/bin/bash
# Alphatracer end-to-end demo
# Usage: bash demo.sh
# Requires: curl (jq optional — falls back to python -m json.tool)

BASE="http://localhost:8011/api/v1"
EMAIL="demo_$(date +%s)@example.com"
PASSWORD="demo1234"

pretty() {
  # use jq if available, else python json.tool
  if command -v jq &>/dev/null; then
    jq .
  else
    python3 -m json.tool 2>/dev/null || cat
  fi
}

echo "=========================================="
echo "  Alphatracer API Demo"
echo "  Base: $BASE"
echo "=========================================="

# 1. Register
echo ""
echo "[1/7] Registering user: $EMAIL"
REGISTER=$(curl -s -X POST "$BASE/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"$EMAIL\", \"password\": \"$PASSWORD\", \"full_name\": \"Demo User\"}")
echo "$REGISTER" | pretty

# 2. Login (JSON)
echo ""
echo "[2/7] Logging in (JSON)..."
LOGIN=$(curl -s -X POST "$BASE/auth/login/json" \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"$EMAIL\", \"password\": \"$PASSWORD\"}")
echo "$LOGIN" | pretty

if command -v jq &>/dev/null; then
  TOKEN=$(echo "$LOGIN" | jq -r '.access_token')
else
  TOKEN=$(echo "$LOGIN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))")
fi

if [ -z "$TOKEN" ] || [ "$TOKEN" = "null" ]; then
  echo "ERROR: Could not get token. Is the server running at $BASE?"
  exit 1
fi
echo "  Token: ${TOKEN:0:40}..."

# 3. Get current user
echo ""
echo "[3/7] Current user profile..."
curl -s "$BASE/users/me" \
  -H "Authorization: Bearer $TOKEN" | pretty

# 4. Search stocks
echo ""
echo "[4/7] Searching for 'apple'..."
curl -s "$BASE/stocks/search?q=apple&limit=3" | pretty

# 5. Buy AAPL
echo ""
echo "[5/7] Buying 5 shares of AAPL @ \$175.00..."
BUY=$(curl -s -X POST "$BASE/portfolio/transactions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "stock_ticker": "AAPL",
    "type": "buy",
    "quantity": 5,
    "price_per_share": 175.00,
    "transaction_date": "2026-04-01"
  }')
echo "$BUY" | pretty

# 6. View portfolio
echo ""
echo "[6/7] Portfolio (with live prices)..."
curl -s "$BASE/portfolio" \
  -H "Authorization: Bearer $TOKEN" | pretty

# 7. Add to watchlist
echo ""
echo "[7/7] Adding TSLA to watchlist..."
curl -s -X POST "$BASE/watchlist/TSLA" \
  -H "Authorization: Bearer $TOKEN" | pretty

echo ""
echo "=========================================="
echo "  Demo complete!"
echo "  Swagger docs: http://localhost:8011/docs"
echo "=========================================="
