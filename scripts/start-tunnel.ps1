# Start localtunnel to expose the backend (port 8000) for icons and logos.
# Google Slides API needs a public URL to fetch images when createImage is used.
#
# Prerequisites: npm install -g localtunnel
# Usage: .\scripts\start-tunnel.ps1
#        .\scripts\start-tunnel.ps1 -Subdomain "ib-scaffold"
#
# After starting:
# 1. Copy the URL (e.g. https://ib-scaffold.loca.lt)
# 2. Add to .env: ICON_BASE_URL=https://ib-scaffold.loca.lt
# 3. Restart your backend

param(
    [string]$Subdomain = "",
    [int]$Port = 8000
)

if ($Subdomain) {
    Write-Host "Starting localtunnel on port $Port with subdomain: $Subdomain"
    npx --yes localtunnel --port $Port --subdomain $Subdomain
} else {
    Write-Host "Starting localtunnel on port $Port (random subdomain)"
    Write-Host "Tip: Use -Subdomain 'ib-scaffold' for a consistent URL"
    npx --yes localtunnel --port $Port
}
