#!/bin/bash
# Alphatracer startup script
set -e

echo "=== Alphatracer Backend ==="

# Install dependencies
echo "[1/3] Installing dependencies..."
pip install -r requirements.txt -q

# Tables are auto-created by lifespan on first boot
echo "[2/3] Starting server (tables auto-created on first boot)..."
echo "[3/3] API available at: http://localhost:8011"
echo "      Docs at:          http://localhost:8011/docs"
echo ""

uvicorn app.main:app --host 0.0.0.0 --port 8011 --reload
