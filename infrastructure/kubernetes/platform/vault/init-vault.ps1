# Vault Init Script — Seeds application secrets after Vault is running
# Usage: Run after `helm install vault` and port-forward to localhost:8200
#
# Prerequisites:
#   - Vault CLI installed (choco install vault / scoop install vault)
#   - Vault port-forwarded: kubectl port-forward -n vault svc/vault 8200:8200
#
# In dev mode, the root token is "root" (see helm-values.yaml)

$env:VAULT_ADDR = "http://127.0.0.1:8200"
$env:VAULT_TOKEN = "root"

Write-Host "Seeding AlphaTracer secrets into Vault..." -ForegroundColor Cyan

# Enable KV v2 secrets engine (already enabled in dev mode at secret/)
# vault secrets enable -path=secret kv-v2

# Write application secrets
vault kv put secret/alphatracer/database `
    url="postgresql://alphatracer:$(New-Guid)@postgresql.alphatracer.svc:5432/trading_db"

vault kv put secret/alphatracer/jwt `
    secret-key="$(New-Guid)-$(New-Guid)" `
    algorithm="HS256"

# Enable Kubernetes auth method
vault auth enable kubernetes

# Configure Kubernetes auth to use the K3s API
vault write auth/kubernetes/config `
    kubernetes_host="https://kubernetes.default.svc:443"

# Create a role for the alphatracer service account
vault write auth/kubernetes/role/alphatracer `
    bound_service_account_names="default" `
    bound_service_account_namespaces="alphatracer,alphatracer-dev" `
    policies="alphatracer" `
    ttl="1h"

# Apply the policy
vault policy write alphatracer infrastructure/kubernetes/platform/vault/vault-secret-policy.hcl

Write-Host "Vault secrets seeded and Kubernetes auth configured!" -ForegroundColor Green
Write-Host "  -> Vault UI: http://localhost:8200/ui (token: root)" -ForegroundColor Yellow
