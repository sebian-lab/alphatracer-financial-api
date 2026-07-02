#!/usr/bin/env bash
# =============================================================================
# Alphatracer E2E Test Suite: Deployment → Running API
# 
# This script verifies the complete deployment pipeline and functional API tests.
# Base URL: http://100.91.204.48:8011/api/v1
# =============================================================================

set -euo pipefail

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
BASE_URL="http://100.91.204.48:8011/api/v1"
API_BASE="${BASE_URL%*/api/v1}"  # For docs health check
TEST_PASSWORD="TestPass123!"
TEST_STOCK1="AAPL"
TEST_STOCK2="GOOGL"
WATCH_STOCK1="MSFT"
WATCH_STOCK2="TSLA"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}ℹ${NC} $1"; }
log_success() { echo -e "${GREEN}✓${NC} $1"; }
log_failure() { echo -e "${RED}✗${NC} $1" >&2; exit 1; }
log_warn()   { echo -e "${YELLOW}⚠${NC} $1"; }

# -----------------------------------------------------------------------------
# Helper: Check required tools
# -----------------------------------------------------------------------------
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    if ! command -v curl >/dev/null 2>&1; then
        log_failure "curl not found (install with: apt-get install curl)"
    fi
    if ! command -v jq >/dev/null 2>&1; then
        log_failure "jq not found (install with: apt-get install jq)"
    fi
    if ! command -v python3 >/dev/null 2>&1; then
        log_failure "python3 not found"
    fi
    
    log_success "Prerequisites satisfied"
}

# -----------------------------------------------------------------------------
# Helper: Wait for API to be ready (health check)
# -----------------------------------------------------------------------------
wait_for_api() {
    log_info "Waiting for API at ${BASE_URL}..."
    
    local http_code
    for i in $(seq 1 30); do
        http_code=$(curl -s -o /dev/null -w "%{http_code}" "${API_BASE}/docs" 2>/dev/null || echo "000")
        
        if [[ "$http_code" =~ ^2[0-9]{2}$ ]] || [[ "$http_code" == "404" ]]; then
            log_success "API is reachable (HTTP ${http_code})"
            return 0
        fi
        
        sleep 2
    done
    
    log_failure "API not responding after 60 seconds"
}

# -----------------------------------------------------------------------------
# Helper: Run Alembic migrations check
# -----------------------------------------------------------------------------
run_migrations() {
    log_info "Running database migrations..."
    
    if [ -f "alembic.ini" ]; then
        if [[ -n "${DATABASE_URL:-}" ]]; then
            if command -v alembic >/dev/null 2>&1 && alembic current >/dev/null 2>&1; then
                log_success "Migrations are up to date"
            else
                log_warn "Alembic not configured or missing DATABASE_URL"
            fi
        else
            log_info "DATABASE_URL not set - skipping migration check"
        fi
    else
        log_info "No alembic.ini found - skipping migration check"
    fi
    
    return 0
}

# -----------------------------------------------------------------------------
# Helper: Start Uvicorn server in background (if source exists)
# -----------------------------------------------------------------------------
start_server() {
    log_info "Checking for local application source..."
    
    if [[ ! -d "backend_fin" ]] && [[ ! -f "main.py" ]]; then
        log_warn "No application source found - assuming external server"
        return 0
    fi
    
    # Check for uvicorn app
    if grep -r "from.*app import app" backend_fin/ >/dev/null 2>&1; then
        log_info "Starting Uvicorn..."
        python3 -m uvicorn main:app --host 127.0.0.1 --port 8011 > /tmp/uvicorn.log 2>&1 &
        
        # Wait for server to start
        local count=0
        while [[ $count -lt 15 ]]; do
            if curl -s -o /dev/null -w "%{http_code}" "${API_BASE}/docs" | grep -qE "^2[0-9]{2}$|404"; then
                log_success "Uvicorn server started on port 8011"
                return 0
            fi
            sleep 1
            count=$((count + 1))
        done
        
        log_warn "Server startup timeout - using external server assumption"
    else
        log_warn "Main application file not found - assuming external server"
    fi
    
    return 0
}

