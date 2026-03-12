# GWS Slides Assistant

A ChatGPT-style chat interface for managing **Google Slides**, **Drive**, and other Google Workspace services. Powered by the [Google Workspace CLI (gws)](https://github.com/googleworkspace/cli) and MCP (Model Context Protocol).

![Architecture](https://img.shields.io/badge/Stack-React%20%2B%20Express%20%2B%20MCP-blue)

## Prerequisites

- **Node.js 18+**
- **gws CLI 0.7.x** (MCP was removed in 0.8+): `npm install -g @googleworkspace/cli@0.7.0`
- **gws authenticated**: `gws auth login -s slides,drive`
- **Gemini API key**: Set `GOOGLE_GENERATIVE_AI_API_KEY` in `backend/.env` (get from [Google AI Studio](https://aistudio.google.com/apikey))

## Quick Start

1. **Install dependencies**

   ```bash
   npm install
   cd backend && npm install
   cd ../frontend && npm install
   ```

2. **Configure backend**

   ```bash
   cd backend
   cp .env.example .env
   # Edit .env and add GOOGLE_GENERATIVE_AI_API_KEY
   ```

3. **Authenticate gws** (one-time)

   ```bash
   gws auth login -s slides,drive
   ```

4. **Run the app**

   ```bash
   npm run start
   ```

   - Backend: http://localhost:3001  
   - Frontend: http://localhost:5173

   Or run separately:

   ```bash
   npm run backend   # Terminal 1
   npm run frontend  # Terminal 2
   ```

## Project Structure

```
├── backend/
│   ├── src/
│   │   ├── index.js
│   │   ├── mcp/
│   │   │   └── gwsClient.js   # MCP client for gws
│   │   └── agent/
│   │       └── index.js      # LLM agent with tool calling
│   └── skills/
│       └── README.md         # gws skills reference
├── frontend/
│   └── src/
│       ├── App.jsx
│       └── ...
└── package.json
```

## What You Can Do

- **List files** in Google Drive
- **Create** Google Slides presentations
- **Search** Drive for presentations
- **Manage** Sheets, Docs, Gmail, Calendar (when gws auth includes those scopes)

The agent connects to `gws mcp -s slides,drive` and uses MCP tools. Ask in natural language.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GOOGLE_GENERATIVE_AI_API_KEY` | Google Gemini API key (required) |
| `GWS_MCP_SERVICES` | Comma-separated gws services (default: `slides,drive`) |
| `PORT` | Backend port (default: 3001) |

## Troubleshooting

- **"gws not found"**: Ensure `gws` is in PATH after `npm install -g @googleworkspace/cli`
- **"Access blocked"**: Add your Google account as a test user in the OAuth consent screen
- **"No LLM configured"**: Set `GOOGLE_GENERATIVE_AI_API_KEY` in `backend/.env`
- **"insufficient authentication scopes"**: `gws auth login -s slides,drive`
- **"Unknown service 'mcp'"**: Use gws 0.7.x: `npm install -g @googleworkspace/cli@0.7.0`
- **"Slides API not enabled"**: Enable at [console.cloud.google.com/flows/enableapi?apiid=slides.googleapis.com](https://console.cloud.google.com/flows/enableapi?apiid=slides.googleapis.com)
