# 🚀 AlphaTracer — DevSecOps Setup & Deployment Guide

Welcome! This setup guide walks through configuring and running AlphaTracer with modern **DevSecOps standards**, the **3-branch workflow (`dev`, `main`, `prod`)**, **Kyverno Policy-as-Code**, and **Kubernetes Secret management** (with zero cleartext `.env` files).

---

## 📋 Prerequisites

- **Python 3.10+** & `pip`
- **Docker** / **Containerd**
- **Git** & **GitHub CLI (`gh`)**
- **Kubernetes CLI (`kubectl`)** (for K3s / Minikube cluster administration)

---

## 🔒 1. DevSecOps Secret Practice: Zero Cleartext `.env` Files

> ⚠️ **Security Standard**: In accordance with CIS benchmarks and production DevSecOps best practices, **never create, commit, or store unencrypted `.env` files on disk**.

Instead, secrets and configuration are handled through secure, isolated channels:

### A. Local Development (In-Process Shell Environment)
Configure variables directly in your active terminal session without touching disk:

**In PowerShell (Windows):**
```powershell
$env:DATABASE_URL = "sqlite:///./trading.db"
$env:SECRET_KEY = [System.Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Maximum 256 }))
$env:ALGORITHM = "HS256"
$env:ACCESS_TOKEN_EXPIRE_MINUTES = "60"

# Start the service
uvicorn app.main:app --host 0.0.0.0 --port 8011 --reload
```

**In Bash (Linux / macOS):**
```bash
export DATABASE_URL="sqlite:///./trading.db"
export SECRET_KEY=$(openssl rand -base64 32)
export ALGORITHM="HS256"
export ACCESS_TOKEN_EXPIRE_MINUTES="60"

# Start the service
uvicorn app.main:app --host 0.0.0.0 --port 8011 --reload
```

### B. Kubernetes / K3s Secrets (Production & Development Namespaces)
Run the automated script to provision runtime secrets securely:
```powershell
.\scripts\create-k3s-secrets.ps1
```
Or manually create them via `kubectl`:
```bash
# Production namespace
kubectl create namespace alphatracer --dry-run=client -o yaml | kubectl apply -f -
kubectl -n alphatracer create secret generic alphatracer-secrets \
  --from-literal=database-url="postgresql://postgres:postgres_secure_pass@db:5432/trading_db" \
  --from-literal=secret-key="$(openssl rand -base64 32)" \
  --dry-run=client -o yaml | kubectl apply -f -

# Development namespace
kubectl create namespace alphatracer-dev --dry-run=client -o yaml | kubectl apply -f -
kubectl -n alphatracer-dev create secret generic alphatracer-secrets \
  --from-literal=database-url="postgresql://postgres:postgres_secure_pass@db:5432/trading_db" \
  --from-literal=secret-key="$(openssl rand -base64 32)" \
  --dry-run=client -o yaml | kubectl apply -f -
```

---

## 🛡️ 2. Kyverno Policy-as-Code Enforcement

Kyverno admission controller guards against container privilege escalation and root execution across both `alphatracer` and `alphatracer-dev` namespaces.

### Deploy the Kyverno Policy:
```bash
kubectl apply -f policies/kyverno/disallow-root.yaml
```

### Verify the Policy:
```bash
kubectl get clusterpolicy
```
```text
NAME                         BACKGROUND   VALIDATE ACTION   READY
disallow-privileged-and-root true         Enforce           true
```

### Test Admission Control (Simulate an Unauthorized Root Pod):
```bash
kubectl run evil-root-pod --image=busybox --restart=Never -n alphatracer --command -- sleep 3600
```
**Expected Response:**
```text
Error from server: admission webhook "validate.kyverno.svc" denied the request:
Security Policy Violation: Running as root (UID 0) is forbidden in AlphaTracer workloads.
```

---

## 🌿 3. 3-Branch Git Workflow (`dev` ➔ `main` ➔ `prod`)

| Branch | Stage | Gating & Promotion | K3s Namespace |
| :--- | :--- | :--- | :--- |
| **`dev`** | Rapid Integration & Testing | Push triggers unit tests, Bandit SAST, CVE scan, and dev overlay update | `alphatracer-dev` |
| **`main`** | Release Candidate / Staging | PR review required; SBOM generation and staging dry-run | `alphatracer` (staging) |
| **`prod`** | Production Release | **🛑 Manual Approval Only** via GitHub Environment `production`, Cosign Keyless Image Signing | `alphatracer` (prod) |

### Branch Switching & Pull Requests:
```bash
# 1. Everyday development on dev branch
git checkout dev

# 2. Run local shift-left check before opening PR
.\dev-check.ps1

# 3. Create PR to promote into staging/main
gh pr create --base main --head dev --title "feat: new market data endpoints"

# 4. Production Release PR (Protected by manual sign-off)
gh pr create --base prod --head main --title "release: production deployment v1.0"
```

---

## 🧪 4. Local K3s Auto-Pull Mockup Script

Test the entire DevSecOps lifecycle locally without any external cloud costs:

```powershell
# Windows PowerShell
.\scripts\mock-k3s-autopull.ps1 -TargetBranch dev
```
```bash
# Linux / macOS Bash
bash ./scripts/mock-k3s-autopull.sh dev
```

---

## 🔬 5. Running Automated Tests

Tests execute in-process with ephemeral credentials (zero disk secrets):
```bash
python -m pytest -q
```
Expected output:
```text
3 passed in ~3s
```
