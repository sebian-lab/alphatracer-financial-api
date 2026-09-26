# ==============================================================================
# 🔑 Initialize and Seed HashiCorp Vault with AlphaTracer Secrets
# Usage: .\scripts\seed-vault.ps1
# ==============================================================================

param(
    [string]$VaultUrl = "http://localhost:8200",
    [string]$VaultToken = "root"
)

$ErrorActionPreference = "Stop"

Write-Host "🔑 Initializing HashiCorp Vault Secrets for AlphaTracer..." -ForegroundColor Cyan

$headers = @{
    "X-Vault-Token" = $VaultToken
    "Content-Type"  = "application/json"
}

# 1. Verify Vault is responsive
try {
    $health = Invoke-RestMethod -Uri "$VaultUrl/v1/sys/health" -Method Get -TimeoutSec 3
    Write-Host "   ✅ Vault is online and healthy." -ForegroundColor Green
} catch {
    Write-Host "   ⚠️ Could not reach Vault at $VaultUrl. Is 'docker compose up -d' running?" -ForegroundColor Yellow
    exit 1
}

# 2. Write secrets into KV v2 engine: secret/data/alphatracer
$secretPayload = @{
    data = @{
        database_url = "postgresql://postgres:postgres_secure_pass@db:5432/trading_db"
        secret_key   = "vault-managed-high-entropy-jwt-secret-key-32bytes"
        algorithm    = "HS256"
    }
} | ConvertTo-Json

try {
    Invoke-RestMethod -Uri "$VaultUrl/v1/secret/data/alphatracer" -Method Post -Headers $headers -Body $secretPayload | Out-Null
    Write-Host "   ✅ Successfully stored 'alphatracer' secrets in Vault KV engine." -ForegroundColor Green
    Write-Host "      - secret/data/alphatracer -> database_url, secret_key" -ForegroundColor Gray
} catch {
    Write-Host "   ❌ Failed to store secret in Vault: $_" -ForegroundColor Red
    exit 1
}

Write-Host "`n🎉 Vault seeding complete! AlphaTracer API will automatically load these secrets." -ForegroundColor Green
