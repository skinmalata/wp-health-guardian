# WordPress Health Guardian

An AI-powered agent that monitors and analyzes WordPress site health using **Google Gemini** (via ADK), **Dynatrace MCP** for observability, and comprehensive health checking tools.

Built for the **Google Cloud Rapid Agent Hackathon** — Dynatrace Track.

## Features

- **Health Checks**: Uptime monitoring, SSL certificate validation, DNS resolution, WordPress endpoint checks
- **Dynatrace Integration**: Connect to Dynatrace MCP for deep observability (problems, vulnerabilities, performance metrics)
- **AI Analysis**: Gemini analyzes all data and generates actionable recommendations
- **Health Reports**: Structured reports with health scores, check results, and prioritized recommendations
- **Web UI**: Clean dashboard for running health checks

## Architecture

```
User → Web UI → FastAPI Server → ADK Agent → [Health Check Tools, Dynatrace MCP, Gemini Analysis]
```

The agent uses Google's **Agent Development Kit (ADK)** for orchestration, with tools for HTTP health checking, SSL validation, WordPress endpoint probing, and Dynatrace MCP integration for observability data.

## Prerequisites

- Python 3.10+
- Google Gemini API key
- Dynatrace tenant (optional — for Dynatrace MCP features)

## Quick Start

1. **Clone and install**

```bash
pip install -r requirements.txt
```

2. **Configure environment**

```bash
cp .env.example .env
# Edit .env with your API keys
```

3. **Run the app**

```bash
python app.py
```

4. **Open browser**

Visit `http://localhost:8080`

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GOOGLE_API_KEY` | Yes | Google Gemini API key |
| `GOOGLE_CLOUD_PROJECT` | No | GCP project ID |
| `DT_ENVIRONMENT` | No | Dynatrace Platform URL |
| `DT_PLATFORM_TOKEN` | No | Dynatrace Platform Token |

## API Endpoints

- `GET /` — Web UI
- `GET /api/health` — Health check endpoint
- `GET /api/check?url=https://example.com&use_dynatrace=true` — Run agent health check

## Deployment (Cloud Run)

```bash
gcloud builds submit --config=deploy/cloudbuild.yaml \
  --substitutions=_GOOGLE_API_KEY=your_key
```

Or deploy manually:

```bash
gcloud run deploy wordpress-health-guardian \
  --source . \
  --region=us-central1 \
  --set-env-vars=GOOGLE_API_KEY=your_key
```

## Tech Stack

- **Google ADK** — Agent orchestration framework
- **Gemini 2.5 Flash** — LLM for analysis and reasoning
- **Dynatrace MCP** — Observability integration via Model Context Protocol
- **FastAPI** — Web server
- **Cloud Run** — Deployment target

## License

MIT
