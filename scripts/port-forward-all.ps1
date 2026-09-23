# ==============================================================================
#  AlphaTracer DevSecOps Sandbox - Port-Forward All Platform Services
# Connects local host browser directly to all K3s cluster & monitoring endpoints
# Usage: .\scripts\port-forward-all.ps1
# ==============================================================================

Write-Host "`n Initializing Port-Forwards for AlphaTracer DevSecOps Sandbox..." -ForegroundColor Cyan

# Kill any existing port-forward processes
Get-Process -Name kubectl -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "port-forward" } | Stop-Process -Force -ErrorAction SilentlyContinue

$services = @(
    #    Application Layer   
    @{ Name = "Production API (FastAPI)";       Namespace = "alphatracer";      Svc = "alphatracer-service";          LocalPort = 8011; RemotePort = 8011 },
    @{ Name = "Development API (FastAPI)";      Namespace = "alphatracer-dev";  Svc = "alphatracer-service";          LocalPort = 8012; RemotePort = 8011 },

    #    GitOps   
    @{ Name = "ArgoCD GitOps Dashboard";        Namespace = "argocd";           Svc = "argocd-server";                LocalPort = 8080; RemotePort = 443 },

    #    Secrets   
    @{ Name = "HashiCorp Vault";                Namespace = "vault";            Svc = "vault";                        LocalPort = 8200; RemotePort = 8200 },

    #    Registry   
    @{ Name = "Local Container Registry";       Namespace = "registry";         Svc = "registry";                     LocalPort = 5000; RemotePort = 5000 },

    #    Observability   
    @{ Name = "Prometheus";                     Namespace = "monitoring";       Svc = "kube-prometheus-kube-prome-prometheus"; LocalPort = 9090; RemotePort = 9090 },
    @{ Name = "Grafana";                        Namespace = "monitoring";       Svc = "kube-prometheus-grafana";       LocalPort = 3000; RemotePort = 80 },
    @{ Name = "Alertmanager";                   Namespace = "monitoring";       Svc = "kube-prometheus-kube-prome-alertmanager"; LocalPort = 9093; RemotePort = 9093 },
    @{ Name = "Jaeger Tracing UI";              Namespace = "monitoring";       Svc = "jaeger-query";                 LocalPort = 16686; RemotePort = 16686 },
    @{ Name = "Loki Log Aggregation";           Namespace = "monitoring";       Svc = "loki";                         LocalPort = 3100; RemotePort = 3100 },
    @{ Name = "OpenCost";                       Namespace = "monitoring";       Svc = "opencost";                     LocalPort = 9095; RemotePort = 9090 },

    #    Security   
    @{ Name = "Falcosidekick Runtime UI";       Namespace = "falco";            Svc = "falco-falcosidekick-ui";       LocalPort = 2801; RemotePort = 2801 },
    @{ Name = "Policy Reporter (Kyverno)";      Namespace = "kyverno";          Svc = "policy-reporter";              LocalPort = 8082; RemotePort = 8082 },

    #    Auth / SSO   
    @{ Name = "Keycloak SSO";                   Namespace = "keycloak";         Svc = "keycloak";                     LocalPort = 8081; RemotePort = 8080 },

    #    Data Layer   
    @{ Name = "pgAdmin 4";                      Namespace = "alphatracer";      Svc = "pgadmin";                      LocalPort = 5050; RemotePort = 5050 },

    #    Testing   
    @{ Name = "OWASP ZAP (DAST)";              Namespace = "testing";          Svc = "zap";                          LocalPort = 8090; RemotePort = 8090 },
    @{ Name = "SonarQube (Code Quality)";       Namespace = "testing";          Svc = "sonarqube-sonarqube";          LocalPort = 9000; RemotePort = 9000 },

    #    Compliance   
    @{ Name = "Dependency-Track (SBOM)";        Namespace = "compliance";       Svc = "dependency-track";             LocalPort = 8083; RemotePort = 8080 },
    @{ Name = "DefectDojo (Vuln Mgmt)";         Namespace = "compliance";       Svc = "defectdojo-django";            LocalPort = 8084; RemotePort = 8080 },

    #    Chaos Engineering   
    @{ Name = "Chaos Mesh Dashboard";           Namespace = "chaos-mesh";       Svc = "chaos-dashboard";              LocalPort = 2333; RemotePort = 2333 }
)

$successCount = 0
$failCount = 0

foreach ($s in $services) {
    Write-Host "  -> Forwarding $($s.Name) on http://localhost:$($s.LocalPort)..." -ForegroundColor Yellow
    try {
        Start-Process kubectl -ArgumentList "port-forward", "-n", $s.Namespace, "svc/$($s.Svc)", "$($s.LocalPort):$($s.RemotePort)" -WindowStyle Hidden -ErrorAction Stop
        $successCount++
    } catch {
        Write-Host "     [WARN] Could not forward $($s.Name): service may not exist yet" -ForegroundColor DarkYellow
        $failCount++
    }
}

