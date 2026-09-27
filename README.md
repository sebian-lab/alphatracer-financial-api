# 📈 AlphaTracer Financial API — DevSecOps & Enterprise Observability Platform

[![DevSecOps Pipeline](https://img.shields.io/badge/CI%2FCD-3--Branch%20GitHub%20Actions-blue?logo=githubactions)](https://github.com/sebian-lab/alphatracer-financial-api/actions)
[![Architecture](https://img.shields.io/badge/Architecture-10--Container%20Docker%20Compose-2496ED?logo=docker)](docker-compose.yml)
[![Observability](https://img.shields.io/badge/Observability-Prometheus%20%2B%20Grafana%20%2B%20Jaeger%20%2B%20Loki-red?logo=prometheus)](https://prometheus.io/)
[![Secrets](https://img.shields.io/badge/Secrets-HashiCorp%20Vault-black?logo=vault)](https://www.vaultproject.io/)
[![Container Security](https://img.shields.io/badge/Security-Trivy%20%2B%20Cosign%20Signing-blue?logo=aquasec)](https://trivy.dev/)
[![Shift-Left Security](https://img.shields.io/badge/Shift--Left-Gitleaks%20%2B%20Bandit%20%2B%20Ruff-cyan)](#-developer-productivity--pre-commit-safeguards)
[![Zero Cloud Cost](https://img.shields.io/badge/Cloud%20Spend-%240%20Zero%20Cost%20Local%20Stack-success)](#-complete-devsecops--observability-platform-stack)
[![Target Role](https://img.shields.io/badge/Focus-Software%20Engineering%20%2F%20DevSecOps-blue)](#-competencies--engineering-focus-general-internship-presentation)

> 🎓 **Engineering Internship Portfolio Project**: A production-grade **DevSecOps & Dual-Architecture Platform** demonstrating an automated **3-branch workflow (`dev`, `main`, `prod`)**, **Shift-Left Security**, **GitHub Actions CI/CD**, **Container Supply Chain Security (Trivy, Cosign, SBOM)**, **Dual Docker Compose (Dev Hot-Reload vs. Prod Immutable Signed Stack)**, and **Full-Stack Observability (Prometheus, Grafana, Jaeger, Loki)**.

---

## 🎯 Engineering Objectives & Project Architecture

This repository demonstrates practical implementation of production software delivery standards:
1. **Multi-stage release branches (`dev` ➔ `main` ➔ `prod`)** with automated promotion and branch protection safeguards.
2. **Shift security left to the local workstation**: block leaked credentials and vulnerable code *before* commit (`.pre-commit-config.yaml` + Gitleaks + Ruff + Bandit).
3. **Automate container supply chain verification**: scan CVEs (Trivy), generate SBOMs (Anchore), and sign container images keylessly via Cosign and GitHub OIDC.
4. **Dual Docker Compose Architectures**: maintain a fast developer hot-reloading environment alongside a hardened, signed production container stack.
5. **Full-Stack Observability & Telemetry**: unified monitoring with custom ASGI Prometheus metrics, Jaeger OTel distributed tracing, Loki centralized logging, and Grafana dashboards.

---

## 🌿 3-Branch Strategy & DevSecOps Flow

```mermaid
flowchart TD
    subgraph DevMachine["💻 Developer Workstation (Shift-Left)"]
        Code["Developer Code Changes"] --> PreCommit{"Pre-Commit Hooks (<2s)<br/>• Gitleaks (Secret Detection)<br/>• Ruff (Linting & Formatting)"}
        PreCommit --> ScriptCheck["Local Verification Script<br/>dev-check.ps1 (Tests + Bandit + Compose)"]
        ScriptCheck -->|Pass: Zero Secrets & Vulnerabilities| PushDev["git push origin dev"]
    end

    subgraph BranchDev["🧪 Branch: 'dev' (Development & Fast Iteration)"]
        PushDev --> PipelineDev["Full CI/CD Pipeline<br/>• Pytest Unit & Financial Ledger Tests<br/>• Bandit SAST Security Scan<br/>• Trivy Container CVE Scan (Export SARIF)<br/>• Local Dev: docker-compose.yml (Hot-Reload)"]
    end

    subgraph BranchMain["🚀 Branch: 'main' (Staging & Release Candidate)"]
        PipelineDev -.->|Open Pull Request| PRReview{"PR Code Review & CI Gating<br/>• Strict CI Checks Required<br/>• Linear Git History Enforced"}
        PRReview -->|Merge PR| PipelineMain["Staging Verification Pipeline<br/>• Integration Test Suite<br/>• SBOM Generation (SPDX format)<br/>• Push Candidate Image to GHCR"]
    end

    subgraph BranchProd["🛡️ Branch: 'prod' (Production Release — Gated)"]
        PipelineMain -.->|Release Promotion PR| Gate{"🛑 MANUAL APPROVAL REQUIRED<br/>GitHub Environment: 'production'<br/>Lead Reviewer Sign-Off"}
        Gate -->|Approved & Signed Off| PipelineProd["Production Sign & Deploy<br/>• Sigstore Cosign Keyless OIDC Signing<br/>• Rekor Transparency Log Recording<br/>• Update docker-compose.prod.yml Image Tag"]
        PipelineProd --> DockerProd["Production Docker Deployment<br/>• docker compose -f docker-compose.prod.yml up -d<br/>• Immutable signed image from GHCR"]
    end
```

| Branch | Environment | Compose File | Deployment Mechanism | Image Signing | Deployment Gate |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`dev`** | Development | `docker-compose.yml` | Local build & live hot-reload (`./app` bind mount) | No (Fast iteration) | Automated |
| **`main`** | Release Candidate / Staging | `docker-compose.prod.yml` | Pre-prod verification & SBOM | Optional | Automated PR Review |
| **`prod`** | Production | `docker-compose.prod.yml` | Immutable GHCR pull (Zero host bind mounts) | **Yes (Cosign Keyless)** | **🛑 Manual Approval Only** |

---

## ⚡ Developer Productivity & Pre-Commit Safeguards

### 1. Instant Pre-Commit Hooks (Shift-Left in <2 Seconds)
Catching security flaws before code leaves the workstation preserves developer velocity and eliminates CI failures:
```bash
# Install and activate pre-commit hooks
pip install pre-commit
pre-commit install

# Manually trigger on all files
pre-commit run --all-files
```
- 🔒 **Gitleaks**: Scans staged commits for hardcoded secrets, database passwords, and API tokens.
- ⚡ **Ruff**: High-speed Python linter and formatter running in milliseconds.
- 🧹 **File Hygiene**: Automatically strips trailing whitespace and validates YAML structure.

### 2. Fast Pre-PR Validation Script (`dev-check.ps1`)
Run locally before opening a Pull Request to catch issues in seconds:
```powershell
.\dev-check.ps1
```
```text
🔍 Starting AlphaTracer DevSecOps Pre-PR Checks...

🧪 [1/5] Running Pytest Unit Tests... ✅
🛡️ [2/5] Running Bandit SAST Code Analysis... ✅
🔒 [3/5] Running Gitleaks Secret Detection... ✅
🐳 [4/5] Validating Development Docker Compose (docker-compose.yml)... ✅
🚀 [5/5] Validating Production Docker Compose (docker-compose.prod.yml)... ✅

🎉 ALL PRE-PR CHECKS PASSED SUCCESSFULLY! Ready to push & open PR. 🚀
```

### 3. DevSecOps Secret Practice: Zero Cleartext `.env` Files
> **DevSecOps Principle**: In accordance with CIS benchmarks and production security guidelines, **no cleartext `.env` files are checked into source control**.
> - In Production / Compose: Secrets are injected dynamically at runtime via **HashiCorp Vault** (`app/core/config.py`).
> - In CI/CD: Injected via ephemeral runner environment variables (`${{ secrets.GITHUB_TOKEN }}`).
> - In Local Pytest: Driven dynamically in-process via test runners without touching disk.

---

## 📸 Terminal Evidence & CI/CD Pipelines

### 1. Shift-Left SAST & Unit Tests Running Locally
```text
$ pytest -q
...                                                                      [100%]
3 passed, 3 warnings in 0.94s
```

### 2. Live GitHub Actions Pipeline Proof (`gh run list --workflow="main-ci.yml"`)
```text
$ gh run list --workflow="main-ci.yml" --limit 3
STATUS      RESULT   TITLE                        WORKFLOW             BRANCH  EVENT          ID            ELAPSED  AGE
completed   success  Dev                          Full CI/CD Pipeline  dev     pull_request   30170907249   2m16s    1m
completed   success  Merge branch 'main' into dev Full CI/CD Pipeline  dev     push           30170905899   2m59s    1m
completed   success  fix: add production defaults Full CI/CD Pipeline  dev     push           30170757484   3m47s    1m
```

### 3. Real Security Scan Details (`gh run view 30170905899 --job 89711796054`)
```text
✓ dev Full CI/CD Pipeline sebian-lab/alphatracer-financial-api#5 · 30170905899
✓ security / security-scan in 2m14s (ID 89711796054)
  ✓ Set up job
  ✓ Run actions/checkout@v4
  ✓ Gitleaks (Zero secret findings)
  ✓ Set up Docker Buildx
  ✓ Build image
  ✓ Load image into Docker daemon
  ✓ Trivy container scan (Zero HIGH/CRITICAL CVEs)
  ✓ Upload SARIF to GitHub Security tab
  ✓ Generate SBOM (Anchore / SPDX format)
  ✓ Upload SBOM artifact
  ✓ Push and Sign (keyless via Cosign & Sigstore OIDC)
  ✓ Complete job
```

### 4. Automated Production Compose Promotion (`main-ci.yml`)
```text
✓ update-prod-compose in 8s
  ✓ Set up job
  ✓ Run actions/checkout@v4
  ✓ Update signed image tag in docker-compose.prod.yml
  ✓ Commit and push compose update
  ✓ Complete job
```

---

## 🐳 Dual Docker Architecture: Development vs. Production

To bridge the gap between rapid developer velocity and hardened cloud security, AlphaTracer maintains two distinct, purpose-built Docker Compose architectures:

```mermaid
flowchart TB
    subgraph DEV_ENV["🧪 Development Stack (docker-compose.yml)"]
        direction TB
        HostCode["💻 Host Filesystem (./app)"]
        DevAPI["alphatracer-api (:8011)<br/>• Local Build: Dockerfile<br/>• Live Bind-Mount: ./app:/app/app<br/>• Uvicorn Hot-Reload"]
        DevDB[("PostgreSQL 15<br/>Volume: postgres_data")]
        DevTools["Local DevSecOps & Security Tools<br/>• HashiCorp Vault (:8200)<br/>• Trivy Scanner Server (:4954)<br/>• Local Docker OCI Registry (:5000)"]
        
        HostCode ==>|Live Bind-Mount| DevAPI
        DevAPI -->|SQL Queries| DevDB
        DevAPI -.->|Dynamic Secrets| DevTools
    end

    subgraph PROD_ENV["🛡️ Production Stack (docker-compose.prod.yml)"]
        direction TB
        GHCR["📦 GitHub Container Registry (GHCR)<br/>ghcr.io/sebian-lab/alphatracer-financial-api:sha"]
        CosignVerify["🔐 Sigstore / Cosign Verification<br/>Keyless OIDC Signed Image"]
        ProdAPI["alphatracer-api-prod (:8011)<br/>• Pulls Verified Signed Image from GHCR<br/>• Zero Host Bind-Mounts (Code Sealed Inside)<br/>• Non-Root appuser (UID 1000)"]
        ProdDB[("PostgreSQL 15<br/>Volume: postgres_prod_data")]
        
        GHCR --> CosignVerify -->|Pull Signed Artifact| ProdAPI
        ProdAPI -->|Production DB Transactions| ProdDB
    end

    subgraph TELEMETRY["📊 Shared Enterprise Observability & Monitoring Engine"]
        Prom["Prometheus (:9090)<br/>Scrapes :8011/metrics every 15s"]
        Alert["Alertmanager (:9093)<br/>Notification Routing & Grouping"]
        Jaeger["Jaeger OTLP (:16686)<br/>Distributed Request Spans (:4318)"]
        Loki["Loki Engine (:3100)<br/>High-Throughput Log Aggregator"]
        Grafana["Grafana Dashboards (:3000)<br/>Unified Golden Signals Visualizer"]
        
        Prom -->|Fire Threshold Alerts| Alert
        Grafana -->|PromQL| Prom
        Grafana -->|LogQL| Loki
    end

    %% Observability Connections
    DevAPI -->|Metrics / Traces / Logs| TELEMETRY
    ProdAPI -->|Metrics / Traces / Logs| TELEMETRY
```

### Architectural Comparison: Dev vs. Production

| Dimension | Development (`docker-compose.yml`) | Production (`docker-compose.prod.yml`) |
| :--- | :--- | :--- |
| **Primary Goal** | Sub-second developer iteration & debugging | Immutability, zero configuration drift, high security |
| **Image Artifact** | Built locally on-the-fly (`build: .`) | Pulled from GHCR with immutable Git commit SHA tag |
| **Code Mounting** | **Host bind mount** (`./app:/app/app`) for hot-reload | **Zero host mounts** (Code is immutably sealed in image) |
| **Container User** | `appuser` (non-root in Dockerfile) | `appuser` (non-root enforced) |
| **Supply Chain Security**| Local unverified builds | Cryptographically signed via **Sigstore / Cosign** |
| **Database Isolation** | Volume: `postgres_data` | Isolated Volume: `postgres_prod_data` |
| **Supporting Services** | Includes Vault, Trivy scanner, Local Registry | Streamlined stack with database & observability |
| **Startup Command** | `docker compose -f docker-compose.yml up --build -d` | `docker compose -f docker-compose.prod.yml up -d` |

---

## 🖥️ Complete DevSecOps & Observability Platform Stack

All 10 services are pre-wired and running locally via Docker Compose (`docker compose up -d`):

| Platform Component | Local Endpoint URL | Role / Why It Matters | Status |
| :--- | :--- | :--- | :--- |
| **AlphaTracer API (FastAPI)** | [`http://localhost:8011/docs`](http://localhost:8011/docs) | Financial market data backend (Swagger UI & `/health`) | 🟢 Active |
| **PostgreSQL 15 Database** | `localhost:5432` | Relational ledger, users, portfolios, and transactions | 🟢 Active |
| **Prometheus Metrics** | [`http://localhost:9090`](http://localhost:9090) | Time-Series Metrics Scraper & PromQL Target Status | 🟢 Active |
| **Grafana UI** | [`http://localhost:3000`](http://localhost:3000) (admin / admin) | Unified Golden Signals, Dashboards, and Visualizations | 🟢 Active |
| **Alertmanager** | [`http://localhost:9093`](http://localhost:9093) | Prometheus Alert Routing, Silences & Webhooks | 🟢 Active |
| **Jaeger Tracing** | [`http://localhost:16686`](http://localhost:16686) | OTLP Distributed Tracing & Request Latency Spans | 🟢 Active |
| **Loki Log Engine** | [`http://localhost:3100`](http://localhost:3100) | Centralized JSON Container Log Stream Collector | 🟢 Active |
| **HashiCorp Vault** | [`http://localhost:8200`](http://localhost:8200) | Centralized KV v2 Secret Management & Dynamic Retrieval | 🟢 Active |
| **Local Docker Registry**| [`http://localhost:5000`](http://localhost:5000) | Local Container Push/Pull Distribution Cache | 🟢 Active |
| **Trivy Vulnerability Server** | [`http://localhost:4954`](http://localhost:4954) | Container & Dependency Security CVE Scanner Daemon | 🟢 Active |

### 📋 Live Platform Execution Log
Run the automated live probe script anytime to verify all platform services:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\probe-observability.ps1
```
```text
=================================================================================
 [PROBE] ALPHATRACER DEVSECOPS & OBSERVABILITY LIVE PLATFORM STATUS
 Running on Local Workstation / Homelab Architecture
 Timestamp: 2026-09-24 15:13:41 +02:00
=================================================================================

 [ONLINE] AlphaTracer API (FastAPI)    HTTP 200 (76.1ms) -> Core Financial Portfolio & Market Engine (REST API)
 [ONLINE] FastAPI Swagger Docs         HTTP 200 (2.7ms)  -> OpenAPI 3.1 Interactive Contract & Endpoint Explorer
 [ONLINE] Prometheus Metrics Exporter  HTTP 200 (3.8ms)  -> Dynamic Prometheus Text Exposition (/metrics)
 [ONLINE] Prometheus Time-Series DB    HTTP 200 (5.4ms)  -> Time-Series Telemetry Scraper & PromQL Target Status
 [ONLINE] Grafana Dashboards           HTTP 200 (5.6ms)  -> Unified Golden Signals, LogQL & Tracing Visualizer
 [ONLINE] Alertmanager                 HTTP 200 (5.8ms)  -> Alert Routing Engine, Silences & Grouping Webhooks
 [ONLINE] Jaeger Distributed Tracing   HTTP 200 (7.4ms)  -> OTLP Request Span Waterfall & Latency Bottleneck Analysis
 [ONLINE] Loki Container Log Engine    HTTP 200 (8.1ms)  -> High-Efficiency Index-Free Container Log Aggregator
 [ONLINE] HashiCorp Vault              HTTP 200 (5.3ms)  -> Dynamic Secret Storage, Leasing & Central Identity Engine
 [ONLINE] Local Docker OCI Registry    HTTP 200 (12.8ms) -> Local Container Push/Pull Distribution Cache (:5000)
 [ONLINE] Trivy Vulnerability Server   HTTP 200 (5.9ms)  -> Container Image & Filesystem CVE Scanner Daemon (:4954)

=================================================================================
 [SUMMARY] PLATFORM HEALTH: 11 / 11 Endpoints Healthy
 All DevSecOps & Observability Docker containers verified operational!
=================================================================================
```

### 📸 Visual Evidence Gallery: Running Services on Workstation

#### 1. AlphaTracer Financial API (FastAPI Swagger Contract UI)
![FastAPI Swagger UI](docs/screenshots/01_fastapi_swagger.png)

#### 2. Grafana Unified Telemetry & Golden Signals Dashboards
![Grafana UI](docs/screenshots/02_grafana_ui.png)

#### 3. Prometheus PromQL Metrics Engine & Target Health (1/1 UP)
![Prometheus PromQL Graph](docs/screenshots/03_prometheus_graph.png)
![Prometheus Active Scrape Targets](docs/screenshots/03_prometheus_targets.png)

#### 4. Alertmanager (Notification Routing & Firing Alerts)
![Alertmanager UI](docs/screenshots/04_alertmanager_ui.png)

#### 5. Jaeger Distributed Tracing (OTLP Waterfall Spans & Endpoint Latency)
![Jaeger Tracing UI](docs/screenshots/05_jaeger_tracing.png)

#### 6. HashiCorp Vault (Dynamic Secrets & Central Identity)
![HashiCorp Vault UI](docs/screenshots/06_vault_ui.png)

#### 7. Local Container Registry v2 (Image Catalog API)
![Local Docker Registry](docs/screenshots/07_local_registry.png)

#### 8. Trivy Vulnerability Security Server (CVE Scan Service)
![Trivy Server](docs/screenshots/08_trivy_server.png)

#### 9. Loki Centralized Log Aggregator Engine
![Loki Ready Probe](docs/screenshots/09_loki_ready.png)

#### 10. Cloud-Native Blueprint & Cluster Experimentation
![Cluster Status](docs/screenshots/10_k3s_cluster.png)

### ⚡ Quick Start: Manage Stack with Docker Compose
```bash
# Start the complete platform stack in the background
docker compose up -d

# Verify all services status
docker compose ps
```

---

## 🛠️ Complete DevSecOps Toolchain Summary

| Category | Tool / Component | Implementation & Value | Local Sandbox Endpoint | Verification |
| :--- | :--- | :--- | :--- | :--- |
| **API Application** | [FastAPI](https://fastapi.tiangolo.com/) + PostgreSQL 15 | Financial market data & portfolio tracking backend | [`http://localhost:8011/docs`](http://localhost:8011/docs) • [`/health`](http://localhost:8011/health) | [app/main.py](app/main.py) |
| **Observability (Metrics)**| [Prometheus](https://prometheus.io/) | Time-series scraper collecting `/metrics` counters, histograms, and uptime | [`http://localhost:9090`](http://localhost:9090) | [prometheus.yml](infrastructure/prometheus/prometheus.yml) |
| **Observability (Dashboards)**| [Grafana](https://grafana.com/) | Unified Golden Signals visualizer with PromQL & LogQL streams | [`http://localhost:3000`](http://localhost:3000) (admin / admin) | Pre-configured in Docker Compose |
| **Distributed Tracing** | [Jaeger OTLP](https://www.jaegertracing.io/) | OpenTelemetry request span waterfalls and latency profiling | [`http://localhost:16686`](http://localhost:16686) (OTLP :4318) | Live OpenTelemetry instrumentation |
| **Log Aggregation** | [Grafana Loki](https://grafana.com/oss/loki/) | High-efficiency container log aggregation via direct HTTP push | [`http://localhost:3100/ready`](http://localhost:3100/ready) | Direct HTTP push handler |
| **Alert Routing** | [Alertmanager](https://prometheus.io/docs/alerting/latest/alertmanager/) | Prometheus alert grouping, silence windows, and webhook routing | [`http://localhost:9093`](http://localhost:9093) | Clustered on port 9094 |
| **Secret Management** | [HashiCorp Vault](https://www.vaultproject.io/) | Centralized KV v2 dynamic secret leasing (JWT keys & DB credentials) | [`http://localhost:8200`](http://localhost:8200) | [scripts/seed-vault.ps1](scripts/seed-vault.ps1) |
| **Container CVE Scan** | [Aqua Security Trivy](https://trivy.dev/) | Image and filesystem CVE vulnerability scanner daemon | [`http://localhost:4954/healthz`](http://localhost:4954/healthz) | Live daemon + CI action |
| **Local OCI Registry** | [Docker Registry v2](https://distribution.github.io/distribution/) | Private container distribution cache | [`http://localhost:5000/v2/`](http://localhost:5000/v2/) | Local container push/pull |
| **Cryptographic Provenance**| [Sigstore Cosign](https://docs.sigstore.dev/cosign/overview/) | Keyless container image signing using GitHub OIDC on `prod` branch | [GitHub Container Registry (GHCR)](https://github.com/sebian-lab?tab=packages) | Verified by Sigstore |
| **Software Supply Chain**| [Anchore Syft (SBOM)](https://github.com/anchore/syft) | Automated SPDX Software Bill of Materials generation | Downloadable in CI Artifacts | [.github/workflows/main-ci.yml](.github/workflows/main-ci.yml) |
| **Secret Scanning** | [Gitleaks](https://github.com/gitleaks/gitleaks) | Secret detection blocking credential leaks before commit | Instant pre-PR & pre-commit hook | [.gitleaks.toml](.gitleaks.toml) |
| **SAST Code Scanner** | [PyCQA Bandit](https://bandit.readthedocs.io/) | Python AST static security vulnerability analysis | CLI: `bandit -r app/ -ll -ii` | [dev-check.ps1](dev-check.ps1) |
| **CI/CD Orchestration** | [GitHub Actions](https://github.com/sebian-lab/alphatracer-financial-api/actions) | 3-Branch automated pipeline: tests, SAST, Trivy, SBOM, signing, and compose tag update | Cloud Runner Matrix | [.github/workflows/main-ci.yml](.github/workflows/main-ci.yml) |

---

## 📂 Repository Structure

```
alphatracer-financial-api/
├── .github/
│   └── workflows/
│       ├── main-ci.yml             # 3-Branch Orchestrator (dev, main, prod triggers)
│       └── reusable-security.yml   # Security scan, Trivy SARIF, SBOM & Cosign signing
├── app/                            # FastAPI application code & endpoints
│   ├── api/v1/                     # Modular API endpoints (auth, stocks, portfolio, watchlist)
│   ├── core/                       # App config, database session, security, and telemetry
│   ├── models/                     # SQLAlchemy ORM models (user, stock, portfolio, watchlist)
│   ├── schemas/                    # Pydantic data schemas & request/response validation
│   ├── services/                   # Business logic (price caching, indicators, metrics)
│   └── utils/                      # InMemoryLimiter, CSV loaders & helpers
├── docs/
│   └── screenshots/                # Real captured evidence of platform services & UI
├── infrastructure/
│   └── prometheus/                 # Prometheus scrape configuration (prometheus.yml)
├── scripts/
│   ├── dev-check.ps1               # 30-second pre-PR developer validation script
│   ├── probe-observability.ps1     # Live health probe for all 10 platform services
│   ├── seed-vault.ps1              # HashiCorp Vault initialization & secret seeding
│   ├── generate-demo-traffic.ps1   # Traffic simulator for telemetry & latency graphs
│   └── showcase-devops-lifecycle.ps1
├── tests/                          # Automated Pytest suite & E2E integration test scripts
│   ├── test_deployment_to_running.sh  # 456-line E2E script covering full platform lifecycle
│   ├── test_all_endpoints.sh       # Comprehensive API endpoint verification script
│   └── test_health.py              # Pytest unit tests for rate limits & health routes
├── .env.example                    # Sample environment variables template
├── .gitleaks.toml                  # Gitleaks custom secret scanning ruleset
├── .pre-commit-config.yaml         # Pre-commit configuration for git hooks (Gitleaks, Ruff)
├── alembic.ini                     # Database migration configuration
├── Dockerfile                      # Hardened container build with non-root appuser
├── docker-compose.yml              # Local development stack (10 containers, hot-reloading)
├── docker-compose.prod.yml         # Production stack (GHCR immutable signed images)
├── requirements.txt                # Python dependencies & libraries
├── README.md                       # Main Architecture & DevSecOps Overview
└── Usage&examples.md               # Detailed API Reference & Local Developer Guide
```

---

## ⚡ Quick Start: 3-Branch Git Commands for Testing & Review

Using standard `git` and `gh` (GitHub CLI):

```bash
# 1. Switch to 'dev' branch for everyday feature work:
git checkout dev

# 2. Make your code changes & run local pre-PR checks:
powershell -File dev-check.ps1

# 3. Commit changes (pre-commit runs Gitleaks & Ruff):
git add README.md
git commit -m "docs: align README with codebase architecture"

# 4. Push to dev & open PR into main via gh:
git push origin dev
gh pr create --base main --head dev --title "docs: align README with codebase architecture"

# 5. When approved and ready for production promotion:
gh pr create --base prod --head main --title "release: promote documentation updates to production"
```

---

## 💼 Competencies & Engineering Focus (General Internship Presentation)

| Focus Area | Demonstrated Competency & Practical Implementation |
| :--- | :--- |
| **Container & Platform Engineering** | Dual Docker Compose architecture (Dev hot-reload vs. Prod immutable signed images), containerized microservices stack, and cloud-native migration readiness. |
| **DevSecOps & Shift-Left Security** | Shift-left pre-commit (Gitleaks, Ruff), Bandit SAST, Trivy container vulnerability scanning (SARIF export), SBOM generation (SPDX), and HashiCorp Vault runtime secrets. |
| **Software Supply Chain Security** | Cryptographic keyless container signing with Cosign (Sigstore / GitHub OIDC), automated tag promotion, and vulnerability reporting. |
| **Backend & Observability** | FastAPI API architecture, PostgreSQL database, Prometheus metrics, Grafana dashboards, Jaeger distributed tracing, and Loki log aggregation. |

---

<p align="center">
  <b>AlphaTracer Financial API — Engineering & DevSecOps Platform</b><br>
  <i>Designed and built for presenting technical skills for software engineering and DevSecOps internships.</i>
</p>
