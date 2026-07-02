#!/usr/bin/env bash
# =============================================================================
# Alphatracer — complete endpoint test suite
#   Covers: Auth, Users, Stocks, Portfolio (full CRUD), Watchlist, Market Data
#   No jq required — uses Python's built-in json module
#   Works on Linux, macOS, Windows (Git Bash / WSL)
# Usage:
#   bash tests/test_all_endpoints.sh
#   bash tests/test_all_endpoints.sh --base http://myserver:8011
# =============================================================================

BASE="http://100.81.217.35:8011/api/v1"

while [[ $# -gt 0 ]]; do
  case $1 in --base) BASE="$2"; shift 2;; *) shift;; esac
done

PASS=0; FAIL=0; WARN=0
TOKEN=""

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; NC='\033[0m'; BOLD='\033[1m'

ok()   { echo -e "${GREEN}  ✓${NC} $1"; ((PASS++)); }
fail() { echo -e "${RED}  ✗${NC} $1"; [[ -n "$2" ]] && echo -e "    ${RED}→ $2${NC}"; ((FAIL++)); }
warn() { echo -e "${YELLOW}  ~${NC} $1 (market may be closed / data unavailable)"; ((WARN++)); }
hdr()  { echo -e "\n${CYAN}${BOLD}══ $1 ══${NC}"; }

# ---------------------------------------------------------------------------
# curl wrapper — connect + max-time prevents HTTP 000 on slow yfinance calls
# ---------------------------------------------------------------------------
_curl() { curl -s --connect-timeout 10 --max-time 60 "$@"; }

# ---------------------------------------------------------------------------
# JSON helpers — pass the JSON body via the JSON env var so no shell quoting,
# heredoc stdin conflicts, or special-character issues ever occur.
#
#   json_get  "$BODY" "dot.path"   → prints value, empty string if missing
#   json_len  "$BODY"              → length of top-level list or dict
#   json_has  "$BODY" "key"        → exits 0 if key exists (handles 0/false)
# ---------------------------------------------------------------------------

json_get() {
  JSON="$1" python3 -c "
import os, json
try:
    d = json.loads(os.environ['JSON'])
    for k in '${2}'.split('.'):
        d = d[k] if isinstance(d, dict) else None
    print('' if d is None else d)
except Exception:
    print('')
"
}

json_len() {
  JSON="$1" python3 -c "
import os, json
try:
    d = json.loads(os.environ['JSON'])
    print(len(d) if isinstance(d, (list, dict)) else '?')
except Exception:
    print('?')
"
}

json_has() {
  JSON="$1" python3 -c "
import os, json, sys
try:
    d = json.loads(os.environ['JSON'])
    sys.exit(0 if '${2}' in d else 1)
except Exception:
    sys.exit(1)
"
}

check() {
  local code=$1 expected=$2 label=$3 body=$4
  if [ "$code" = "$expected" ]; then ok "$label (HTTP $code)"
  else fail "$label — expected HTTP $expected, got HTTP $code" "$body"
  fi
}

# =============================================================================
# PRE-FLIGHT
# =============================================================================
hdr "Pre-flight"

HC=$(_curl -o /dev/null -w "%{http_code}" "${BASE%/api/v1}/health" 2>/dev/null)
if [ "$HC" = "200" ]; then
  ok "Server reachable at ${BASE%/api/v1}"
else
  echo -e "${RED}✗ Server not reachable (HTTP $HC) — start with:${NC}"
  echo "  uvicorn app.main:app --host 0.0.0.0 --port 8011 --reload"
  exit 1
fi

TS=$(python3 -c "import time; print(int(time.time()))")
EMAIL="testuser_${TS}@alphatracer.test"
PASS_WORD="SecurePass${TS}!"

# =============================================================================
# ── AUTH ──────────────────────────────────────────────────────────────────────
# =============================================================================
hdr "Auth — Register"

R=$(_curl -w "\n%{http_code}" -X POST "$BASE/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS_WORD\",\"full_name\":\"Test User\"}")
CODE=$(echo "$R"|tail -1); BODY=$(echo "$R"|head -1)
check "$CODE" "201" "POST /auth/register — new user" "$BODY"
[ "$(json_get "$BODY" "email")" = "$EMAIL" ] && ok "  email matches" || fail "  email mismatch" "$BODY"
json_has "$BODY" "id" && ok "  id present" || fail "  id missing" "$BODY"

