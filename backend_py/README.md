# GWS Slides Assistant - Python Backend

FastAPI backend with Gemini agent and gws CLI tools for Google Slides & Drive.

## Setup

```bash
cd backend_py
pip install -r requirements.txt
```

## Environment

Create `.env` in project root or `backend_py/`:

```
GOOGLE_GENERATIVE_AI_API_KEY=your_gemini_api_key
```

## gws Auth

```powershell
gws auth login -s slides,drive
```

On Windows, set `GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND=file` (handled automatically).

## Run

```bash
python run.py
```

Server runs on http://localhost:8000

## API

- `POST /api/chat` - Chat with agent (messages array)
- `GET /api/tools` - List available tools
- `GET /api/health` - Health check
