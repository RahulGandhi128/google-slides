#!/usr/bin/env bash
# Start localtunnel to expose the backend (port 8000) for icons and logos.
# Google Slides API needs a public URL to fetch images when createImage is used.
#
# Prerequisites: npm install -g localtunnel
# Usage: ./scripts/start-tunnel.sh [--subdomain NAME]
#
# After starting:
# 1. Copy the URL (e.g. https://your-subdomain.loca.lt)
# 2. Add to .env: ICON_BASE_URL=https://your-subdomain.loca.lt
# 3. Restart your backend

set -e
PORT="${PORT:-8000}"
SUBDOMAIN=""

for arg in "$@"; do
  if [ "$arg" = "--subdomain" ]; then
    NEXT_SUB=1
  elif [ -n "$NEXT_SUB" ]; then
    SUBDOMAIN="$arg"
    NEXT_SUB=""
  fi
done

if [ -n "$SUBDOMAIN" ]; then
  echo "Starting localtunnel on port $PORT with subdomain: $SUBDOMAIN"
  npx --yes localtunnel --port "$PORT" --subdomain "$SUBDOMAIN"
else
  echo "Starting localtunnel on port $PORT (random subdomain)"
  echo "Tip: Use --subdomain NAME for a consistent URL, e.g. ./scripts/start-tunnel.sh --subdomain ib-scaffold"
  npx --yes localtunnel --port "$PORT"
fi
