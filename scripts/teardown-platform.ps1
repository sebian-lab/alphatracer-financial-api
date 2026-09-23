# ==============================================================================
# AlphaTracer DevSecOps Platform - Teardown Script
# Uninstalls all Helm releases and deletes namespaces in reverse order
# Usage: .\scripts\teardown-platform.ps1 [-Confirm]
# ==============================================================================

param (
    [switch]$Confirm
)

if (-not $Confirm) {
    Write-Host "[WARNING] This will destroy ALL platform services in your K3s cluster!" -ForegroundColor Red
    Write-Host "          Re-run with -Confirm to proceed." -ForegroundColor Yellow
    exit 0
}

Write-Host "`nTearing down AlphaTracer DevSecOps Platform..." -ForegroundColor Red

# Phase 1: Uninstall Helm releases (reverse dependency order)
$releases = @(
    @{ Name = "defectdojo"; Namespace = "compliance" },
    @{ Name = "sonarqube"; Namespace = "testing" },
    @{ Name = "chaos-mesh"; Namespace = "chaos-mesh" },
    @{ Name = "velero"; Namespace = "velero" },
    @{ Name = "opencost"; Namespace = "monitoring" },
    @{ Name = "keycloak"; Namespace = "keycloak" },
    @{ Name = "jaeger"; Namespace = "monitoring" },
    @{ Name = "loki"; Namespace = "monitoring" },
    @{ Name = "kube-prometheus"; Namespace = "monitoring" },
    @{ Name = "policy-reporter"; Namespace = "kyverno" },
    @{ Name = "falco"; Namespace = "falco" },
    @{ Name = "kyverno"; Namespace = "kyverno" },
    @{ Name = "argocd"; Namespace = "argocd" },
    @{ Name = "postgresql"; Namespace = "alphatracer" },
    @{ Name = "cert-manager"; Namespace = "cert-manager" },
    @{ Name = "vault"; Namespace = "vault" }
)

foreach ($r in $releases) {
    Write-Host "  -> Uninstalling $($r.Name)..." -ForegroundColor Gray
    helm uninstall $r.Name -n $r.Namespace 2>&1 | Out-Null
}

# Phase 2: Delete raw kubectl resources
$rawManifests = @(
    "infrastructure\kubernetes\platform\registry\deployment.yaml",
    "infrastructure\kubernetes\platform\testing\zap-deployment.yaml",
    "infrastructure\kubernetes\platform\data\pgadmin-deployment.yaml",
    "infrastructure\kubernetes\platform\compliance\dependency-track.yaml",
    "infrastructure\kubernetes\platform\observability\otel-collector.yaml",
    "infrastructure\kubernetes\platform\observability\alertmanager-config.yaml",
    "infrastructure\kubernetes\platform\ingress\traefik-ingress-routes.yaml",
    "infrastructure\kubernetes\platform\ingress\self-signed-issuer.yaml",
    "policies\kyverno\disallow-root.yaml",
    "policies\kyverno\require-resource-limits.yaml",
    "policies\kyverno\restrict-registries.yaml"
)

$ROOT = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
foreach ($m in $rawManifests) {
    $path = "$ROOT\$m"
    if (Test-Path $path) {
        Write-Host "  -> Deleting resources from $m..." -ForegroundColor Gray
        kubectl delete -f $path --ignore-not-found 2>&1 | Out-Null
    }
}

# Phase 3: Delete namespaces
$namespaces = @("compliance", "testing", "chaos-mesh", "velero", "keycloak", "falco", "kyverno", "argocd", "monitoring", "registry", "vault", "cert-manager", "alphatracer-staging", "alphatracer-dev", "alphatracer")
foreach ($ns in $namespaces) {
    Write-Host "  -> Deleting namespace $ns..." -ForegroundColor Gray
    kubectl delete namespace $ns --ignore-not-found 2>&1 | Out-Null
}

Write-Host "`n[OK] AlphaTracer platform teardown complete!" -ForegroundColor Green
