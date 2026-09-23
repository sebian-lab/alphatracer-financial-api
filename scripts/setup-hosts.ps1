# ==============================================================================
# AlphaTracer DevSecOps - Hosts File Setup
# Adds local DNS entries for Traefik IngressRoutes
# MUST run as Administrator
# ==============================================================================

$hostsFile = "C:\Windows\System32\drivers\etc\hosts"
$entries = @(
    "127.0.0.1 alphatracer.local",
    "127.0.0.1 dev.alphatracer.local",
    "127.0.0.1 staging.alphatracer.local",
    "127.0.0.1 argocd.local",
    "127.0.0.1 grafana.local",
    "127.0.0.1 vault.local"
)

# Check admin rights
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[ERROR] This script requires Administrator privileges." -ForegroundColor Red
    Write-Host "        Right-click PowerShell -> 'Run as Administrator', then re-run this script." -ForegroundColor Yellow
    exit 1
}

$currentContent = Get-Content $hostsFile -Raw

Write-Host "Adding AlphaTracer DNS entries to hosts file..." -ForegroundColor Cyan

foreach ($entry in $entries) {
    $hostname = ($entry -split " ")[1]
    if ($currentContent -match [regex]::Escape($hostname)) {
        Write-Host "  [SKIP] $hostname already exists" -ForegroundColor Gray
    } else {
        Add-Content -Path $hostsFile -Value $entry
        Write-Host "  [OK]   $entry" -ForegroundColor Green
    }
}

Write-Host "`nHosts file updated! Flush DNS cache:" -ForegroundColor Yellow
ipconfig /flushdns | Out-Null
Write-Host "  [OK] DNS cache flushed" -ForegroundColor Green
