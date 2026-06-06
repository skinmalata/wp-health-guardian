import os
import traceback
from pathlib import Path
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from agent.main import create_health_guardian_agent
from agent.tools.storage import (
    save_health_check, get_check_history, get_recent_checks, get_check_by_id,
    get_dashboard, get_monitored_sites, add_monitored_site, remove_monitored_site,
)
from agent.tools.analyzer import generate_health_report, format_report_for_display
from notifications.email_sender import send_health_alert
from agent.tools.health_check import (
    check_site_uptime,
    check_ssl_certificate,
    check_wordpress_specific,
    check_dns_resolution,
)
from agent.tools.gcp_setup import check_gcp_config
from agent.tools.dynatrace_tools import (
    check_dynatrace_config,
    query_dynatrace_problems,
    query_dynatrace_entities,
    query_dynatrace_davis_analysis,
    query_dynatrace_for_domain,
)

app = FastAPI(title="WordPress Health Guardian")

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/")
    async def serve_ui():
        return FileResponse(str(static_dir / "index.html"))


@app.get("/api/health")
async def health():
    return {"status": "ok", "gcp": check_gcp_config()}


@app.get("/api/gcp-config")
async def gcp_config():
    return check_gcp_config()


@app.get("/api/history")
async def history(
    site_url: str = Query(None, description="Filter by site URL"),
    limit: int = Query(20, description="Max results"),
):
    try:
        results = await get_check_history(site_url=site_url, limit=limit)
        return {"results": results, "count": len(results)}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
        )


@app.get("/api/recent")
async def recent(limit: int = Query(10)):
    try:
        results = await get_recent_checks(limit=limit)
        return {"results": results, "count": len(results)}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
        )


@app.get("/api/dynatrace")
async def dynatrace_status(
    domain: str = Query(None, description="Optional domain to look up in Dynatrace"),
):
    config = check_dynatrace_config()
    if not config.get("configured"):
        return {"configured": False, "message": "Dynatrace not configured"}
    problems = query_dynatrace_problems(status="OPEN")
    entities = query_dynatrace_entities()
    domain_data = None
    if domain:
        domain_data = query_dynatrace_for_domain(domain)
    davis = []
    if problems.get("configured") and problems.get("problems"):
        for prob in problems["problems"][:3]:
            pid = prob.get("id")
            if pid:
                davis.append(query_dynatrace_davis_analysis(pid))
    return {"configured": True, "problems": problems, "entities": entities, "davis": davis, "config": config, "domain_data": domain_data}


@app.get("/api/dashboard")
async def dashboard():
    try:
        sites = await get_monitored_sites()
        latest = await get_dashboard()
        return {"sites": sites, "latest": latest}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/monitored-sites")
async def list_monitored_sites():
    try:
        sites = await get_monitored_sites()
        return {"sites": sites}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/monitored-sites")
async def create_monitored_site(url: str = Query(..., description="Site URL to monitor")):
    try:
        result = await add_monitored_site(url)
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.delete("/api/monitored-sites/{site_id}")
async def delete_monitored_site(site_id: str):
    try:
        result = await remove_monitored_site(site_id)
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/check")
async def check_site(
    url: str = Query(..., description="WordPress site URL to check"),
    use_dynatrace: bool = Query(True, description="Whether to use Dynatrace MCP"),
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

        prompt = (
            f"Run a full health check on {url}. "
            f"Call query_dynatrace_problems and query_dynatrace_entities, then include any findings in the report. "
            f"If problems are found, call query_dynatrace_davis_analysis for each problem to get Davis AI root cause. "
            f"After collecting all data, ALWAYS call generate_health_report with the raw dict data you collected "
            f"(pass the dicts directly, do NOT stringify them). "
            f"Then ALWAYS call format_report_for_display on the report dict to produce your final output. "
            f"DO NOT write your own report format — use those two tools."
        )
        if use_dynatrace:
            prompt += " Also use the dynatrace_ MCP tools for deeper queries."

        new_message = types.UserContent(parts=[types.Part(text=prompt)])

        events = []
        errors = []
        result = None
        try:
            async for event in runner.run_async(
                session_id="check-session",
                user_id="user",
                new_message=new_message,
            ):
                events.append(event)
        except Exception as e:
            errors.append(str(e))

        for event in reversed(events):
            content = getattr(event, 'content', None)
            if content and hasattr(content, 'parts') and content.parts:
                texts = [p.text for p in content.parts if hasattr(p, 'text') and p.text]
                if texts:
                    result = texts[0]
                    break

        # Always run direct checks and save to Firestore (even if agent succeeds)
        # so the dashboard has data to display.
        uptime = check_site_uptime(url)
        ssl = check_ssl_certificate(url)
        dns = check_dns_resolution(url)
        wp = check_wordpress_specific(url)
        dp = query_dynatrace_problems(status="OPEN")
        de = query_dynatrace_entities()
        ddomain = query_dynatrace_for_domain(url)
        davis_results = []
        if dp.get("configured") and dp.get("problems"):
            for prob in dp["problems"][:3]:
                pid = prob.get("id")
                if pid:
                    davis_results.append(query_dynatrace_davis_analysis(pid))
        report = generate_health_report(
            url=url,
            uptime_data=uptime,
            ssl_data=ssl,
            wp_data=wp,
            dynatrace_problems=dp,
            dynatrace_entities=de,
            dynatrace_domain_data=ddomain,
        )

        if not result:
            result = format_report_for_display(report)
            result += "\n\n> ⚠️ AI agent analysis was unavailable (check Gemini API key, Vertex AI auth, or quota). Results from direct health check shown above."

        await save_health_check(report)
        send_health_alert(report)

        return {
            "url": url,
            "result": result,
            "events_count": len(events),
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "traceback": traceback.format_exc()},
        )