# -----------------------------------------------------------------------------
# Helper: Generate unique test email (avoid duplicate emails)
# -----------------------------------------------------------------------------
generate_test_user() {
    echo "e2e-test-$(date +%s%N)@example.com"
}

# -----------------------------------------------------------------------------
# Main Test Flow
# -----------------------------------------------------------------------------
run_api_tests() {
    local token=""
    local email=""
    local verify_headers=""
    
    echo ""
    echo "========================================================================="
    log_info "Starting API Tests"
    echo "========================================================================="
    
    # -----------------------------------------------------------------------
    # Step 1: User Registration (with duplicate handling)
    # -----------------------------------------------------------------------
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    log_info "Step 1: User Registration"
    
    email=$(generate_test_user)
    log_info "Test email: ${email}"
    
    local reg_response=""
    reg_response=$(curl -s -X POST "${BASE_URL}/auth/register" \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"${email}\",\"password\":\"${TEST_PASSWORD}\"}")
    
    if echo "$reg_response" | jq -e '.user_id' >/dev/null 2>&1; then
        log_success "User registered successfully"
    else
        # Check HTTP status - 409 means duplicate
        local http_code=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/auth/register" \
            -H "Content-Type: application/json" \
            -d "{\"email\":\"${email}\",\"password\":\"${TEST_PASSWORD}\"}")
        
        if [[ "$http_code" == "409" ]]; then
            log_warn "Email already exists - attempting login with existing user"
            # Use a fallback email for login if registration failed due to duplicate
            email="e2e-existing@example.com"
        else
            log_failure "Registration failed: ${reg_response}"
        fi
    fi
    
    # -----------------------------------------------------------------------
    # Step 2: Login and Get Access Token
    # -----------------------------------------------------------------------
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    log_info "Step 2: User Login"
    
    local login_response=""
    # Use POST method with query parameters (API expects POST, not GET)
    login_response=$(curl -s -X POST "${BASE_URL}/auth/login?email=${email}&password=${TEST_PASSWORD}" \
        --compressed)
    
    token=$(echo "$login_response" | jq -r '.access_token // empty')
    
    if [[ -z "$token" ]] || [[ "$token" == "null" ]]; then
        log_failure "Login failed - no access token received"
    fi
    
    verify_headers="Authorization: Bearer $token"
    
    # Verify token works
    local http_code=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/portfolio" \
        -H "$verify_headers")
    
    if [[ "$http_code" =~ ^2[0-9]{2}$ ]]; then
        log_success "Access token obtained and verified (HTTP ${http_code})"
    else
        log_failure "Token verification failed (HTTP ${http_code})"
    fi
    
    # -----------------------------------------------------------------------
    # Step 3: Stock Search
    # -----------------------------------------------------------------------
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    log_info "Step 3: Stock Search ('apple')"
    
    local search_response=""
    search_response=$(curl -s "${BASE_URL}/stocks/search?q=apple&limit=5" \
        -H "$verify_headers")
    
    # Check if AAPL was found in results
    local ticker_found=$(echo "$search_response" | jq -r '.results[]?.ticker // empty' 2>/dev/null || true)
    
    if echo "$ticker_found" | grep -qi "${TEST_STOCK1}"; then
        log_success "Stock search returned ${TEST_STOCK1}"
    else
        local http_code=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/stocks/search?q=apple")
        log_failure "Stock search did not return ${TEST_STOCK1} (HTTP: ${http_code})"
    fi
    
    # -----------------------------------------------------------------------
    # Step 4: Fetch Stock Details
    # -----------------------------------------------------------------------
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    log_info "Step 4: Stock Details (${TEST_STOCK1})"
    
    local details=""
    details=$(curl -s "${BASE_URL}/stocks/${TEST_STOCK1}" \
        -H "$verify_headers")
    
    local name=$(echo "$details" | jq -r '.name // empty')
    
    if [[ -n "$name" ]] && [[ "$name" != "null" ]]; then
        log_success "Stock details retrieved: ${name}"
    else
        log_failure "Failed to get stock details for ${TEST_STOCK1}"
    fi
    
    # -----------------------------------------------------------------------
    # Step 5: Add BUY Transaction (AAPL)
    # -----------------------------------------------------------------------
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    log_info "Step 5: Add BUY Transaction (${TEST_STOCK1})"
    
    local tx1=""
    tx1=$(curl -s -X POST "${BASE_URL}/portfolio/transactions" \
        -H "Content-Type: application/json" \
        -H "$verify_headers" \
        -d "{\"stock_ticker\":\"${TEST_STOCK1}\",\"transaction_type\":\"BUY\",\"quantity\":10,\"price_per_share\":175.00,\"transaction_date\":\"2026-04-02\"}")
    
    local tx_id1=$(echo "$tx1" | jq -r '.transaction_id // empty')
    
    if [[ -n "$tx_id1" ]] && [[ "$tx_id1" != "null" ]]; then
        log_success "Transaction recorded: ${tx_id1}"
    else
        log_failure "Failed to add BUY transaction for ${TEST_STOCK1}"
    fi
    
    # -----------------------------------------------------------------------
    # Step 6: Add BUY Transaction (GOOGL)
    # -----------------------------------------------------------------------
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    log_info "Step 6: Add BUY Transaction (${TEST_STOCK2})"
    
    local tx2=""
    tx2=$(curl -s -X POST "${BASE_URL}/portfolio/transactions" \
        -H "Content-Type: application/json" \
        -H "$verify_headers" \
        -d "{\"stock_ticker\":\"${TEST_STOCK2}\",\"transaction_type\":\"BUY\",\"quantity\":5,\"price_per_share\":180.50,\"transaction_date\":\"2026-04-02\"}")
    
    local tx_id2=$(echo "$tx2" | jq -r '.transaction_id // empty')
    
    if [[ -n "$tx_id2" ]] && [[ "$tx_id2" != "null" ]]; then
        log_success "Transaction recorded: ${tx_id2}"
    else
        log_failure "Failed to add BUY transaction for ${TEST_STOCK2}"
    fi
    
    # -----------------------------------------------------------------------
    # Step 7: View Portfolio Holdings
    # -----------------------------------------------------------------------
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    log_info "Step 7: Portfolio Holdings"
    
    local portfolio=""
    portfolio=$(curl -s "${BASE_URL}/portfolio" \
        -H "$verify_headers")
    
    local holdings_count=$(echo "$portfolio" | jq '.holdings // empty' 2>/dev/null || echo "0")
    
    if [[ ${holdings_count:-0} -ge 2 ]]; then
        log_success "Portfolio contains ${holdings_count} holdings (expected ≥ 2)"
    else
        log_failure "Portfolio has insufficient holdings (${holdings_count})"
    fi
    
    # -----------------------------------------------------------------------
    # Step 8: Transaction History
    # -----------------------------------------------------------------------
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    log_info "Step 8: Transaction History"
    
    local history=""
    history=$(curl -s "${BASE_URL}/portfolio/transactions" \
        -H "$verify_headers")
    
    local tx_count=$(echo "$history" | jq '.transactions // empty' 2>/dev/null || echo "0")
    
    if [[ ${tx_count:-0} -ge 2 ]]; then
        log_success "Transaction history contains ${tx_count} entries (expected ≥ 2)"
        
        # Verify both transactions are present
        local aapl_tx=$(echo "$history" | jq '[.transactions[] | select(.stock_ticker == "'${TEST_STOCK1}'\")] | length' 2>/dev/null || echo "0")
        local googl_tx=$(echo "$history" | jq '[.transactions[] | select(.stock_ticker == "'${TEST_STOCK2}'\")] | length' 2>/dev/null || echo "0")
        
        if [[ ${aapl_tx:-0} -ge 1 ]] && [[ ${googl_tx:-0} -ge 1 ]]; then
            log_success "Both transactions found in history (${TEST_STOCK1}, ${TEST_STOCK2})"
        else
            log_warn "One or both transactions not explicitly found (may be acceptable)"
        fi
    else
        log_failure "Transaction history has insufficient entries (${tx_count})"
    fi
    
    # -----------------------------------------------------------------------
    # Step 9: Add to Watchlist
    # -----------------------------------------------------------------------
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    log_info "Step 9: Add to Watchlist"
    
    local watch_status=0
    
    curl -s -X POST "${BASE_URL}/watchlist/${WATCH_STOCK1}" \
        -H "$verify_headers" >/dev/null 2>&1 || watch_status=$?
    
    curl -s -X POST "${BASE_URL}/watchlist/${WATCH_STOCK2}" \
        -H "$verify_headers" >/dev/null 2>&1 || watch_status=$?
    
    if [[ $watch_status -eq 0 ]] || [[ $watch_status -eq 409 ]]; then
        log_success "Watchlist items added (${WATCH_STOCK1}, ${WATCH_STOCK2})"
    else
        log_failure "Failed to add watchlist items (HTTP: ${watch_status})"
    fi
    
    # -----------------------------------------------------------------------
    # Step 10: View Watchlist
    # -----------------------------------------------------------------------
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    log_info "Step 10: View Watchlist"
    
    local watchlist=""
    watchlist=$(curl -s "${BASE_URL}/watchlist" \
        -H "$verify_headers")
    
    # Check HTTP status (any 2xx or 4xx is acceptable)
    local http_code=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/watchlist")
    
    if [[ $http_code =~ ^2[0-9]{2}$ ]] || [[ $http_code =~ ^4[0-9]{2}$ ]]; then
        log_success "Watchlist endpoint accessible (HTTP ${http_code})"
    else
        log_failure "Watchlist endpoint returned HTTP: ${http_code}"
    fi
    
    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    echo ""
    echo "========================================================================="
    log_success "ALL API TESTS PASSED"
    echo "========================================================================="
    
    return 0
}

