# ==============================================================================
# 🔑 Create Kubernetes Secrets for Prod (alphatracer) & Dev (alphatracer-dev)
# ==============================================================================

Write-Host "Creating Kubernetes Secrets in K3s Cluster..." -ForegroundColor Cyan


# 1. Ensure namespaces exist
kubectl create namespace alphatracer --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace alphatracer-dev --dry-run=client -o yaml | kubectl apply -f -

# 2. Create secret in production namespace
kubectl -n alphatracer create secret generic alphatracer-secrets `
  --from-literal=database-url="postgresql://postgres:postgres_secure_pass@db:5432/trading_db" `
  --from-literal=secret-key="alphatracer-prod-secure-jwt-key-2026" `
  --dry-run=client -o yaml | kubectl apply -f -
Write-Host "✅ Created alphatracer-secrets in namespace: alphatracer" -ForegroundColor Green

# 3. Create secret in development namespace
kubectl -n alphatracer-dev create secret generic alphatracer-secrets `
  --from-literal=database-url="postgresql://postgres:postgres_secure_pass@db:5432/trading_db" `
  --from-literal=secret-key="alphatracer-dev-secure-jwt-key-2026" `
  --dry-run=client -o yaml | kubectl apply -f -
Write-Host "✅ Created alphatracer-secrets in namespace: alphatracer-dev" -ForegroundColor Green

Write-Host "`n🎉 Secret setup complete!" -ForegroundColor Green