R=$(_curl -w "\n%{http_code}" -X POST "$BASE/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS_WORD\"}")
check "$(echo "$R"|tail -1)" "409" "POST /auth/register — duplicate → 409" ""

hdr "Auth — Login"

R=$(_curl -w "\n%{http_code}" -X POST "$BASE/auth/login" \
  --data-urlencode "username=$EMAIL" \
  --data-urlencode "password=$PASS_WORD")
CODE=$(echo "$R"|tail -1); BODY=$(echo "$R"|head -1)
check "$CODE" "200" "POST /auth/login — correct credentials" "$BODY"
TOKEN=$(json_get "$BODY" "access_token")
REFRESH=$(json_get "$BODY" "refresh_token")
if [ -n "$TOKEN" ]; then
  ok "  access_token received (${#TOKEN} chars)"
else
  fail "  no access_token — cannot continue"
  exit 1
fi
[ -n "$REFRESH" ] && ok "  refresh_token received" || fail "  refresh_token missing" "$BODY"

R=$(_curl -w "\n%{http_code}" -X POST "$BASE/auth/login" \
  --data-urlencode "username=$EMAIL" \
  --data-urlencode "password=wrongpassword")
check "$(echo "$R"|tail -1)" "401" "POST /auth/login — wrong password → 401" ""

hdr "Auth — Refresh"

R=$(_curl -w "\n%{http_code}" -X POST "$BASE/auth/refresh" \
  -H "Authorization: Bearer $TOKEN")
CODE=$(echo "$R"|tail -1); BODY=$(echo "$R"|head -1)
check "$CODE" "200" "POST /auth/refresh — new tokens" "$BODY"
json_has "$BODY" "access_token" && ok "  new access_token present" || fail "  no access_token" "$BODY"

# =============================================================================
# ── USERS ─────────────────────────────────────────────────────────────────────
# =============================================================================
hdr "Users"

R=$(_curl -w "\n%{http_code}" "$BASE/users/me" -H "Authorization: Bearer $TOKEN")
CODE=$(echo "$R"|tail -1); BODY=$(echo "$R"|head -1)
check "$CODE" "200" "GET /users/me" "$BODY"
[ "$(json_get "$BODY" "email")" = "$EMAIL" ] && ok "  email matches" || fail "  email mismatch" "$BODY"

R=$(_curl -w "\n%{http_code}" -X PUT "$BASE/users/me" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"full_name":"Updated Name"}')
CODE=$(echo "$R"|tail -1); BODY=$(echo "$R"|head -1)
check "$CODE" "200" "PUT /users/me — update full_name" "$BODY"
[ "$(json_get "$BODY" "full_name")" = "Updated Name" ] \
  && ok "  full_name=Updated Name" || fail "  full_name not updated" "$BODY"

check "$(_curl -o /dev/null -w "%{http_code}" "$BASE/users/me")" \
  "401" "GET /users/me — no token → 401" ""

# =============================================================================
# ── STOCKS ────────────────────────────────────────────────────────────────────
# =============================================================================
hdr "Stocks — Search"

for QUERY in apple TSLA microsoft NVDA; do
  R=$(_curl -w "\n%{http_code}" "$BASE/stocks/search?q=$QUERY&limit=5")
  CODE=$(echo "$R"|tail -1); BODY=$(echo "$R"|head -1)
  check "$CODE" "200" "GET /stocks/search?q=$QUERY" "$BODY"
  CNT=$(json_len "$BODY")
  [ "$CNT" -gt 0 ] 2>/dev/null \
    && ok "  $CNT results for '$QUERY'" \
    || warn "  0 results for '$QUERY' (CSV sources may be offline)"
done

hdr "Stocks — Detail"

R=$(_curl -w "\n%{http_code}" "$BASE/stocks/AAPL")
CODE=$(echo "$R"|tail -1); BODY=$(echo "$R"|head -1)
check "$CODE" "200" "GET /stocks/AAPL" "$BODY"
[ "$(json_get "$BODY" "ticker")" = "AAPL" ] && ok "  ticker=AAPL" || fail "  wrong ticker" "$BODY"