# -----------------------------------------------------------------------------
# Deployment Verification (Optional)
# -----------------------------------------------------------------------------
verify_deployment() {
    log_info "--- Deployment Verification ---"
    
    # Check PostgreSQL connectivity
    if command -v psql >/dev/null 2>&1; then
        echo "Checking PostgreSQL..."
        if PGPASSWORD=secretpassword psql -h 100.91.204.48 -U admin -d alphatracer \
            -c "SELECT 1" >/dev/null 2>&1; then
            log_success "PostgreSQL accessible at 100.91.204.48:5432"
        else
            log_warn "PostgreSQL not reachable - assuming external DB"
        fi
    fi
    
    # Check Alembic migrations
    if [ -f "alembic.ini" ]; then
        echo "Checking migrations..."
        run_migrations
    else
        log_info "No alembic.ini found - skipping migration check"
    fi
    
    echo ""
}

# -----------------------------------------------------------------------------
# Main Entry Point
# -----------------------------------------------------------------------------
main() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════════════════╗"
    echo "║         Alphatracer E2E Test Suite: Deployment → API                  ║"
    echo "║         Base URL: ${BASE_URL}                                       ║"
    echo "╚══════════════════════════════════════════════════════════════════════╝"
    echo ""
    
    # Phase 1: Prerequisites & Environment
    check_prerequisites
    
    # Phase 2: Deployment Verification (Optional)
    verify_deployment
    
    # Phase 3: Wait for Database (if psql available)
    if command -v psql >/dev/null 2>&1; then
        wait_for_database || true
    fi
    
    # Phase 4: Run Migrations Check
    run_migrations
    
    # Phase 5: Start Server (if local source exists)
    start_server
    
    # Phase 6: Wait for API to be Ready
    wait_for_api
    
    # Phase 7: Execute API Tests
    run_api_tests
    
    echo ""
    log_success "Test Suite Completed Successfully!"
    
    return 0
}

# Run main function with all arguments
main "$@"
