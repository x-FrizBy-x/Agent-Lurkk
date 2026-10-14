# AI Agent Calendar Assistant

A lightweight AI assistant prototype for managing Google Calendar events and answering simple conversational questions. It can:

- create calendar events
- list upcoming events
- delete events
- move existing events
- keep a small memory of previous conversations
- respond to basic general prompts when no calendar action is needed

## Project structure

- `agent/backend/` — FastAPI backend, Google Calendar integration, memory storage, and Ollama model calls
- `agent/frontend/` — static web UI for chatting with the assistant

## Requirements

- Python 3.10+
- A working Google Calendar API setup with `credentials.json` and `token.json`
- Ollama installed and running locally
- The model `llama3` available in Ollama

## Run the app

### 1) Backend

From the backend folder:

```powershell
cd "C:\Users\Alexa\PycharmProjects\AI Agent\agent\backend"
& "C:\Users\Alexa\PycharmProjects\AI Agent\.venv\Scripts\python.exe" -m uvicorn backend:app --host 127.0.0.1 --port 8000
```

### 2) Frontend

From the frontend folder:

```powershell
cd "C:\Users\Alexa\PycharmProjects\AI Agent\agent\frontend"
& "C:\Users\Alexa\PycharmProjects\AI Agent\.venv\Scripts\python.exe" -m http.server 8001
```

Then open:

```text
http://127.0.0.1:8001
```

## Health check

You can verify the API is running with:

```powershell
Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing
```

Expected result:

```json
{"status":"ok"}
```

## Troubleshooting

### `WinError 10013` / socket access error

This usually means a stale Python process is still holding the port.

Check active ports:

```powershell
Get-NetTCPConnection -LocalPort 8000,8001 -ErrorAction SilentlyContinue
```

If needed, stop the old process:

```powershell
Stop-Process -Id <PID> -Force
```

Then restart the backend/frontend.

### Backend cannot reach Ollama

Make sure Ollama is installed and the model is available:

```powershell
ollama run llama3
```

### Google Calendar login errors

Verify your Google OAuth credentials are present and the app has permission to create a `token.json` file.

## Notes

This is a prototype and is intended for local development/testing rather than production deployment.
