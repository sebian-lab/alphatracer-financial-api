# Vault Policy for AlphaTracer application secrets
# Apply: vault policy write alphatracer vault-secret-policy.hcl

# Allow read access to AlphaTracer application secrets
path "secret/data/alphatracer/*" {
  capabilities = ["read", "list"]
}

# Allow the app to renew its own token
path "auth/token/renew-self" {
  capabilities = ["update"]
}

# Allow listing secret engines (for admin/debug)
path "sys/mounts" {
  capabilities = ["read", "list"]
}
