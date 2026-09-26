# ==============================================================================
# Generate Realistic Trading Traffic for Live Monitoring Demo
# Populates Prometheus metrics, Jaeger traces, Loki logs, and Postgres DB
# ==============================================================================

$BaseUrl = "http://localhost:8011/api/v1"

Write-Host "Generating Realistic Traffic for AlphaTracer Observability Demo..." -ForegroundColor Cyan

$users = @(
    @{ email = "trader.alice@quantfirm.com"; password = "Password123!"; name = "Alice Quant" },
    @{ email = "trader.bob@hedgefund.io";    password = "Password123!"; name = "Bob Hedger" },
    @{ email = "lead.charlie@familyoffice.com"; password = "Password123!"; name = "Charlie Portfolio" }
)

$trades = @(
    @{ ticker = "AAPL"; type = "buy";  qty = 25; price = 182.50 },
    @{ ticker = "MSFT"; type = "buy";  qty = 15; price = 415.20 },
    @{ ticker = "TSLA"; type = "buy";  qty = 40; price = 245.80 },
    @{ ticker = "NVDA"; type = "buy";  qty = 30; price = 128.40 },
    @{ ticker = "AAPL"; type = "sell"; qty = 10; price = 185.00 },
    @{ ticker = "TSLA"; type = "sell"; qty = 15; price = 252.10 }
)

foreach ($u in $users) {
    Write-Host "`n[USER] Registering $($u.name) ($($u.email))..." -ForegroundColor Yellow
    $regBody = @{
        email     = $u.email
        password  = $u.password
        full_name = $u.name
    } | ConvertTo-Json

    try {
        $reg = Invoke-RestMethod -Uri "$BaseUrl/auth/register" -Method Post -Body $regBody -ContentType "application/json" -ErrorAction SilentlyContinue
    } catch {
        # Already registered is fine
    }

    # Login
    $loginBody = @{
        email    = $u.email
        password = $u.password
    } | ConvertTo-Json

    $loginResp = Invoke-RestMethod -Uri "$BaseUrl/auth/login/json" -Method Post -Body $loginBody -ContentType "application/json"
    $token = $loginResp.access_token
    $headers = @{ "Authorization" = "Bearer $token" }
    Write-Host "  -> Authenticated. JWT token received." -ForegroundColor Green

    # Search stocks
    Write-Host "  -> Searching tickers (AAPL, NVDA, TSLA)..." -ForegroundColor Gray
    Invoke-RestMethod -Uri "$BaseUrl/stocks/search?q=apple&limit=3" -Method Get -Headers $headers | Out-Null
    Invoke-RestMethod -Uri "$BaseUrl/stocks/search?q=nvidia&limit=3" -Method Get -Headers $headers | Out-Null
    Invoke-RestMethod -Uri "$BaseUrl/stocks/search?q=tesla&limit=3" -Method Get -Headers $headers | Out-Null

    # Execute trades
    foreach ($t in $trades) {
        $tradePayload = @{
            stock_ticker     = $t.ticker
            type             = $t.type
            quantity         = $t.qty
            price_per_share  = $t.price
            transaction_date = (Get-Date).ToString("yyyy-MM-dd")
        } | ConvertTo-Json

        try {
            $tradeResp = Invoke-RestMethod -Uri "$BaseUrl/portfolio/transactions" -Method Post -Headers $headers -Body $tradePayload -ContentType "application/json"
            Write-Host "  [TRADE] $($t.type.ToUpper()) $($t.qty) $($t.ticker) @ `$$($t.price) -> OK" -ForegroundColor Green
        } catch {
            Write-Host "  [TRADE] $($t.type.ToUpper()) $($t.ticker) -> $_" -ForegroundColor DarkYellow
        }
    }

    # Add Watchlist
    Invoke-RestMethod -Uri "$BaseUrl/watchlist/AAPL" -Method Post -Headers $headers | Out-Null
    Invoke-RestMethod -Uri "$BaseUrl/watchlist/NVDA" -Method Post -Headers $headers | Out-Null

    # View portfolio
    $portfolio = Invoke-RestMethod -Uri "$BaseUrl/portfolio" -Method Get -Headers $headers
    Write-Host "  -> Portfolio loaded. Total Holdings: $($portfolio.holdings.Count)" -ForegroundColor Cyan
}

# Generate a couple of 404 / 400 requests to demonstrate error tracking in Prometheus & Loki
Write-Host "`nGenerating telemetry edge-cases (404 Not Found & 401 Unauthorized)..." -ForegroundColor Yellow
try { Invoke-RestMethod -Uri "$BaseUrl/stocks/search?q=INVALID_TICKER_99999" -Method Get } catch {}
try { Invoke-RestMethod -Uri "$BaseUrl/portfolio" -Method Get } catch {}

Write-Host "`nDemo traffic generation complete! All telemetry pipelines populated." -ForegroundColor Green
