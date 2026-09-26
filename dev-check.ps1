# ==============================================================================
# 🚀 AlphaTracer DevSecOps Pre-PR Validation Script (dev-check.ps1)
# Fast ~30-second local validation script to run before opening Pull Requests
# Workflow: Always push to dev -> PR to main -> Approve to prod
# ==============================================================================

$ErrorActionPreference = "Stop"

Write-Host "`n🔍 Starting AlphaTracer DevSecOps Pre-PR Checks...`n" -ForegroundColor Cyan

# Step 1: Run Pytest Unit Tests
Write-Host "🧪 [1/5] Running Pytest Unit Tests..." -ForegroundColor Yellow
$env:DATABASE_URL = "sqlite:///./test.db"
$env:SECRET_KEY = "test-secret-key-1234"
$env:ALGORITHM = "HS256"
$env:ACCESS_TOKEN_EXPIRE_MINUTES = "60"
pytest -q
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Unit tests failed!" -ForegroundColor Red
    exit 1
}
Write-Host "   ✅ Unit tests passed." -ForegroundColor Green

# Step 2: Run Bandit SAST Security Scanner
Write-Host "`n🛡️ [2/5] Running Bandit SAST Code Analysis..." -ForegroundColor Yellow
if (Get-Command bandit -ErrorAction SilentlyContinue) {
    bandit -r app/ -ll -ii
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Bandit detected high/medium severity security flaws!" -ForegroundColor Red
        exit 1
    }
    Write-Host "   ✅ SAST check passed." -ForegroundColor Green
} else {
    Write-Host "   ⚠️ Bandit not installed. Skipping SAST check." -ForegroundColor Gray
}

# Step 3: Run Gitleaks Secret Scanner
Write-Host "`n🔒 [3/5] Running Gitleaks Secret Detection..." -ForegroundColor Yellow
if (Get-Command gitleaks -ErrorAction SilentlyContinue) {
    gitleaks detect --verbose --config .gitleaks.toml
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Gitleaks detected secrets!" -ForegroundColor Red
        exit 1
    }
    Write-Host "   ✅ Secret scan passed." -ForegroundColor Green
} else {
    Write-Host "   ⚠️ Gitleaks CLI not installed. Skipping local secret scan." -ForegroundColor Gray
}

# Step 4: Validate Docker Compose Dev Configuration
Write-Host "`n🐳 [4/5] Validating Development Docker Compose (docker-compose.yml)..." -ForegroundColor Yellow
docker compose -f docker-compose.yml config --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ docker-compose.yml syntax or config invalid!" -ForegroundColor Red
    exit 1
}
Write-Host "   ✅ Development Docker Compose config valid." -ForegroundColor Green

# Step 5: Validate Docker Compose Prod Configuration
Write-Host "`n🚀 [5/5] Validating Production Docker Compose (docker-compose.prod.yml)..." -ForegroundColor Yellow
docker compose -f docker-compose.prod.yml config --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ docker-compose.prod.yml syntax or config invalid!" -ForegroundColor Red
    exit 1
}
Write-Host "   ✅ Production Docker Compose config valid." -ForegroundColor Green

Write-Host "`n🎉 ALL PRE-PR CHECKS PASSED SUCCESSFULLY! Ready to push & open PR. 🚀`n" -ForegroundColor Green
