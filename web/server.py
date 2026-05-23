import os
import traceback
from pathlib import Path
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from agent.main import create_health_guardian_agent

app = FastAPI(title="WordPress Health Guardian")

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/")
    async def serve_ui():
        return FileResponse(str(static_dir / "index.html"))


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/check")
async def check_site(
    url: str = Query(..., description="WordPress site URL to check"),
    use_dynatrace: bool = Query(False, description="Whether to use Dynatrace MCP"),
):
    try:
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.adk.flows.llm_flows.contents import types

        agent = create_health_guardian_agent()
        session_service = InMemorySessionService()

        runner = Runner(
            agent=agent,
            app_name="wordpress-health-guardian",
            session_service=session_service,
        )

        await session_service.create_session(
            app_name="wordpress-health-guardian",
            user_id="user",
            session_id="check-session",
        )

        prompt = f"Run a full health check on {url}"
        if use_dynatrace:
            prompt += ". Also check Dynatrace for any related problems or vulnerabilities for the domain."

        new_message = types.UserContent(parts=[types.Part(text=prompt)])

        events = []
        async for event in runner.run_async(
            session_id="check-session",
            user_id="user",
            new_message=new_message,
        ):
            events.append(event)

        result = None
        for event in reversed(events):
            content = getattr(event, 'content', None)
            if content and hasattr(content, 'parts') and content.parts:
                texts = [p.text for p in content.parts if hasattr(p, 'text') and p.text]
                if texts:
                    result = "\n".join(texts)
                    break

        return {
            "url": url,
            "result": str(result or "No output generated"),
            "events_count": len(events),
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "traceback": traceback.format_exc()},
        )