@app.get("/api/quick-check")
async def quick_check(
    url: str = Query(..., description="WordPress site URL to check"),
):
    """Run checks directly without the ADK agent, store result in Firestore."""
    try:
        uptime = check_site_uptime(url)
        ssl = check_ssl_certificate(url)
        dns = check_dns_resolution(url)
        wp = check_wordpress_specific(url)

        dynatrace_problems = query_dynatrace_problems(status="OPEN")
        dynatrace_entities = query_dynatrace_entities()
        dynatrace_domain = query_dynatrace_for_domain(url)
        dynatrace_davis = []
        if dynatrace_problems.get("configured") and dynatrace_problems.get("problems"):
            for prob in dynatrace_problems["problems"][:3]:
                pid = prob.get("id")
                if pid:
                    dynatrace_davis.append(query_dynatrace_davis_analysis(pid))

        report = generate_health_report(
            url=url,
            uptime_data=uptime,
            ssl_data=ssl,
            wp_data=wp,
            dynatrace_problems=dynatrace_problems,
            dynatrace_entities=dynatrace_entities,
            dynatrace_domain_data=dynatrace_domain,
        )

        doc_id = await save_health_check(report)
        if doc_id:
            report["stored_in_firestore"] = True
            report["document_id"] = doc_id

        report["checks_raw"] = {
            "uptime": uptime, "ssl": ssl, "dns": dns, "wordpress": wp,
            "dynatrace": {"problems": dynatrace_problems, "entities": dynatrace_entities, "davis": dynatrace_davis, "domain": dynatrace_domain},
        }

        send_health_alert(report)

        return report

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "traceback": traceback.format_exc()},
        )


@app.get("/api/scheduled-check")
async def scheduled_check(
    url: str = Query(...),
    secret: str = Query(None),
):
    """Endpoint intended for Cloud Scheduler to call periodically."""
    expected_secret = os.environ.get("SCHEDULED_CHECK_SECRET", "").strip()
    if expected_secret and secret != expected_secret:
        raise HTTPException(status_code=403, detail="Invalid secret")

    try:
        uptime = check_site_uptime(url)
        ssl = check_ssl_certificate(url)
        dns = check_dns_resolution(url)
        wp = check_wordpress_specific(url)

        dynatrace_problems = query_dynatrace_problems(status="OPEN")
        dynatrace_entities = query_dynatrace_entities()
        dynatrace_domain = query_dynatrace_for_domain(url)
        dynatrace_davis = []
        if dynatrace_problems.get("configured") and dynatrace_problems.get("problems"):
            for prob in dynatrace_problems["problems"][:3]:
                pid = prob.get("id")
                if pid:
                    dynatrace_davis.append(query_dynatrace_davis_analysis(pid))

        report = generate_health_report(
            url=url,
            uptime_data=uptime,
            ssl_data=ssl,
            wp_data=wp,
            dynatrace_problems=dynatrace_problems,
            dynatrace_entities=dynatrace_entities,
            dynatrace_domain_data=dynatrace_domain,
        )

        doc_id = await save_health_check(report)
        send_health_alert(report)

        summary = report["summary"]
        return {
            "status": "ok",
            "document_id": doc_id,
            "summary": summary,
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
        )


@app.get("/api/check-detail/{doc_id}")
async def check_detail(doc_id: str):
    try:
        data = await get_check_by_id(doc_id)
        if data is None:
            raise HTTPException(status_code=404, detail="Check not found")
        return data
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
        )