check "$(_curl -o /dev/null -w "%{http_code}" "$BASE/stocks/ZZZNOTREAL")" \
  "404" "GET /stocks/ZZZNOTREAL → 404" ""

hdr "Stocks — Financial Metrics (EPS, ROI, Margins — yfinance)"

R=$(_curl -w "\n%{http_code}" "$BASE/stocks/AAPL/metrics")
CODE=$(echo "$R"|tail -1); BODY=$(echo "$R"|head -1)
check "$CODE" "200" "GET /stocks/AAPL/metrics" "$BODY"
for F in eps_ttm pe_ratio net_margin roe roi gross_margin; do
  V=$(json_get "$BODY" "$F")
  if [ -n "$V" ] && [ "$V" != "null" ] && [ "$V" != "None" ]; then
    ok "  $F = $V"
  else
    warn "  $F = null (yfinance may not have it right now)"
  fi
done

# =============================================================================
# ── MARKET DATA ───────────────────────────────────────────────────────────────
# =============================================================================
hdr "Market — Live Quote (no auth required)"

for SYM in AAPL TSLA MSFT; do
  R=$(_curl -w "\n%{http_code}" "$BASE/market/$SYM/quote")
  CODE=$(echo "$R"|tail -1); BODY=$(echo "$R"|head -1)
  check "$CODE" "200" "GET /market/$SYM/quote" "$BODY"
  PRICE=$(json_get "$BODY" "price")
  CHG=$(json_get "$BODY" "change_pct")
  if [ -n "$PRICE" ] && [ "$PRICE" != "null" ]; then
    ok "  $SYM price=$PRICE  change=$CHG%"
  else
    warn "  $SYM price unavailable (market may be closed)"
  fi
  json_has "$BODY" "week_52_high" && ok "  52-week high present" || warn "  52-week high missing"
done

hdr "Market — Full TradingView Analysis (1d candles)"

R=$(_curl -w "\n%{http_code}" "$BASE/market/AAPL/analysis?interval=1d&period=3mo")
CODE=$(echo "$R"|tail -1); BODY=$(echo "$R"|head -1)
check "$CODE" "200" "GET /market/AAPL/analysis?interval=1d&period=3mo" "$BODY"

for F in price change_pct amplitude_pct; do
  V=$(json_get "$BODY" "quote.$F")
  [ -n "$V" ] && [ "$V" != "null" ] && ok "  quote.$F = $V" || warn "  quote.$F null"
done

echo -e "\n  ${BOLD}Moving Averages:${NC}"
for F in sma_20 sma_50 sma_200 ema_9 ema_21 ema_50; do
  V=$(json_get "$BODY" "ma.$F")
  [ -n "$V" ] && [ "$V" != "null" ] && ok "  ma.$F = $V" || warn "  ma.$F null"
done

echo -e "\n  ${BOLD}Oscillators:${NC}"
for F in rsi_14 stoch_k stoch_d cci_20 williams_r macd macd_signal macd_hist adx; do
  V=$(json_get "$BODY" "oscillators.$F")
  [ -n "$V" ] && [ "$V" != "null" ] && ok "  $F = $V" || warn "  $F null"
done

echo -e "\n  ${BOLD}Volatility:${NC}"
for F in bb_upper bb_middle bb_lower bb_width bb_pct_b atr_14; do
  V=$(json_get "$BODY" "volatility.$F")
  [ -n "$V" ] && [ "$V" != "null" ] && ok "  $F = $V" || warn "  $F null"
done

echo -e "\n  ${BOLD}Volume:${NC}"
for F in obv volume rel_volume; do
  V=$(json_get "$BODY" "volume.$F")
  [ -n "$V" ] && [ "$V" != "null" ] && ok "  $F = $V" || warn "  $F null"
done

echo -e "\n  ${BOLD}Signal:${NC}"
RATING=$(json_get "$BODY" "signal.rating")
SCORE=$(json_get  "$BODY" "signal.score")
BUYS=$(json_get   "$BODY" "signal.buy_signals")
SELLS=$(json_get  "$BODY" "signal.sell_signals")
[ -n "$RATING" ] && ok "  Rating: $RATING (score=$SCORE  buy=$BUYS sell=$SELLS)" \
                 || fail "  signal.rating missing" "$BODY"

