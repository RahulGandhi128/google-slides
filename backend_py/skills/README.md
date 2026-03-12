# gws Auth & Setup

The Python backend uses the **gws CLI** directly (subprocess) for Slides and Drive.

## Auth

```powershell
gws auth login -s slides,drive
```

## Enable Google Slides API

If you see "Slides API might not be enabled", enable it for your GCP project:

1. **Console**: Open [Enable Google Slides API](https://console.cloud.google.com/flows/enableapi?apiid=slides.googleapis.com) and click **Enable**.

2. **Or with gcloud** (if you have it):
   ```bash
   gcloud services enable slides.googleapis.com
   ```

3. Ensure your gws project matches: set `GOOGLE_WORKSPACE_PROJECT_ID` in `.env` if needed.

## Services

| Flag | Services |
|------|----------|
| `-s slides,drive` | Slides + Drive (default) |
| `-s slides,drive,gmail` | + Gmail |
| `-s slides,drive,sheets` | + Sheets |