Write-Host "`n Port-Forward Summary: $successCount launched, $failCount skipped" -ForegroundColor Green

Write-Host "`n+==================================================================+" -ForegroundColor Cyan
Write-Host "|  AlphaTracer DevSecOps Platform - Live Endpoints                |" -ForegroundColor Cyan
Write-Host " ================================================================== " -ForegroundColor Cyan
Write-Host "|  APPLICATION                                                    |" -ForegroundColor Cyan
Write-Host "|    Prod API Swagger : http://localhost:8011/docs                |" -ForegroundColor White
Write-Host "|    Prod API ReDoc   : http://localhost:8011/redoc               |" -ForegroundColor White
Write-Host "|    Prod OpenAPI     : http://localhost:8011/openapi.json        |" -ForegroundColor White
Write-Host "|    Prod Health      : http://localhost:8011/health              |" -ForegroundColor White
Write-Host "|    Dev API Swagger  : http://localhost:8012/docs                |" -ForegroundColor White
Write-Host "|                                                                  |" -ForegroundColor Cyan
Write-Host "|  GITOPS                                                          |" -ForegroundColor Cyan
Write-Host "|    ArgoCD           : https://localhost:8080                     |" -ForegroundColor White
Write-Host "|    ArgoCD Dev App   : https://localhost:8080/applications/alphatracer-dev  |" -ForegroundColor White
Write-Host "|    ArgoCD Prod App  : https://localhost:8080/applications/alphatracer-prod |" -ForegroundColor White
Write-Host "|                                                                  |" -ForegroundColor Cyan
Write-Host "|  SECRETS & REGISTRY                                              |" -ForegroundColor Cyan
Write-Host "|    Vault UI         : http://localhost:8200                      |" -ForegroundColor White
Write-Host "|    Local Registry   : http://localhost:5000/v2/_catalog          |" -ForegroundColor White
Write-Host "|                                                                  |" -ForegroundColor Cyan
Write-Host "|  OBSERVABILITY                                                   |" -ForegroundColor Cyan
Write-Host "|    Prometheus       : http://localhost:9090                      |" -ForegroundColor White
Write-Host "|    Grafana          : http://localhost:3000   (admin/alphatracer)|" -ForegroundColor White
Write-Host "|    Alertmanager     : http://localhost:9093                      |" -ForegroundColor White
Write-Host "|    Jaeger Tracing   : http://localhost:16686                     |" -ForegroundColor White
Write-Host "|    Loki Logs        : http://localhost:3100                      |" -ForegroundColor White
Write-Host "|    OpenCost         : http://localhost:9095                      |" -ForegroundColor White
Write-Host "|                                                                  |" -ForegroundColor Cyan
Write-Host "|  SECURITY                                                        |" -ForegroundColor Cyan
Write-Host "|    Falco Runtime    : http://localhost:2801                      |" -ForegroundColor White
Write-Host "|    Policy Reporter  : http://localhost:8082                      |" -ForegroundColor White
Write-Host "|                                                                  |" -ForegroundColor Cyan
Write-Host "|  AUTH / DATA                                                     |" -ForegroundColor Cyan
Write-Host "|    Keycloak SSO     : http://localhost:8081   (admin/alphatracer)|" -ForegroundColor White
Write-Host "|    pgAdmin          : http://localhost:5050                      |" -ForegroundColor White
Write-Host "|                                                                  |" -ForegroundColor Cyan
Write-Host "|  TESTING & COMPLIANCE                                            |" -ForegroundColor Cyan
Write-Host "|    ZAP DAST         : http://localhost:8090                      |" -ForegroundColor White
Write-Host "|    SonarQube        : http://localhost:9000   (admin/admin)      |" -ForegroundColor White
Write-Host "|    Dependency-Track : http://localhost:8083                      |" -ForegroundColor White
Write-Host "|    DefectDojo       : http://localhost:8084   (admin/alphatracer)|" -ForegroundColor White
Write-Host "|                                                                  |" -ForegroundColor Cyan
Write-Host "|  CHAOS ENGINEERING                                               |" -ForegroundColor Cyan
Write-Host "|    Chaos Mesh       : http://localhost:2333                      |" -ForegroundColor White
Write-Host "|                                                                  |" -ForegroundColor Cyan
Write-Host "|  INGRESS (after setup-hosts.ps1)                                 |" -ForegroundColor Cyan
Write-Host "|    Prod             : https://alphatracer.local                  |" -ForegroundColor White
Write-Host "|    Dev              : https://dev.alphatracer.local              |" -ForegroundColor White
Write-Host "|    Staging          : https://staging.alphatracer.local          |" -ForegroundColor White
Write-Host "|    ArgoCD           : https://argocd.local                       |" -ForegroundColor White
Write-Host "+==================================================================+" -ForegroundColor Cyan
Write-Host ""