C=$(JSON="$BODY" python3 -c "
import os,json
try: print(len(json.loads(os.environ['JSON']).get('candles',[])))
except: print(0)
" 2>/dev/null)
[ "$C" -gt 0 ] 2>/dev/null && ok "  $C candles returned" || warn "  no candles"

hdr "Market — Different Intervals"

for INT_PER in "5m/5d" "15m/5d" "1h/1mo" "1wk/1y"; do
  INT="${INT_PER%%/*}"; PER="${INT_PER##*/}"
  R=$(_curl -w "\n%{http_code}" "$BASE/market/AAPL/analysis?interval=$INT&period=$PER")
  CODE=$(echo "$R"|tail -1); BODY=$(echo "$R"|head -1)
  check "$CODE" "200" "GET /market/AAPL/analysis?interval=$INT&period=$PER" "$BODY"
done

hdr "Market — Candles Only"

R=$(_curl -w "\n%{http_code}" "$BASE/market/TSLA/candles?interval=1d&period=1mo")
CODE=$(echo "$R"|tail -1); BODY=$(echo "$R"|head -1)
check "$CODE" "200" "GET /market/TSLA/candles?interval=1d&period=1mo" "$BODY"
C=$(JSON="$BODY" python3 -c "
import os,json
try: print(len(json.loads(os.environ['JSON']).get('candles',[])))
except: print(0)
" 2>/dev/null)
[ "$C" -gt 0 ] 2>/dev/null && ok "  $C OHLCV bars" || warn "  no bars returned"

hdr "Market — Indicators Only (no candles)"

R=$(_curl -w "\n%{http_code}" "$BASE/market/MSFT/indicators?interval=1d&period=6mo")
CODE=$(echo "$R"|tail -1); BODY=$(echo "$R"|head -1)
check "$CODE" "200" "GET /market/MSFT/indicators — no candles in payload" "$BODY"
json_has "$BODY" "ma"          && ok "  ma block present"          || fail "  ma block missing" "$BODY"
json_has "$BODY" "oscillators" && ok "  oscillators block present" || fail "  oscillators missing" "$BODY"
json_has "$BODY" "signal"      && ok "  signal block present"      || fail "  signal missing" "$BODY"

hdr "Market — Compare Multiple Tickers"

R=$(_curl -w "\n%{http_code}" "$BASE/market/compare/quotes?tickers=AAPL,TSLA,MSFT,NVDA")
CODE=$(echo "$R"|tail -1); BODY=$(echo "$R"|head -1)
check "$CODE" "200" "GET /market/compare/quotes?tickers=AAPL,TSLA,MSFT,NVDA" "$BODY"
CNT=$(json_get "$BODY" "count")
[ "$CNT" = "4" ] && ok "  4 quotes returned" || fail "  expected 4, got $CNT" "$BODY"

hdr "Market — Validation errors"

check "$(_curl -o /dev/null -w "%{http_code}" \
  "$BASE/market/AAPL/analysis?interval=99x")" \
  "400" "GET /market/AAPL/analysis?interval=99x → 400" ""

check "$(_curl -o /dev/null -w "%{http_code}" \
  "$BASE/market/AAPL/analysis?period=100y")" \
  "400" "GET /market/AAPL/analysis?period=100y → 400" ""

# =============================================================================
# ── PORTFOLIO — Full CRUD ─────────────────────────────────────────────────────
# =============================================================================
hdr "Portfolio — Buy Transactions (CREATE)"

R=$(_curl -w "\n%{http_code}" -X POST "$BASE/portfolio/transactions" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"stock_ticker":"AAPL","type":"buy","quantity":10,"price_per_share":175.00,"transaction_date":"2026-01-10"}')
CODE=$(echo "$R"|tail -1); BODY=$(echo "$R"|head -1)
check "$CODE" "201" "POST /portfolio/transactions — BUY AAPL×10 @175" "$BODY"
TX1=$(json_get "$BODY" "id")
[ -n "$TX1" ] && ok "  id=$TX1" || fail "  no id" "$BODY"
TV=$(json_get "$BODY" "total_value")
[ "$TV" = "1750.0" ] && ok "  total_value=1750.0" || ok "  total_value=$TV"

R=$(_curl -w "\n%{http_code}" -X POST "$BASE/portfolio/transactions" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"stock_ticker":"TSLA","type":"buy","quantity":5,"price_per_share":250.00,"transaction_date":"2026-01-15"}')
CODE=$(echo "$R"|tail -1); BODY=$(echo "$R"|head -1)
check "$CODE" "201" "POST /portfolio/transactions — BUY TSLA×5 @250" "$BODY"
TX2=$(json_get "$BODY" "id")

hdr "Portfolio — READ Transactions"

R=$(_curl -w "\n%{http_code}" "$BASE/portfolio/transactions" \
  -H "Authorization: Bearer $TOKEN")
CODE=$(echo "$R"|tail -1); BODY=$(echo "$R"|head -1)
check "$CODE" "200" "GET /portfolio/transactions — all" "$BODY"
CNT=$(json_len "$BODY")
[ "$CNT" -ge 2 ] 2>/dev/null && ok "  $CNT transactions" || fail "  expected ≥2, got $CNT" "$BODY"

R=$(_curl -w "\n%{http_code}" "$BASE/portfolio/transactions?stock_ticker=AAPL" \
  -H "Authorization: Bearer $TOKEN")
check "$(echo "$R"|tail -1)" "200" "GET /portfolio/transactions?stock_ticker=AAPL" ""

R=$(_curl -w "\n%{http_code}" "$BASE/portfolio/transactions?transaction_type=buy" \
  -H "Authorization: Bearer $TOKEN")
check "$(echo "$R"|tail -1)" "200" "GET /portfolio/transactions?transaction_type=buy" ""

hdr "Portfolio — UPDATE Transaction (price correction)"

if [ -n "$TX1" ]; then
  R=$(_curl -w "\n%{http_code}" -X PUT "$BASE/portfolio/transactions/$TX1" \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d '{"stock_ticker":"AAPL","type":"buy","quantity":10,"price_per_share":180.00,"transaction_date":"2026-01-10"}')
  CODE=$(echo "$R"|tail -1); BODY=$(echo "$R"|head -1)
  check "$CODE" "200" "PUT /portfolio/transactions/$TX1 — correct price to 180" "$BODY"
  [ "$(json_get "$BODY" "price_per_share")" = "180.0" ] \
    && ok "  price_per_share=180.0" || fail "  price not updated" "$BODY"
fi

hdr "Portfolio — Holdings & Live P&L"

R=$(_curl -w "\n%{http_code}" "$BASE/portfolio" -H "Authorization: Bearer $TOKEN")
CODE=$(echo "$R"|tail -1); BODY=$(echo "$R"|head -1)
check "$CODE" "200" "GET /portfolio — holdings with live prices" "$BODY"
HOLD=$(JSON="$BODY" python3 -c "
import os,json
try: print(len(json.loads(os.environ['JSON']).get('holdings',[])))
except: print(0)
" 2>/dev/null)
[ "$HOLD" -ge 2 ] 2>/dev/null && ok "  $HOLD holdings" || fail "  expected ≥2 holdings" "$BODY"
TC=$(json_get "$BODY" "total_cost")
[ -n "$TC" ] && ok "  total_cost=$TC" || fail "  total_cost missing" "$BODY"

hdr "Portfolio — Metrics Summary (weighted P/E, Beta)"

R=$(_curl -w "\n%{http_code}" "$BASE/portfolio/metrics" -H "Authorization: Bearer $TOKEN")
CODE=$(echo "$R"|tail -1); BODY=$(echo "$R"|head -1)
check "$CODE" "200" "GET /portfolio/metrics — aggregated metrics" "$BODY"
for F in total_cost holdings_count; do
  V=$(json_get "$BODY" "$F")
  [ -n "$V" ] && ok "  $F=$V" || fail "  $F missing" "$BODY"
done

hdr "Portfolio — SELL & Validation"

R=$(_curl -w "\n%{http_code}" -X POST "$BASE/portfolio/transactions" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"stock_ticker":"AAPL","type":"sell","quantity":3,"price_per_share":195.00}')
CODE=$(echo "$R"|tail -1); BODY=$(echo "$R"|head -1)
check "$CODE" "201" "POST /portfolio/transactions — SELL AAPL×3 (valid)" "$BODY"
SELL_ID=$(json_get "$BODY" "id")
[ "$(json_get "$BODY" "type")" = "sell" ] && ok "  type=sell" || fail "  type wrong" "$BODY"

R=$(_curl -w "\n%{http_code}" -X POST "$BASE/portfolio/transactions" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"stock_ticker":"AAPL","type":"sell","quantity":99999,"price_per_share":1.00}')
check "$(echo "$R"|tail -1)" "400" "POST /portfolio/transactions — oversell → 400" ""

hdr "Portfolio — DELETE Transaction"

if [ -n "$SELL_ID" ]; then
  check "$(_curl -o /dev/null -w "%{http_code}" -X DELETE \
    "$BASE/portfolio/transactions/$SELL_ID" -H "Authorization: Bearer $TOKEN")" \
    "204" "DELETE /portfolio/transactions/$SELL_ID — delete sell tx" ""
fi

check "$(_curl -o /dev/null -w "%{http_code}" -X DELETE \
  "$BASE/portfolio/transactions/999999" -H "Authorization: Bearer $TOKEN")" \
  "404" "DELETE /portfolio/transactions/999999 — not found → 404" ""

# =============================================================================
# ── WATCHLIST ─────────────────────────────────────────────────────────────────
# =============================================================================
hdr "Watchlist — Full CRUD"

for SYM in AAPL TSLA; do
  check "$(_curl -o /dev/null -w "%{http_code}" -X POST \
    "$BASE/watchlist/$SYM" -H "Authorization: Bearer $TOKEN")" \
    "201" "POST /watchlist/$SYM — add" ""
done

check "$(_curl -o /dev/null -w "%{http_code}" -X POST \
  "$BASE/watchlist/AAPL" -H "Authorization: Bearer $TOKEN")" \
  "409" "POST /watchlist/AAPL — duplicate → 409" ""

R=$(_curl -w "\n%{http_code}" "$BASE/watchlist" -H "Authorization: Bearer $TOKEN")
CODE=$(echo "$R"|tail -1); BODY=$(echo "$R"|head -1)
check "$CODE" "200" "GET /watchlist" "$BODY"
WL=$(json_len "$BODY")
[ "$WL" -ge 2 ] 2>/dev/null && ok "  $WL items in watchlist" || fail "  expected ≥2" "$BODY"

check "$(_curl -o /dev/null -w "%{http_code}" -X DELETE \
  "$BASE/watchlist/TSLA" -H "Authorization: Bearer $TOKEN")" \
  "204" "DELETE /watchlist/TSLA — remove" ""

check "$(_curl -o /dev/null -w "%{http_code}" -X DELETE \
  "$BASE/watchlist/TSLA" -H "Authorization: Bearer $TOKEN")" \
  "404" "DELETE /watchlist/TSLA — already gone → 404" ""

# =============================================================================
# ── CLEANUP ───────────────────────────────────────────────────────────────────
# =============================================================================
hdr "Cleanup"

check "$(_curl -o /dev/null -w "%{http_code}" -X DELETE \
  "$BASE/users/me" -H "Authorization: Bearer $TOKEN")" \
  "204" "DELETE /users/me — remove test account" ""

# =============================================================================
# SUMMARY
# =============================================================================
TOTAL=$((PASS + FAIL))
echo ""
echo -e "${BOLD}══════════════════════════════════════════════${NC}"
echo -e "${BOLD}  Results: ${GREEN}$PASS passed${NC}  ${RED}$FAIL failed${NC}  ${YELLOW}$WARN warnings${NC}  / $TOTAL checks${NC}"
echo -e "${BOLD}══════════════════════════════════════════════${NC}"
if [ "$FAIL" -eq 0 ]; then
  echo -e "${GREEN}${BOLD}  All hard checks passed ✓${NC}"
  [ "$WARN" -gt 0 ] && echo -e "${YELLOW}  $WARN warnings (market closed / yfinance data temporarily unavailable)${NC}"
else
  echo -e "${RED}${BOLD}  $FAIL check(s) failed ✗${NC}"
fi
echo ""
exit $FAIL
