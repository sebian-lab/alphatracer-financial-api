# AlphaTracer — Full DevSecOps Platform Implementation Plan

> **Goal**: Make every URL in the DevSecOps sandbox **actually functional** — no mock servers, no fake HTTP endpoints. Every service runs as a real container inside the K3s cluster (or locally via Docker Compose for dev-only tooling).

---

## Current State Assessment

### ✅ What Already Exists and Works

| Component | File(s) | Status |
|---|---|---|
| FastAPI application | [`app/main.py`](file:///c:/Users/sebia/Downloads/school/intern/2th/alphatracer-financial-api/app/main.py) | ✅ Running on `:8011` with `/health`, `/metrics`, `/docs` |
| CI/CD pipeline | [`.github/workflows/main-ci.yml`](file:///c:/Users/sebia/Downloads/school/intern/2th/alphatracer-financial-api/.github/workflows/main-ci.yml) | ✅ 3-branch (dev/main/prod), manual gate on prod |
| Security scanning | [`.github/workflows/reusable-security.yml`](file:///c:/Users/sebia/Downloads/school/intern/2th/alphatracer-financial-api/.github/workflows/reusable-security.yml) | ✅ Gitleaks, Bandit, Trivy, SBOM, Cosign signing |
| K8s base manifests | [`infrastructure/kubernetes/base/`](file:///c:/Users/sebia/Downloads/school/intern/2th/alphatracer-financial-api/infrastructure/kubernetes/base) | ✅ Deployment, Service, Ingress, ServiceMonitor |
| Kustomize overlays | `overlays/dev` and `overlays/prod` | ✅ Image tag pinning per environment |
| ArgoCD apps | `argo-app-dev.yaml`, `argo-app-prod.yaml` | ✅ Definitions exist (need cluster to apply) |
| Kyverno policy | [`policies/kyverno/disallow-root.yaml`](file:///c:/Users/sebia/Downloads/school/intern/2th/alphatracer-financial-api/policies/kyverno/disallow-root.yaml) | ✅ Disallow root + privileged |
| Terraform IaC | [`infrastructure/terraform/main.tf`](file:///c:/Users/sebia/Downloads/school/intern/2th/alphatracer-financial-api/infrastructure/terraform/main.tf) | ✅ Dry-run plan in CI |
| Docker Compose | [`docker-compose.yml`](file:///c:/Users/sebia/Downloads/school/intern/2th/alphatracer-financial-api/docker-compose.yml) | ⚠️ Exists but Docker Desktop is stopped |
| Port-forward script | [`scripts/port-forward-all.ps1`](file:///c:/Users/sebia/Downloads/school/intern/2th/alphatracer-financial-api/scripts/port-forward-all.ps1) | ⚠️ References services that don't exist yet in cluster |

### ❌ What's Missing — The 17 Gaps

Every item below has **no Kubernetes manifest, no Helm values, and no setup automation**. The port-forward script references some of them, but the backing services don't exist.

---

## Prerequisites

> [!IMPORTANT]
> **Docker Desktop must be started** before any of this can work. Currently `com.docker.service` is `Stopped` and both WSL distros (`docker-desktop`, `Ubuntu`) are `Stopped`.
>
> Run: `Start-Service com.docker.service` or launch Docker Desktop from the Start Menu.
> Then verify K3s/kubectl: `kubectl cluster-info`

> [!IMPORTANT]
> **K3s cluster must be running**. If you're using K3s inside WSL2 or Docker Desktop Kubernetes, ensure `kubectl get nodes` returns `Ready`. All platform services will be deployed there.

---

## Proposed Changes — By Layer

Each layer below creates **real Kubernetes manifests** under `infrastructure/kubernetes/platform/` and/or Helm `values.yaml` files. A master setup script (`scripts/setup-platform.ps1`) will deploy everything sequentially.

---

### Layer 1: Secrets — HashiCorp Vault
**Target URL**: `http://localhost:8200`

#### [NEW] `infrastructure/kubernetes/platform/vault/namespace.yaml`
- Creates `vault` namespace

#### [NEW] `infrastructure/kubernetes/platform/vault/helm-values.yaml`
- Vault Helm chart values for dev mode (single-node, auto-unseal, in-memory storage)
- UI enabled at port 8200
- Injector enabled for sidecar secret injection into app pods

#### [NEW] `infrastructure/kubernetes/platform/vault/vault-secret-policy.hcl`
- Vault policy granting `alphatracer/*` secret path read access
- Kubernetes auth method config for service account binding

**Deploy command**:
```powershell
helm repo add hashicorp https://helm.releases.hashicorp.com
helm install vault hashicorp/vault -n vault --create-namespace -f infrastructure/kubernetes/platform/vault/helm-values.yaml
```

**Post-deploy**: Init script seeds `secret/alphatracer/database-url` and `secret/alphatracer/secret-key` into Vault.

---

### Layer 2: Local Container Registry
**Target URL**: `http://localhost:5000`

#### [NEW] `infrastructure/kubernetes/platform/registry/deployment.yaml`
- Runs `registry:2` image in `registry` namespace
- NodePort service on 5000 so K3s nodes can pull `localhost:5000/alphatracer:*`

#### [NEW] `infrastructure/kubernetes/platform/registry/service.yaml`
- ClusterIP + NodePort exposing 5000

**Why not Harbor**: Harbor requires 2+ GB RAM and multiple containers. For a student project, the official Docker registry is sufficient and proves the concept (local pull path instead of GHCR).

**Deploy command**:
```powershell
kubectl apply -f infrastructure/kubernetes/platform/registry/
```

---

### Layer 3: Ingress / TLS / Local DNS
**Target URLs**: `http://alphatracer.local`, `https://dev.alphatracer.local`, `https://argocd.local`

#### [NEW] `infrastructure/kubernetes/platform/ingress/traefik-ingress-routes.yaml`
- IngressRoute CRDs for Traefik (K3s ships with Traefik by default)
- Routes: `alphatracer.local` → `alphatracer-service:8011` (prod namespace)
- Routes: `dev.alphatracer.local` → `alphatracer-service:8011` (dev namespace)
- Routes: `argocd.local` → `argocd-server:443` (argocd namespace)

#### [NEW] `infrastructure/kubernetes/platform/ingress/cert-manager-values.yaml`
- Helm values for cert-manager with self-signed ClusterIssuer
- Used by ingress annotations to auto-generate TLS certs

#### [NEW] `scripts/setup-hosts.ps1`
- Adds `127.0.0.1 alphatracer.local dev.alphatracer.local staging.alphatracer.local argocd.local` to `C:\Windows\System32\drivers\etc\hosts` (requires admin)

**Deploy commands**:
```powershell
helm repo add jetstack https://charts.jetstack.io
helm install cert-manager jetstack/cert-manager -n cert-manager --create-namespace --set installCRDs=true
kubectl apply -f infrastructure/kubernetes/platform/ingress/
```

---

### Layer 4: Runtime Security — Falco + Falcosidekick
**Target URL**: `http://localhost:2801` (Falcosidekick UI)

#### [NEW] `infrastructure/kubernetes/platform/falco/helm-values.yaml`
- Falco Helm chart with:
  - `falcosidekick.enabled: true`
  - `falcosidekick.webui.enabled: true` (port 2801)
  - Custom rules detecting suspicious exec in alphatracer containers
  - eBPF driver (works in K3s without kernel modules)

**Deploy command**:
```powershell
helm repo add falcosecurity https://falcosecurity.github.io/charts
helm install falco falcosecurity/falco -n falco --create-namespace -f infrastructure/kubernetes/platform/falco/helm-values.yaml
```

---

### Layer 5: Policy Verification — Kyverno + Policy Reporter
**Target URL**: `http://localhost:8082` (Policy Reporter UI)

#### [MODIFY] `policies/kyverno/disallow-root.yaml`
- Add `alphatracer-prod` namespace to match list

#### [NEW] `policies/kyverno/verify-image-signatures.yaml`
- `verifyImages` ClusterPolicy requiring Cosign signature on `ghcr.io/sebian-lab/*` images
- Uses keyless verification with Fulcio/Rekor transparency log

#### [NEW] `policies/kyverno/restrict-registries.yaml`
- Allowlist policy: only `ghcr.io/sebian-lab/*` and `localhost:5000/*` images allowed

#### [NEW] `policies/kyverno/require-resource-limits.yaml`
- Enforce `resources.limits.cpu` and `resources.limits.memory` on all pods in alphatracer namespaces

#### [NEW] `infrastructure/kubernetes/platform/policy-reporter/helm-values.yaml`
- Policy Reporter Helm chart with UI enabled on port 8082
- Aggregates all Kyverno policy results into a dashboard

**Deploy commands**:
```powershell
helm repo add kyverno https://kyverno.github.io/kyverno/
helm install kyverno kyverno/kyverno -n kyverno --create-namespace
kubectl apply -f policies/kyverno/
helm repo add policy-reporter https://kyverno.github.io/policy-reporter
helm install policy-reporter policy-reporter/policy-reporter -n kyverno -f infrastructure/kubernetes/platform/policy-reporter/helm-values.yaml
```

---

### Layer 6: Supply Chain Verification
**Target**: Cosign verification at admission (uses Layer 5's `verify-image-signatures.yaml`)

No separate service needed — Kyverno's `verifyImages` policy handles this at admission time. The existing Cosign signing in CI + the new Kyverno policy closes the loop.

#### [NEW] `policies/kyverno/verify-image-signatures.yaml` (covered in Layer 5)
- Verifies `ghcr.io/sebian-lab/alphatracer-financial-api` images are signed via Sigstore keyless

---

### Layer 7: Testing — ZAP (DAST) + SonarQube
**Target URLs**: `http://localhost:8090` (ZAP), `http://localhost:9000` (SonarQube)

#### [NEW] `infrastructure/kubernetes/platform/testing/zap-deployment.yaml`
- OWASP ZAP in daemon mode with API enabled on port 8090
- Runs in `testing` namespace
- ZAP can target `http://alphatracer-service.alphatracer.svc:8011` for in-cluster DAST scanning

#### [NEW] `infrastructure/kubernetes/platform/testing/sonarqube-helm-values.yaml`
- SonarQube Community Edition via Helm (port 9000)
- Postgres backend (reuses the data layer Postgres or its own)

**Deploy commands**:
```powershell
kubectl apply -f infrastructure/kubernetes/platform/testing/zap-deployment.yaml
helm repo add sonarqube https://SonarSource.github.io/helm-chart-sonarqube
helm install sonarqube sonarqube/sonarqube -n testing --create-namespace -f infrastructure/kubernetes/platform/testing/sonarqube-helm-values.yaml
```

---

### Layer 8: Observability — Alertmanager, Loki, Jaeger, OTel
**Target URLs**: `http://localhost:9093` (Alertmanager), `http://localhost:16686` (Jaeger), `http://localhost:3100` (Loki)

#### [NEW] `infrastructure/kubernetes/platform/observability/kube-prometheus-values.yaml`
- kube-prometheus-stack Helm values extending existing Prometheus/Grafana:
  - `alertmanager.enabled: true` (port 9093)
  - AlertManager routes for `alphatracer` namespace alerts
  - `kube-state-metrics.enabled: true`
  - `nodeExporter.enabled: true`
  - Custom scrape configs for `alphatracer-dev` and `alphatracer` namespaces
  - Grafana provisioned dashboards for dev and prod

#### [NEW] `infrastructure/kubernetes/platform/observability/loki-values.yaml`
- Grafana Loki (single binary mode for local dev) on port 3100
- Promtail DaemonSet collecting pod logs from all namespaces

#### [NEW] `infrastructure/kubernetes/platform/observability/jaeger-values.yaml`
- Jaeger all-in-one deployment (port 16686)
- OTel Collector sidecar config forwarding traces from FastAPI → Jaeger

#### [NEW] `infrastructure/kubernetes/platform/observability/otel-collector.yaml`
- OpenTelemetry Collector deployment receiving OTLP from app pods
- Exports to Jaeger (traces), Prometheus (metrics), Loki (logs)

#### [NEW] `infrastructure/kubernetes/platform/observability/alertmanager-routes.yaml`
- AlertManagerConfig CRD with routes for:
  - `severity: critical` → webhook/notification
  - `namespace: alphatracer` → alphatracer team channel

#### [NEW] `infrastructure/kubernetes/platform/observability/grafana-dashboards/alphatracer-dev.json`
#### [NEW] `infrastructure/kubernetes/platform/observability/grafana-dashboards/alphatracer-prod.json`
- Pre-built Grafana dashboards as JSON ConfigMaps
- Dev dashboard: request rate, error rate, latency P50/P95/P99
- Prod dashboard: SLO burn rate, uptime, apdex

**Deploy commands**:
```powershell
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm upgrade --install kube-prometheus prometheus-community/kube-prometheus-stack -n monitoring --create-namespace -f infrastructure/kubernetes/platform/observability/kube-prometheus-values.yaml

helm repo add grafana https://grafana.github.io/helm-charts
helm install loki grafana/loki-stack -n monitoring -f infrastructure/kubernetes/platform/observability/loki-values.yaml
helm install jaeger grafana/jaeger -n monitoring -f infrastructure/kubernetes/platform/observability/jaeger-values.yaml
kubectl apply -f infrastructure/kubernetes/platform/observability/otel-collector.yaml
```

---

### Layer 9: Logging / SIEM — Loki + Promtail (no ELK)
**Covered by Layer 8** — Loki + Promtail replaces ELK for a student project. Kibana (`localhost:5601`) is too heavy; Grafana Explore + Loki is the modern lightweight alternative.

The Loki data source in Grafana provides:
- `http://localhost:3000/explore` → LogQL queries on all pod logs
- K8s audit logs via Falco → Falcosidekick → Loki integration

---

### Layer 10: Backup / DR — Velero
**Target**: `velero` CLI (no UI)

#### [NEW] `infrastructure/kubernetes/platform/velero/helm-values.yaml`
- Velero with local MinIO backend (S3-compatible) for backup storage
- Scheduled backup of `alphatracer` and `alphatracer-dev` namespaces
- MinIO deployed as sub-chart on port 9001

**Deploy command**:
```powershell
helm repo add vmware-tanzu https://vmware-tanzu.github.io/helm-charts
helm install velero vmware-tanzu/velero -n velero --create-namespace -f infrastructure/kubernetes/platform/velero/helm-values.yaml
```

**Usage**:
```powershell
velero backup create alphatracer-backup --include-namespaces alphatracer
velero backup get
```

---

### Layer 11: Chaos Engineering — Chaos Mesh
**Target URL**: `http://localhost:2333` (Chaos Mesh Dashboard)

#### [NEW] `infrastructure/kubernetes/platform/chaos-mesh/helm-values.yaml`
- Chaos Mesh with dashboard enabled on port 2333
- Pre-configured chaos experiments:
  - Pod kill in `alphatracer-dev` (test self-healing)
  - Network delay 100ms on `alphatracer-service`

#### [NEW] `infrastructure/kubernetes/platform/chaos-mesh/experiments/pod-kill.yaml`
#### [NEW] `infrastructure/kubernetes/platform/chaos-mesh/experiments/network-delay.yaml`

**Deploy command**:
```powershell
helm repo add chaos-mesh https://charts.chaos-mesh.org
helm install chaos-mesh chaos-mesh/chaos-mesh -n chaos-mesh --create-namespace -f infrastructure/kubernetes/platform/chaos-mesh/helm-values.yaml
```

---

### Layer 12: Auth / SSO — Keycloak
**Target URL**: `http://localhost:8081`

#### [NEW] `infrastructure/kubernetes/platform/keycloak/helm-values.yaml`
- Keycloak with:
  - `alphatracer` realm pre-configured
  - OIDC clients for ArgoCD and Grafana
  - Dev admin user for local testing
  - HTTP mode (no TLS required for local dev)
  - Port 8081

**Deploy command**:
```powershell
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install keycloak bitnami/keycloak -n keycloak --create-namespace -f infrastructure/kubernetes/platform/keycloak/helm-values.yaml
```

---

### Layer 13: Data Layer — PostgreSQL + pgAdmin
**Target URL**: `http://localhost:5050` (pgAdmin)

#### [NEW] `infrastructure/kubernetes/platform/data/postgres-helm-values.yaml`
- PostgreSQL 15 via Bitnami Helm chart
- Database: `trading_db` in `alphatracer` namespace
- Credentials stored in Vault (Layer 1) or K8s Secret

#### [NEW] `infrastructure/kubernetes/platform/data/pgadmin-deployment.yaml`
- pgAdmin 4 on port 5050
- Pre-configured server connection to the PostgreSQL instance

**Deploy commands**:
```powershell
helm install postgresql bitnami/postgresql -n alphatracer --create-namespace -f infrastructure/kubernetes/platform/data/postgres-helm-values.yaml
kubectl apply -f infrastructure/kubernetes/platform/data/pgadmin-deployment.yaml
```

---

### Layer 14: Compliance — Dependency-Track + DefectDojo
**Target URLs**: `http://localhost:8083` (Dependency-Track), `http://localhost:8084` (DefectDojo)

#### [NEW] `infrastructure/kubernetes/platform/compliance/dependency-track.yaml`
- Dependency-Track (OWASP) deployment + service on port 8083
- Ingests the SBOM generated by CI (`sbom.spdx.json`)
- API endpoint for automated SBOM upload from CI pipeline

#### [NEW] `infrastructure/kubernetes/platform/compliance/defectdojo-helm-values.yaml`
- DefectDojo Helm chart on port 8084
- Imports Trivy SARIF results and Bandit findings from CI
- Tracks vulnerabilities across releases

**Deploy commands**:
```powershell
kubectl apply -f infrastructure/kubernetes/platform/compliance/dependency-track.yaml
helm repo add defectdojo https://raw.githubusercontent.com/DefectDojo/django-DefectDojo/helm-charts
helm install defectdojo defectdojo/defectdojo -n compliance --create-namespace -f infrastructure/kubernetes/platform/compliance/defectdojo-helm-values.yaml
```

---

### Layer 15: Cost Visibility — OpenCost
**Target URL**: `http://localhost:9095`

#### [NEW] `infrastructure/kubernetes/platform/opencost/helm-values.yaml`
- OpenCost (free, CNCF) instead of Kubecost
- UI on port 9095
- Reads Prometheus metrics for cost allocation

**Deploy command**:
```powershell
helm repo add opencost https://opencost.github.io/opencost-helm-chart
helm install opencost opencost/opencost -n monitoring -f infrastructure/kubernetes/platform/opencost/helm-values.yaml
```

---

### Layer 16: Notifications — Alertmanager Routes
**Target URL**: `http://localhost:9093` (already part of Layer 8)

Alertmanager is deployed as part of kube-prometheus-stack. Additional configuration:

#### [NEW] `infrastructure/kubernetes/platform/observability/alertmanager-config.yaml`
- Routes: critical alerts → webhook receiver (can forward to Discord/Slack/email)
- Webhook receiver deployment that logs alerts (for demo/portfolio purposes)
- Inhibit rules to prevent alert storms

---

### Layer 17: CI Runners — ARC (Actions Runner Controller)
**No UI** — CLI/kubectl only

#### [NEW] `infrastructure/kubernetes/platform/arc/helm-values.yaml`
- GitHub Actions Runner Controller (ARC) for self-hosted runners inside K3s
- Runner scale set targeting `sebian-lab/alphatracer-financial-api` repo
- Requires a GitHub PAT (stored in Vault, Layer 1)

**Deploy command**:
```powershell
helm repo add actions-runner-controller https://actions-runner-controller.github.io/actions-runner-controller
helm install arc actions-runner-controller/actions-runner-controller -n arc --create-namespace -f infrastructure/kubernetes/platform/arc/helm-values.yaml
```

> [!WARNING]
> ARC requires a GitHub Personal Access Token with `repo` and `actions` scope. This should be stored in Vault and referenced as a K8s secret — never committed to git.

---

## Missing Branch / Product URL Patterns

### Environment Ingress Routes

All of these are handled by Layer 3 (Traefik IngressRoutes):

| URL | Backend | Namespace | Status |
|---|---|---|---|
| `https://alphatracer.local` | `alphatracer-service:8011` | `alphatracer` | [NEW] IngressRoute |
| `https://dev.alphatracer.local` | `alphatracer-service:8011` | `alphatracer-dev` | [NEW] IngressRoute |
| `https://staging.alphatracer.local` | `alphatracer-service:8011` | `alphatracer-staging` | [NEW] IngressRoute + namespace |
| `https://argocd.local` | `argocd-server:443` | `argocd` | [NEW] IngressRoute |

### FastAPI Endpoints (Already Working, Just Not Documented)

| URL | Notes |
|---|---|
| `http://localhost:8011/openapi.json` | ✅ FastAPI auto-generates this |
| `http://localhost:8011/redoc` | ✅ FastAPI auto-generates this |
| `http://localhost:8011/docs` | ✅ Already working |
| `http://localhost:8011/health` | ✅ Already working |
| `http://localhost:8011/metrics` | ✅ Already working |

### ArgoCD App-Specific URLs

| URL | Notes |
|---|---|
| `https://localhost:8080/applications/alphatracer-dev` | Works once ArgoCD + argo-app-dev.yaml are applied |
| `https://localhost:8080/applications/alphatracer-prod` | Works once ArgoCD + argo-app-prod.yaml are applied |

### Grafana Dashboard URLs

| URL | Notes |
|---|---|
| `http://localhost:3000/d/alphatracer-dev` | [NEW] ConfigMap dashboard provisioned in Layer 8 |
| `http://localhost:3000/d/alphatracer-prod` | [NEW] ConfigMap dashboard provisioned in Layer 8 |

### Prometheus Target URLs

| URL | Notes |
|---|---|
| `http://localhost:9090/targets?search=alphatracer-dev` | Works once ServiceMonitor in dev namespace is scraped |
| `http://localhost:9090/targets?search=alphatracer-prod` | Works once ServiceMonitor in prod namespace is scraped |

---

## Master Setup Script

#### [NEW] `scripts/setup-platform.ps1`

Orchestrates the entire platform deployment in correct dependency order:

```
Phase 1: Prerequisites
  → Start Docker Desktop
  → Verify K3s cluster
  → Add hosts file entries

Phase 2: Core Infrastructure
  → Vault (secrets must exist before apps)
  → Local Registry
  → cert-manager + Ingress routes

Phase 3: Application Deployment
  → PostgreSQL (data layer)
  → ArgoCD (deploys the app via GitOps)
  → Apply ArgoCD Application manifests

Phase 4: Security & Policy
  → Kyverno + policies
  → Policy Reporter
  → Falco

Phase 5: Observability
  → kube-prometheus-stack (Prometheus + Grafana + Alertmanager)
  → Loki + Promtail
  → Jaeger + OTel Collector

Phase 6: Extended Platform
  → Keycloak
  → pgAdmin
  → OpenCost
  → Chaos Mesh
  → Velero
  → ZAP + SonarQube

Phase 7: Compliance
  → Dependency-Track
  → DefectDojo

Phase 8: Verification
  → Port-forward all services
  → Health check all URLs
  → Print URL table with status
```

#### [NEW] `scripts/teardown-platform.ps1`
- Uninstalls all Helm releases and deletes namespaces in reverse order

---

## Updated Port-Forward Script

#### [MODIFY] [`scripts/port-forward-all.ps1`](file:///c:/Users/sebia/Downloads/school/intern/2th/alphatracer-financial-api/scripts/port-forward-all.ps1)

Add all new services:

| Service | Namespace | Local Port | Remote Port |
|---|---|---|---|
| Vault | `vault` | 8200 | 8200 |
| Local Registry | `registry` | 5000 | 5000 |
| Falcosidekick UI | `falco` | 2801 | 2801 |
| Policy Reporter | `kyverno` | 8082 | 8082 |
| Alertmanager | `monitoring` | 9093 | 9093 |
| Jaeger Query | `monitoring` | 16686 | 16686 |
| Loki | `monitoring` | 3100 | 3100 |
| Keycloak | `keycloak` | 8081 | 8080 |
| pgAdmin | `alphatracer` | 5050 | 5050 |
| OpenCost | `monitoring` | 9095 | 9090 |
| Chaos Mesh | `chaos-mesh` | 2333 | 2333 |
| ZAP | `testing` | 8090 | 8090 |
| SonarQube | `testing` | 9000 | 9000 |
| Dependency-Track | `compliance` | 8083 | 8080 |
| DefectDojo | `compliance` | 8084 | 8080 |

---

## New File Tree (Platform Services)

```
infrastructure/kubernetes/platform/
├── vault/
│   ├── namespace.yaml
│   ├── helm-values.yaml
│   └── vault-secret-policy.hcl
├── registry/
│   ├── deployment.yaml
│   └── service.yaml
├── ingress/
│   ├── traefik-ingress-routes.yaml
│   ├── cert-manager-values.yaml
│   └── self-signed-issuer.yaml
├── falco/
│   └── helm-values.yaml
├── policy-reporter/
│   └── helm-values.yaml
├── observability/
│   ├── kube-prometheus-values.yaml
│   ├── loki-values.yaml
│   ├── jaeger-values.yaml
│   ├── otel-collector.yaml
│   ├── alertmanager-config.yaml
│   └── grafana-dashboards/
│       ├── alphatracer-dev.json
│       └── alphatracer-prod.json
├── testing/
│   ├── zap-deployment.yaml
│   └── sonarqube-helm-values.yaml
├── keycloak/
│   └── helm-values.yaml
├── data/
│   ├── postgres-helm-values.yaml
│   └── pgadmin-deployment.yaml
├── compliance/
│   ├── dependency-track.yaml
│   └── defectdojo-helm-values.yaml
├── opencost/
│   └── helm-values.yaml
├── velero/
│   └── helm-values.yaml
├── chaos-mesh/
│   ├── helm-values.yaml
│   └── experiments/
│       ├── pod-kill.yaml
│       └── network-delay.yaml
└── arc/
    └── helm-values.yaml

policies/kyverno/
├── disallow-root.yaml          (MODIFY — add prod namespace)
├── verify-image-signatures.yaml (NEW)
├── restrict-registries.yaml     (NEW)
└── require-resource-limits.yaml (NEW)

scripts/
├── setup-platform.ps1           (NEW — master deploy script)
├── setup-hosts.ps1              (NEW — hosts file setup)
├── teardown-platform.ps1        (NEW — cleanup script)
├── port-forward-all.ps1         (MODIFY — add all new services)
├── create-k3s-secrets.ps1       (existing)
└── mock-k3s-autopull.ps1        (existing)
```

---

## Complete URL Table After Implementation

| # | Service | URL | Layer |
|---|---|---|---|
| 1 | **Prod API Swagger** | `http://localhost:8011/docs` | Existing |
| 2 | **Prod API ReDoc** | `http://localhost:8011/redoc` | Existing |
| 3 | **Prod API OpenAPI** | `http://localhost:8011/openapi.json` | Existing |
| 4 | **Prod API Health** | `http://localhost:8011/health` | Existing |
| 5 | **Prod API Metrics** | `http://localhost:8011/metrics` | Existing |
| 6 | **Dev API Swagger** | `http://localhost:8012/docs` | Layer 3 |
| 7 | **Prod Ingress** | `https://alphatracer.local` | Layer 3 |
| 8 | **Dev Ingress** | `https://dev.alphatracer.local` | Layer 3 |
| 9 | **Staging Ingress** | `https://staging.alphatracer.local` | Layer 3 |
| 10 | **ArgoCD Dashboard** | `https://localhost:8080` | Existing manifest |
| 11 | **ArgoCD Dev App** | `https://localhost:8080/applications/alphatracer-dev` | Existing manifest |
| 12 | **ArgoCD Prod App** | `https://localhost:8080/applications/alphatracer-prod` | Existing manifest |
| 13 | **HashiCorp Vault** | `http://localhost:8200` | Layer 1 |
| 14 | **Local Registry** | `http://localhost:5000/v2/_catalog` | Layer 2 |
| 15 | **Prometheus** | `http://localhost:9090` | Layer 8 |
| 16 | **Prometheus Dev Targets** | `http://localhost:9090/targets?search=alphatracer-dev` | Layer 8 |
| 17 | **Prometheus Prod Targets** | `http://localhost:9090/targets?search=alphatracer-prod` | Layer 8 |
| 18 | **Grafana** | `http://localhost:3000` | Layer 8 |
| 19 | **Grafana Dev Dashboard** | `http://localhost:3000/d/alphatracer-dev` | Layer 8 |
| 20 | **Grafana Prod Dashboard** | `http://localhost:3000/d/alphatracer-prod` | Layer 8 |
| 21 | **Alertmanager** | `http://localhost:9093` | Layer 8 |
| 22 | **Jaeger Tracing** | `http://localhost:16686` | Layer 8 |
| 23 | **Loki Logs** | `http://localhost:3100` | Layer 8 |
| 24 | **Falcosidekick UI** | `http://localhost:2801` | Layer 4 |
| 25 | **Policy Reporter** | `http://localhost:8082` | Layer 5 |
| 26 | **Keycloak SSO** | `http://localhost:8081` | Layer 12 |
| 27 | **pgAdmin** | `http://localhost:5050` | Layer 13 |
| 28 | **ZAP DAST** | `http://localhost:8090` | Layer 7 |
| 29 | **SonarQube** | `http://localhost:9000` | Layer 7 |
| 30 | **Dependency-Track** | `http://localhost:8083` | Layer 14 |
| 31 | **DefectDojo** | `http://localhost:8084` | Layer 14 |
| 32 | **OpenCost** | `http://localhost:9095` | Layer 15 |
| 33 | **Chaos Mesh** | `http://localhost:2333` | Layer 11 |

---

## Open Questions

> [!IMPORTANT]
> **Resource constraints**: Running all 17 layers simultaneously needs ~16 GB RAM minimum. Your local machine may not handle Vault + Keycloak + SonarQube + DefectDojo + Chaos Mesh all at once.
>
> **Option A**: Deploy everything (needs 16+ GB RAM)
> **Option B**: Deploy in tiers — Core (Layers 1-5, 8) first (~8 GB), Extended (Layers 7, 11-15) on demand
>
> Which approach do you prefer?

> [!IMPORTANT]
> **Docker Desktop vs WSL2 K3s**: Your Docker Desktop service is stopped and K3s is not responding. Do you want:
> 1. Start Docker Desktop and use its built-in Kubernetes? (easiest)
> 2. Install K3s inside the existing Ubuntu WSL2 distro? (more realistic, matches prod)
> 3. Use K3d (K3s in Docker) once Docker Desktop is running?

> [!WARNING]
> **GitHub PAT for ARC**: The Actions Runner Controller (Layer 17) requires a GitHub Personal Access Token. Do you already have one, or should we skip ARC and use `act` (local GitHub Actions runner) instead?

---

## Verification Plan

### Automated Verification
```powershell
# After setup-platform.ps1 completes:
.\scripts\port-forward-all.ps1

# Health check all URLs
$urls = @(
    "http://localhost:8011/health",
    "http://localhost:8200/v1/sys/health",
    "http://localhost:5000/v2/_catalog",
    "http://localhost:9090/-/healthy",
    "http://localhost:3000/api/health",
    "http://localhost:9093/-/healthy",
    "http://localhost:16686/",
    "http://localhost:2801/",
    "http://localhost:8082/",
    "http://localhost:8081/",
    "http://localhost:5050/",
    "http://localhost:9000/api/system/status",
    "http://localhost:8083/",
    "http://localhost:8084/",
    "http://localhost:9095/",
    "http://localhost:2333/"
)

foreach ($url in $urls) {
    try {
        $r = Invoke-WebRequest -Uri $url -TimeoutSec 5 -UseBasicParsing
        Write-Host "✅ $url -> $($r.StatusCode)" -ForegroundColor Green
    } catch {
        Write-Host "❌ $url -> FAILED" -ForegroundColor Red
    }
}
```

### Manual Verification
- Open each URL in browser and verify the UI loads
- Create a test secret in Vault UI
- Push a test image to `localhost:5000`
- Trigger a Kyverno policy violation and check Policy Reporter
- View Falco alerts in Falcosidekick UI
- Query logs in Grafana Explore via Loki
- View traces in Jaeger
