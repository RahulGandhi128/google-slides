# Local Tunnel Setup for Icons & Logos

Google Slides API `createImage` requires a **publicly reachable URL** to fetch images. When running locally, use a tunnel so Google's servers can reach your backend.

## Quick Start

### 1. Install localtunnel (one-time)

```bash
npm install -g localtunnel
```

Or use `npx` (no install): the scripts use `npx localtunnel` automatically.

### 2. Start your backend

```bash
cd backend_py
python run.py
```

Backend runs on **port 8000**.

### 3. Start the tunnel

**Windows (PowerShell):**
```powershell
.\scripts\start-tunnel.ps1 -Subdomain ib-scaffold
```

**Mac/Linux:**
```bash
./scripts/start-tunnel.sh --subdomain ib-scaffold
```

**Or manually:**
```bash
npx localtunnel --port 8000 --subdomain ib-scaffold
```

### 4. Configure ICON_BASE_URL

Copy the URL from the tunnel output (e.g. `https://ib-scaffold.loca.lt`) and add to `backend_py/.env`:

```
ICON_BASE_URL=https://ib-scaffold.loca.lt
```

### 5. Restart your backend

Restart the Python server so it picks up the new env var.

## What This Enables

| Feature | Without tunnel | With tunnel |
|--------|----------------|------------|
| **Icons** (add_icon_to_slide) | Data URL only (≤2KB, small icons) | Full-size icons via `/api/icon/png?name=...` |
| **Logos** (scaffold) | Data URL only (≤2KB, compressed) | Full-quality logos via `/api/branding/logo/{role}/image` |

## Troubleshooting

### "localtunnel reminder" blocks Google

Localtunnel may show a "Click to continue" page for first-time visitors. **Google's servers cannot click**—they may receive HTML instead of the image.

**Fix:** Use [ngrok](https://ngrok.com) instead (no reminder page for API requests):

```bash
ngrok http 8000
# Set ICON_BASE_URL to the ngrok URL (e.g. https://abc123.ngrok-free.app)
```

### Subdomain already in use

Subdomains are first-come-first-served. Try a different name or omit `--subdomain` for a random URL (you'll need to update `.env` each time).

### Verify tunnel works

```bash
# Replace with your tunnel URL
curl -I https://ib-scaffold.loca.lt/api/health
# Should return 200 OK
```
