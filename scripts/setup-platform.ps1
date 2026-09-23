# ==============================================================================
# AlphaTracer DevSecOps Platform - Master Setup Script
# Deploys ALL platform services to K3s cluster in correct dependency order
#
# Prerequisites:
#   - Docker Desktop running (Start-Service com.docker.service)
#   - K3s cluster accessible (kubectl cluster-info)
#   - Helm 3 installed (choco install kubernetes-helm)
#
# Usage: .\scripts\setup-platform.ps1 [-SkipHeavy] [-DryRun]
#   -SkipHeavy: Skip resource-intensive services (SonarQube, DefectDojo, Chaos Mesh)
#   -DryRun:    Only print commands without executing
# ==============================================================================

param (
    [switch]$SkipHeavy,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PLATFORM = "$ROOT\infrastructure\kubernetes\platform"

function Run-Step {
    param([string]$Description, [scriptblock]$Command)
    Write-Host "  -> $Description" -ForegroundColor Gray
    if (-not $DryRun) {
        try { & $Command } catch {
            Write-Host "     [WARN] $($_.Exception.Message)" -ForegroundColor Yellow
        }
    }
}

# +==========================================================+
# |  PHASE 1: Prerequisites                                |
# +==========================================================+
Write-Host "`n[PHASE 1/8] Prerequisites" -ForegroundColor Cyan

# Check Docker with strict 2-second timeout to avoid Windows named pipe hangs
$dockerRunning = $false
try {
    $proc = Start-Process -FilePath "docker" -ArgumentList "version" -NoNewWindow -PassThru -RedirectStandardOutput "$env:TEMP\docker_v_out.txt" -RedirectStandardError "$env:TEMP\docker_v_err.txt"
    $finished = $proc.WaitForExit(2000)
    if (-not $finished) {
        $proc.Kill()
    } elseif ($proc.ExitCode -eq 0) {
        $dockerRunning = $true
    }
} catch {}

if (-not $dockerRunning) {
    Write-Host "  -> Docker daemon is not responding. Checking Docker Desktop..." -ForegroundColor Yellow
    try {
        $dockerProc = Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue
        if (-not $dockerProc -and (Test-Path "C:\Program Files\Docker\Docker\Docker Desktop.exe")) {
            Write-Host "     Launching Docker Desktop..." -ForegroundColor Gray
            Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
            Write-Host "     Docker Desktop launched." -ForegroundColor Green
        }
    } catch {
        Write-Host "     [WARN] Could not auto-launch Docker Desktop: $($_.Exception.Message)" -ForegroundColor Yellow
    }
} else {
    Write-Host "  [OK] Docker daemon reachable" -ForegroundColor Green
}

# Check kubectl & cluster (fast detection to avoid NativeCommandError and timeouts)
Write-Host "  -> Verifying K8s cluster connectivity..." -ForegroundColor Gray
$kubeConfigPath = "$env:USERPROFILE\.kube\config"
$clusterReady = $false

if (Test-Path $kubeConfigPath) {
    try {
        $p = Start-Process -FilePath "kubectl" -ArgumentList "cluster-info", "--request-timeout=3s" -NoNewWindow -PassThru -RedirectStandardOutput "$env:TEMP\k_out.txt" -RedirectStandardError "$env:TEMP\k_err.txt"
        $finished = $p.WaitForExit(3000)
        if (-not $finished) { $p.Kill() }
        elseif ($p.ExitCode -eq 0) { $clusterReady = $true }
    } catch {}
}

if (-not $clusterReady) {
    Write-Host "     [ERROR] Kubernetes cluster is NOT reachable!" -ForegroundColor Red
    Write-Host "     Reason: ~/.kube/config is missing or cluster did not respond within 3s." -ForegroundColor Yellow
    Write-Host "     (Without an active cluster, kubectl falls back to http://localhost:8080)" -ForegroundColor Gray
    Write-Host ""
    Write-Host "     How to start your local Kubernetes cluster:" -ForegroundColor Cyan
    Write-Host "       1. Docker Desktop : Open Docker Desktop -> Settings (gear icon) -> Kubernetes -> Check 'Enable Kubernetes' -> Click 'Apply & restart'" -ForegroundColor White
    Write-Host "       2. Minikube       : Run 'winget install Kubernetes.minikube' then 'minikube start'" -ForegroundColor White
    Write-Host "       3. K3d (Light)    : Run 'winget install k3d.k3d' then 'k3d cluster create devsecops'" -ForegroundColor White
    Write-Host "       4. Dry-Run Check  : Run '.\scripts\setup-platform.ps1 -DryRun' to preview all manifests safely" -ForegroundColor White
    Write-Host ""
    if (-not $DryRun) {
        Write-Host "     Deployment stopped safely. Start your Kubernetes engine and re-run." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "     [OK] Cluster reachable" -ForegroundColor Green
}

# Check Helm
Run-Step "Verifying Helm package manager" {
    $helmCmd = Get-Command helm -ErrorAction SilentlyContinue
    if (-not $helmCmd) {
        Write-Host "     Helm not found in PATH. Checking winget..." -ForegroundColor Yellow
        $wingetCmd = Get-Command winget -ErrorAction SilentlyContinue
        if ($wingetCmd) {
            Write-Host "     Attempting automatic Helm installation via winget..." -ForegroundColor Cyan
            try {
                winget install --id Helm.Helm -e --silent --accept-source-agreements --accept-package-agreements 2>&1 | Out-Null
                $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
            } catch {
                Write-Host "     [WARN] Automatic Helm install skipped." -ForegroundColor Yellow
            }
        }
    }

    $null = helm version --short 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "     [WARN] Helm is not available. Install via: winget install Helm.Helm or choco install kubernetes-helm" -ForegroundColor Yellow
        if (-not $DryRun) {
            Write-Host "     [ERROR] Helm is required for deploying platform charts." -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "     [OK] Helm available" -ForegroundColor Green
    }
}

# +==========================================================+
# |  PHASE 2: Add Helm Repositories                        |
# +==========================================================+
Write-Host "`n[PHASE 2/8] Adding Helm Repositories" -ForegroundColor Cyan

$repos = @(
    @{ Name = "hashicorp"; Url = "https://helm.releases.hashicorp.com" },
    @{ Name = "jetstack"; Url = "https://charts.jetstack.io" },
    @{ Name = "falcosecurity"; Url = "https://falcosecurity.github.io/charts" },
    @{ Name = "kyverno"; Url = "https://kyverno.github.io/kyverno/" },
    @{ Name = "policy-reporter"; Url = "https://kyverno.github.io/policy-reporter" },
    @{ Name = "prometheus-community"; Url = "https://prometheus-community.github.io/helm-charts" },
    @{ Name = "grafana"; Url = "https://grafana.github.io/helm-charts" },
    @{ Name = "jaegertracing"; Url = "https://jaegertracing.github.io/helm-charts" },
    @{ Name = "bitnami"; Url = "https://charts.bitnami.com/bitnami" },
    @{ Name = "chaos-mesh"; Url = "https://charts.chaos-mesh.org" },
    @{ Name = "opencost"; Url = "https://opencost.github.io/opencost-helm-chart" },
    @{ Name = "vmware-tanzu"; Url = "https://vmware-tanzu.github.io/helm-charts" },
    @{ Name = "argo"; Url = "https://argoproj.github.io/argo-helm" }
)

foreach ($r in $repos) {
    Run-Step "Adding $($r.Name)" { helm repo add $r.Name $r.Url --force-update 2>&1 | Out-Null }
}
Run-Step "Updating Helm repos" { helm repo update 2>&1 | Out-Null }
Write-Host "  [OK] All Helm repos ready" -ForegroundColor Green

# +==========================================================+
# |  PHASE 3: Core Infrastructure                          |
# +==========================================================+
Write-Host "`n[PHASE 3/8] Core Infrastructure" -ForegroundColor Cyan

# Create namespaces
$namespaces = @("alphatracer", "alphatracer-dev", "alphatracer-staging", "argocd", "monitoring", "vault", "falco", "kyverno")
foreach ($ns in $namespaces) {
    Run-Step "Namespace: $ns" { kubectl create namespace $ns --dry-run=client -o yaml | kubectl apply -f - 2>&1 | Out-Null }
}

# Vault
Run-Step "HashiCorp Vault (secrets management)" {
    helm upgrade --install vault hashicorp/vault -n vault `
        -f "$PLATFORM\vault\helm-values.yaml" `
        --wait --timeout 120s
}

# Local Registry
Run-Step "Local Container Registry" {
    kubectl apply -f "$PLATFORM\registry\deployment.yaml"
}

# cert-manager
Run-Step "cert-manager (TLS certificates)" {
    helm upgrade --install cert-manager jetstack/cert-manager -n cert-manager `
        --create-namespace `
        -f "$PLATFORM\ingress\cert-manager-values.yaml" `
        --wait --timeout 120s
}

# Self-signed issuer (after cert-manager is ready)
Start-Sleep -Seconds 5
Run-Step "Self-signed ClusterIssuer" {
    kubectl apply -f "$PLATFORM\ingress\self-signed-issuer.yaml"
}

# Traefik IngressRoutes
Run-Step "Traefik IngressRoutes (local DNS)" {
    kubectl apply -f "$PLATFORM\ingress\traefik-ingress-routes.yaml"
}

Write-Host "  [OK] Core infrastructure deployed" -ForegroundColor Green

# +==========================================================+
# |  PHASE 4: Data Layer                                   |
# +==========================================================+
Write-Host "`n[PHASE 4/8] Data Layer" -ForegroundColor Cyan

Run-Step "PostgreSQL (trading_db)" {
    helm upgrade --install postgresql bitnami/postgresql -n alphatracer `
        -f "$PLATFORM\data\postgres-helm-values.yaml" `
        --wait --timeout 120s
}

Run-Step "pgAdmin 4" {
    kubectl apply -f "$PLATFORM\data\pgadmin-deployment.yaml"
}

Write-Host "  [OK] Data layer deployed" -ForegroundColor Green

# +==========================================================+
# |  PHASE 5: GitOps - ArgoCD                              |
# +==========================================================+
Write-Host "`n[PHASE 5/8] GitOps - ArgoCD" -ForegroundColor Cyan

Run-Step "ArgoCD Server" {
    helm upgrade --install argocd argo/argo-cd -n argocd `
        --set server.service.type=ClusterIP `
        --set configs.params."server\.insecure"=true `
        --wait --timeout 180s
}

Run-Step "ArgoCD Applications (dev + prod)" {
    kubectl apply -f "$ROOT\infrastructure\kubernetes\argo-app-dev.yaml"
    kubectl apply -f "$ROOT\infrastructure\kubernetes\argo-app-prod.yaml"
}

Write-Host "  [OK] ArgoCD deployed" -ForegroundColor Green

# +==========================================================+
# |  PHASE 6: Security & Policy                            |
# +==========================================================+
Write-Host "`n[PHASE 6/8] Security & Policy" -ForegroundColor Cyan

# Kyverno
Run-Step "Kyverno (policy engine)" {
    helm upgrade --install kyverno kyverno/kyverno -n kyverno `
        --set replicaCount=1 `
        --wait --timeout 120s
}

# Kyverno policies
Run-Step "Kyverno Policies" {
    kubectl apply -f "$ROOT\policies\kyverno\disallow-root.yaml"
    kubectl apply -f "$ROOT\policies\kyverno\require-resource-limits.yaml"
    kubectl apply -f "$ROOT\policies\kyverno\restrict-registries.yaml"
    # verify-image-signatures.yaml - apply after first signed image is pushed
    # kubectl apply -f "$ROOT\policies\kyverno\verify-image-signatures.yaml"
}

# Policy Reporter
Run-Step "Policy Reporter (Kyverno UI)" {
    helm upgrade --install policy-reporter policy-reporter/policy-reporter -n kyverno `
        -f "$PLATFORM\policy-reporter\helm-values.yaml" `
        --wait --timeout 120s
}

# Falco
Run-Step "Falco (runtime security)" {
    helm upgrade --install falco falcosecurity/falco -n falco `
        -f "$PLATFORM\falco\helm-values.yaml" `
        --wait --timeout 180s
}

Write-Host "  [OK] Security stack deployed" -ForegroundColor Green

# +==========================================================+
# |  PHASE 7: Observability                                |
# +==========================================================+
Write-Host "`n[PHASE 7/8] Observability" -ForegroundColor Cyan

# kube-prometheus-stack (Prometheus + Grafana + Alertmanager)
Run-Step "kube-prometheus-stack" {
    helm upgrade --install kube-prometheus prometheus-community/kube-prometheus-stack -n monitoring `
        -f "$PLATFORM\observability\kube-prometheus-values.yaml" `
        --wait --timeout 300s
}

# Loki + Promtail
Run-Step "Loki Stack (centralized logging)" {
    helm upgrade --install loki grafana/loki-stack -n monitoring `
        -f "$PLATFORM\observability\loki-values.yaml" `
        --wait --timeout 120s
}

# Jaeger
Run-Step "Jaeger (distributed tracing)" {
    helm upgrade --install jaeger jaegertracing/jaeger -n monitoring `
        -f "$PLATFORM\observability\jaeger-values.yaml" `
        --wait --timeout 120s
}

# OTel Collector
Run-Step "OpenTelemetry Collector" {
    kubectl apply -f "$PLATFORM\observability\otel-collector.yaml"
}

# Alertmanager webhook
Run-Step "Alertmanager webhook receiver" {
    kubectl apply -f "$PLATFORM\observability\alertmanager-config.yaml"
}

# Grafana dashboards ConfigMap
Run-Step "Grafana dashboards" {
    kubectl create configmap grafana-alphatracer-dashboards -n monitoring `
        --from-file="$PLATFORM\observability\grafana-dashboards\alphatracer-dev.json" `
        --from-file="$PLATFORM\observability\grafana-dashboards\alphatracer-prod.json" `
        --dry-run=client -o yaml | kubectl apply -f -
}

# OpenCost
Run-Step "OpenCost (cost visibility)" {
    helm upgrade --install opencost opencost/opencost -n monitoring `
        -f "$PLATFORM\opencost\helm-values.yaml" `
        --wait --timeout 120s
}

Write-Host "  [OK] Observability stack deployed" -ForegroundColor Green

# +==========================================================+
# |  PHASE 8: Extended Platform                            |
# +==========================================================+
Write-Host "`n[PHASE 8/8] Extended Platform" -ForegroundColor Cyan

# Keycloak
Run-Step "Keycloak (SSO/IAM)" {
    helm upgrade --install keycloak bitnami/keycloak -n keycloak `
        --create-namespace `
        -f "$PLATFORM\keycloak\helm-values.yaml" `
        --wait --timeout 180s
}

if (-not $SkipHeavy) {
    # Chaos Mesh
    Run-Step "Chaos Mesh (resilience testing)" {
        helm upgrade --install chaos-mesh chaos-mesh/chaos-mesh -n chaos-mesh `
            --create-namespace `
            -f "$PLATFORM\chaos-mesh\helm-values.yaml" `
            --wait --timeout 120s
    }

    # Velero + MinIO
    Run-Step "Velero + MinIO (backup/DR)" {
        kubectl create namespace velero --dry-run=client -o yaml | kubectl apply -f -
        kubectl apply -f "$PLATFORM\velero\helm-values.yaml" 2>&1 | Out-Null
        helm upgrade --install velero vmware-tanzu/velero -n velero `
            -f "$PLATFORM\velero\helm-values.yaml" `
            --wait --timeout 120s
    }

    # ZAP
    Run-Step "OWASP ZAP (DAST scanner)" {
        kubectl apply -f "$PLATFORM\testing\zap-deployment.yaml"
    }

    # SonarQube
    Run-Step "SonarQube (code quality)" {
        helm repo add sonarqube https://SonarSource.github.io/helm-chart-sonarqube 2>&1 | Out-Null
        helm upgrade --install sonarqube sonarqube/sonarqube -n testing `
            --create-namespace `
            -f "$PLATFORM\testing\sonarqube-helm-values.yaml" `
            --wait --timeout 300s
    }

    # Compliance
    Run-Step "Dependency-Track (SBOM analysis)" {
        kubectl apply -f "$PLATFORM\compliance\dependency-track.yaml"
    }

    Run-Step "DefectDojo (vulnerability management)" {
        helm repo add defectdojo https://raw.githubusercontent.com/DefectDojo/django-DefectDojo/helm-charts 2>&1 | Out-Null
        helm upgrade --install defectdojo defectdojo/defectdojo -n compliance `
            -f "$PLATFORM\compliance\defectdojo-helm-values.yaml" `
            --wait --timeout 300s
    }
} else {
    Write-Host "  [SKIP] Heavy services skipped (-SkipHeavy flag)" -ForegroundColor Yellow
}

Write-Host "  [OK] Extended platform deployed" -ForegroundColor Green

# +==========================================================+
# |  SUMMARY                                               |
# +==========================================================+
Write-Host "`n============================================================" -ForegroundColor DarkCyan
Write-Host " AlphaTracer DevSecOps Platform - Deployment Complete!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor DarkCyan
Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "  1. Run port-forwards:  .\scripts\port-forward-all.ps1" -ForegroundColor Gray
Write-Host "  2. Add DNS entries:    .\scripts\setup-hosts.ps1 (requires admin)" -ForegroundColor Gray
Write-Host "  3. Init Vault secrets: .\infrastructure\kubernetes\platform\vault\init-vault.ps1" -ForegroundColor Gray
Write-Host '  4. Get ArgoCD password: kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d' -ForegroundColor Gray
Write-Host ""
