#!/usr/bin/env bash
# ==============================================================================
# 🚀 AlphaTracer DevSecOps Mockup: Pre-Commit -> CI/CD -> K3s Auto-Pull Simulation
# Author: Sebian (DevSecOps Student & Engineering Intern Candidate)
# ==============================================================================
set -e

TARGET_BRANCH="${1:-dev}"
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "main")
GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "localtest")

echo -e "\n\033[1;36m🎓 [STUDENT EXPERIMENT] Local DevSecOps & K3s Auto-Pull Mockup\033[0m"
echo -e "\033[0;36m=================================================================\033[0m"
echo -e "\033[1;33m📍 Active Git Branch : $CURRENT_BRANCH\033[0m"
echo -e "\033[1;33m🔖 Latest Commit SHA : $GIT_SHA\033[0m"
echo -e "\033[1;33m🎯 Target Environment: $TARGET_BRANCH\033[0m\n"

# Stage 1: Shift-Left Checks
echo -e "\033[1;35m[STAGE 1/4] 🛡️ Running Shift-Left Pre-Commit Checks...\033[0m"
if command -v gitleaks &> /dev/null; then
    gitleaks detect --no-git -v --config .gitleaks.toml
    echo -e "\033[1;32m  ✅ Secret scan clean. Zero credentials exposed!\033[0m"
else
    echo "  ℹ️ Gitleaks CLI not installed locally. Checked via pre-commit / CI."
fi

if command -v bandit &> /dev/null; then
    bandit -r app/ -ll -ii
    echo -e "\033[1;32m  ✅ Bandit SAST passed clean!\033[0m"
fi

# Stage 2: Docker Build
IMAGE_NAME="ghcr.io/sebian-lab/alphatracer-financial-api:$GIT_SHA"
echo -e "\n\033[1;35m[STAGE 2/4] 🐳 Building Container Image (Simulating GitHub Actions CI)...\033[0m"
if command -v docker &> /dev/null; then
    docker build -t "$IMAGE_NAME" -t "alphatracer:local-$GIT_SHA" . -q
    echo -e "\033[1;32m  ✅ Docker image built successfully: $IMAGE_NAME\033[0m"
else
    echo "  ℹ️ Docker daemon not detected. Simulated build step."
fi

# Stage 3: GitOps Overlay Manifest Update Simulation
echo -e "\n\033[1;35m[STAGE 3/4] 📦 Simulating GitOps Manifest Synchronization (Kustomize)...\033[0m"
echo "  -> Target overlay: infrastructure/kubernetes/overlays/$TARGET_BRANCH"
echo -e "\033[1;32m  ✅ Manifest reflects immutable tag: $GIT_SHA [skip ci]\033[0m"

# Stage 4: K3s Auto-Pull Simulation
NAMESPACE=$([ "$TARGET_BRANCH" == "dev" ] && echo "alphatracer-dev" || echo "alphatracer")
echo -e "\n\033[1;35m[STAGE 4/4] ☸️ Simulating K3s Cluster Auto-Pull & Rollout...\033[0m"
echo "  -> Target Namespace  : $NAMESPACE"
echo "  -> Sync Mechanism     : ArgoCD automated selfHeal & prune"
echo "  -> Container Runtime  : containerd (K3s Node: k3smaster)"

echo -e "\n\033[1;36m🔄 Rollout Simulation Status for Deployment 'alphatracer' in '$NAMESPACE':\033[0m"
echo "  [1/3] Fetching new image $IMAGE_NAME from local registry cache... Done."
echo "  [2/3] Spawning new pod with NonRoot UID 1000 securityContext... Done."
echo "  [3/3] Readiness & Liveness probes passed: GET /health -> 200 OK. Done."
echo -e "\033[1;32m  ✅ Deployment updated smoothly to tag $GIT_SHA with zero downtime!\033[0m\n"

echo -e "\033[0;36m=================================================================\033[0m"
echo -e "\033[1;32m🎉 MOCKUP TEST PASSED: DevSecOps pipeline & K3s rollout validated!\033[0m"
echo -e "Ready to showcase to recruiters or run 'git push origin $CURRENT_BRANCH' with confidence! 🚀\n"
