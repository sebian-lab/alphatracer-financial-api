# ==============================================================================
# 🚀 AlphaTracer DevSecOps Pre-PR Validation Script (dev-check.ps1)
# Fast ~30-second local validation script to run before opening Pull Requests
# ==============================================================================

$ErrorActionPreference = "Stop"

Write-Host "`n🔍 Starting AlphaTracer DevSecOps Pre-PR Checks...`n" -ForegroundColor Cyan

# Step 1: Run Pytest Unit Tests
Write-Host "🧪 [1/6] Running Pytest Unit Tests..." -ForegroundColor Yellow
$env:DATABASE_URL = "sqlite:///./test.db"
$env:SECRET_KEY = [System.Guid]::NewGuid().ToString("N")
$env:ALGORITHM = "HS256"
$env:ACCESS_TOKEN_EXPIRE_MINUTES = "60"
$env:PRIMARY_TICKER_CSV = "https://raw.githubusercontent.com/abbadata/stock-tickers/main/data/all.csv"
$env:SECONDARY_TICKER_CSV = "https://raw.githubusercontent.com/Ate329/top-us-stock-tickers/main/tickers/all.csv"
pytest -q
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Unit tests failed!" -ForegroundColor Red
    exit 1
}
Write-Host "   ✅ Unit tests passed." -ForegroundColor Green

# Step 2: Run Bandit SAST Security Scanner
Write-Host "`n🛡️ [2/6] Running Bandit SAST Code Analysis..." -ForegroundColor Yellow
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
Write-Host "`n🔒 [3/6] Running Gitleaks Secret Detection..." -ForegroundColor Yellow
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

# Step 4: Validate Terraform IaC Config
Write-Host "`n🏗️ [4/6] Validating Terraform Infrastructure Code..." -ForegroundColor Yellow
if (Get-Command terraform -ErrorAction SilentlyContinue) {
    Push-Location infrastructure/terraform
    try {
        terraform init -backend=false -input=false | Out-Null
        terraform validate
        if ($LASTEXITCODE -ne 0) {
            Write-Host "❌ Terraform validation failed!" -ForegroundColor Red
            exit 1
        }
        Write-Host "   ✅ Terraform IaC validation passed." -ForegroundColor Green
    } finally {
        Pop-Location
    }
} else {
    Write-Host "   ⚠️ Terraform CLI not installed. Skipping IaC check." -ForegroundColor Gray
}

# Step 5: Validate Kyverno Policy-as-Code Manifests
Write-Host "`n📜 [5/6] Validating Kyverno Policy-as-Code Manifests..." -ForegroundColor Yellow
if (Get-Command kubectl -ErrorAction SilentlyContinue) {
    kubectl apply --dry-run=client -f policies/kyverno/disallow-root.yaml | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Kyverno policy manifest invalid!" -ForegroundColor Red
        exit 1
    }
    Write-Host "   ✅ Kyverno policy manifest valid." -ForegroundColor Green
} else {
    Write-Host "   ⚠️ kubectl not installed. Skipping manifest dry-run." -ForegroundColor Gray
}

# Step 6: Validate Kustomize Kubernetes Overlays
Write-Host "`n📦 [6/6] Building Kustomize Kubernetes Production Overlay..." -ForegroundColor Yellow
if (Get-Command kubectl -ErrorAction SilentlyContinue) {
    kubectl kustomize infrastructure/kubernetes/overlays/prod | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Kustomize build failed!" -ForegroundColor Red
        exit 1
    }
    Write-Host "   ✅ Kustomize overlay build passed." -ForegroundColor Green
} else {
    Write-Host "   ⚠️ kubectl not installed. Skipping Kustomize build." -ForegroundColor Gray
}

Write-Host "`n🎉 ALL PRE-PR CHECKS PASSED SUCCESSFULLY! Ready to push & open PR. 🚀`n" -ForegroundColor Green
