# WordPress Health Guardian

An AI-powered agent that monitors and analyzes WordPress site health using **Google Gemini / Vertex AI** (via ADK), **Dynatrace** for observability, and **Google Cloud** services for persistence and scheduling.

Built for the **Google Cloud Rapid Agent Hackathon** — Dynatrace Track.

## Features

- **Health Checks**: Uptime monitoring, SSL certificate validation, DNS resolution, WordPress endpoint checks
- **Dynatrace Integration**: Dynatrace MCP server for deep observability + direct API calls via classic token (problems, entities)
- **OpenTelemetry**: Traces shipped to Dynatrace via OTLP exporter for observability
- **AI Analysis**: Gemini 2.5 Flash analyzes all data and generates actionable recommendations
- **Health Reports**: Structured reports with health scores, check results, and prioritized recommendations
- **Web UI**: Clean dashboard with 4 tabs — Health Check, History, GCP, Dynatrace
- **Check History**: All results persisted to **Firestore** for trend analysis
- **Scheduled Checks**: **Cloud Scheduler** integration for periodic automated monitoring
- **Rate Limit Fallback**: Falls back to direct health checks when Vertex AI quota is exceeded

## Architecture

```
User → Web UI (4 tabs) → FastAPI Server → ADK Agent → [Health Check Tools, Dynatrace MCP, Gemini via Vertex AI]
                                                     → Dynatrace API (classic token)
                                                     → OpenTelemetry → Dynatrace OTLP
                                                          ↓
                                                    Firestore (history)
```

| Layer | Technology |
|---|---|
| Web Server | FastAPI + Uvicorn |
| Agent | Google ADK (Agent Development Kit) |
| LLM | Gemini 2.5 Flash (Vertex AI) |
| Partner Integration | Dynatrace MCP + Dynatrace API v2 (classic token) |
| Observability | OpenTelemetry → Dynatrace OTLP endpoint |
| Database | Firestore (check history) |
| Compute | Cloud Run (serverless) |
| CI/CD | Cloud Build (cloudbuild.yaml) |
| Scheduling | Cloud Scheduler (weekly Mon 8AM UTC) |
| Secrets | Secret Manager (4 secrets) |

## Prerequisites

- Python 3.12+
- Google Cloud project with billing enabled (for Vertex AI, Firestore, Cloud Run)
- Google Gemini API key (for local dev without GCP)
- Dynatrace tenant (optional — for Dynatrace MCP and OTel features)

## Quick Start

### Local Development

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
python app.py
```

Visit `http://localhost:8080`

### Deploy to Google Cloud Run

```bash
chmod +x deploy/deploy.sh
./deploy/deploy.sh your-project-id us-central1
```

Or use Cloud Build CI/CD:

```bash
gcloud builds submit --config=deploy/cloudbuild.yaml
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GOOGLE_API_KEY` | Local dev | Gemini API key (not needed on GCP) |
| `GOOGLE_CLOUD_PROJECT` | GCP | GCP project ID |
| `GOOGLE_CLOUD_LOCATION` | No | GCP region (default: us-central1) |
| `DT_ENVIRONMENT` | Dynatrace | Dynatrace environment URL (e.g. `lcb76549.live.dynatrace.com`) |
| `DT_PLATFORM_TOKEN` | Dynatrace MCP | Dynatrace platform token for MCP server |
| `DT_CLASSIC_TOKEN` | Dynatrace API | Classic token with `problems.read` + `entities.read` scopes |
| `DT_OTEL_TOKEN` | OTel | Token with `openTelemetryTrace.ingest` scope for trace shipping |
| `FIRESTORE_COLLECTION` | No | Firestore collection name (default: health-checks) |
| `SCHEDULED_CHECK_SECRET` | No | Secret for protecting scheduled check endpoint |

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /` | Web UI (4 tabs) |
| `GET /api/health` | Health check with GCP status |
| `GET /api/check?url=...` | Full ADK agent health check |
| `GET /api/quick-check?url=...` | Direct checks without AI agent |
| `GET /api/history?site_url=...` | Check history from Firestore |
| `GET /api/recent` | Recent checks across all sites |
| `GET /api/gcp-config` | GCP configuration status |
| `GET /api/dynatrace` | Dynatrace configuration status |
| `GET /api/scheduled-check?url=...` | Endpoint for Cloud Scheduler |

## Google Cloud Integration

- **Vertex AI**: Gemini 2.5 Flash model inference via Vertex AI when deployed on GCP
- **Firestore**: Persistent health check history with queryable API
- **Cloud Run**: Serverless container deployment with auto-scaling
- **Cloud Scheduler**: Periodic automated health checks (weekly)
- **Secret Manager**: Secure API key management (4 secrets via Cloud Run integration)
- **Artifact Registry**: Container image storage
- **Cloud Build**: CI/CD pipeline (cloudbuild.yaml)

## Tech Stack

- **Google ADK** — Agent orchestration framework
- **Gemini 2.5 Flash** — LLM for analysis and reasoning (Vertex AI on GCP)
- **Dynatrace MCP** — Observability integration via Model Context Protocol
- **Dynatrace API v2** — Direct problem/entity queries via classic token
- **OpenTelemetry** — Trace instrumentation shipped to Dynatrace OTLP
- **FastAPI** — Web server
- **Firestore** — Check history database
- **Cloud Run** — Serverless deployment
- **Cloud Scheduler** — Periodic monitoring

## Project Structure

```
├── app.py                        # Entry point (FastAPI + OTel middleware)
├── agent/
│   ├── main.py                   # ADK agent definition (VertexAIGemini model)
│   └── tools/
│       ├── health_check.py       # Uptime, SSL, DNS, WordPress checks
│       ├── analyzer.py           # Report generation & formatting
│       ├── dynatrace_tools.py    # Dynatrace MCP + API v2 integration
│       ├── storage.py            # Firestore persistence
│       └── gcp_setup.py          # GCP config detection
├── web/
│   ├── server.py                 # FastAPI routes (check, history, dynatrace, etc.)
│   └── static/index.html         # UI dashboard (4 tabs)
├── observability/
│   └── otel_setup.py             # OpenTelemetry → Dynatrace OTLP exporter
├── deploy/
│   ├── Dockerfile                # Cloud Run container
│   ├── cloudbuild.yaml           # CI/CD pipeline
│   └── deploy.sh                 # One-command deploy script
└── tests/
    └── test_agent.py             # Test suite
```

## License

MIT
